package middleware

import (
	"bytes"
	"fmt"
	"io"
	"math/rand"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

// LoggingMiddleware creates structured logging middleware
func LoggingMiddleware(logger *zap.Logger) gin.HandlerFunc {
	return gin.LoggerWithConfig(gin.LoggerConfig{
		Formatter: func(param gin.LogFormatterParams) string {
			// Log using structured logging
			fields := []zap.Field{
				zap.String("method", param.Method),
				zap.String("path", param.Path),
				zap.String("query", param.Request.URL.RawQuery),
				zap.Int("status", param.StatusCode),
				zap.Duration("latency", param.Latency),
				zap.String("client_ip", param.ClientIP),
				zap.String("user_agent", param.Request.UserAgent()),
				zap.Int("body_size", param.BodySize),
			}

			// Add error if present
			if param.ErrorMessage != "" {
				fields = append(fields, zap.String("error", param.ErrorMessage))
			}

			// Add user info if available
			if userID := param.Request.Header.Get("X-User-ID"); userID != "" {
				fields = append(fields, zap.String("user_id", userID))
			}

			// Add trace info if available
			if traceID := param.Request.Header.Get("X-Trace-ID"); traceID != "" {
				fields = append(fields, zap.String("trace_id", traceID))
			}

			if requestID := param.Request.Header.Get("X-Request-ID"); requestID != "" {
				fields = append(fields, zap.String("request_id", requestID))
			}

			// Choose log level based on status code
			switch {
			case param.StatusCode >= 500:
				logger.Error("HTTP Request", fields...)
			case param.StatusCode >= 400:
				logger.Warn("HTTP Request", fields...)
			default:
				logger.Info("HTTP Request", fields...)
			}

			return "" // Return empty string since we're using structured logging
		},
		Output: io.Discard, // Discard gin's default output since we're using zap
	})
}

// DetailedLoggingMiddleware creates more detailed logging middleware
func DetailedLoggingMiddleware(logger *zap.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()

		// Capture request body if needed (for debugging)
		var requestBody []byte
		if c.Request.Body != nil && c.Request.ContentLength > 0 && c.Request.ContentLength < 1024*10 { // Only capture small bodies
			requestBody, _ = io.ReadAll(c.Request.Body)
			c.Request.Body = io.NopCloser(bytes.NewBuffer(requestBody))
		}

		// Create response writer wrapper to capture response
		blw := &bodyLogWriter{body: bytes.NewBufferString(""), ResponseWriter: c.Writer}
		c.Writer = blw

		// Process request
		c.Next()

		// Calculate duration
		duration := time.Since(start)

		// Prepare log fields
		fields := []zap.Field{
			zap.String("method", c.Request.Method),
			zap.String("path", c.Request.URL.Path),
			zap.String("query", c.Request.URL.RawQuery),
			zap.Int("status", c.Writer.Status()),
			zap.Duration("duration", duration),
			zap.String("client_ip", c.ClientIP()),
			zap.String("user_agent", c.Request.UserAgent()),
			zap.Int("request_size", int(c.Request.ContentLength)),
			zap.Int("response_size", blw.body.Len()),
		}

		// Add request headers
		importantHeaders := []string{
			"Authorization",
			"Content-Type",
			"Accept",
			"Origin",
			"Referer",
			"X-Forwarded-For",
			"X-Real-IP",
		}

		headerFields := make([]zap.Field, 0, len(importantHeaders))
		for _, header := range importantHeaders {
			if value := c.Request.Header.Get(header); value != "" {
				// Mask sensitive headers
				if header == "Authorization" && len(value) > 20 {
					value = value[:20] + "..."
				}
				headerFields = append(headerFields, zap.String("header_"+strings.ToLower(header), value))
			}
		}
		fields = append(fields, headerFields...)

		// Add user context if available
		if user, exists := GetUserFromContext(c); exists {
			fields = append(fields,
				zap.String("user_id", user.UserID),
				zap.String("user_email", user.Email),
				zap.Strings("user_roles", user.Roles),
			)
		}

		// Add request body for debugging (only for errors)
		if c.Writer.Status() >= 400 && len(requestBody) > 0 && len(requestBody) < 1024 {
			fields = append(fields, zap.String("request_body", string(requestBody)))
		}

		// Add response body for errors (only small responses)
		if c.Writer.Status() >= 400 && blw.body.Len() < 1024 {
			fields = append(fields, zap.String("response_body", blw.body.String()))
		}

		// Add any errors from the request context
		if errors := c.Errors.Errors(); len(errors) > 0 {
			fields = append(fields, zap.Strings("errors", errors))
		}

		// Log based on status code and duration
		switch {
		case c.Writer.Status() >= 500:
			logger.Error("HTTP Request Failed", fields...)
		case c.Writer.Status() >= 400:
			logger.Warn("HTTP Request Client Error", fields...)
		case duration > 5*time.Second:
			logger.Warn("HTTP Request Slow", fields...)
		case duration > 1*time.Second:
			logger.Info("HTTP Request", fields...)
		default:
			logger.Debug("HTTP Request", fields...)
		}
	}
}

// bodyLogWriter wraps gin.ResponseWriter to capture response body
type bodyLogWriter struct {
	gin.ResponseWriter
	body *bytes.Buffer
}

func (w *bodyLogWriter) Write(b []byte) (int, error) {
	w.body.Write(b)
	return w.ResponseWriter.Write(b)
}

// RequestIDMiddleware adds unique request ID to each request
func RequestIDMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// Check if request ID already exists
		requestID := c.GetHeader("X-Request-ID")
		if requestID == "" {
			// Generate new request ID
			requestID = generateRequestID()
		}

		// Set request ID in context and header
		c.Header("X-Request-ID", requestID)
		c.Set("request_id", requestID)

		c.Next()
	}
}

// SecurityLoggingMiddleware logs security-related events
func SecurityLoggingMiddleware(logger *zap.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Log suspicious patterns
		userAgent := c.Request.UserAgent()
		if isSuspiciousUserAgent(userAgent) {
			logger.Warn("Suspicious User Agent",
				zap.String("user_agent", userAgent),
				zap.String("client_ip", c.ClientIP()),
				zap.String("path", c.Request.URL.Path),
			)
		}

		// Log authentication failures
		authHeader := c.GetHeader("Authorization")
		if authHeader != "" && !isValidAuthFormat(authHeader) {
			logger.Warn("Invalid Authorization Header Format",
				zap.String("client_ip", c.ClientIP()),
				zap.String("path", c.Request.URL.Path),
			)
		}

		c.Next()

		// Log failed authentication attempts
		if c.Writer.Status() == 401 {
			logger.Warn("Authentication Failed",
				zap.String("client_ip", c.ClientIP()),
				zap.String("path", c.Request.URL.Path),
				zap.String("method", c.Request.Method),
				zap.String("user_agent", userAgent),
			)
		}

		// Log authorization failures
		if c.Writer.Status() == 403 {
			logger.Warn("Authorization Failed",
				zap.String("client_ip", c.ClientIP()),
				zap.String("path", c.Request.URL.Path),
				zap.String("method", c.Request.Method),
			)
		}
	}
}

// generateRequestID generates a unique request ID
func generateRequestID() string {
	// Simple implementation - in production, use UUID or similar
	return fmt.Sprintf("%d-%d", time.Now().UnixNano(), rand.Intn(1000))
}

// isSuspiciousUserAgent checks for suspicious user agents
func isSuspiciousUserAgent(userAgent string) bool {
	suspiciousPatterns := []string{
		"sqlmap",
		"nikto",
		"nmap",
		"masscan",
		"zap",
		"burp",
		"wget",
		"curl", // Be careful with curl - it's often legitimate
	}

	userAgentLower := strings.ToLower(userAgent)
	for _, pattern := range suspiciousPatterns {
		if strings.Contains(userAgentLower, pattern) {
			return true
		}
	}

	return false
}

// isValidAuthFormat checks if authorization header has valid format
func isValidAuthFormat(authHeader string) bool {
	// Basic check for Bearer token format
	if strings.HasPrefix(authHeader, "Bearer ") && len(authHeader) > 7 {
		return true
	}
	
	// Basic check for Basic auth format
	if strings.HasPrefix(authHeader, "Basic ") && len(authHeader) > 6 {
		return true
	}

	return false
}

// AuditLoggingMiddleware logs important actions for audit purposes
func AuditLoggingMiddleware(logger *zap.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Only log certain methods and paths for audit
		if !shouldAuditLog(c.Request.Method, c.Request.URL.Path) {
			c.Next()
			return
		}

		start := time.Now()
		c.Next()
		duration := time.Since(start)

		// Get user context
		var userID, userEmail string
		if user, exists := GetUserFromContext(c); exists {
			userID = user.UserID
			userEmail = user.Email
		}

		// Log audit event
		logger.Info("Audit Log",
			zap.String("event_type", "api_access"),
			zap.String("method", c.Request.Method),
			zap.String("path", c.Request.URL.Path),
			zap.String("user_id", userID),
			zap.String("user_email", userEmail),
			zap.String("client_ip", c.ClientIP()),
			zap.Int("status_code", c.Writer.Status()),
			zap.Duration("duration", duration),
			zap.Time("timestamp", start),
		)
	}
}

// shouldAuditLog determines if a request should be audit logged
func shouldAuditLog(method, path string) bool {
	// Log all write operations
	if method == "POST" || method == "PUT" || method == "PATCH" || method == "DELETE" {
		return true
	}

	// Log access to sensitive endpoints
	sensitivePatterns := []string{
		"/admin/",
		"/api/users/",
		"/api/auth/",
		"/api/settings/",
	}

	for _, pattern := range sensitivePatterns {
		if strings.HasPrefix(path, pattern) {
			return true
		}
	}

	return false
}