package server

import (
	"context"
	"fmt"
	"time"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/anypb"
	"google.golang.org/protobuf/types/known/timestamppb"
	"go.uber.org/zap"

	pb "github.com/wearforce/gateway/pkg/proto"
	"github.com/wearforce/gateway/internal/auth"
)

// ChatService implements the chat service
type ChatService struct {
	pb.UnimplementedChatServiceServer
	logger *zap.Logger
}

// JoinChat joins a user to a chat room
func (s *ChatService) JoinChat(ctx context.Context, req *pb.JoinChatRequest) (*pb.JoinChatResponse, error) {
	s.logger.Info("User joining chat",
		zap.String("room_id", req.RoomId),
		zap.String("user_id", req.UserId),
		zap.String("user_name", req.UserName),
	)

	// Validate request
	if req.RoomId == "" {
		return nil, status.Error(codes.InvalidArgument, "room_id is required")
	}
	if req.UserId == "" {
		return nil, status.Error(codes.InvalidArgument, "user_id is required")
	}

	// Generate session ID
	sessionID := fmt.Sprintf("session-%d-%s", time.Now().Unix(), req.UserId)

	// Mock active users (in real implementation, this would come from database)
	activeUsers := []*pb.ChatUser{
		{
			UserId:      "user1",
			UserName:    "Alice",
			DisplayName: "Alice Smith",
			Status:      pb.UserStatus_ONLINE,
			Role:        pb.UserRole_MEMBER,
		},
		{
			UserId:      "user2",
			UserName:    "Bob",
			DisplayName: "Bob Johnson",
			Status:      pb.UserStatus_ONLINE,
			Role:        pb.UserRole_MODERATOR,
		},
	}

	return &pb.JoinChatResponse{
		Success:     true,
		SessionId:   sessionID,
		ActiveUsers: activeUsers,
	}, nil
}

// LeaveChat removes a user from a chat room
func (s *ChatService) LeaveChat(ctx context.Context, req *pb.LeaveChatRequest) (*pb.LeaveChatResponse, error) {
	s.logger.Info("User leaving chat",
		zap.String("room_id", req.RoomId),
		zap.String("user_id", req.UserId),
		zap.String("session_id", req.SessionId),
	)

	return &pb.LeaveChatResponse{
		Success: true,
	}, nil
}

// SendMessage sends a message to a chat room
func (s *ChatService) SendMessage(ctx context.Context, req *pb.SendMessageRequest) (*pb.SendMessageResponse, error) {
	s.logger.Info("Sending message",
		zap.String("room_id", req.RoomId),
		zap.String("user_id", req.UserId),
	)

	// Validate request
	if req.Content == nil {
		return nil, status.Error(codes.InvalidArgument, "message content is required")
	}

	// Generate message ID
	messageID := fmt.Sprintf("msg-%d", time.Now().UnixNano())

	return &pb.SendMessageResponse{
		Success:   true,
		MessageId: messageID,
		Timestamp: timestamppb.Now(),
	}, nil
}

// StreamMessages streams messages from a chat room
func (s *ChatService) StreamMessages(req *pb.StreamMessagesRequest, stream pb.ChatService_StreamMessagesServer) error {
	s.logger.Info("Starting message stream",
		zap.String("room_id", req.RoomId),
		zap.String("user_id", req.UserId),
	)

	ctx := stream.Context()

	// Mock streaming messages (in real implementation, this would use WebSocket or similar)
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	counter := 0
	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-ticker.C:
			counter++
			
			// Send a mock message
			message := &pb.ChatMessage{
				MessageId: fmt.Sprintf("msg-%d", counter),
				RoomId:    req.RoomId,
				UserId:    "system",
				UserName:  "System",
				Content: &pb.MessageContent{
					Type: pb.MessageContent_TEXT,
					Text: fmt.Sprintf("System message #%d", counter),
				},
				Timestamp: timestamppb.Now(),
				Status:    pb.MessageStatus_SENT,
			}

			if err := stream.Send(message); err != nil {
				s.logger.Error("Failed to send message", zap.Error(err))
				return err
			}

			// Stop after 5 messages for demo
			if counter >= 5 {
				return nil
			}
		}
	}
}

// GetChatHistory retrieves chat history
func (s *ChatService) GetChatHistory(ctx context.Context, req *pb.GetChatHistoryRequest) (*pb.GetChatHistoryResponse, error) {
	s.logger.Info("Getting chat history",
		zap.String("room_id", req.RoomId),
		zap.Int32("limit", req.Limit),
	)

	// Mock chat history
	messages := []*pb.ChatMessage{
		{
			MessageId: "msg-1",
			RoomId:    req.RoomId,
			UserId:    "user1",
			UserName:  "Alice",
			Content: &pb.MessageContent{
				Type: pb.MessageContent_TEXT,
				Text: "Hello everyone!",
			},
			Timestamp: timestamppb.Now(),
			Status:    pb.MessageStatus_SENT,
		},
		{
			MessageId: "msg-2",
			RoomId:    req.RoomId,
			UserId:    "user2",
			UserName:  "Bob",
			Content: &pb.MessageContent{
				Type: pb.MessageContent_TEXT,
				Text: "Hi Alice! How are you?",
			},
			Timestamp: timestamppb.Now(),
			Status:    pb.MessageStatus_SENT,
		},
	}

	return &pb.GetChatHistoryResponse{
		Messages:   messages,
		NextCursor: "cursor-123",
		HasMore:    false,
	}, nil
}

// GetActiveUsers gets list of active users in a chat room
func (s *ChatService) GetActiveUsers(ctx context.Context, req *pb.GetActiveUsersRequest) (*pb.GetActiveUsersResponse, error) {
	s.logger.Info("Getting active users",
		zap.String("room_id", req.RoomId),
	)

	// Mock active users
	users := []*pb.ChatUser{
		{
			UserId:      "user1",
			UserName:    "Alice",
			DisplayName: "Alice Smith",
			Status:      pb.UserStatus_ONLINE,
			Role:        pb.UserRole_MEMBER,
			LastSeen:    timestamppb.Now(),
		},
		{
			UserId:      "user2",
			UserName:    "Bob",
			DisplayName: "Bob Johnson",
			Status:      pb.UserStatus_ONLINE,
			Role:        pb.UserRole_MODERATOR,
			LastSeen:    timestamppb.Now(),
		},
	}

	return &pb.GetActiveUsersResponse{
		Users:      users,
		TotalCount: int32(len(users)),
	}, nil
}

// GatewayService implements the gateway service
type GatewayService struct {
	pb.UnimplementedGatewayServiceServer
	logger *zap.Logger
}

// HealthCheck performs health check
func (s *GatewayService) HealthCheck(ctx context.Context, req *pb.HealthCheckRequest) (*pb.HealthCheckResponse, error) {
	s.logger.Debug("Health check requested", zap.String("service", req.Service))

	return &pb.HealthCheckResponse{
		Status:    pb.HealthCheckResponse_SERVING,
		Timestamp: timestamppb.Now(),
		Details: map[string]string{
			"version": "1.0.0",
			"uptime":  "24h",
		},
	}, nil
}

// GetServiceStatus gets service status and metrics
func (s *GatewayService) GetServiceStatus(ctx context.Context, req *pb.ServiceStatusRequest) (*pb.ServiceStatusResponse, error) {
	s.logger.Debug("Service status requested", zap.Strings("services", req.Services))

	// Mock service statuses
	services := []*pb.ServiceStatus{
		{
			Name:    "gateway",
			Status:  pb.HealthCheckResponse_SERVING,
			Version: "1.0.0",
			Uptime:  timestamppb.Now(),
			Dependencies: []*pb.Dependency{
				{
					Name:      "redis",
					Type:      "cache",
					Status:    pb.HealthCheckResponse_SERVING,
					Endpoint:  "redis://localhost:6379",
					LastCheck: timestamppb.Now(),
				},
			},
		},
	}

	metrics := &pb.SystemMetrics{
		CpuUsage:            25.5,
		MemoryUsage:         60.2,
		ActiveConnections:   150,
		TotalRequests:       10000,
		FailedRequests:      10,
		AverageResponseTime: 0.125,
	}

	return &pb.ServiceStatusResponse{
		Services:      services,
		SystemMetrics: metrics,
		Timestamp:     timestamppb.Now(),
	}, nil
}

// ForwardRequest forwards request to backend services
func (s *GatewayService) ForwardRequest(ctx context.Context, req *pb.ForwardRequestData) (*pb.ForwardResponseData, error) {
	s.logger.Info("Forwarding request",
		zap.String("service", req.ServiceName),
		zap.String("method", req.Method),
		zap.String("path", req.Path),
	)

	// Mock response
	return &pb.ForwardResponseData{
		StatusCode: 200,
		Headers: map[string]string{
			"Content-Type": "application/json",
		},
		Body: []byte(`{"status": "success", "message": "Request forwarded successfully"}`),
		Metadata: &pb.ResponseMetadata{
			RequestId:        req.Metadata.RequestId,
			Timestamp:        timestamppb.Now(),
			ProcessingTimeMs: 50,
			ServiceVersion:   "1.0.0",
			TraceId:          req.Metadata.TraceId,
		},
	}, nil
}

// BatchForward forwards multiple requests
func (s *GatewayService) BatchForward(ctx context.Context, req *pb.BatchForwardRequest) (*pb.BatchForwardResponse, error) {
	s.logger.Info("Batch forwarding requests", zap.Int("count", len(req.Requests)))

	responses := make([]*pb.ForwardResponseData, len(req.Requests))
	successCount := int32(0)
	
	for i, request := range req.Requests {
		// Forward each request
		resp, err := s.ForwardRequest(ctx, request)
		if err != nil {
			// Create error response
			responses[i] = &pb.ForwardResponseData{
				StatusCode: 500,
				Body:       []byte(fmt.Sprintf(`{"error": "%s"}`, err.Error())),
			}
		} else {
			responses[i] = resp
			successCount++
		}
	}

	return &pb.BatchForwardResponse{
		Responses:       responses,
		SuccessfulCount: successCount,
		FailedCount:     int32(len(req.Requests)) - successCount,
	}, nil
}

// ServiceProxyService implements the service proxy
type ServiceProxyService struct {
	pb.UnimplementedServiceProxyServiceServer
	logger *zap.Logger
}

// ForwardToCRM forwards request to CRM service
func (s *ServiceProxyService) ForwardToCRM(ctx context.Context, req *pb.ProxyRequest) (*pb.ProxyResponse, error) {
	s.logger.Info("Forwarding to CRM service",
		zap.String("method", req.Method),
		zap.String("path", req.Path),
	)

	// Get user context for authorization
	user := getUserFromContext(ctx)
	if user == nil || !user.HasRole("manager") && !user.HasRole("admin") {
		return nil, status.Error(codes.PermissionDenied, "insufficient permissions for CRM access")
	}

	// Mock CRM response
	return &pb.ProxyResponse{
		StatusCode: 200,
		Headers: map[string]string{
			"Content-Type": "application/json",
		},
		Body: &anypb.Any{}, // Would contain actual CRM data
		Metadata: &pb.ResponseMetadata{
			RequestId:        req.Metadata.RequestId,
			Timestamp:        timestamppb.Now(),
			ProcessingTimeMs: 100,
			ServiceVersion:   "crm-v1.0.0",
		},
	}, nil
}

// ForwardToERP forwards request to ERP service
func (s *ServiceProxyService) ForwardToERP(ctx context.Context, req *pb.ProxyRequest) (*pb.ProxyResponse, error) {
	s.logger.Info("Forwarding to ERP service",
		zap.String("method", req.Method),
		zap.String("path", req.Path),
	)

	// Similar implementation to CRM
	user := getUserFromContext(ctx)
	if user == nil || !user.HasRole("manager") && !user.HasRole("admin") {
		return nil, status.Error(codes.PermissionDenied, "insufficient permissions for ERP access")
	}

	return &pb.ProxyResponse{
		StatusCode: 200,
		Headers: map[string]string{
			"Content-Type": "application/json",
		},
		Body: &anypb.Any{},
		Metadata: &pb.ResponseMetadata{
			RequestId:        req.Metadata.RequestId,
			Timestamp:        timestamppb.Now(),
			ProcessingTimeMs: 120,
			ServiceVersion:   "erp-v1.0.0",
		},
	}, nil
}

// ForwardToSTT forwards request to STT service
func (s *ServiceProxyService) ForwardToSTT(ctx context.Context, req *pb.ProxyRequest) (*pb.ProxyResponse, error) {
	s.logger.Info("Forwarding to STT service",
		zap.String("method", req.Method),
		zap.String("path", req.Path),
	)

	return &pb.ProxyResponse{
		StatusCode: 200,
		Headers: map[string]string{
			"Content-Type": "application/json",
		},
		Body: &anypb.Any{},
		Metadata: &pb.ResponseMetadata{
			RequestId:        req.Metadata.RequestId,
			Timestamp:        timestamppb.Now(),
			ProcessingTimeMs: 200,
			ServiceVersion:   "stt-v1.0.0",
		},
	}, nil
}

// ForwardToTTS forwards request to TTS service
func (s *ServiceProxyService) ForwardToTTS(ctx context.Context, req *pb.ProxyRequest) (*pb.ProxyResponse, error) {
	s.logger.Info("Forwarding to TTS service",
		zap.String("method", req.Method),
		zap.String("path", req.Path),
	)

	return &pb.ProxyResponse{
		StatusCode: 200,
		Headers: map[string]string{
			"Content-Type": "application/json",
		},
		Body: &anypb.Any{},
		Metadata: &pb.ResponseMetadata{
			RequestId:        req.Metadata.RequestId,
			Timestamp:        timestamppb.Now(),
			ProcessingTimeMs: 180,
			ServiceVersion:   "tts-v1.0.0",
		},
	}, nil
}

// ForwardToUser forwards request to User service
func (s *ServiceProxyService) ForwardToUser(ctx context.Context, req *pb.ProxyRequest) (*pb.ProxyResponse, error) {
	s.logger.Info("Forwarding to User service",
		zap.String("method", req.Method),
		zap.String("path", req.Path),
	)

	return &pb.ProxyResponse{
		StatusCode: 200,
		Headers: map[string]string{
			"Content-Type": "application/json",
		},
		Body: &anypb.Any{},
		Metadata: &pb.ResponseMetadata{
			RequestId:        req.Metadata.RequestId,
			Timestamp:        timestamppb.Now(),
			ProcessingTimeMs: 80,
			ServiceVersion:   "user-v1.0.0",
		},
	}, nil
}

// ForwardToNotification forwards request to Notification service
func (s *ServiceProxyService) ForwardToNotification(ctx context.Context, req *pb.ProxyRequest) (*pb.ProxyResponse, error) {
	s.logger.Info("Forwarding to Notification service",
		zap.String("method", req.Method),
		zap.String("path", req.Path),
	)

	return &pb.ProxyResponse{
		StatusCode: 200,
		Headers: map[string]string{
			"Content-Type": "application/json",
		},
		Body: &anypb.Any{},
		Metadata: &pb.ResponseMetadata{
			RequestId:        req.Metadata.RequestId,
			Timestamp:        timestamppb.Now(),
			ProcessingTimeMs: 60,
			ServiceVersion:   "notification-v1.0.0",
		},
	}, nil
}