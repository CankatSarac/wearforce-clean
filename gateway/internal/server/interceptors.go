package server

import (
	"context"
	"fmt"
	"runtime"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
	"go.uber.org/zap"

	"github.com/wearforce/gateway/internal/auth"
)

// unaryAuthInterceptor handles authentication for unary gRPC calls
func unaryAuthInterceptor(validator *auth.JWTValidator, logger *zap.Logger) grpc.UnaryServerInterceptor {
	return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
		// Skip auth for health checks
		if isPublicMethod(info.FullMethod) {
			return handler(ctx, req)
		}

		// Extract token from metadata
		token, err := extractTokenFromMetadata(ctx)
		if err != nil {
			logger.Debug("Failed to extract token",
				zap.String("method", info.FullMethod),
				zap.Error(err),
			)
			return nil, status.Error(codes.Unauthenticated, "authentication required")
		}

		// Validate token
		userCtx, err := validator.ValidateToken(token)
		if err != nil {
			logger.Debug("Token validation failed",
				zap.String("method", info.FullMethod),
				zap.Error(err),
			)
			return nil, status.Error(codes.Unauthenticated, "invalid token")
		}

		// Add user context to gRPC context
		ctx = context.WithValue(ctx, "user", userCtx)
		ctx = metadata.AppendToOutgoingContext(ctx, "user-id", userCtx.UserID)

		return handler(ctx, req)
	}
}

// streamAuthInterceptor handles authentication for streaming gRPC calls
func streamAuthInterceptor(validator *auth.JWTValidator, logger *zap.Logger) grpc.StreamServerInterceptor {
	return func(srv interface{}, stream grpc.ServerStream, info *grpc.StreamServerInfo, handler grpc.StreamHandler) error {
		// Skip auth for public methods
		if isPublicMethod(info.FullMethod) {
			return handler(srv, stream)
		}

		// Extract token from metadata
		token, err := extractTokenFromMetadata(stream.Context())
		if err != nil {
			logger.Debug("Failed to extract token from stream",
				zap.String("method", info.FullMethod),
				zap.Error(err),
			)
			return status.Error(codes.Unauthenticated, "authentication required")
		}

		// Validate token
		userCtx, err := validator.ValidateToken(token)
		if err != nil {
			logger.Debug("Stream token validation failed",
				zap.String("method", info.FullMethod),
				zap.Error(err),
			)
			return status.Error(codes.Unauthenticated, "invalid token")
		}

		// Create wrapped stream with user context
		wrappedStream := &authenticatedStream{
			ServerStream: stream,
			ctx:          context.WithValue(stream.Context(), "user", userCtx),
		}

		return handler(srv, wrappedStream)
	}
}

// authenticatedStream wraps ServerStream with authenticated context
type authenticatedStream struct {
	grpc.ServerStream
	ctx context.Context
}

func (s *authenticatedStream) Context() context.Context {
	return s.ctx
}

// unaryLoggingInterceptor logs unary gRPC calls
func unaryLoggingInterceptor(logger *zap.Logger) grpc.UnaryServerInterceptor {
	return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
		start := time.Now()

		// Get user context if available
		var userID string
		if user := getUserFromContext(ctx); user != nil {
			userID = user.UserID
		}

		resp, err := handler(ctx, req)

		duration := time.Since(start)
		code := codes.OK
		if err != nil {
			if st, ok := status.FromError(err); ok {
				code = st.Code()
			} else {
				code = codes.Internal
			}
		}

		fields := []zap.Field{
			zap.String("method", info.FullMethod),
			zap.Duration("duration", duration),
			zap.String("code", code.String()),
			zap.String("user_id", userID),
		}

		if err != nil {
			fields = append(fields, zap.Error(err))
			logger.Error("gRPC unary call failed", fields...)
		} else {
			logger.Info("gRPC unary call", fields...)
		}

		return resp, err
	}
}

// streamLoggingInterceptor logs streaming gRPC calls
func streamLoggingInterceptor(logger *zap.Logger) grpc.StreamServerInterceptor {
	return func(srv interface{}, stream grpc.ServerStream, info *grpc.StreamServerInfo, handler grpc.StreamHandler) error {
		start := time.Now()

		// Get user context if available
		var userID string
		if user := getUserFromContext(stream.Context()); user != nil {
			userID = user.UserID
		}

		err := handler(srv, stream)

		duration := time.Since(start)
		code := codes.OK
		if err != nil {
			if st, ok := status.FromError(err); ok {
				code = st.Code()
			} else {
				code = codes.Internal
			}
		}

		fields := []zap.Field{
			zap.String("method", info.FullMethod),
			zap.Duration("duration", duration),
			zap.String("code", code.String()),
			zap.String("user_id", userID),
			zap.Bool("client_stream", info.IsClientStream),
			zap.Bool("server_stream", info.IsServerStream),
		}

		if err != nil {
			fields = append(fields, zap.Error(err))
			logger.Error("gRPC stream call failed", fields...)
		} else {
			logger.Info("gRPC stream call", fields...)
		}

		return err
	}
}

// unaryPanicRecoveryInterceptor recovers from panics in unary calls
func unaryPanicRecoveryInterceptor(logger *zap.Logger) grpc.UnaryServerInterceptor {
	return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (resp interface{}, err error) {
		defer func() {
			if r := recover(); r != nil {
				stack := make([]byte, 4096)
				length := runtime.Stack(stack, false)
				
				logger.Error("gRPC unary call panic",
					zap.String("method", info.FullMethod),
					zap.Any("panic", r),
					zap.String("stack", string(stack[:length])),
				)
				
				err = status.Error(codes.Internal, "internal server error")
			}
		}()

		return handler(ctx, req)
	}
}

// streamPanicRecoveryInterceptor recovers from panics in streaming calls
func streamPanicRecoveryInterceptor(logger *zap.Logger) grpc.StreamServerInterceptor {
	return func(srv interface{}, stream grpc.ServerStream, info *grpc.StreamServerInfo, handler grpc.StreamHandler) (err error) {
		defer func() {
			if r := recover(); r != nil {
				stack := make([]byte, 4096)
				length := runtime.Stack(stack, false)
				
				logger.Error("gRPC stream call panic",
					zap.String("method", info.FullMethod),
					zap.Any("panic", r),
					zap.String("stack", string(stack[:length])),
				)
				
				err = status.Error(codes.Internal, "internal server error")
			}
		}()

		return handler(srv, stream)
	}
}

// rateLimitInterceptor applies rate limiting to gRPC calls
func unaryRateLimitInterceptor(limiter interface{}) grpc.UnaryServerInterceptor {
	return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
		// Skip rate limiting for health checks
		if isPublicMethod(info.FullMethod) {
			return handler(ctx, req)
		}

		// TODO: Implement rate limiting logic
		// This would use the rate limiter from middleware package

		return handler(ctx, req)
	}
}

// metricsInterceptor collects metrics for gRPC calls
func unaryMetricsInterceptor() grpc.UnaryServerInterceptor {
	return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
		start := time.Now()

		resp, err := handler(ctx, req)

		duration := time.Since(start)
		code := codes.OK
		if err != nil {
			if st, ok := status.FromError(err); ok {
				code = st.Code()
			} else {
				code = codes.Internal
			}
		}

		// TODO: Record metrics
		// This would integrate with Prometheus metrics
		_ = duration
		_ = code
		_ = info.FullMethod

		return resp, err
	}
}

// tracingInterceptor adds distributed tracing to gRPC calls
func unaryTracingInterceptor() grpc.UnaryServerInterceptor {
	return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
		// TODO: Implement OpenTelemetry tracing
		// This would create spans for gRPC calls

		return handler(ctx, req)
	}
}

// Helper functions

// extractTokenFromMetadata extracts JWT token from gRPC metadata
func extractTokenFromMetadata(ctx context.Context) (string, error) {
	md, ok := metadata.FromIncomingContext(ctx)
	if !ok {
		return "", fmt.Errorf("no metadata found")
	}

	// Try different header names
	headerNames := []string{"authorization", "Authorization", "token", "Token"}
	
	for _, headerName := range headerNames {
		values := md.Get(headerName)
		if len(values) > 0 {
			token := values[0]
			// Remove "Bearer " prefix if present
			if len(token) > 7 && token[:7] == "Bearer " {
				return token[7:], nil
			}
			return token, nil
		}
	}

	return "", fmt.Errorf("authorization token not found in metadata")
}

// isPublicMethod checks if a gRPC method should skip authentication
func isPublicMethod(fullMethod string) bool {
	publicMethods := []string{
		"/grpc.health.v1.Health/Check",
		"/grpc.health.v1.Health/Watch",
		"/wearforce.gateway.v1.GatewayService/HealthCheck",
	}

	for _, method := range publicMethods {
		if fullMethod == method {
			return true
		}
	}

	return false
}

// validateMethodAccess checks if user has access to specific method
func validateMethodAccess(ctx context.Context, fullMethod string) error {
	user := getUserFromContext(ctx)
	if user == nil {
		return status.Error(codes.Unauthenticated, "user not found in context")
	}

	// Define method-role mappings
	methodRoles := map[string][]string{
		"/wearforce.gateway.v1.AudioStreamingService/BiDirectionalStream": {"user", "premium"},
		"/wearforce.gateway.v1.AudioStreamingService/SpeechToText":        {"user", "premium"},
		"/wearforce.gateway.v1.AudioStreamingService/TextToSpeech":        {"user", "premium"},
		"/wearforce.gateway.v1.ChatService/JoinChat":                      {"user"},
		"/wearforce.gateway.v1.ChatService/SendMessage":                   {"user"},
		"/wearforce.gateway.v1.ServiceProxyService/ForwardToCRM":          {"admin", "manager"},
		"/wearforce.gateway.v1.ServiceProxyService/ForwardToERP":          {"admin", "manager"},
	}

	requiredRoles, exists := methodRoles[fullMethod]
	if !exists {
		// Method not in map, allow access (or you could default to deny)
		return nil
	}

	// Check if user has any of the required roles
	for _, requiredRole := range requiredRoles {
		if user.HasRole(requiredRole) {
			return nil
		}
	}

	return status.Error(codes.PermissionDenied, "insufficient permissions")
}

// roleBasedAccessInterceptor enforces role-based access control
func unaryRoleBasedAccessInterceptor() grpc.UnaryServerInterceptor {
	return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
		// Skip for public methods
		if isPublicMethod(info.FullMethod) {
			return handler(ctx, req)
		}

		// Validate method access
		if err := validateMethodAccess(ctx, info.FullMethod); err != nil {
			return nil, err
		}

		return handler(ctx, req)
	}
}

// streamRoleBasedAccessInterceptor enforces role-based access control for streams
func streamRoleBasedAccessInterceptor() grpc.StreamServerInterceptor {
	return func(srv interface{}, stream grpc.ServerStream, info *grpc.StreamServerInfo, handler grpc.StreamHandler) error {
		// Skip for public methods
		if isPublicMethod(info.FullMethod) {
			return handler(srv, stream)
		}

		// Validate method access
		if err := validateMethodAccess(stream.Context(), info.FullMethod); err != nil {
			return err
		}

		return handler(srv, stream)
	}
}