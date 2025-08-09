package middleware

import (
	"crypto/rand"
	"encoding/base64"
	"fmt"
	"net/http"
	"regexp"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"
)

// SecurityConfig contains security middleware configuration
type SecurityConfig struct {
	// Content Security Policy
	CSP struct {
		DefaultSrc  []string
		ScriptSrc   []string
		StyleSrc    []string
		ImgSrc      []string
		FontSrc     []string
		ConnectSrc  []string
		FrameSrc    []string
		ObjectSrc   []string
		MediaSrc    []string
		BaseURI     []string
		FormAction  []string
		ReportURI   string
	}

	// HTTP Strict Transport Security
	HSTS struct {
		MaxAge            int
		IncludeSubDomains bool
		Preload           bool
	}

	// Other security headers
	XFrameOptions            string
	XContentTypeOptions      bool
	XSSProtection            string
	ReferrerPolicy           string
	PermissionsPolicy        string
	CrossOriginEmbedderPolicy string
	CrossOriginOpenerPolicy   string
	CrossOriginResourcePolicy string

	// Input validation
	MaxRequestSize  int64
	MaxHeaderSize   int
	AllowedMethods  []string
	BlockedUserAgents []string
	BlockedIPs        []string
}

// DefaultSecurityConfig returns a secure default configuration
func DefaultSecurityConfig() *SecurityConfig {
	return &SecurityConfig{
		CSP: struct {
			DefaultSrc  []string
			ScriptSrc   []string
			StyleSrc    []string
			ImgSrc      []string
			FontSrc     []string
			ConnectSrc  []string
			FrameSrc    []string
			ObjectSrc   []string
			MediaSrc    []string
			BaseURI     []string
			FormAction  []string
			ReportURI   string
		}{
			DefaultSrc:  []string{"'self'"},
			ScriptSrc:   []string{"'self'", "'strict-dynamic'"}, // Remove unsafe-inline and unsafe-eval
			StyleSrc:    []string{"'self'", "https://fonts.googleapis.com"},
			ImgSrc:      []string{"'self'", "data:", "https://*.wearforce.io", "https://secure.gravatar.com"},
			FontSrc:     []string{"'self'", "https://fonts.gstatic.com"},
			ConnectSrc:  []string{"'self'", "https://api.wearforce.io", "wss://api.wearforce.io", "https://*.wearforce.io"},
			FrameSrc:    []string{"'none'"},
			ObjectSrc:   []string{"'none'"},
			MediaSrc:    []string{"'self'", "https://*.wearforce.io"},
			BaseURI:     []string{"'self'"},
			FormAction:  []string{"'self'"},
			ReportURI:   "/api/csp-report",
		},
		HSTS: struct {
			MaxAge            int
			IncludeSubDomains bool
			Preload           bool
		}{
			MaxAge:            31536000, // 1 year
			IncludeSubDomains: true,
			Preload:           true,
		},
		XFrameOptions:            "DENY",
		XContentTypeOptions:      true,
		XSSProtection:            "1; mode=block",
		ReferrerPolicy:           "strict-origin-when-cross-origin",
		PermissionsPolicy:        "geolocation=(), microphone=(), camera=(), payment=(), usb=()",
		CrossOriginEmbedderPolicy: "require-corp",
		CrossOriginOpenerPolicy:   "same-origin",
		CrossOriginResourcePolicy: "cross-origin",
		MaxRequestSize:           10 * 1024 * 1024, // 10MB
		MaxHeaderSize:            8192,             // 8KB
		AllowedMethods:           []string{"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"},
		BlockedUserAgents:        []string{},
		BlockedIPs:              []string{},
	}
}

// SecurityHeadersMiddleware adds comprehensive security headers
func SecurityHeadersMiddleware(config *SecurityConfig, logger *zap.Logger) gin.HandlerFunc {
	if config == nil {
		config = DefaultSecurityConfig()
	}

	return func(c *gin.Context) {
		// Generate nonce for CSP
		nonce := generateNonce()
		c.Set("csp-nonce", nonce)

		// Content Security Policy
		csp := buildCSP(config, nonce)
		if csp != "" {
			c.Header("Content-Security-Policy", csp)
		}

		// HTTP Strict Transport Security (only over HTTPS)
		if c.Request.TLS != nil || c.GetHeader("X-Forwarded-Proto") == "https" {
			hsts := buildHSTS(config)
			if hsts != "" {
				c.Header("Strict-Transport-Security", hsts)
			}
		}

		// X-Frame-Options
		if config.XFrameOptions != "" {
			c.Header("X-Frame-Options", config.XFrameOptions)
		}

		// X-Content-Type-Options
		if config.XContentTypeOptions {
			c.Header("X-Content-Type-Options", "nosniff")
		}

		// X-XSS-Protection
		if config.XSSProtection != "" {
			c.Header("X-XSS-Protection", config.XSSProtection)
		}

		// Referrer-Policy
		if config.ReferrerPolicy != "" {
			c.Header("Referrer-Policy", config.ReferrerPolicy)
		}

		// Permissions-Policy
		if config.PermissionsPolicy != "" {
			c.Header("Permissions-Policy", config.PermissionsPolicy)
		}

		// Cross-Origin-Embedder-Policy
		if config.CrossOriginEmbedderPolicy != "" {
			c.Header("Cross-Origin-Embedder-Policy", config.CrossOriginEmbedderPolicy)
		}

		// Cross-Origin-Opener-Policy
		if config.CrossOriginOpenerPolicy != "" {
			c.Header("Cross-Origin-Opener-Policy", config.CrossOriginOpenerPolicy)
		}

		// Cross-Origin-Resource-Policy
		if config.CrossOriginResourcePolicy != "" {
			c.Header("Cross-Origin-Resource-Policy", config.CrossOriginResourcePolicy)
		}

		// Server header obfuscation
		c.Header("Server", "WearForce")

		// Remove sensitive headers
		c.Header("X-Powered-By", "")

		// Cache control for sensitive endpoints
		if isSensitiveEndpoint(c.Request.URL.Path) {
			c.Header("Cache-Control", "no-store, no-cache, must-revalidate, private")
			c.Header("Pragma", "no-cache")
			c.Header("Expires", "0")
		}

		c.Next()
	}
}

// InputValidationMiddleware validates and sanitizes input
func InputValidationMiddleware(config *SecurityConfig, logger *zap.Logger) gin.HandlerFunc {
	if config == nil {
		config = DefaultSecurityConfig()
	}

	return func(c *gin.Context) {
		// Check request size
		if c.Request.ContentLength > config.MaxRequestSize {
			logger.Warn("Request too large",
				zap.Int64("content_length", c.Request.ContentLength),
				zap.Int64("max_size", config.MaxRequestSize),
				zap.String("path", c.Request.URL.Path),
				zap.String("client_ip", c.ClientIP()),
			)
			c.JSON(http.StatusRequestEntityTooLarge, gin.H{
				"error": "Request entity too large",
				"code":  "REQUEST_TOO_LARGE",
			})
			c.Abort()
			return
		}

		// Check HTTP method
		if !isMethodAllowed(c.Request.Method, config.AllowedMethods) {
			logger.Warn("Method not allowed",
				zap.String("method", c.Request.Method),
				zap.String("path", c.Request.URL.Path),
				zap.String("client_ip", c.ClientIP()),
			)
			c.JSON(http.StatusMethodNotAllowed, gin.H{
				"error": "Method not allowed",
				"code":  "METHOD_NOT_ALLOWED",
			})
			c.Abort()
			return
		}

		// Check User-Agent
		userAgent := c.GetHeader("User-Agent")
		if isBlockedUserAgent(userAgent, config.BlockedUserAgents) {
			logger.Warn("Blocked user agent",
				zap.String("user_agent", userAgent),
				zap.String("path", c.Request.URL.Path),
				zap.String("client_ip", c.ClientIP()),
			)
			c.JSON(http.StatusForbidden, gin.H{
				"error": "Access denied",
				"code":  "USER_AGENT_BLOCKED",
			})
			c.Abort()
			return
		}

		// Check IP address
		clientIP := c.ClientIP()
		if isBlockedIP(clientIP, config.BlockedIPs) {
			logger.Warn("Blocked IP address",
				zap.String("client_ip", clientIP),
				zap.String("path", c.Request.URL.Path),
			)
			c.JSON(http.StatusForbidden, gin.H{
				"error": "Access denied",
				"code":  "IP_BLOCKED",
			})
			c.Abort()
			return
		}

		// Validate headers
		for name, values := range c.Request.Header {
			for _, value := range values {
				if len(value) > config.MaxHeaderSize {
					logger.Warn("Header too large",
						zap.String("header", name),
						zap.Int("size", len(value)),
						zap.Int("max_size", config.MaxHeaderSize),
						zap.String("client_ip", clientIP),
					)
					c.JSON(http.StatusBadRequest, gin.H{
						"error": "Header too large",
						"code":  "HEADER_TOO_LARGE",
					})
					c.Abort()
					return
				}

				// Check for potential XSS in headers
				if containsSuspiciousContent(value) {
					logger.Warn("Suspicious header content",
						zap.String("header", name),
						zap.String("value", value[:min(len(value), 100)]),
						zap.String("client_ip", clientIP),
					)
					c.JSON(http.StatusBadRequest, gin.H{
						"error": "Invalid header content",
						"code":  "INVALID_HEADER",
					})
					c.Abort()
					return
				}
			}
		}

		// Validate query parameters
		for param, values := range c.Request.URL.Query() {
			for _, value := range values {
				if containsSuspiciousContent(value) {
					logger.Warn("Suspicious query parameter",
						zap.String("param", param),
						zap.String("value", value[:min(len(value), 100)]),
						zap.String("client_ip", clientIP),
					)
					c.JSON(http.StatusBadRequest, gin.H{
						"error": "Invalid query parameter",
						"code":  "INVALID_QUERY_PARAM",
					})
					c.Abort()
					return
				}
			}
		}

		c.Next()
	}
}

// DDoSProtectionMiddleware provides basic DDoS protection
func DDoSProtectionMiddleware(logger *zap.Logger) gin.HandlerFunc {
	// Simple connection tracking
	connections := make(map[string]int)
	maxConnectionsPerIP := 100

	return func(c *gin.Context) {
		clientIP := c.ClientIP()
		
		// Track connections per IP
		connections[clientIP]++
		defer func() {
			connections[clientIP]--
			if connections[clientIP] <= 0 {
				delete(connections, clientIP)
			}
		}()

		// Check if IP has too many concurrent connections
		if connections[clientIP] > maxConnectionsPerIP {
			logger.Warn("Too many concurrent connections",
				zap.String("client_ip", clientIP),
				zap.Int("connections", connections[clientIP]),
				zap.Int("max_allowed", maxConnectionsPerIP),
			)
			c.JSON(http.StatusTooManyRequests, gin.H{
				"error": "Too many concurrent connections",
				"code":  "TOO_MANY_CONNECTIONS",
			})
			c.Abort()
			return
		}

		c.Next()
	}
}

// generateNonce generates a cryptographically secure nonce for CSP
func generateNonce() string {
	bytes := make([]byte, 16)
	_, err := rand.Read(bytes)
	if err != nil {
		// Fallback to time-based nonce
		return base64.StdEncoding.EncodeToString([]byte(fmt.Sprintf("%d", time.Now().UnixNano())))
	}
	return base64.StdEncoding.EncodeToString(bytes)
}

// buildCSP constructs the Content Security Policy header value
func buildCSP(config *SecurityConfig, nonce string) string {
	var policies []string

	if len(config.CSP.DefaultSrc) > 0 {
		policies = append(policies, fmt.Sprintf("default-src %s", strings.Join(config.CSP.DefaultSrc, " ")))
	}

	if len(config.CSP.ScriptSrc) > 0 {
		scriptSrc := append(config.CSP.ScriptSrc, fmt.Sprintf("'nonce-%s'", nonce))
		policies = append(policies, fmt.Sprintf("script-src %s", strings.Join(scriptSrc, " ")))
	}

	if len(config.CSP.StyleSrc) > 0 {
		policies = append(policies, fmt.Sprintf("style-src %s", strings.Join(config.CSP.StyleSrc, " ")))
	}

	if len(config.CSP.ImgSrc) > 0 {
		policies = append(policies, fmt.Sprintf("img-src %s", strings.Join(config.CSP.ImgSrc, " ")))
	}

	if len(config.CSP.FontSrc) > 0 {
		policies = append(policies, fmt.Sprintf("font-src %s", strings.Join(config.CSP.FontSrc, " ")))
	}

	if len(config.CSP.ConnectSrc) > 0 {
		policies = append(policies, fmt.Sprintf("connect-src %s", strings.Join(config.CSP.ConnectSrc, " ")))
	}

	if len(config.CSP.FrameSrc) > 0 {
		policies = append(policies, fmt.Sprintf("frame-src %s", strings.Join(config.CSP.FrameSrc, " ")))
	}

	if len(config.CSP.ObjectSrc) > 0 {
		policies = append(policies, fmt.Sprintf("object-src %s", strings.Join(config.CSP.ObjectSrc, " ")))
	}

	if len(config.CSP.MediaSrc) > 0 {
		policies = append(policies, fmt.Sprintf("media-src %s", strings.Join(config.CSP.MediaSrc, " ")))
	}

	if len(config.CSP.BaseURI) > 0 {
		policies = append(policies, fmt.Sprintf("base-uri %s", strings.Join(config.CSP.BaseURI, " ")))
	}

	if len(config.CSP.FormAction) > 0 {
		policies = append(policies, fmt.Sprintf("form-action %s", strings.Join(config.CSP.FormAction, " ")))
	}

	if config.CSP.ReportURI != "" {
		policies = append(policies, fmt.Sprintf("report-uri %s", config.CSP.ReportURI))
	}

	return strings.Join(policies, "; ")
}

// buildHSTS constructs the HSTS header value
func buildHSTS(config *SecurityConfig) string {
	hsts := fmt.Sprintf("max-age=%d", config.HSTS.MaxAge)
	
	if config.HSTS.IncludeSubDomains {
		hsts += "; includeSubDomains"
	}
	
	if config.HSTS.Preload {
		hsts += "; preload"
	}
	
	return hsts
}

// isSensitiveEndpoint checks if the path contains sensitive endpoints
func isSensitiveEndpoint(path string) bool {
	sensitivePatterns := []string{
		"/admin",
		"/api/admin",
		"/auth",
		"/login",
		"/logout",
		"/api/user",
		"/api/payment",
		"/api/pii",
	}

	for _, pattern := range sensitivePatterns {
		if strings.HasPrefix(path, pattern) {
			return true
		}
	}

	return false
}

// isMethodAllowed checks if HTTP method is allowed
func isMethodAllowed(method string, allowedMethods []string) bool {
	for _, allowed := range allowedMethods {
		if method == allowed {
			return true
		}
	}
	return false
}

// isBlockedUserAgent checks if user agent is blocked
func isBlockedUserAgent(userAgent string, blockedAgents []string) bool {
	userAgent = strings.ToLower(userAgent)
	for _, blocked := range blockedAgents {
		if strings.Contains(userAgent, strings.ToLower(blocked)) {
			return true
		}
	}
	return false
}

// isBlockedIP checks if IP address is blocked
func isBlockedIP(ip string, blockedIPs []string) bool {
	for _, blocked := range blockedIPs {
		if ip == blocked {
			return true
		}
	}
	return false
}

// containsSuspiciousContent checks for potentially malicious content
func containsSuspiciousContent(content string) bool {
	// Common XSS patterns
	xssPatterns := []string{
		"<script",
		"javascript:",
		"data:text/html",
		"vbscript:",
		"onload=",
		"onerror=",
		"onclick=",
		"onmouseover=",
		"onfocus=",
		"onblur=",
		"onkeyup=",
		"onchange=",
		"eval(",
		"expression(",
		"url(javascript:",
	}

	contentLower := strings.ToLower(content)
	for _, pattern := range xssPatterns {
		if strings.Contains(contentLower, pattern) {
			return true
		}
	}

	// SQL injection patterns
	sqlPatterns := []string{
		"union select",
		"' or '1'='1",
		"' or 1=1--",
		"; drop table",
		"; delete from",
		"0x",
		"char(",
		"waitfor delay",
	}

	for _, pattern := range sqlPatterns {
		if strings.Contains(contentLower, pattern) {
			return true
		}
	}

	// Directory traversal patterns
	if strings.Contains(content, "../") || strings.Contains(content, "..\\") {
		return true
	}

	// Command injection patterns
	cmdPatterns := []string{
		"; ls",
		"| cat",
		"& cat",
		"; cat",
		"$(cat",
		"`cat",
		"; id",
		"| id",
		"& id",
		"; whoami",
	}

	for _, pattern := range cmdPatterns {
		if strings.Contains(contentLower, pattern) {
			return true
		}
	}

	// Check for excessive length (potential buffer overflow)
	if len(content) > 10000 {
		return true
	}

	// Check for null bytes
	if strings.Contains(content, "\x00") {
		return true
	}

	// Check for control characters
	controlCharPattern := regexp.MustCompile(`[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]`)
	if controlCharPattern.MatchString(content) {
		return true
	}

	return false
}

// min returns the minimum of two integers
func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// CSPReportMiddleware handles CSP violation reports
func CSPReportMiddleware(logger *zap.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		if c.Request.URL.Path == "/api/csp-report" && c.Request.Method == "POST" {
			var report map[string]interface{}
			if err := c.ShouldBindJSON(&report); err == nil {
				logger.Warn("CSP violation reported",
					zap.Any("report", report),
					zap.String("client_ip", c.ClientIP()),
					zap.String("user_agent", c.GetHeader("User-Agent")),
				)
			}
			c.Status(http.StatusNoContent)
			c.Abort()
			return
		}
		c.Next()
	}
}