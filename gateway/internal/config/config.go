package config

import (
	"fmt"
	"time"

	"github.com/spf13/viper"
)

// Config holds all configuration for the gateway service
type Config struct {
	Server     ServerConfig     `mapstructure:"server"`
	TLS        TLSConfig        `mapstructure:"tls"`
	JWT        JWTConfig        `mapstructure:"jwt"`
	Redis      RedisConfig      `mapstructure:"redis"`
	Services   ServicesConfig   `mapstructure:"services"`
	RateLimit  RateLimitConfig  `mapstructure:"rate_limit"`
	Tracing    TracingConfig    `mapstructure:"tracing"`
	Metrics    MetricsConfig    `mapstructure:"metrics"`
	WebSocket  WebSocketConfig  `mapstructure:"websocket"`
	Logging    LoggingConfig    `mapstructure:"logging"`
}

// ServerConfig contains server configuration
type ServerConfig struct {
	Host            string        `mapstructure:"host"`
	HTTPPort        int           `mapstructure:"http_port"`
	GRPCPort        int           `mapstructure:"grpc_port"`
	ReadTimeout     time.Duration `mapstructure:"read_timeout"`
	WriteTimeout    time.Duration `mapstructure:"write_timeout"`
	IdleTimeout     time.Duration `mapstructure:"idle_timeout"`
	ShutdownTimeout time.Duration `mapstructure:"shutdown_timeout"`
	MaxHeaderBytes  int           `mapstructure:"max_header_bytes"`
}

// TLSConfig contains TLS and Let's Encrypt configuration
type TLSConfig struct {
	Enabled        bool     `mapstructure:"enabled"`
	CertFile       string   `mapstructure:"cert_file"`
	KeyFile        string   `mapstructure:"key_file"`
	LetsEncrypt    LEConfig `mapstructure:"lets_encrypt"`
	MinTLSVersion  string   `mapstructure:"min_tls_version"`
	CipherSuites   []string `mapstructure:"cipher_suites"`
}

// LEConfig contains Let's Encrypt configuration
type LEConfig struct {
	Enabled    bool     `mapstructure:"enabled"`
	Domains    []string `mapstructure:"domains"`
	CacheDir   string   `mapstructure:"cache_dir"`
	Email      string   `mapstructure:"email"`
	Staging    bool     `mapstructure:"staging"`
	RenewBefore int     `mapstructure:"renew_before_days"`
}

// JWTConfig contains JWT validation configuration
type JWTConfig struct {
	Keycloak KeycloakConfig `mapstructure:"keycloak"`
	Secret   string         `mapstructure:"secret"`
	Issuer   string         `mapstructure:"issuer"`
	Audience string         `mapstructure:"audience"`
	TTL      time.Duration  `mapstructure:"ttl"`
}

// KeycloakConfig contains Keycloak-specific JWT configuration
type KeycloakConfig struct {
	BaseURL      string        `mapstructure:"base_url"`
	Realm        string        `mapstructure:"realm"`
	ClientID     string        `mapstructure:"client_id"`
	ClientSecret string        `mapstructure:"client_secret"`
	JWKSPath     string        `mapstructure:"jwks_path"`
	CacheTimeout time.Duration `mapstructure:"cache_timeout"`
}

// RedisConfig contains Redis configuration
type RedisConfig struct {
	Address     string        `mapstructure:"address"`
	Password    string        `mapstructure:"password"`
	DB          int           `mapstructure:"db"`
	PoolSize    int           `mapstructure:"pool_size"`
	MaxRetries  int           `mapstructure:"max_retries"`
	IdleTimeout time.Duration `mapstructure:"idle_timeout"`
	ReadTimeout time.Duration `mapstructure:"read_timeout"`
	WriteTimeout time.Duration `mapstructure:"write_timeout"`
}

// ServicesConfig contains backend service configurations
type ServicesConfig struct {
	STT          ServiceEndpoint `mapstructure:"stt"`
	TTS          ServiceEndpoint `mapstructure:"tts"`
	CRM          ServiceEndpoint `mapstructure:"crm"`
	ERP          ServiceEndpoint `mapstructure:"erp"`
	User         ServiceEndpoint `mapstructure:"user"`
	Notification ServiceEndpoint `mapstructure:"notification"`
}

// ServiceEndpoint contains individual service endpoint configuration
type ServiceEndpoint struct {
	URL             string            `mapstructure:"url"`
	Timeout         time.Duration     `mapstructure:"timeout"`
	MaxRetries      int               `mapstructure:"max_retries"`
	RetryBackoff    time.Duration     `mapstructure:"retry_backoff"`
	Headers         map[string]string `mapstructure:"headers"`
	HealthCheckPath string            `mapstructure:"health_check_path"`
	CircuitBreaker  CircuitBreakerConfig `mapstructure:"circuit_breaker"`
}

// CircuitBreakerConfig contains circuit breaker configuration
type CircuitBreakerConfig struct {
	Enabled          bool          `mapstructure:"enabled"`
	MaxRequests      uint32        `mapstructure:"max_requests"`
	Interval         time.Duration `mapstructure:"interval"`
	Timeout          time.Duration `mapstructure:"timeout"`
	ReadyToTrip      uint32        `mapstructure:"ready_to_trip"`
}

// RateLimitConfig contains rate limiting configuration
type RateLimitConfig struct {
	Enabled       bool                   `mapstructure:"enabled"`
	DefaultLimits map[string]LimitConfig `mapstructure:"default_limits"`
	UserLimits    map[string]LimitConfig `mapstructure:"user_limits"`
	IPLimits      map[string]LimitConfig `mapstructure:"ip_limits"`
}

// LimitConfig contains individual rate limit configuration
type LimitConfig struct {
	Requests int           `mapstructure:"requests"`
	Window   time.Duration `mapstructure:"window"`
	Burst    int           `mapstructure:"burst"`
}

// TracingConfig contains OpenTelemetry tracing configuration
type TracingConfig struct {
	Enabled        bool              `mapstructure:"enabled"`
	ServiceName    string            `mapstructure:"service_name"`
	ServiceVersion string            `mapstructure:"service_version"`
	Environment    string            `mapstructure:"environment"`
	Exporter       ExporterConfig    `mapstructure:"exporter"`
	Sampling       SamplingConfig    `mapstructure:"sampling"`
	Resources      map[string]string `mapstructure:"resources"`
}

// ExporterConfig contains trace exporter configuration
type ExporterConfig struct {
	Type     string            `mapstructure:"type"` // jaeger, otlp-http, otlp-grpc
	Endpoint string            `mapstructure:"endpoint"`
	Headers  map[string]string `mapstructure:"headers"`
	Insecure bool              `mapstructure:"insecure"`
}

// SamplingConfig contains sampling configuration
type SamplingConfig struct {
	Type  string  `mapstructure:"type"` // always, never, ratio
	Ratio float64 `mapstructure:"ratio"`
}

// MetricsConfig contains Prometheus metrics configuration
type MetricsConfig struct {
	Enabled    bool          `mapstructure:"enabled"`
	Path       string        `mapstructure:"path"`
	Port       int           `mapstructure:"port"`
	Interval   time.Duration `mapstructure:"interval"`
	Namespace  string        `mapstructure:"namespace"`
	Subsystem  string        `mapstructure:"subsystem"`
	Labels     map[string]string `mapstructure:"labels"`
}

// WebSocketConfig contains WebSocket configuration
type WebSocketConfig struct {
	ReadBufferSize    int           `mapstructure:"read_buffer_size"`
	WriteBufferSize   int           `mapstructure:"write_buffer_size"`
	HandshakeTimeout  time.Duration `mapstructure:"handshake_timeout"`
	ReadDeadline      time.Duration `mapstructure:"read_deadline"`
	WriteDeadline     time.Duration `mapstructure:"write_deadline"`
	PongTimeout       time.Duration `mapstructure:"pong_timeout"`
	PingPeriod        time.Duration `mapstructure:"ping_period"`
	MaxMessageSize    int64         `mapstructure:"max_message_size"`
	MaxConnections    int           `mapstructure:"max_connections"`
	CheckOrigin       bool          `mapstructure:"check_origin"`
	Subprotocols      []string      `mapstructure:"subprotocols"`
}

// LoggingConfig contains logging configuration
type LoggingConfig struct {
	Level      string `mapstructure:"level"`      // debug, info, warn, error
	Format     string `mapstructure:"format"`     // json, text
	Output     string `mapstructure:"output"`     // stdout, stderr, file
	File       string `mapstructure:"file"`       // log file path
	MaxSize    int    `mapstructure:"max_size"`   // megabytes
	MaxAge     int    `mapstructure:"max_age"`    // days
	MaxBackups int    `mapstructure:"max_backups"`
	Compress   bool   `mapstructure:"compress"`
}

// Load loads configuration from environment variables and config files
func Load() (*Config, error) {
	viper.SetConfigName("gateway")
	viper.SetConfigType("yaml")
	viper.AddConfigPath(".")
	viper.AddConfigPath("./configs")
	viper.AddConfigPath("/etc/gateway")

	// Set default values
	setDefaults()

	// Enable environment variable support
	viper.AutomaticEnv()
	viper.SetEnvPrefix("GATEWAY")

	// Read config file
	if err := viper.ReadInConfig(); err != nil {
		if _, ok := err.(viper.ConfigFileNotFoundError); !ok {
			return nil, fmt.Errorf("error reading config file: %w", err)
		}
		// Config file not found, continue with defaults and env vars
	}

	var config Config
	if err := viper.Unmarshal(&config); err != nil {
		return nil, fmt.Errorf("error unmarshaling config: %w", err)
	}

	return &config, nil
}

// setDefaults sets default configuration values
func setDefaults() {
	// Server defaults
	viper.SetDefault("server.host", "0.0.0.0")
	viper.SetDefault("server.http_port", 8080)
	viper.SetDefault("server.grpc_port", 8081)
	viper.SetDefault("server.read_timeout", "30s")
	viper.SetDefault("server.write_timeout", "30s")
	viper.SetDefault("server.idle_timeout", "120s")
	viper.SetDefault("server.shutdown_timeout", "10s")
	viper.SetDefault("server.max_header_bytes", 1048576) // 1MB

	// TLS defaults
	viper.SetDefault("tls.enabled", false)
	viper.SetDefault("tls.min_tls_version", "1.2")
	viper.SetDefault("tls.lets_encrypt.enabled", false)
	viper.SetDefault("tls.lets_encrypt.cache_dir", "/tmp/autocert")
	viper.SetDefault("tls.lets_encrypt.staging", true)
	viper.SetDefault("tls.lets_encrypt.renew_before_days", 30)

	// JWT defaults
	viper.SetDefault("jwt.ttl", "24h")
	viper.SetDefault("jwt.keycloak.cache_timeout", "5m")
	viper.SetDefault("jwt.keycloak.jwks_path", "/auth/realms/{realm}/protocol/openid_connect/certs")

	// Redis defaults
	viper.SetDefault("redis.address", "localhost:6379")
	viper.SetDefault("redis.db", 0)
	viper.SetDefault("redis.pool_size", 10)
	viper.SetDefault("redis.max_retries", 3)
	viper.SetDefault("redis.idle_timeout", "300s")
	viper.SetDefault("redis.read_timeout", "3s")
	viper.SetDefault("redis.write_timeout", "3s")

	// Service defaults
	viper.SetDefault("services.stt.timeout", "30s")
	viper.SetDefault("services.stt.max_retries", 3)
	viper.SetDefault("services.stt.retry_backoff", "1s")
	viper.SetDefault("services.tts.timeout", "30s")
	viper.SetDefault("services.tts.max_retries", 3)
	viper.SetDefault("services.tts.retry_backoff", "1s")
	viper.SetDefault("services.crm.timeout", "30s")
	viper.SetDefault("services.crm.max_retries", 3)
	viper.SetDefault("services.crm.retry_backoff", "1s")
	viper.SetDefault("services.erp.timeout", "30s")
	viper.SetDefault("services.erp.max_retries", 3)
	viper.SetDefault("services.erp.retry_backoff", "1s")

	// Rate limiting defaults
	viper.SetDefault("rate_limit.enabled", true)
	viper.SetDefault("rate_limit.default_limits.requests", 100)
	viper.SetDefault("rate_limit.default_limits.window", "1m")
	viper.SetDefault("rate_limit.default_limits.burst", 20)

	// Tracing defaults
	viper.SetDefault("tracing.enabled", false)
	viper.SetDefault("tracing.service_name", "wearforce-gateway")
	viper.SetDefault("tracing.service_version", "1.0.0")
	viper.SetDefault("tracing.environment", "development")
	viper.SetDefault("tracing.exporter.type", "otlp-http")
	viper.SetDefault("tracing.exporter.endpoint", "http://localhost:4318/v1/traces")
	viper.SetDefault("tracing.sampling.type", "ratio")
	viper.SetDefault("tracing.sampling.ratio", 0.1)

	// Metrics defaults
	viper.SetDefault("metrics.enabled", true)
	viper.SetDefault("metrics.path", "/metrics")
	viper.SetDefault("metrics.port", 9090)
	viper.SetDefault("metrics.interval", "15s")
	viper.SetDefault("metrics.namespace", "wearforce")
	viper.SetDefault("metrics.subsystem", "gateway")

	// WebSocket defaults
	viper.SetDefault("websocket.read_buffer_size", 1024)
	viper.SetDefault("websocket.write_buffer_size", 1024)
	viper.SetDefault("websocket.handshake_timeout", "10s")
	viper.SetDefault("websocket.read_deadline", "60s")
	viper.SetDefault("websocket.write_deadline", "10s")
	viper.SetDefault("websocket.pong_timeout", "60s")
	viper.SetDefault("websocket.ping_period", "54s")
	viper.SetDefault("websocket.max_message_size", 512*1024) // 512KB
	viper.SetDefault("websocket.max_connections", 1000)
	viper.SetDefault("websocket.check_origin", false)

	// Logging defaults
	viper.SetDefault("logging.level", "info")
	viper.SetDefault("logging.format", "json")
	viper.SetDefault("logging.output", "stdout")
	viper.SetDefault("logging.max_size", 100) // 100MB
	viper.SetDefault("logging.max_age", 30)   // 30 days
	viper.SetDefault("logging.max_backups", 10)
	viper.SetDefault("logging.compress", true)
}

// Validate validates the configuration
func (c *Config) Validate() error {
	if c.Server.HTTPPort <= 0 || c.Server.HTTPPort > 65535 {
		return fmt.Errorf("invalid HTTP port: %d", c.Server.HTTPPort)
	}

	if c.Server.GRPCPort <= 0 || c.Server.GRPCPort > 65535 {
		return fmt.Errorf("invalid gRPC port: %d", c.Server.GRPCPort)
	}

	if c.TLS.Enabled {
		if c.TLS.LetsEncrypt.Enabled {
			if len(c.TLS.LetsEncrypt.Domains) == 0 {
				return fmt.Errorf("Let's Encrypt enabled but no domains specified")
			}
			if c.TLS.LetsEncrypt.Email == "" {
				return fmt.Errorf("Let's Encrypt enabled but no email specified")
			}
		} else {
			if c.TLS.CertFile == "" || c.TLS.KeyFile == "" {
				return fmt.Errorf("TLS enabled but cert/key files not specified")
			}
		}
	}

	if c.JWT.Keycloak.BaseURL == "" {
		return fmt.Errorf("Keycloak base URL not specified")
	}

	if c.JWT.Keycloak.Realm == "" {
		return fmt.Errorf("Keycloak realm not specified")
	}

	return nil
}