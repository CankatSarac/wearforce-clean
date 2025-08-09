package middleware

import (
	"context"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"

	"github.com/wearforce/gateway/internal/auth"
)

// AuthMiddleware creates JWT authentication middleware
func AuthMiddleware(validator *auth.JWTValidator, logger *zap.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Skip auth for health checks and metrics
		if isPublicPath(c.Request.URL.Path) {
			c.Next()
			return
		}

		// Extract token from Authorization header
		authHeader := c.GetHeader("Authorization")
		if authHeader == "" {
			logger.Debug("Missing Authorization header", 
				zap.String("path", c.Request.URL.Path),
				zap.String("method", c.Request.Method),
			)
			c.JSON(http.StatusUnauthorized, gin.H{
				"error": "Authorization header required",
				"code":  "MISSING_AUTH_HEADER",
			})
			c.Abort()
			return
		}

		// Validate token
		userCtx, err := validator.ValidateToken(authHeader)
		if err != nil {
			// Log detailed error for debugging but don't expose it to client
			logger.Warn("Token validation failed",
				zap.String("error_type", getErrorType(err)),
				zap.String("path", c.Request.URL.Path),
				zap.String("method", c.Request.Method),
				zap.String("user_agent", c.GetHeader("User-Agent")),
				zap.String("remote_addr", c.ClientIP()),
			)
			
			// Return generic error message to prevent information leakage
			c.JSON(http.StatusUnauthorized, gin.H{
				"error": "Authentication failed",
				"code":  "AUTHENTICATION_FAILED",
			})
			c.Abort()
			return
		}

		// Add user context to request context
		ctx := context.WithValue(c.Request.Context(), "user", userCtx)
		c.Request = c.Request.WithContext(ctx)

		// Add user info to Gin context for easy access
		c.Set("user", userCtx)
		c.Set("user_id", userCtx.UserID)
		c.Set("user_email", userCtx.Email)
		c.Set("user_roles", userCtx.Roles)

		logger.Debug("User authenticated",
			zap.String("user_id", userCtx.UserID),
			zap.String("email", userCtx.Email),
			zap.Strings("roles", userCtx.Roles),
			zap.String("path", c.Request.URL.Path),
		)

		c.Next()
	}
}

// RequireRole creates middleware that requires specific roles
func RequireRole(roles ...string) gin.HandlerFunc {
	return func(c *gin.Context) {
		userCtx, exists := c.Get("user")
		if !exists {
			c.JSON(http.StatusUnauthorized, gin.H{
				"error": "User not authenticated",
				"code":  "NOT_AUTHENTICATED",
			})
			c.Abort()
			return
		}

		user, ok := userCtx.(*auth.UserContext)
		if !ok {
			logger.Error("Invalid user context type assertion failed",
				zap.String("path", c.Request.URL.Path),
				zap.String("method", c.Request.Method),
			)
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": "Internal server error",
				"code":  "INTERNAL_ERROR",
			})
			c.Abort()
			return
		}

		// Check if user has any of the required roles
		hasRole := false
		for _, requiredRole := range roles {
			if user.HasRole(requiredRole) {
				hasRole = true
				break
			}
		}

		if !hasRole {
			logger.Warn("Authorization failed - insufficient roles",
				zap.String("user_id", user.UserID),
				zap.Strings("required_roles", roles),
				zap.Strings("user_roles", user.Roles),
				zap.String("path", c.Request.URL.Path),
				zap.String("method", c.Request.Method),
			)
			
			// Return generic error message without exposing role details
			c.JSON(http.StatusForbidden, gin.H{
				"error": "Access denied",
				"code":  "ACCESS_DENIED",
			})
			c.Abort()
			return
		}

		c.Next()
	}
}

// RequireClientRole creates middleware that requires specific client roles
func RequireClientRole(clientID string, roles ...string) gin.HandlerFunc {
	return func(c *gin.Context) {
		userCtx, exists := c.Get("user")
		if !exists {
			c.JSON(http.StatusUnauthorized, gin.H{
				"error": "User not authenticated",
				"code":  "NOT_AUTHENTICATED",
			})
			c.Abort()
			return
		}

		user, ok := userCtx.(*auth.UserContext)
		if !ok {
			logger.Error("Invalid user context type assertion failed",
				zap.String("path", c.Request.URL.Path),
				zap.String("method", c.Request.Method),
			)
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": "Internal server error",
				"code":  "INTERNAL_ERROR",
			})
			c.Abort()
			return
		}

		// Check if user has any of the required client roles
		hasRole := false
		for _, requiredRole := range roles {
			if user.HasClientRole(clientID, requiredRole) {
				hasRole = true
				break
			}
		}

		if !hasRole {
			clientRoles, _ := user.ClientRoles[clientID]
			logger.Warn("Authorization failed - insufficient client roles",
				zap.String("user_id", user.UserID),
				zap.String("client_id", clientID),
				zap.Strings("required_roles", roles),
				zap.Strings("user_client_roles", clientRoles),
				zap.String("path", c.Request.URL.Path),
				zap.String("method", c.Request.Method),
			)
			
			// Return generic error message without exposing role details
			c.JSON(http.StatusForbidden, gin.H{
				"error": "Access denied",
				"code":  "ACCESS_DENIED",
			})
			c.Abort()
			return
		}

		c.Next()
	}
}

// RequireGroup creates middleware that requires membership in specific groups
func RequireGroup(groups ...string) gin.HandlerFunc {
	return func(c *gin.Context) {
		userCtx, exists := c.Get("user")
		if !exists {
			c.JSON(http.StatusUnauthorized, gin.H{
				"error": "User not authenticated",
				"code":  "NOT_AUTHENTICATED",
			})
			c.Abort()
			return
		}

		user, ok := userCtx.(*auth.UserContext)
		if !ok {
			logger.Error("Invalid user context type assertion failed",
				zap.String("path", c.Request.URL.Path),
				zap.String("method", c.Request.Method),
			)
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": "Internal server error",
				"code":  "INTERNAL_ERROR",
			})
			c.Abort()
			return
		}

		// Check if user is in any of the required groups
		inGroup := false
		for _, requiredGroup := range groups {
			if user.InGroup(requiredGroup) {
				inGroup = true
				break
			}
		}

		if !inGroup {
			logger.Warn("Authorization failed - insufficient group membership",
				zap.String("user_id", user.UserID),
				zap.Strings("required_groups", groups),
				zap.Strings("user_groups", user.Groups),
				zap.String("path", c.Request.URL.Path),
				zap.String("method", c.Request.Method),
			)
			
			// Return generic error message without exposing group details
			c.JSON(http.StatusForbidden, gin.H{
				"error": "Access denied",
				"code":  "ACCESS_DENIED",
			})
			c.Abort()
			return
		}

		c.Next()
	}
}

// OptionalAuth creates middleware that validates JWT if present but doesn't require it
func OptionalAuth(validator *auth.JWTValidator, logger *zap.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		authHeader := c.GetHeader("Authorization")
		if authHeader == "" {
			// No auth header, continue without authentication
			c.Next()
			return
		}

		// Attempt to validate token
		userCtx, err := validator.ValidateToken(authHeader)
		if err != nil {
			logger.Debug("Optional auth failed",
				zap.Error(err),
				zap.String("path", c.Request.URL.Path),
			)
			// Continue without authentication
			c.Next()
			return
		}

		// Add user context if token is valid
		ctx := context.WithValue(c.Request.Context(), "user", userCtx)
		c.Request = c.Request.WithContext(ctx)
		c.Set("user", userCtx)
		c.Set("user_id", userCtx.UserID)

		c.Next()
	}
}

// isPublicPath checks if the path should skip authentication
func isPublicPath(path string) bool {
	publicPaths := []string{
		"/health",
		"/metrics",
		"/ping",
		"/favicon.ico",
		"/docs",
		"/swagger",
	}

	for _, publicPath := range publicPaths {
		if strings.HasPrefix(path, publicPath) {
			return true
		}
	}

	return false
}

// GetUserFromContext is a helper to extract authenticated user from Gin context
func GetUserFromContext(c *gin.Context) (*auth.UserContext, bool) {
	if userCtx, exists := c.Get("user"); exists {
		if user, ok := userCtx.(*auth.UserContext); ok {
			return user, true
		}
	}
	return nil, false
}

// GetUserIDFromContext is a helper to extract user ID from Gin context
func GetUserIDFromContext(c *gin.Context) (string, bool) {
	if userID, exists := c.Get("user_id"); exists {
		if id, ok := userID.(string); ok {
			return id, true
		}
	}
	return "", false
}

// getErrorType classifies error types for logging without exposing sensitive details
func getErrorType(err error) string {
	if err == nil {
		return "unknown"
	}
	
	errMsg := strings.ToLower(err.Error())
	
	switch {
	case strings.Contains(errMsg, "expired"):
		return "token_expired"
	case strings.Contains(errMsg, "invalid"):
		return "token_invalid"
	case strings.Contains(errMsg, "malformed") || strings.Contains(errMsg, "format"):
		return "token_malformed"
	case strings.Contains(errMsg, "signature"):
		return "signature_invalid"
	case strings.Contains(errMsg, "issuer"):
		return "issuer_mismatch"
	case strings.Contains(errMsg, "audience"):
		return "audience_mismatch"
	case strings.Contains(errMsg, "not before"):
		return "token_not_active"
	case strings.Contains(errMsg, "service unavailable"):
		return "auth_service_unavailable"
	default:
		return "token_validation_failed"
	}
}