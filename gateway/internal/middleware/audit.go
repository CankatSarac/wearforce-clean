package middleware

import (
	"bytes"
	"encoding/json"
	"io"
	"strconv"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

// AuditEvent represents an audit log event
type AuditEvent struct {
	Timestamp    time.Time              `json:"timestamp"`
	EventType    string                 `json:"event_type"`
	UserID       string                 `json:"user_id,omitempty"`
	UserEmail    string                 `json:"user_email,omitempty"`
	UserRoles    []string               `json:"user_roles,omitempty"`
	ClientIP     string                 `json:"client_ip"`
	UserAgent    string                 `json:"user_agent"`
	Method       string                 `json:"method"`
	Path         string                 `json:"path"`
	Query        string                 `json:"query,omitempty"`
	StatusCode   int                    `json:"status_code"`
	ResponseSize int                    `json:"response_size"`
	Duration     time.Duration          `json:"duration"`
	RequestID    string                 `json:"request_id,omitempty"`
	TraceID      string                 `json:"trace_id,omitempty"`
	Headers      map[string][]string    `json:"headers,omitempty"`
	RequestBody  string                 `json:"request_body,omitempty"`
	ResponseBody string                 `json:"response_body,omitempty"`
	Error        string                 `json:"error,omitempty"`
	Metadata     map[string]interface{} `json:"metadata,omitempty"`
	Severity     string                 `json:"severity"`
	Category     string                 `json:"category"`
	Source       string                 `json:"source"`
}

// AuditConfig contains audit logging configuration
type AuditConfig struct {
	Enabled           bool
	LogRequestBody    bool
	LogResponseBody   bool
	LogHeaders        bool
	MaxBodySize       int64
	SensitiveHeaders  []string
	SensitivePaths    []string
	ExcludedPaths     []string
	LogSuccessEvents  bool
	LogFailureEvents  bool
	LogAuthEvents     bool
	LogAdminEvents    bool
	LogDataEvents     bool
	MinLogLevel       string
}

// DefaultAuditConfig returns default audit configuration
func DefaultAuditConfig() *AuditConfig {
	return &AuditConfig{
		Enabled:          true,
		LogRequestBody:   false,
		LogResponseBody:  false,
		LogHeaders:       false,
		MaxBodySize:      1024 * 1024, // 1MB
		SensitiveHeaders: []string{"authorization", "cookie", "x-api-key", "x-auth-token"},
		SensitivePaths: []string{
			"/admin",
			"/api/admin",
			"/api/user",
			"/api/payment",
			"/api/pii",
			"/auth",
		},
		ExcludedPaths: []string{
			"/health",
			"/metrics",
			"/ping",
			"/favicon.ico",
		},
		LogSuccessEvents: true,
		LogFailureEvents: true,
		LogAuthEvents:    true,
		LogAdminEvents:   true,
		LogDataEvents:    true,
		MinLogLevel:      "info",
	}
}

// responseWriter is a wrapper to capture response body
type responseWriter struct {
	gin.ResponseWriter
	body       *bytes.Buffer
	statusCode int
}

// Write captures the response body
func (rw *responseWriter) Write(data []byte) (int, error) {
	rw.body.Write(data)
	return rw.ResponseWriter.Write(data)
}

// WriteHeader captures the status code
func (rw *responseWriter) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}

// AuditLoggingMiddleware creates comprehensive audit logging middleware
func AuditLoggingMiddleware(config *AuditConfig, logger *zap.Logger) gin.HandlerFunc {
	if config == nil {
		config = DefaultAuditConfig()
	}

	return func(c *gin.Context) {
		if !config.Enabled {
			c.Next()
			return
		}

		// Skip excluded paths
		if isPathExcluded(c.Request.URL.Path, config.ExcludedPaths) {
			c.Next()
			return
		}

		startTime := time.Now()

		// Capture request body if needed
		var requestBody string
		if config.LogRequestBody && shouldLogBody(c.Request.URL.Path, config.SensitivePaths) {
			if c.Request.Body != nil && c.Request.ContentLength <= config.MaxBodySize {
				bodyBytes, err := io.ReadAll(c.Request.Body)
				if err == nil {
					requestBody = sanitizeBody(string(bodyBytes))
					// Restore the body for further processing
					c.Request.Body = io.NopCloser(bytes.NewBuffer(bodyBytes))
				}
			}
		}

		// Wrap response writer to capture response body
		var responseWriter *responseWriter
		if config.LogResponseBody {
			responseWriter = &responseWriter{
				ResponseWriter: c.Writer,
				body:          &bytes.Buffer{},
				statusCode:    200,
			}
			c.Writer = responseWriter
		}

		// Process request
		c.Next()

		// Capture response information
		statusCode := c.Writer.Status()
		if responseWriter != nil && responseWriter.statusCode != 0 {
			statusCode = responseWriter.statusCode
		}

		duration := time.Since(startTime)

		// Create audit event
		event := &AuditEvent{
			Timestamp:    startTime,
			EventType:    determineEventType(c),
			ClientIP:     c.ClientIP(),
			UserAgent:    c.GetHeader("User-Agent"),
			Method:       c.Request.Method,
			Path:         c.Request.URL.Path,
			Query:        c.Request.URL.RawQuery,
			StatusCode:   statusCode,
			ResponseSize: c.Writer.Size(),
			Duration:     duration,
			RequestID:    c.GetHeader("X-Request-ID"),
			TraceID:      c.GetHeader("X-Trace-ID"),
			Severity:     determineSeverity(statusCode, c.Request.URL.Path),
			Category:     determineCategory(c.Request.URL.Path),
			Source:       "gateway",
		}

		// Add user information if available
		if userCtx, exists := c.Get("user"); exists {
			if user, ok := userCtx.(interface{ GetUserID() string }); ok {
				event.UserID = user.GetUserID()
			}
			if user, ok := userCtx.(interface{ GetEmail() string }); ok {
				event.UserEmail = user.GetEmail()
			}
			if user, ok := userCtx.(interface{ GetRoles() []string }); ok {
				event.UserRoles = user.GetRoles()
			}
		}
		
		// Alternative way to get user info from context
		if userID, exists := c.Get("user_id"); exists {
			if uid, ok := userID.(string); ok {
				event.UserID = uid
			}
		}
		if userEmail, exists := c.Get("user_email"); exists {
			if email, ok := userEmail.(string); ok {
				event.UserEmail = email
			}
		}
		if userRoles, exists := c.Get("user_roles"); exists {
			if roles, ok := userRoles.([]string); ok {
				event.UserRoles = roles
			}
		}

		// Add headers if configured
		if config.LogHeaders {
			event.Headers = filterSensitiveHeaders(c.Request.Header, config.SensitiveHeaders)
		}

		// Add request body if captured
		if requestBody != "" {
			event.RequestBody = requestBody
		}

		// Add response body if captured
		if responseWriter != nil && responseWriter.body.Len() > 0 {
			responseBody := sanitizeBody(responseWriter.body.String())
			if len(responseBody) <= int(config.MaxBodySize) {
				event.ResponseBody = responseBody
			}
		}

		// Add error information if present
		if len(c.Errors) > 0 {
			event.Error = c.Errors.String()
		}

		// Add metadata
		event.Metadata = map[string]interface{}{
			"content_type":   c.GetHeader("Content-Type"),
			"content_length": c.Request.ContentLength,
			"protocol":       c.Request.Proto,
			"host":          c.Request.Host,
			"referer":       c.GetHeader("Referer"),
		}

		// Determine if event should be logged
		if shouldLogEvent(event, config) {
			logAuditEvent(event, logger)
		}

		// Log security events separately if this is a security-related request
		if isSecurityEvent(event) {
			logSecurityEvent(event, logger)
		}
	}
}

// determineEventType determines the type of audit event
func determineEventType(c *gin.Context) string {
	path := c.Request.URL.Path
	method := c.Request.Method

	// Authentication events
	if strings.Contains(path, "/auth") || strings.Contains(path, "/login") || strings.Contains(path, "/logout") {
		return "authentication"
	}

	// Authorization events
	if c.Writer.Status() == 401 || c.Writer.Status() == 403 {
		return "authorization"
	}

	// Admin events
	if strings.HasPrefix(path, "/admin") || strings.HasPrefix(path, "/api/admin") {
		return "admin"
	}

	// Data access events
	if strings.HasPrefix(path, "/api/") {
		switch method {
		case "GET":
			return "data_read"
		case "POST":
			return "data_create"
		case "PUT", "PATCH":
			return "data_update"
		case "DELETE":
			return "data_delete"
		}
	}

	// System events
	if strings.HasPrefix(path, "/health") || strings.HasPrefix(path, "/metrics") {
		return "system"
	}

	return "api_access"
}

// determineSeverity determines the severity level of the event
func determineSeverity(statusCode int, path string) string {
	// Critical security events
	if statusCode == 401 || statusCode == 403 {
		return "high"
	}

	// Server errors
	if statusCode >= 500 {
		return "high"
	}

	// Client errors
	if statusCode >= 400 {
		return "medium"
	}

	// Admin operations
	if strings.HasPrefix(path, "/admin") || strings.HasPrefix(path, "/api/admin") {
		return "high"
	}

	// Sensitive data operations
	if strings.Contains(path, "/payment") || strings.Contains(path, "/pii") {
		return "high"
	}

	// Default for successful operations
	if statusCode >= 200 && statusCode < 300 {
		return "low"
	}

	return "medium"
}

// determineCategory determines the category of the event
func determineCategory(path string) string {
	if strings.HasPrefix(path, "/admin") {
		return "administration"
	}
	if strings.Contains(path, "/auth") {
		return "authentication"
	}
	if strings.Contains(path, "/payment") {
		return "payment"
	}
	if strings.Contains(path, "/user") {
		return "user_management"
	}
	if strings.Contains(path, "/crm") {
		return "crm"
	}
	if strings.Contains(path, "/erp") {
		return "erp"
	}
	if strings.Contains(path, "/api/") {
		return "api"
	}
	return "general"
}

// shouldLogEvent determines if an event should be logged based on configuration
func shouldLogEvent(event *AuditEvent, config *AuditConfig) bool {
	// Always log high severity events
	if event.Severity == "high" {
		return true
	}

	// Check specific event type configurations
	switch event.EventType {
	case "authentication", "authorization":
		return config.LogAuthEvents
	case "admin":
		return config.LogAdminEvents
	case "data_read", "data_create", "data_update", "data_delete":
		return config.LogDataEvents
	}

	// Check success/failure configuration
	if event.StatusCode >= 200 && event.StatusCode < 400 {
		return config.LogSuccessEvents
	}
	if event.StatusCode >= 400 {
		return config.LogFailureEvents
	}

	return true
}

// isSecurityEvent determines if this is a security-related event
func isSecurityEvent(event *AuditEvent) bool {
	return event.EventType == "authentication" ||
		event.EventType == "authorization" ||
		event.StatusCode == 401 ||
		event.StatusCode == 403 ||
		strings.Contains(event.Path, "/admin") ||
		strings.Contains(event.Path, "/auth")
}

// logAuditEvent logs the audit event
func logAuditEvent(event *AuditEvent, logger *zap.Logger) {
	fields := []zap.Field{
		zap.Time("timestamp", event.Timestamp),
		zap.String("event_type", event.EventType),
		zap.String("user_id", event.UserID),
		zap.String("user_email", event.UserEmail),
		zap.Strings("user_roles", event.UserRoles),
		zap.String("client_ip", event.ClientIP),
		zap.String("method", event.Method),
		zap.String("path", event.Path),
		zap.String("query", event.Query),
		zap.Int("status_code", event.StatusCode),
		zap.Int("response_size", event.ResponseSize),
		zap.Duration("duration", event.Duration),
		zap.String("request_id", event.RequestID),
		zap.String("trace_id", event.TraceID),
		zap.String("severity", event.Severity),
		zap.String("category", event.Category),
		zap.String("source", event.Source),
		zap.Any("metadata", event.Metadata),
	}

	if event.Error != "" {
		fields = append(fields, zap.String("error", event.Error))
	}

	if event.RequestBody != "" {
		fields = append(fields, zap.String("request_body", event.RequestBody))
	}

	if event.ResponseBody != "" {
		fields = append(fields, zap.String("response_body", event.ResponseBody))
	}

	logger.Info("Audit Event", fields...)
}

// logSecurityEvent logs security-specific events with additional context
func logSecurityEvent(event *AuditEvent, logger *zap.Logger) {
	logger.With(
		zap.String("event_category", "SECURITY"),
		zap.String("security_event_type", event.EventType),
		zap.String("severity", event.Severity),
	).Warn("Security Event",
		zap.Time("timestamp", event.Timestamp),
		zap.String("user_id", event.UserID),
		zap.String("client_ip", event.ClientIP),
		zap.String("method", event.Method),
		zap.String("path", event.Path),
		zap.Int("status_code", event.StatusCode),
		zap.String("user_agent", event.UserAgent),
	)
}

// isPathExcluded checks if path should be excluded from audit logging
func isPathExcluded(path string, excludedPaths []string) bool {
	for _, excluded := range excludedPaths {
		if strings.HasPrefix(path, excluded) {
			return true
		}
	}
	return false
}

// shouldLogBody determines if request/response body should be logged for this path
func shouldLogBody(path string, sensitivePaths []string) bool {
	// Don't log body for sensitive paths by default
	for _, sensitive := range sensitivePaths {
		if strings.HasPrefix(path, sensitive) {
			return false
		}
	}
	return true
}

// filterSensitiveHeaders removes sensitive headers from the log
func filterSensitiveHeaders(headers map[string][]string, sensitiveHeaders []string) map[string][]string {
	filtered := make(map[string][]string)
	
	for name, values := range headers {
		include := true
		for _, sensitive := range sensitiveHeaders {
			if strings.EqualFold(name, sensitive) {
				include = false
				break
			}
		}
		
		if include {
			filtered[name] = values
		} else {
			filtered[name] = []string{"[REDACTED]"}
		}
	}
	
	return filtered
}

// sanitizeBody sanitizes request/response body for logging
func sanitizeBody(body string) string {
	// Limit body size
	if len(body) > 10000 {
		body = body[:10000] + "...[TRUNCATED]"
	}

	// Try to parse as JSON and remove sensitive fields
	var jsonData map[string]interface{}
	if err := json.Unmarshal([]byte(body), &jsonData); err == nil {
		sensitiveFields := []string{"password", "token", "secret", "key", "credit_card", "ssn", "api_key"}
		
		for field := range jsonData {
			for _, sensitive := range sensitiveFields {
				if strings.Contains(strings.ToLower(field), sensitive) {
					jsonData[field] = "[REDACTED]"
				}
			}
		}
		
		if sanitized, err := json.Marshal(jsonData); err == nil {
			return string(sanitized)
		}
	}

	// Simple text sanitization
	sensitivePatterns := []string{"password=", "token=", "secret=", "key=", "api_key="}
	for _, pattern := range sensitivePatterns {
		body = sanitizeTextPattern(body, pattern)
	}

	return body
}

// sanitizeTextPattern sanitizes specific patterns in text
func sanitizeTextPattern(text, pattern string) string {
	index := strings.Index(strings.ToLower(text), pattern)
	if index == -1 {
		return text
	}

	// Find the end of the value (next & or end of string)
	start := index + len(pattern)
	end := start
	for end < len(text) && text[end] != '&' && text[end] != '\n' && text[end] != ' ' {
		end++
	}

	// Replace the value with [REDACTED]
	return text[:start] + "[REDACTED]" + text[end:]
}

// ComplianceAuditMiddleware provides compliance-specific audit logging
func ComplianceAuditMiddleware(logger *zap.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		path := c.Request.URL.Path
		
		// Log GDPR-related data access
		if isGDPRRelevant(path) {
			logger.Info("GDPR Data Access",
				zap.String("event_type", "gdpr_data_access"),
				zap.String("path", path),
				zap.String("method", c.Request.Method),
				zap.String("client_ip", c.ClientIP()),
				zap.String("user_agent", c.GetHeader("User-Agent")),
				zap.Time("timestamp", time.Now()),
			)
		}

		// Log PCI-related payment data access
		if isPCIRelevant(path) {
			logger.Info("PCI Payment Access",
				zap.String("event_type", "pci_payment_access"),
				zap.String("path", path),
				zap.String("method", c.Request.Method),
				zap.String("client_ip", c.ClientIP()),
				zap.Time("timestamp", time.Now()),
			)
		}

		c.Next()
	}
}

// isGDPRRelevant checks if the request is relevant for GDPR compliance
func isGDPRRelevant(path string) bool {
	gdprPaths := []string{"/api/user", "/api/profile", "/api/personal", "/api/pii"}
	for _, gdprPath := range gdprPaths {
		if strings.HasPrefix(path, gdprPath) {
			return true
		}
	}
	return false
}

// isPCIRelevant checks if the request is relevant for PCI compliance
func isPCIRelevant(path string) bool {
	pciPaths := []string{"/api/payment", "/api/card", "/api/billing"}
	for _, pciPath := range pciPaths {
		if strings.HasPrefix(path, pciPath) {
			return true
		}
	}
	return false
}