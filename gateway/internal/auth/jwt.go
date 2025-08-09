package auth

import (
	"context"
	"crypto/rsa"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"regexp"
	"strings"
	"sync"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/lestrrat-go/jwx/v2/jwk"
	jwxjwt "github.com/lestrrat-go/jwx/v2/jwt"
	"go.uber.org/zap"

	"github.com/wearforce/gateway/internal/config"
)

// JWTValidator handles JWT token validation with Keycloak integration
type JWTValidator struct {
	config     *config.JWTConfig
	logger     *zap.Logger
	httpClient *http.Client
	keySet     jwk.Set
	keyCache   sync.Map
	mu         sync.RWMutex
	lastUpdate time.Time
}

// Claims represents JWT claims structure
type Claims struct {
	Sub               string                 `json:"sub"`
	Iss               string                 `json:"iss"`
	Aud               interface{}            `json:"aud"`
	Exp               int64                  `json:"exp"`
	Iat               int64                  `json:"iat"`
	AuthTime          int64                  `json:"auth_time"`
	Jti               string                 `json:"jti"`
	Email             string                 `json:"email"`
	EmailVerified     bool                   `json:"email_verified"`
	Name              string                 `json:"name"`
	PreferredUsername string                 `json:"preferred_username"`
	GivenName         string                 `json:"given_name"`
	FamilyName        string                 `json:"family_name"`
	RealmAccess       *RealmAccess           `json:"realm_access"`
	ResourceAccess    map[string]*ClientRole `json:"resource_access"`
	Groups            []string               `json:"groups"`
	Roles             []string               `json:"roles"`
	CustomClaims      map[string]interface{} `json:"-"`
	jwt.RegisteredClaims
}

// RealmAccess represents realm-level access information
type RealmAccess struct {
	Roles []string `json:"roles"`
}

// ClientRole represents client-specific role information
type ClientRole struct {
	Roles []string `json:"roles"`
}


// UserContext represents authenticated user context
type UserContext struct {
	UserID            string
	Email             string
	Name              string
	PreferredUsername string
	Roles             []string
	Groups            []string
	ClientRoles       map[string][]string
	Claims            *Claims
}

// NewJWTValidator creates a new JWT validator
func NewJWTValidator(config *config.JWTConfig, logger *zap.Logger) *JWTValidator {
	return &JWTValidator{
		config: config,
		logger: logger,
		httpClient: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

// ValidateToken validates a JWT token and returns user context
func (v *JWTValidator) ValidateToken(tokenString string) (*UserContext, error) {
	// Input validation
	if tokenString == "" {
		return nil, errors.New("empty token")
	}

	// Remove "Bearer " prefix if present
	if strings.HasPrefix(tokenString, "Bearer ") {
		tokenString = strings.TrimPrefix(tokenString, "Bearer ")
	}

	// Additional token length validation to prevent DoS
	if len(tokenString) > 8192 {
		return nil, errors.New("token too long")
	}

	// Validate token format (basic JWT structure check)
	parts := strings.Split(tokenString, ".")
	if len(parts) != 3 {
		return nil, errors.New("invalid token format")
	}

	// Refresh JWKS if needed
	if err := v.refreshJWKS(); err != nil {
		v.logger.Error("Failed to refresh JWKS", zap.Error(err))
		return nil, fmt.Errorf("authentication service unavailable")
	}

	// Ensure we have keys available
	v.mu.RLock()
	keySet := v.keySet
	v.mu.RUnlock()

	if keySet == nil {
		return nil, errors.New("authentication service unavailable")
	}

	// Parse and validate token using JWX with stricter validation
	token, err := jwxjwt.ParseString(tokenString, 
		jwxjwt.WithKeySet(keySet),
		jwxjwt.WithValidate(true),
		jwxjwt.WithIssuer(v.config.Issuer),
		jwxjwt.WithAudience(v.config.Audience),
		jwxjwt.WithClock(jwxjwt.ClockFunc(time.Now)),
		jwxjwt.WithAcceptableSkew(5*time.Second), // Allow 5 second clock skew
	)
	if err != nil {
		v.logger.Warn("Token validation failed", zap.Error(err))
		return nil, errors.New("invalid token")
	}

	// Extract claims into our custom structure
	claims := &Claims{}
	claimsMap, err := token.AsMap(context.Background())
	if err != nil {
		return nil, errors.New("failed to extract claims")
	}

	claimsJSON, err := json.Marshal(claimsMap)
	if err != nil {
		return nil, errors.New("failed to process claims")
	}

	if err := json.Unmarshal(claimsJSON, claims); err != nil {
		return nil, errors.New("failed to process token claims")
	}

	// Additional security validations
	if claims.Sub == "" {
		return nil, errors.New("invalid token: missing subject")
	}

	if time.Unix(claims.Exp, 0).Before(time.Now()) {
		return nil, errors.New("token expired")
	}

	// Validate issued at time is not in the future
	if time.Unix(claims.Iat, 0).After(time.Now().Add(5*time.Second)) {
		return nil, errors.New("token issued in the future")
	}

	// Create user context with input sanitization
	userCtx := &UserContext{
		UserID:            strings.TrimSpace(claims.Sub),
		Email:             strings.TrimSpace(claims.Email),
		Name:              strings.TrimSpace(claims.Name),
		PreferredUsername: strings.TrimSpace(claims.PreferredUsername),
		Claims:            claims,
	}

	// Validate email format if present
	if userCtx.Email != "" && !isValidEmail(userCtx.Email) {
		return nil, errors.New("invalid email format in token")
	}

	// Extract roles with validation
	if claims.RealmAccess != nil {
		userCtx.Roles = sanitizeRoles(claims.RealmAccess.Roles)
	}

	// Extract groups with validation
	userCtx.Groups = sanitizeRoles(claims.Groups)

	// Extract client roles with validation
	userCtx.ClientRoles = make(map[string][]string)
	for client, roles := range claims.ResourceAccess {
		if roles != nil && isValidClientName(client) {
			userCtx.ClientRoles[client] = sanitizeRoles(roles.Roles)
		}
	}

	v.logger.Debug("Token validated successfully",
		zap.String("user_id", userCtx.UserID),
		zap.String("email", userCtx.Email),
		zap.Strings("roles", userCtx.Roles),
		zap.Int("client_roles", len(userCtx.ClientRoles)),
	)

	return userCtx, nil
}

// ValidateTokenWithOPA validates a JWT token and integrates with OPA for authorization
func (v *JWTValidator) ValidateTokenWithOPA(tokenString, method, path string, headers map[string]string) (*UserContext, bool, error) {
	// First validate the token
	userCtx, err := v.ValidateToken(tokenString)
	if err != nil {
		return nil, false, err
	}

	// TODO: Integrate with OPA for authorization decision
	// This would make a call to OPA with the user context and request details
	// For now, we'll implement basic authorization
	authorized := v.basicAuthz(userCtx, method, path)

	return userCtx, authorized, nil
}

// basicAuthz provides basic authorization logic (to be replaced by OPA)
func (v *JWTValidator) basicAuthz(userCtx *UserContext, method, path string) bool {
	// Super admin has access to everything
	if userCtx.HasRole("super_admin") {
		return true
	}

	// Admin has access to most things except super admin endpoints
	if userCtx.HasRole("admin") && !strings.Contains(path, "/super-admin") {
		return true
	}

	// Public endpoints
	publicPaths := []string{"/health", "/metrics", "/ping", "/docs", "/swagger"}
	for _, publicPath := range publicPaths {
		if strings.HasPrefix(path, publicPath) {
			return true
		}
	}

	// Basic role-based access
	if method == "GET" {
		return len(userCtx.Roles) > 0 // Any authenticated user can read
	}

	if method == "POST" || method == "PUT" {
		writeRoles := []string{"admin", "sales_manager", "inventory_manager", "crm_admin", "erp_admin"}
		for _, role := range writeRoles {
			if userCtx.HasRole(role) {
				return true
			}
		}
	}

	if method == "DELETE" {
		deleteRoles := []string{"admin", "crm_admin", "erp_admin"}
		for _, role := range deleteRoles {
			if userCtx.HasRole(role) {
				return true
			}
		}
	}

	return false
}

// refreshJWKS fetches and caches the JWKS from Keycloak
func (v *JWTValidator) refreshJWKS() error {
	// First, check with read lock if we need refresh
	v.mu.RLock()
	needsRefresh := time.Since(v.lastUpdate) >= v.config.Keycloak.CacheTimeout || v.keySet == nil
	v.mu.RUnlock()

	if !needsRefresh {
		return nil
	}

	// Need to refresh, acquire write lock
	v.mu.Lock()
	defer v.mu.Unlock()

	// Double-check in case another goroutine updated while we waited for lock
	if time.Since(v.lastUpdate) < v.config.Keycloak.CacheTimeout && v.keySet != nil {
		return nil
	}

	jwksURL := v.buildJWKSURL()
	v.logger.Debug("Refreshing JWKS", zap.String("url", jwksURL))

	// Create context with timeout for JWKS fetch
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	keySet, err := jwk.Fetch(ctx, jwksURL, 
		jwk.WithHTTPClient(v.httpClient),
		jwk.WithRefreshInterval(v.config.Keycloak.CacheTimeout),
	)
	if err != nil {
		v.logger.Error("Failed to fetch JWKS", zap.Error(err), zap.String("url", jwksURL))
		return fmt.Errorf("failed to fetch JWKS: %w", err)
	}

	// Validate that we have at least one key
	if keySet.Len() == 0 {
		return errors.New("JWKS contains no keys")
	}

	v.keySet = keySet
	v.lastUpdate = time.Now()

	v.logger.Debug("JWKS refreshed successfully", 
		zap.Int("key_count", keySet.Len()),
		zap.Time("updated_at", v.lastUpdate),
	)

	return nil
}

// buildJWKSURL builds the JWKS URL from configuration
func (v *JWTValidator) buildJWKSURL() string {
	jwksPath := strings.ReplaceAll(v.config.Keycloak.JWKSPath, "{realm}", v.config.Keycloak.Realm)
	return v.config.Keycloak.BaseURL + jwksPath
}

// validateAudience validates JWT audience claim
func (v *JWTValidator) validateAudience(aud interface{}, expectedAud string) bool {
	if expectedAud == "" {
		return true // No audience validation required
	}

	switch a := aud.(type) {
	case string:
		return a == expectedAud
	case []interface{}:
		for _, audience := range a {
			if str, ok := audience.(string); ok && str == expectedAud {
				return true
			}
		}
	case []string:
		for _, audience := range a {
			if audience == expectedAud {
				return true
			}
		}
	}

	return false
}

// HasRole checks if user has a specific realm role
func (uc *UserContext) HasRole(role string) bool {
	for _, r := range uc.Roles {
		if r == role {
			return true
		}
	}
	return false
}

// HasClientRole checks if user has a specific client role
func (uc *UserContext) HasClientRole(client, role string) bool {
	if roles, ok := uc.ClientRoles[client]; ok {
		for _, r := range roles {
			if r == role {
				return true
			}
		}
	}
	return false
}

// InGroup checks if user is in a specific group
func (uc *UserContext) InGroup(group string) bool {
	for _, g := range uc.Groups {
		if g == group {
			return true
		}
	}
	return false
}

// ClearKeyCache clears the public key cache
func (v *JWTValidator) ClearKeyCache() {
	v.mu.Lock()
	defer v.mu.Unlock()
	
	v.keySet = nil
	v.lastUpdate = time.Time{}
	v.logger.Info("JWT key cache cleared")
}

// RefreshKeys forces a refresh of public keys
func (v *JWTValidator) RefreshKeys() error {
	v.ClearKeyCache()
	return v.refreshJWKS()
}

// GetUserContextFromContext extracts user context from request context
func GetUserContextFromContext(ctx context.Context) (*UserContext, bool) {
	userCtx, ok := ctx.Value("user").(*UserContext)
	return userCtx, ok
}

// Regular expressions for validation
var (
	emailRegex      = regexp.MustCompile(`^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`)
	roleRegex       = regexp.MustCompile(`^[a-zA-Z0-9_-]{1,64}$`)
	clientNameRegex = regexp.MustCompile(`^[a-zA-Z0-9_-]{1,128}$`)
)

// isValidEmail validates email format
func isValidEmail(email string) bool {
	if len(email) > 254 {
		return false
	}
	return emailRegex.MatchString(email)
}

// sanitizeRoles validates and sanitizes role names
func sanitizeRoles(roles []string) []string {
	var sanitized []string
	for _, role := range roles {
		role = strings.TrimSpace(role)
		if role != "" && len(role) <= 64 && roleRegex.MatchString(role) {
			sanitized = append(sanitized, role)
		}
	}
	return sanitized
}

// isValidClientName validates client name format
func isValidClientName(clientName string) bool {
	return len(clientName) <= 128 && clientNameRegex.MatchString(clientName)
}