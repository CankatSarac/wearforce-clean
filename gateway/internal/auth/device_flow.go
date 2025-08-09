package auth

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/go-redis/redis/v8"
	"go.uber.org/zap"

	"github.com/wearforce/gateway/internal/config"
)

// DeviceFlowManager handles OAuth2 Device Code Flow
type DeviceFlowManager struct {
	config     *config.JWTConfig
	redis      *redis.Client
	logger     *zap.Logger
	httpClient *http.Client
}

// DeviceCodeRequest represents a device code request
type DeviceCodeRequest struct {
	ClientID string `json:"client_id" binding:"required"`
	Scope    string `json:"scope,omitempty"`
}

// DeviceCodeResponse represents the response to a device code request
type DeviceCodeResponse struct {
	DeviceCode              string `json:"device_code"`
	UserCode                string `json:"user_code"`
	VerificationURI         string `json:"verification_uri"`
	VerificationURIComplete string `json:"verification_uri_complete,omitempty"`
	ExpiresIn              int    `json:"expires_in"`
	Interval               int    `json:"interval"`
}

// DeviceTokenRequest represents a token request using device code
type DeviceTokenRequest struct {
	GrantType  string `json:"grant_type" binding:"required"`
	DeviceCode string `json:"device_code" binding:"required"`
	ClientID   string `json:"client_id" binding:"required"`
}

// DeviceTokenResponse represents the token response
type DeviceTokenResponse struct {
	AccessToken  string `json:"access_token,omitempty"`
	TokenType    string `json:"token_type,omitempty"`
	ExpiresIn    int    `json:"expires_in,omitempty"`
	RefreshToken string `json:"refresh_token,omitempty"`
	Scope        string `json:"scope,omitempty"`
	Error        string `json:"error,omitempty"`
	ErrorDescription string `json:"error_description,omitempty"`
}

// DeviceAuthorizationData represents stored device authorization data
type DeviceAuthorizationData struct {
	DeviceCode    string    `json:"device_code"`
	UserCode      string    `json:"user_code"`
	ClientID      string    `json:"client_id"`
	Scope         string    `json:"scope"`
	CreatedAt     time.Time `json:"created_at"`
	ExpiresAt     time.Time `json:"expires_at"`
	Authorized    bool      `json:"authorized"`
	UserID        string    `json:"user_id,omitempty"`
	AccessToken   string    `json:"access_token,omitempty"`
	RefreshToken  string    `json:"refresh_token,omitempty"`
	TokenExpiry   time.Time `json:"token_expiry,omitempty"`
	PollAttempts  int       `json:"poll_attempts"`
	LastPollTime  time.Time `json:"last_poll_time"`
}

const (
	// OAuth2 Device Flow error codes
	ErrorAuthorizationPending = "authorization_pending"
	ErrorSlowDown            = "slow_down"
	ErrorExpiredToken        = "expired_token"
	ErrorAccessDenied        = "access_denied"
	ErrorInvalidRequest      = "invalid_request"
	ErrorInvalidClient       = "invalid_client"
	ErrorInvalidGrant        = "invalid_grant"

	// Device flow configuration
	DefaultExpiresIn      = 1800 // 30 minutes
	DefaultInterval       = 5    // 5 seconds
	UserCodeLength        = 8
	DeviceCodeLength      = 32
	MaxPollAttempts       = 360  // 30 minutes with 5 second intervals
	SlowDownThreshold     = 10   // polls before slowing down
	SlowDownInterval      = 10   // slow down to 10 seconds
)

// NewDeviceFlowManager creates a new device flow manager
func NewDeviceFlowManager(config *config.JWTConfig, redis *redis.Client, logger *zap.Logger) *DeviceFlowManager {
	return &DeviceFlowManager{
		config: config,
		redis:  redis,
		logger: logger,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// InitiateDeviceFlow initiates the device authorization flow
func (dfm *DeviceFlowManager) InitiateDeviceFlow(ctx context.Context, req *DeviceCodeRequest) (*DeviceCodeResponse, error) {
	// Generate device code and user code
	deviceCode, err := dfm.generateDeviceCode()
	if err != nil {
		return nil, fmt.Errorf("failed to generate device code: %w", err)
	}

	userCode, err := dfm.generateUserCode()
	if err != nil {
		return nil, fmt.Errorf("failed to generate user code: %w", err)
	}

	// Create authorization data
	authData := &DeviceAuthorizationData{
		DeviceCode:   deviceCode,
		UserCode:     userCode,
		ClientID:     req.ClientID,
		Scope:        req.Scope,
		CreatedAt:    time.Now(),
		ExpiresAt:    time.Now().Add(time.Duration(DefaultExpiresIn) * time.Second),
		Authorized:   false,
		PollAttempts: 0,
	}

	// Store in Redis
	key := dfm.getDeviceCodeKey(deviceCode)
	userCodeKey := dfm.getUserCodeKey(userCode)

	authDataJSON, err := json.Marshal(authData)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal auth data: %w", err)
	}

	pipe := dfm.redis.Pipeline()
	pipe.Set(ctx, key, authDataJSON, time.Duration(DefaultExpiresIn)*time.Second)
	pipe.Set(ctx, userCodeKey, deviceCode, time.Duration(DefaultExpiresIn)*time.Second)
	
	_, err = pipe.Exec(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to store device authorization: %w", err)
	}

	dfm.logger.Info("Device flow initiated",
		zap.String("client_id", req.ClientID),
		zap.String("user_code", userCode),
		zap.String("device_code", deviceCode[:8]+"..."), // Log partial code for security
	)

	// Build verification URI
	verificationURI := fmt.Sprintf("%s/auth/realms/%s/device", 
		dfm.config.Keycloak.BaseURL,
		dfm.config.Keycloak.Realm)
	
	verificationURIComplete := fmt.Sprintf("%s?user_code=%s", verificationURI, userCode)

	return &DeviceCodeResponse{
		DeviceCode:              deviceCode,
		UserCode:                userCode,
		VerificationURI:         verificationURI,
		VerificationURIComplete: verificationURIComplete,
		ExpiresIn:              DefaultExpiresIn,
		Interval:               DefaultInterval,
	}, nil
}

// PollForToken polls for the access token using device code
func (dfm *DeviceFlowManager) PollForToken(ctx context.Context, req *DeviceTokenRequest) (*DeviceTokenResponse, error) {
	// Validate grant type
	if req.GrantType != "urn:ietf:params:oauth:grant-type:device_code" {
		return &DeviceTokenResponse{
			Error:            ErrorInvalidRequest,
			ErrorDescription: "invalid grant_type",
		}, nil
	}

	// Get authorization data
	key := dfm.getDeviceCodeKey(req.DeviceCode)
	authDataJSON, err := dfm.redis.Get(ctx, key).Result()
	if err == redis.Nil {
		return &DeviceTokenResponse{
			Error:            ErrorExpiredToken,
			ErrorDescription: "device_code has expired or is invalid",
		}, nil
	} else if err != nil {
		return nil, fmt.Errorf("failed to get device authorization: %w", err)
	}

	var authData DeviceAuthorizationData
	if err := json.Unmarshal([]byte(authDataJSON), &authData); err != nil {
		return nil, fmt.Errorf("failed to unmarshal auth data: %w", err)
	}

	// Validate client ID
	if authData.ClientID != req.ClientID {
		return &DeviceTokenResponse{
			Error:            ErrorInvalidClient,
			ErrorDescription: "client_id mismatch",
		}, nil
	}

	// Check if expired
	if time.Now().After(authData.ExpiresAt) {
		dfm.redis.Del(ctx, key)
		return &DeviceTokenResponse{
			Error:            ErrorExpiredToken,
			ErrorDescription: "device_code has expired",
		}, nil
	}

	// Update poll tracking
	authData.PollAttempts++
	authData.LastPollTime = time.Now()

	// Check for too frequent polling
	if authData.PollAttempts > 1 && time.Since(authData.LastPollTime) < time.Duration(DefaultInterval)*time.Second {
		return &DeviceTokenResponse{
			Error:            ErrorSlowDown,
			ErrorDescription: "polling too frequently",
		}, nil
	}

	// Implement slow down logic
	var interval int = DefaultInterval
	if authData.PollAttempts > SlowDownThreshold {
		interval = SlowDownInterval
	}

	// Check if authorization is pending
	if !authData.Authorized {
		// Update auth data with new poll count
		authDataJSON, _ := json.Marshal(authData)
		dfm.redis.Set(ctx, key, authDataJSON, time.Until(authData.ExpiresAt))

		return &DeviceTokenResponse{
			Error:            ErrorAuthorizationPending,
			ErrorDescription: "user has not completed authorization",
		}, nil
	}

	// Check if tokens are already available
	if authData.AccessToken != "" && time.Now().Before(authData.TokenExpiry) {
		dfm.logger.Info("Device flow token retrieved",
			zap.String("client_id", req.ClientID),
			zap.String("user_code", authData.UserCode),
			zap.String("user_id", authData.UserID),
		)

		return &DeviceTokenResponse{
			AccessToken:  authData.AccessToken,
			TokenType:    "Bearer",
			ExpiresIn:    int(time.Until(authData.TokenExpiry).Seconds()),
			RefreshToken: authData.RefreshToken,
			Scope:        authData.Scope,
		}, nil
	}

	// Exchange with Keycloak
	token, err := dfm.exchangeWithKeycloak(ctx, &authData)
	if err != nil {
		dfm.logger.Error("Failed to exchange with Keycloak",
			zap.Error(err),
			zap.String("client_id", req.ClientID),
		)
		return &DeviceTokenResponse{
			Error:            ErrorInvalidGrant,
			ErrorDescription: "failed to obtain access token",
		}, nil
	}

	// Store tokens in auth data
	authData.AccessToken = token.AccessToken
	authData.RefreshToken = token.RefreshToken
	authData.TokenExpiry = time.Now().Add(time.Duration(token.ExpiresIn) * time.Second)

	// Update stored data
	authDataJSON, _ = json.Marshal(authData)
	dfm.redis.Set(ctx, key, authDataJSON, time.Until(authData.ExpiresAt))

	dfm.logger.Info("Device flow completed successfully",
		zap.String("client_id", req.ClientID),
		zap.String("user_code", authData.UserCode),
		zap.String("user_id", authData.UserID),
	)

	return &DeviceTokenResponse{
		AccessToken:  token.AccessToken,
		TokenType:    "Bearer",
		ExpiresIn:    token.ExpiresIn,
		RefreshToken: token.RefreshToken,
		Scope:        token.Scope,
	}, nil
}

// AuthorizeDevice authorizes a device using user code
func (dfm *DeviceFlowManager) AuthorizeDevice(ctx context.Context, userCode, userID string) error {
	// Get device code from user code
	userCodeKey := dfm.getUserCodeKey(userCode)
	deviceCode, err := dfm.redis.Get(ctx, userCodeKey).Result()
	if err == redis.Nil {
		return fmt.Errorf("invalid or expired user code")
	} else if err != nil {
		return fmt.Errorf("failed to get device code: %w", err)
	}

	// Get authorization data
	key := dfm.getDeviceCodeKey(deviceCode)
	authDataJSON, err := dfm.redis.Get(ctx, key).Result()
	if err != nil {
		return fmt.Errorf("failed to get device authorization: %w", err)
	}

	var authData DeviceAuthorizationData
	if err := json.Unmarshal([]byte(authDataJSON), &authData); err != nil {
		return fmt.Errorf("failed to unmarshal auth data: %w", err)
	}

	// Check if expired
	if time.Now().After(authData.ExpiresAt) {
		dfm.redis.Del(ctx, key)
		dfm.redis.Del(ctx, userCodeKey)
		return fmt.Errorf("device authorization has expired")
	}

	// Mark as authorized
	authData.Authorized = true
	authData.UserID = userID

	// Update stored data
	authDataJSON, err = json.Marshal(authData)
	if err != nil {
		return fmt.Errorf("failed to marshal auth data: %w", err)
	}

	err = dfm.redis.Set(ctx, key, authDataJSON, time.Until(authData.ExpiresAt)).Err()
	if err != nil {
		return fmt.Errorf("failed to update device authorization: %w", err)
	}

	dfm.logger.Info("Device authorized",
		zap.String("user_code", userCode),
		zap.String("user_id", userID),
		zap.String("client_id", authData.ClientID),
	)

	return nil
}

// exchangeWithKeycloak exchanges the authorization for tokens with Keycloak
func (dfm *DeviceFlowManager) exchangeWithKeycloak(ctx context.Context, authData *DeviceAuthorizationData) (*DeviceTokenResponse, error) {
	// This would be the actual exchange with Keycloak
	// For now, we'll simulate a successful exchange
	// In a real implementation, you would make a request to Keycloak's token endpoint

	tokenURL := fmt.Sprintf("%s/auth/realms/%s/protocol/openid_connect/token",
		dfm.config.Keycloak.BaseURL,
		dfm.config.Keycloak.Realm)

	// Prepare request data
	data := url.Values{
		"grant_type":   {"urn:ietf:params:oauth:grant-type:device_code"},
		"device_code":  {authData.DeviceCode},
		"client_id":    {authData.ClientID},
	}

	// Add client secret if available
	if dfm.config.Keycloak.ClientSecret != "" {
		data.Set("client_secret", dfm.config.Keycloak.ClientSecret)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", tokenURL, bytes.NewBufferString(data.Encode()))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")

	resp, err := dfm.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to make request: %w", err)
	}
	defer resp.Body.Close()

	var tokenResp DeviceTokenResponse
	if err := json.NewDecoder(resp.Body).Decode(&tokenResp); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("token exchange failed: %s", tokenResp.Error)
	}

	return &tokenResp, nil
}

// generateDeviceCode generates a secure device code
func (dfm *DeviceFlowManager) generateDeviceCode() (string, error) {
	bytes := make([]byte, DeviceCodeLength)
	_, err := rand.Read(bytes)
	if err != nil {
		return "", err
	}
	return hex.EncodeToString(bytes), nil
}

// generateUserCode generates a human-readable user code
func (dfm *DeviceFlowManager) generateUserCode() (string, error) {
	// Use alphanumeric characters excluding similar looking ones
	charset := "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
	bytes := make([]byte, UserCodeLength)
	_, err := rand.Read(bytes)
	if err != nil {
		return "", err
	}

	userCode := make([]byte, UserCodeLength)
	for i := range bytes {
		userCode[i] = charset[int(bytes[i])%len(charset)]
	}

	// Format as XXXX-XXXX
	if UserCodeLength == 8 {
		return fmt.Sprintf("%s-%s", string(userCode[:4]), string(userCode[4:])), nil
	}

	return string(userCode), nil
}

// getDeviceCodeKey returns Redis key for device code
func (dfm *DeviceFlowManager) getDeviceCodeKey(deviceCode string) string {
	return fmt.Sprintf("device_flow:device_code:%s", deviceCode)
}

// getUserCodeKey returns Redis key for user code
func (dfm *DeviceFlowManager) getUserCodeKey(userCode string) string {
	return fmt.Sprintf("device_flow:user_code:%s", userCode)
}

// ValidateUserCode validates a user code format
func (dfm *DeviceFlowManager) ValidateUserCode(userCode string) bool {
	// Remove any dashes
	cleanCode := strings.ReplaceAll(userCode, "-", "")
	
	// Check length
	if len(cleanCode) != UserCodeLength {
		return false
	}

	// Check characters (alphanumeric, no similar looking characters)
	for _, char := range cleanCode {
		if !strings.ContainsRune("ABCDEFGHJKMNPQRSTUVWXYZ23456789", char) {
			return false
		}
	}

	return true
}

// GetDeviceAuthorization retrieves device authorization data
func (dfm *DeviceFlowManager) GetDeviceAuthorization(ctx context.Context, userCode string) (*DeviceAuthorizationData, error) {
	userCodeKey := dfm.getUserCodeKey(userCode)
	deviceCode, err := dfm.redis.Get(ctx, userCodeKey).Result()
	if err == redis.Nil {
		return nil, fmt.Errorf("invalid or expired user code")
	} else if err != nil {
		return nil, fmt.Errorf("failed to get device code: %w", err)
	}

	key := dfm.getDeviceCodeKey(deviceCode)
	authDataJSON, err := dfm.redis.Get(ctx, key).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to get device authorization: %w", err)
	}

	var authData DeviceAuthorizationData
	if err := json.Unmarshal([]byte(authDataJSON), &authData); err != nil {
		return nil, fmt.Errorf("failed to unmarshal auth data: %w", err)
	}

	return &authData, nil
}

// CleanupExpiredCodes removes expired device codes
func (dfm *DeviceFlowManager) CleanupExpiredCodes(ctx context.Context) error {
	// Redis will automatically expire the keys, but this could be used
	// for additional cleanup if needed
	return nil
}