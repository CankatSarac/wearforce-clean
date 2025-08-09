package middleware

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"go.uber.org/zap"

	"github.com/wearforce/gateway/internal/auth"
	"github.com/wearforce/gateway/internal/config"
)

// MockJWTValidator is a mock JWT validator for testing
type MockJWTValidator struct {
	mock.Mock
}

func (m *MockJWTValidator) ValidateToken(tokenString string) (*auth.UserContext, error) {
	args := m.Called(tokenString)
	return args.Get(0).(*auth.UserContext), args.Error(1)
}

func (m *MockJWTValidator) ClearKeyCache() {
	m.Called()
}

func (m *MockJWTValidator) RefreshKeys() error {
	args := m.Called()
	return args.Error(0)
}

func TestAuthMiddleware(t *testing.T) {
	tests := []struct {
		name           string
		path           string
		authHeader     string
		mockSetup      func(*MockJWTValidator)
		expectedStatus int
		expectedBody   string
	}{
		{
			name:           "Public path should skip auth",
			path:           "/health",
			authHeader:     "",
			mockSetup:      func(m *MockJWTValidator) {},
			expectedStatus: http.StatusOK,
			expectedBody:   "OK",
		},
		{
			name:           "Missing auth header",
			path:           "/api/test",
			authHeader:     "",
			mockSetup:      func(m *MockJWTValidator) {},
			expectedStatus: http.StatusUnauthorized,
			expectedBody:   "Authorization header required",
		},
		{
			name:       "Valid token",
			path:       "/api/test",
			authHeader: "Bearer valid-token",
			mockSetup: func(m *MockJWTValidator) {
				m.On("ValidateToken", "Bearer valid-token").Return(&auth.UserContext{
					UserID: "user123",
					Email:  "test@example.com",
					Roles:  []string{"user"},
				}, nil)
			},
			expectedStatus: http.StatusOK,
			expectedBody:   "OK",
		},
		{
			name:       "Invalid token",
			path:       "/api/test",
			authHeader: "Bearer invalid-token",
			mockSetup: func(m *MockJWTValidator) {
				m.On("ValidateToken", "Bearer invalid-token").Return((*auth.UserContext)(nil), assert.AnError)
			},
			expectedStatus: http.StatusUnauthorized,
			expectedBody:   "Invalid or expired token",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Setup
			gin.SetMode(gin.TestMode)
			mockValidator := new(MockJWTValidator)
			tt.mockSetup(mockValidator)

			logger := zap.NewNop()
			
			// Create test server
			router := gin.New()
			router.Use(AuthMiddleware(mockValidator, logger))
			
			router.GET("/health", func(c *gin.Context) {
				c.String(http.StatusOK, "OK")
			})
			
			router.GET("/api/test", func(c *gin.Context) {
				c.String(http.StatusOK, "OK")
			})

			// Create request
			req, _ := http.NewRequest("GET", tt.path, nil)
			if tt.authHeader != "" {
				req.Header.Set("Authorization", tt.authHeader)
			}

			// Record response
			w := httptest.NewRecorder()
			router.ServeHTTP(w, req)

			// Assert
			assert.Equal(t, tt.expectedStatus, w.Code)
			if tt.expectedBody != "" {
				assert.Contains(t, w.Body.String(), tt.expectedBody)
			}

			mockValidator.AssertExpectations(t)
		})
	}
}

func TestRequireRole(t *testing.T) {
	tests := []struct {
		name           string
		userRoles      []string
		requiredRoles  []string
		expectedStatus int
	}{
		{
			name:           "User has required role",
			userRoles:      []string{"admin", "user"},
			requiredRoles:  []string{"admin"},
			expectedStatus: http.StatusOK,
		},
		{
			name:           "User has one of multiple required roles",
			userRoles:      []string{"user", "manager"},
			requiredRoles:  []string{"admin", "manager"},
			expectedStatus: http.StatusOK,
		},
		{
			name:           "User doesn't have required role",
			userRoles:      []string{"user"},
			requiredRoles:  []string{"admin"},
			expectedStatus: http.StatusForbidden,
		},
		{
			name:           "User has no roles",
			userRoles:      []string{},
			requiredRoles:  []string{"admin"},
			expectedStatus: http.StatusForbidden,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			gin.SetMode(gin.TestMode)
			
			router := gin.New()
			router.Use(RequireRole(tt.requiredRoles...))
			
			router.GET("/test", func(c *gin.Context) {
				// Mock user context
				user := &auth.UserContext{
					UserID: "user123",
					Roles:  tt.userRoles,
				}
				c.Set("user", user)
				c.String(http.StatusOK, "OK")
			})

			req, _ := http.NewRequest("GET", "/test", nil)
			w := httptest.NewRecorder()

			// Add user to context before the middleware runs
			router.Use(func(c *gin.Context) {
				user := &auth.UserContext{
					UserID: "user123",
					Roles:  tt.userRoles,
				}
				c.Set("user", user)
				c.Next()
			})

			router.ServeHTTP(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)
		})
	}
}

func BenchmarkAuthMiddleware(b *testing.B) {
	gin.SetMode(gin.TestMode)
	
	mockValidator := new(MockJWTValidator)
	mockValidator.On("ValidateToken", "Bearer valid-token").Return(&auth.UserContext{
		UserID: "user123",
		Email:  "test@example.com",
		Roles:  []string{"user"},
	}, nil)

	logger := zap.NewNop()
	
	router := gin.New()
	router.Use(AuthMiddleware(mockValidator, logger))
	router.GET("/test", func(c *gin.Context) {
		c.String(http.StatusOK, "OK")
	})

	req, _ := http.NewRequest("GET", "/test", nil)
	req.Header.Set("Authorization", "Bearer valid-token")

	b.ResetTimer()
	
	for i := 0; i < b.N; i++ {
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
	}
}