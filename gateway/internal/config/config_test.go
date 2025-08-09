package config

import (
	"os"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestLoad(t *testing.T) {
	tests := []struct {
		name     string
		envVars  map[string]string
		validate func(*testing.T, *Config)
	}{
		{
			name: "Default configuration",
			envVars: map[string]string{
				"GATEWAY_JWT_KEYCLOAK_BASE_URL": "http://localhost:8080",
				"GATEWAY_JWT_KEYCLOAK_REALM":    "test-realm",
			},
			validate: func(t *testing.T, cfg *Config) {
				assert.Equal(t, "0.0.0.0", cfg.Server.Host)
				assert.Equal(t, 8080, cfg.Server.HTTPPort)
				assert.Equal(t, 8081, cfg.Server.GRPCPort)
				assert.Equal(t, 30*time.Second, cfg.Server.ReadTimeout)
				assert.Equal(t, "localhost:6379", cfg.Redis.Address)
				assert.True(t, cfg.RateLimit.Enabled)
				assert.True(t, cfg.Metrics.Enabled)
			},
		},
		{
			name: "Environment variable override",
			envVars: map[string]string{
				"GATEWAY_SERVER_HTTP_PORT":      "9000",
				"GATEWAY_SERVER_GRPC_PORT":      "9001",
				"GATEWAY_REDIS_ADDRESS":         "redis:6379",
				"GATEWAY_JWT_KEYCLOAK_BASE_URL": "http://localhost:8080",
				"GATEWAY_JWT_KEYCLOAK_REALM":    "test-realm",
			},
			validate: func(t *testing.T, cfg *Config) {
				assert.Equal(t, 9000, cfg.Server.HTTPPort)
				assert.Equal(t, 9001, cfg.Server.GRPCPort)
				assert.Equal(t, "redis:6379", cfg.Redis.Address)
			},
		},
		{
			name: "TLS configuration",
			envVars: map[string]string{
				"GATEWAY_TLS_ENABLED":                    "true",
				"GATEWAY_TLS_LETS_ENCRYPT_ENABLED":       "true",
				"GATEWAY_TLS_LETS_ENCRYPT_DOMAINS":       "example.com,www.example.com",
				"GATEWAY_TLS_LETS_ENCRYPT_EMAIL":         "admin@example.com",
				"GATEWAY_JWT_KEYCLOAK_BASE_URL":          "http://localhost:8080",
				"GATEWAY_JWT_KEYCLOAK_REALM":             "test-realm",
			},
			validate: func(t *testing.T, cfg *Config) {
				assert.True(t, cfg.TLS.Enabled)
				assert.True(t, cfg.TLS.LetsEncrypt.Enabled)
				assert.Equal(t, "admin@example.com", cfg.TLS.LetsEncrypt.Email)
				assert.Contains(t, cfg.TLS.LetsEncrypt.Domains, "example.com")
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Set environment variables
			for key, value := range tt.envVars {
				os.Setenv(key, value)
			}

			// Clean up after test
			defer func() {
				for key := range tt.envVars {
					os.Unsetenv(key)
				}
			}()

			cfg, err := Load()
			require.NoError(t, err)
			require.NotNil(t, cfg)

			tt.validate(t, cfg)
		})
	}
}

func TestConfigValidation(t *testing.T) {
	tests := []struct {
		name      string
		config    *Config
		expectErr bool
		errMsg    string
	}{
		{
			name: "Valid configuration",
			config: &Config{
				Server: ServerConfig{
					HTTPPort: 8080,
					GRPCPort: 8081,
				},
				JWT: JWTConfig{
					Keycloak: KeycloakConfig{
						BaseURL: "http://localhost:8080",
						Realm:   "test-realm",
					},
				},
			},
			expectErr: false,
		},
		{
			name: "Invalid HTTP port",
			config: &Config{
				Server: ServerConfig{
					HTTPPort: 0,
					GRPCPort: 8081,
				},
				JWT: JWTConfig{
					Keycloak: KeycloakConfig{
						BaseURL: "http://localhost:8080",
						Realm:   "test-realm",
					},
				},
			},
			expectErr: true,
			errMsg:    "invalid HTTP port",
		},
		{
			name: "Invalid gRPC port",
			config: &Config{
				Server: ServerConfig{
					HTTPPort: 8080,
					GRPCPort: 70000,
				},
				JWT: JWTConfig{
					Keycloak: KeycloakConfig{
						BaseURL: "http://localhost:8080",
						Realm:   "test-realm",
					},
				},
			},
			expectErr: true,
			errMsg:    "invalid gRPC port",
		},
		{
			name: "TLS enabled without Let's Encrypt or cert files",
			config: &Config{
				Server: ServerConfig{
					HTTPPort: 8080,
					GRPCPort: 8081,
				},
				TLS: TLSConfig{
					Enabled: true,
					LetsEncrypt: LEConfig{
						Enabled: false,
					},
				},
				JWT: JWTConfig{
					Keycloak: KeycloakConfig{
						BaseURL: "http://localhost:8080",
						Realm:   "test-realm",
					},
				},
			},
			expectErr: true,
			errMsg:    "cert/key files not specified",
		},
		{
			name: "Let's Encrypt enabled without domains",
			config: &Config{
				Server: ServerConfig{
					HTTPPort: 8080,
					GRPCPort: 8081,
				},
				TLS: TLSConfig{
					Enabled: true,
					LetsEncrypt: LEConfig{
						Enabled: true,
						Email:   "admin@example.com",
					},
				},
				JWT: JWTConfig{
					Keycloak: KeycloakConfig{
						BaseURL: "http://localhost:8080",
						Realm:   "test-realm",
					},
				},
			},
			expectErr: true,
			errMsg:    "no domains specified",
		},
		{
			name: "Missing Keycloak base URL",
			config: &Config{
				Server: ServerConfig{
					HTTPPort: 8080,
					GRPCPort: 8081,
				},
				JWT: JWTConfig{
					Keycloak: KeycloakConfig{
						Realm: "test-realm",
					},
				},
			},
			expectErr: true,
			errMsg:    "Keycloak base URL not specified",
		},
		{
			name: "Missing Keycloak realm",
			config: &Config{
				Server: ServerConfig{
					HTTPPort: 8080,
					GRPCPort: 8081,
				},
				JWT: JWTConfig{
					Keycloak: KeycloakConfig{
						BaseURL: "http://localhost:8080",
					},
				},
			},
			expectErr: true,
			errMsg:    "Keycloak realm not specified",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.config.Validate()
			
			if tt.expectErr {
				assert.Error(t, err)
				if tt.errMsg != "" {
					assert.Contains(t, err.Error(), tt.errMsg)
				}
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

func TestDefaultValues(t *testing.T) {
	// Set minimum required env vars
	os.Setenv("GATEWAY_JWT_KEYCLOAK_BASE_URL", "http://localhost:8080")
	os.Setenv("GATEWAY_JWT_KEYCLOAK_REALM", "test-realm")
	
	defer func() {
		os.Unsetenv("GATEWAY_JWT_KEYCLOAK_BASE_URL")
		os.Unsetenv("GATEWAY_JWT_KEYCLOAK_REALM")
	}()

	cfg, err := Load()
	require.NoError(t, err)

	// Test server defaults
	assert.Equal(t, "0.0.0.0", cfg.Server.Host)
	assert.Equal(t, 8080, cfg.Server.HTTPPort)
	assert.Equal(t, 8081, cfg.Server.GRPCPort)
	assert.Equal(t, 30*time.Second, cfg.Server.ReadTimeout)
	assert.Equal(t, 30*time.Second, cfg.Server.WriteTimeout)
	assert.Equal(t, 120*time.Second, cfg.Server.IdleTimeout)
	assert.Equal(t, 10*time.Second, cfg.Server.ShutdownTimeout)

	// Test TLS defaults
	assert.False(t, cfg.TLS.Enabled)
	assert.Equal(t, "1.2", cfg.TLS.MinTLSVersion)
	assert.False(t, cfg.TLS.LetsEncrypt.Enabled)
	assert.True(t, cfg.TLS.LetsEncrypt.Staging)

	// Test Redis defaults
	assert.Equal(t, "localhost:6379", cfg.Redis.Address)
	assert.Equal(t, 0, cfg.Redis.DB)
	assert.Equal(t, 10, cfg.Redis.PoolSize)
	assert.Equal(t, 3, cfg.Redis.MaxRetries)

	// Test rate limit defaults
	assert.True(t, cfg.RateLimit.Enabled)

	// Test metrics defaults
	assert.True(t, cfg.Metrics.Enabled)
	assert.Equal(t, "/metrics", cfg.Metrics.Path)
	assert.Equal(t, 9090, cfg.Metrics.Port)

	// Test WebSocket defaults
	assert.Equal(t, 1024, cfg.WebSocket.ReadBufferSize)
	assert.Equal(t, 1024, cfg.WebSocket.WriteBufferSize)
	assert.Equal(t, 10*time.Second, cfg.WebSocket.HandshakeTimeout)
	assert.Equal(t, 1000, cfg.WebSocket.MaxConnections)

	// Test logging defaults
	assert.Equal(t, "info", cfg.Logging.Level)
	assert.Equal(t, "json", cfg.Logging.Format)
	assert.Equal(t, "stdout", cfg.Logging.Output)
}

func BenchmarkLoad(b *testing.B) {
	os.Setenv("GATEWAY_JWT_KEYCLOAK_BASE_URL", "http://localhost:8080")
	os.Setenv("GATEWAY_JWT_KEYCLOAK_REALM", "test-realm")
	
	defer func() {
		os.Unsetenv("GATEWAY_JWT_KEYCLOAK_BASE_URL")
		os.Unsetenv("GATEWAY_JWT_KEYCLOAK_REALM")
	}()

	b.ResetTimer()
	
	for i := 0; i < b.N; i++ {
		_, err := Load()
		if err != nil {
			b.Fatal(err)
		}
	}
}

func BenchmarkValidate(b *testing.B) {
	config := &Config{
		Server: ServerConfig{
			HTTPPort: 8080,
			GRPCPort: 8081,
		},
		JWT: JWTConfig{
			Keycloak: KeycloakConfig{
				BaseURL: "http://localhost:8080",
				Realm:   "test-realm",
			},
		},
	}

	b.ResetTimer()
	
	for i := 0; i < b.N; i++ {
		err := config.Validate()
		if err != nil {
			b.Fatal(err)
		}
	}
}