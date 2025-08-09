package api

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"go.uber.org/zap"

	"github.com/wearforce/gateway/internal/auth"
)

// DeviceFlowHandler handles device flow API endpoints
type DeviceFlowHandler struct {
	deviceFlowManager *auth.DeviceFlowManager
	logger           *zap.Logger
}

// NewDeviceFlowHandler creates a new device flow handler
func NewDeviceFlowHandler(deviceFlowManager *auth.DeviceFlowManager, logger *zap.Logger) *DeviceFlowHandler {
	return &DeviceFlowHandler{
		deviceFlowManager: deviceFlowManager,
		logger:           logger,
	}
}

// DeviceAuthorizationEndpoint handles device authorization requests (RFC 8628)
// POST /oauth/device_authorization
func (h *DeviceFlowHandler) DeviceAuthorizationEndpoint(c *gin.Context) {
	var req auth.DeviceCodeRequest
	if err := c.ShouldBind(&req); err != nil {
		h.logger.Warn("Invalid device authorization request",
			zap.Error(err),
			zap.String("client_ip", c.ClientIP()),
		)
		c.JSON(http.StatusBadRequest, gin.H{
			"error":             "invalid_request",
			"error_description": "Invalid request parameters",
		})
		return
	}

	// Validate client ID (basic validation)
	if req.ClientID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":             "invalid_request",
			"error_description": "client_id is required",
		})
		return
	}

	// Validate client ID against allowed wearable clients
	if !h.isWearableClient(req.ClientID) {
		h.logger.Warn("Invalid client for device flow",
			zap.String("client_id", req.ClientID),
			zap.String("client_ip", c.ClientIP()),
		)
		c.JSON(http.StatusUnauthorized, gin.H{
			"error":             "invalid_client",
			"error_description": "Client not authorized for device flow",
		})
		return
	}

	// Initiate device flow
	resp, err := h.deviceFlowManager.InitiateDeviceFlow(c.Request.Context(), &req)
	if err != nil {
		h.logger.Error("Failed to initiate device flow",
			zap.Error(err),
			zap.String("client_id", req.ClientID),
		)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":             "server_error",
			"error_description": "Failed to initiate device authorization",
		})
		return
	}

	h.logger.Info("Device authorization initiated",
		zap.String("client_id", req.ClientID),
		zap.String("user_code", resp.UserCode),
	)

	c.JSON(http.StatusOK, resp)
}

// TokenEndpoint handles device token requests (RFC 8628)
// POST /oauth/token
func (h *DeviceFlowHandler) TokenEndpoint(c *gin.Context) {
	var req auth.DeviceTokenRequest
	if err := c.ShouldBind(&req); err != nil {
		h.logger.Warn("Invalid token request",
			zap.Error(err),
			zap.String("client_ip", c.ClientIP()),
		)
		c.JSON(http.StatusBadRequest, gin.H{
			"error":             "invalid_request",
			"error_description": "Invalid request parameters",
		})
		return
	}

	// Validate required parameters
	if req.GrantType == "" || req.DeviceCode == "" || req.ClientID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":             "invalid_request",
			"error_description": "Missing required parameters",
		})
		return
	}

	// Poll for token
	resp, err := h.deviceFlowManager.PollForToken(c.Request.Context(), &req)
	if err != nil {
		h.logger.Error("Failed to poll for token",
			zap.Error(err),
			zap.String("client_id", req.ClientID),
		)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":             "server_error",
			"error_description": "Failed to process token request",
		})
		return
	}

	// Handle error responses with appropriate status codes
	if resp.Error != "" {
		statusCode := http.StatusBadRequest

		switch resp.Error {
		case auth.ErrorAuthorizationPending:
			statusCode = http.StatusBadRequest
		case auth.ErrorSlowDown:
			statusCode = http.StatusBadRequest
		case auth.ErrorExpiredToken:
			statusCode = http.StatusBadRequest
		case auth.ErrorAccessDenied:
			statusCode = http.StatusForbidden
		case auth.ErrorInvalidRequest:
			statusCode = http.StatusBadRequest
		case auth.ErrorInvalidClient:
			statusCode = http.StatusUnauthorized
		case auth.ErrorInvalidGrant:
			statusCode = http.StatusBadRequest
		}

		c.JSON(statusCode, gin.H{
			"error":             resp.Error,
			"error_description": resp.ErrorDescription,
		})
		return
	}

	// Success response
	c.JSON(http.StatusOK, gin.H{
		"access_token":  resp.AccessToken,
		"token_type":    resp.TokenType,
		"expires_in":    resp.ExpiresIn,
		"refresh_token": resp.RefreshToken,
		"scope":         resp.Scope,
	})
}

// UserCodeVerificationEndpoint handles user code verification page
// GET /device/verify
func (h *DeviceFlowHandler) UserCodeVerificationEndpoint(c *gin.Context) {
	userCode := c.Query("user_code")
	
	if userCode != "" && h.deviceFlowManager.ValidateUserCode(userCode) {
		// In a real implementation, this would render an HTML page
		// For now, we'll return JSON instructions
		c.JSON(http.StatusOK, gin.H{
			"message":   "Please confirm device authorization",
			"user_code": userCode,
			"next_step": "POST to /device/authorize with user_code and authentication",
		})
		return
	}

	// Render code input form (in JSON for now)
	c.JSON(http.StatusOK, gin.H{
		"message": "Enter your device code",
		"form":    "Please provide user_code parameter",
	})
}

// AuthorizeDeviceEndpoint handles device authorization confirmation
// POST /device/authorize
func (h *DeviceFlowHandler) AuthorizeDeviceEndpoint(c *gin.Context) {
	// This endpoint requires user authentication
	userCtx, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{
			"error":             "authentication_required",
			"error_description": "User must be authenticated to authorize device",
		})
		return
	}

	// Extract user ID from context
	var userID string
	if uctx, ok := userCtx.(*auth.UserContext); ok {
		userID = uctx.UserID
	} else if uid, ok := c.Get("user_id"); ok {
		if id, ok := uid.(string); ok {
			userID = id
		}
	}

	if userID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":             "invalid_user",
			"error_description": "Unable to identify user",
		})
		return
	}

	var req struct {
		UserCode string `json:"user_code" binding:"required"`
		Approve  bool   `json:"approve"`
	}

	if err := c.ShouldBind(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":             "invalid_request",
			"error_description": "Invalid request parameters",
		})
		return
	}

	// Validate user code format
	if !h.deviceFlowManager.ValidateUserCode(req.UserCode) {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":             "invalid_user_code",
			"error_description": "Invalid user code format",
		})
		return
	}

	// Check if approval was denied
	if !req.Approve {
		// TODO: Mark as denied in the device flow manager
		h.logger.Info("Device authorization denied",
			zap.String("user_code", req.UserCode),
			zap.String("user_id", userID),
		)
		
		c.JSON(http.StatusOK, gin.H{
			"message": "Device authorization denied",
			"status":  "denied",
		})
		return
	}

	// Get device authorization details
	authData, err := h.deviceFlowManager.GetDeviceAuthorization(c.Request.Context(), req.UserCode)
	if err != nil {
		h.logger.Warn("Failed to get device authorization",
			zap.Error(err),
			zap.String("user_code", req.UserCode),
			zap.String("user_id", userID),
		)
		
		c.JSON(http.StatusBadRequest, gin.H{
			"error":             "invalid_user_code",
			"error_description": "Invalid or expired user code",
		})
		return
	}

	// Authorize the device
	err = h.deviceFlowManager.AuthorizeDevice(c.Request.Context(), req.UserCode, userID)
	if err != nil {
		h.logger.Error("Failed to authorize device",
			zap.Error(err),
			zap.String("user_code", req.UserCode),
			zap.String("user_id", userID),
		)
		
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":             "authorization_failed",
			"error_description": "Failed to authorize device",
		})
		return
	}

	h.logger.Info("Device authorization approved",
		zap.String("user_code", req.UserCode),
		zap.String("user_id", userID),
		zap.String("client_id", authData.ClientID),
	)

	c.JSON(http.StatusOK, gin.H{
		"message":   "Device authorized successfully",
		"status":    "approved",
		"user_code": req.UserCode,
		"client_id": authData.ClientID,
	})
}

// DeviceStatusEndpoint returns device authorization status
// GET /device/status/:user_code
func (h *DeviceFlowHandler) DeviceStatusEndpoint(c *gin.Context) {
	userCode := c.Param("user_code")
	
	if !h.deviceFlowManager.ValidateUserCode(userCode) {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "invalid_user_code",
		})
		return
	}

	authData, err := h.deviceFlowManager.GetDeviceAuthorization(c.Request.Context(), userCode)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{
			"error": "user_code_not_found",
		})
		return
	}

	status := "pending"
	if authData.Authorized {
		status = "authorized"
	}

	c.JSON(http.StatusOK, gin.H{
		"user_code":   userCode,
		"status":      status,
		"client_id":   authData.ClientID,
		"created_at":  authData.CreatedAt,
		"expires_at":  authData.ExpiresAt,
	})
}

// isWearableClient checks if the client ID is authorized for device flow
func (h *DeviceFlowHandler) isWearableClient(clientID string) bool {
	// List of client IDs that are allowed to use device flow
	allowedClients := []string{
		"wearforce-wearables",
		"wearforce-watchos",
		"wearforce-wearos",
	}

	for _, allowed := range allowedClients {
		if clientID == allowed {
			return true
		}
	}

	return false
}

// RegisterDeviceFlowRoutes registers device flow routes with the router
func (h *DeviceFlowHandler) RegisterRoutes(router *gin.Engine) {
	// OAuth2 Device Flow endpoints
	oauth := router.Group("/oauth")
	{
		oauth.POST("/device_authorization", h.DeviceAuthorizationEndpoint)
		oauth.POST("/token", h.TokenEndpoint)
	}

	// Device authorization UI endpoints
	device := router.Group("/device")
	{
		device.GET("/verify", h.UserCodeVerificationEndpoint)
		device.POST("/authorize", h.AuthorizeDeviceEndpoint) // Requires authentication
		device.GET("/status/:user_code", h.DeviceStatusEndpoint)
	}
}

// DeviceFlowInfo returns information about device flow configuration
type DeviceFlowInfo struct {
	DeviceAuthorizationEndpoint string `json:"device_authorization_endpoint"`
	TokenEndpoint              string `json:"token_endpoint"`
	VerificationURI            string `json:"verification_uri"`
	SupportedGrantTypes        []string `json:"supported_grant_types"`
	SupportedClients           []string `json:"supported_clients"`
}

// GetDeviceFlowInfo returns device flow configuration information
// GET /.well-known/device_flow
func (h *DeviceFlowHandler) GetDeviceFlowInfo(c *gin.Context) {
	baseURL := getBaseURL(c)
	
	info := DeviceFlowInfo{
		DeviceAuthorizationEndpoint: baseURL + "/oauth/device_authorization",
		TokenEndpoint:              baseURL + "/oauth/token",
		VerificationURI:            baseURL + "/device/verify",
		SupportedGrantTypes: []string{
			"urn:ietf:params:oauth:grant-type:device_code",
		},
		SupportedClients: []string{
			"wearforce-wearables",
			"wearforce-watchos",
			"wearforce-wearos",
		},
	}

	c.JSON(http.StatusOK, info)
}

// getBaseURL extracts base URL from request
func getBaseURL(c *gin.Context) string {
	scheme := "http"
	if c.Request.TLS != nil || c.GetHeader("X-Forwarded-Proto") == "https" {
		scheme = "https"
	}
	
	host := c.Request.Host
	if forwardedHost := c.GetHeader("X-Forwarded-Host"); forwardedHost != "" {
		host = forwardedHost
	}
	
	return scheme + "://" + host
}