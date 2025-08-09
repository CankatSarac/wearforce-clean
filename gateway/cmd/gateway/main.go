package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.uber.org/zap"

	"github.com/wearforce/gateway/internal/auth"
	"github.com/wearforce/gateway/internal/config"
	"github.com/wearforce/gateway/internal/middleware"
	"github.com/wearforce/gateway/internal/proxy"
	"github.com/wearforce/gateway/internal/server"
	"github.com/wearforce/gateway/internal/tracing"
)

func main() {
	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		panic(fmt.Sprintf("Failed to load configuration: %v", err))
	}

	// Validate configuration
	if err := cfg.Validate(); err != nil {
		panic(fmt.Sprintf("Invalid configuration: %v", err))
	}

	// Initialize logger
	logger, err := initLogger(cfg.Logging)
	if err != nil {
		panic(fmt.Sprintf("Failed to initialize logger: %v", err))
	}
	defer logger.Sync()

	logger.Info("Starting WearForce Gateway",
		zap.String("version", "1.0.0"),
		zap.String("environment", cfg.Tracing.Environment),
	)

	// Initialize tracing
	tracingMgr, err := tracing.NewTracingManager(&cfg.Tracing, logger)
	if err != nil {
		logger.Fatal("Failed to initialize tracing", zap.Error(err))
	}
	defer func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := tracingMgr.Shutdown(ctx); err != nil {
			logger.Error("Failed to shutdown tracing", zap.Error(err))
		}
	}()

	// Initialize Redis client
	redisClient := initRedisClient(&cfg.Redis, logger)
	defer redisClient.Close()

	// Test Redis connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	
	if err := redisClient.Ping(ctx).Err(); err != nil {
		logger.Warn("Redis connection failed, some features may not work", zap.Error(err))
	} else {
		logger.Info("Redis connection established")
	}

	// Initialize JWT validator
	jwtValidator := auth.NewJWTValidator(&cfg.JWT, logger)

	// Initialize TLS manager
	tlsMgr, err := server.NewTLSManager(&cfg.TLS, logger)
	if err != nil {
		logger.Fatal("Failed to initialize TLS manager", zap.Error(err))
	}

	if err := tlsMgr.ValidateConfiguration(); err != nil {
		logger.Fatal("TLS configuration validation failed", zap.Error(err))
	}

	// Get TLS config
	tlsConfig, err := tlsMgr.GetTLSConfig()
	if err != nil {
		logger.Fatal("Failed to get TLS config", zap.Error(err))
	}

	// Initialize rate limiter
	rateLimiter := middleware.NewRateLimiter(redisClient, &cfg.RateLimit, logger)

	// Initialize WebSocket proxy
	wsProxy := proxy.NewWebSocketProxy(&cfg.WebSocket, logger, jwtValidator)

	// Initialize gRPC server
	grpcServer, err := server.NewGRPCServer(&cfg.Server, tlsConfig, logger, jwtValidator)
	if err != nil {
		logger.Fatal("Failed to initialize gRPC server", zap.Error(err))
	}

	// Initialize HTTP server
	httpServer := initHTTPServer(cfg, logger, jwtValidator, rateLimiter, wsProxy)

	// Start servers
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Start ACME challenge server if Let's Encrypt is enabled
	if cfg.TLS.LetsEncrypt.Enabled {
		go func() {
			if err := tlsMgr.StartACMEChallengeServer(ctx, ":80"); err != nil {
				logger.Error("ACME challenge server error", zap.Error(err))
			}
		}()

		// Start certificate renewal
		go tlsMgr.StartCertificateRenewal(ctx)
	}

	// Start metrics server
	if cfg.Metrics.Enabled {
		go startMetricsServer(cfg.Metrics, logger)
	}

	// Start WebSocket cleanup worker
	go wsProxy.StartCleanupWorker(ctx)

	// Start gRPC server
	go func() {
		if err := grpcServer.Start(); err != nil {
			logger.Error("gRPC server error", zap.Error(err))
		}
	}()

	// Start HTTP server
	go func() {
		addr := fmt.Sprintf("%s:%d", cfg.Server.Host, cfg.Server.HTTPPort)
		
		if tlsConfig != nil {
			logger.Info("Starting HTTPS server", zap.String("address", addr))
			server := &http.Server{
				Addr:           addr,
				Handler:        httpServer,
				TLSConfig:      tlsConfig,
				ReadTimeout:    cfg.Server.ReadTimeout,
				WriteTimeout:   cfg.Server.WriteTimeout,
				IdleTimeout:    cfg.Server.IdleTimeout,
				MaxHeaderBytes: cfg.Server.MaxHeaderBytes,
			}
			
			if err := server.ListenAndServeTLS("", ""); err != nil && err != http.ErrServerClosed {
				logger.Error("HTTPS server error", zap.Error(err))
			}
		} else {
			logger.Info("Starting HTTP server", zap.String("address", addr))
			server := &http.Server{
				Addr:           addr,
				Handler:        httpServer,
				ReadTimeout:    cfg.Server.ReadTimeout,
				WriteTimeout:   cfg.Server.WriteTimeout,
				IdleTimeout:    cfg.Server.IdleTimeout,
				MaxHeaderBytes: cfg.Server.MaxHeaderBytes,
			}
			
			if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
				logger.Error("HTTP server error", zap.Error(err))
			}
		}
	}()

	logger.Info("All servers started successfully")

	// Wait for interrupt signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	<-sigChan

	logger.Info("Shutting down servers...")

	// Cancel context to stop background workers
	cancel()

	// Shutdown gRPC server
	if err := grpcServer.Stop(cfg.Server.ShutdownTimeout); err != nil {
		logger.Error("Failed to shutdown gRPC server", zap.Error(err))
	}

	logger.Info("Gateway shutdown completed")
}

// initLogger initializes the logger
func initLogger(cfg config.LoggingConfig) (*zap.Logger, error) {
	var zapCfg zap.Config

	if cfg.Format == "json" {
		zapCfg = zap.NewProductionConfig()
	} else {
		zapCfg = zap.NewDevelopmentConfig()
	}

	// Set log level
	switch cfg.Level {
	case "debug":
		zapCfg.Level = zap.NewAtomicLevelAt(zap.DebugLevel)
	case "info":
		zapCfg.Level = zap.NewAtomicLevelAt(zap.InfoLevel)
	case "warn":
		zapCfg.Level = zap.NewAtomicLevelAt(zap.WarnLevel)
	case "error":
		zapCfg.Level = zap.NewAtomicLevelAt(zap.ErrorLevel)
	}

	// Set output
	if cfg.Output == "stderr" {
		zapCfg.OutputPaths = []string{"stderr"}
	} else if cfg.Output == "file" && cfg.File != "" {
		zapCfg.OutputPaths = []string{cfg.File}
	}

	return zapCfg.Build()
}

// initRedisClient initializes Redis client
func initRedisClient(cfg *config.RedisConfig, logger *zap.Logger) *redis.Client {
	return redis.NewClient(&redis.Options{
		Addr:         cfg.Address,
		Password:     cfg.Password,
		DB:           cfg.DB,
		PoolSize:     cfg.PoolSize,
		MaxRetries:   cfg.MaxRetries,
		IdleTimeout:  cfg.IdleTimeout,
		ReadTimeout:  cfg.ReadTimeout,
		WriteTimeout: cfg.WriteTimeout,
	})
}

// initHTTPServer initializes the HTTP server with middleware
func initHTTPServer(
	cfg *config.Config,
	logger *zap.Logger,
	jwtValidator *auth.JWTValidator,
	rateLimiter *middleware.RateLimiter,
	wsProxy *proxy.WebSocketProxy,
) *gin.Engine {
	// Set Gin mode
	if cfg.Tracing.Environment == "production" {
		gin.SetMode(gin.ReleaseMode)
	}

	router := gin.New()

	// Core middleware
	router.Use(middleware.RequestIDMiddleware())
	router.Use(middleware.CORSMiddleware(middleware.DefaultCORSConfig()))
	router.Use(middleware.LoggingMiddleware(logger))
	router.Use(middleware.SecurityLoggingMiddleware(logger))
	router.Use(gin.Recovery())

	// Rate limiting middleware
	if cfg.RateLimit.Enabled {
		router.Use(rateLimiter.RateLimitMiddleware())
	}

	// Health check endpoints (no auth required)
	router.GET("/health", healthCheck)
	router.GET("/ping", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{"message": "pong"})
	})

	// WebSocket endpoint
	router.GET("/ws", wsProxy.HandleWebSocket())

	// API routes with authentication
	api := router.Group("/api/v1")
	api.Use(middleware.AuthMiddleware(jwtValidator, logger))
	{
		// Chat endpoints
		api.GET("/chat/rooms/:roomId/messages", getChatMessages)
		api.POST("/chat/rooms/:roomId/messages", sendChatMessage)
		api.GET("/chat/rooms/:roomId/users", getChatUsers)

		// Audio endpoints
		api.POST("/audio/stt", speechToText)
		api.POST("/audio/tts", textToSpeech)
		api.GET("/audio/config", getAudioConfig)

		// Service proxy endpoints
		proxy := api.Group("/proxy")
		proxy.Use(middleware.RequireRole("admin", "manager"))
		{
			proxy.Any("/crm/*path", proxyCRM)
			proxy.Any("/erp/*path", proxyERP)
		}

		// Admin endpoints
		admin := api.Group("/admin")
		admin.Use(middleware.RequireRole("admin"))
		{
			admin.GET("/stats", getStats)
			admin.GET("/users", getUsers)
			admin.POST("/users/:userId/roles", updateUserRoles)
		}
	}

	// WebSocket stats endpoint
	router.GET("/ws/stats", func(c *gin.Context) {
		c.JSON(http.StatusOK, wsProxy.GetStats())
	})

	return router
}

// startMetricsServer starts the Prometheus metrics server
func startMetricsServer(cfg config.MetricsConfig, logger *zap.Logger) {
	mux := http.NewServeMux()
	mux.Handle(cfg.Path, promhttp.Handler())
	
	addr := fmt.Sprintf(":%d", cfg.Port)
	logger.Info("Starting metrics server", zap.String("address", addr))
	
	if err := http.ListenAndServe(addr, mux); err != nil {
		logger.Error("Metrics server error", zap.Error(err))
	}
}

// HTTP handler functions (placeholders)
func healthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":    "healthy",
		"timestamp": time.Now().UTC(),
		"version":   "1.0.0",
	})
}

func getChatMessages(c *gin.Context) {
	roomID := c.Param("roomId")
	c.JSON(http.StatusOK, gin.H{
		"room_id":  roomID,
		"messages": []interface{}{},
	})
}

func sendChatMessage(c *gin.Context) {
	roomID := c.Param("roomId")
	c.JSON(http.StatusOK, gin.H{
		"room_id":    roomID,
		"message_id": "msg-123",
		"status":     "sent",
	})
}

func getChatUsers(c *gin.Context) {
	roomID := c.Param("roomId")
	c.JSON(http.StatusOK, gin.H{
		"room_id": roomID,
		"users":   []interface{}{},
	})
}

func speechToText(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"transcription": "Sample transcription",
		"confidence":    0.95,
	})
}

func textToSpeech(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"audio_url": "/api/v1/audio/generated/123.wav",
		"duration":  5.2,
	})
}

func getAudioConfig(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"supported_formats": []string{"wav", "mp3", "ogg"},
		"sample_rates":      []int{16000, 22050, 44100},
	})
}

func proxyCRM(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"service": "crm",
		"path":    c.Param("path"),
		"method":  c.Request.Method,
	})
}

func proxyERP(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"service": "erp",
		"path":    c.Param("path"),
		"method":  c.Request.Method,
	})
}

func getStats(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"active_connections": 150,
		"total_requests":     10000,
		"uptime":            "24h",
	})
}

func getUsers(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"users": []interface{}{},
		"total": 0,
	})
}

func updateUserRoles(c *gin.Context) {
	userID := c.Param("userId")
	c.JSON(http.StatusOK, gin.H{
		"user_id": userID,
		"updated": true,
	})
}