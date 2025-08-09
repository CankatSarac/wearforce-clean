package middleware

import (
	"context"
	"fmt"
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
	"go.uber.org/zap"
	"golang.org/x/time/rate"

	"github.com/wearforce/gateway/internal/config"
)

// RateLimiter handles rate limiting with Redis backend
type RateLimiter struct {
	redis  *redis.Client
	config *config.RateLimitConfig
	logger *zap.Logger
}

// LimitInfo contains rate limit information
type LimitInfo struct {
	Allowed    bool
	Remaining  int
	ResetTime  time.Time
	RetryAfter time.Duration
}

// NewRateLimiter creates a new rate limiter
func NewRateLimiter(redisClient *redis.Client, config *config.RateLimitConfig, logger *zap.Logger) *RateLimiter {
	return &RateLimiter{
		redis:  redisClient,
		config: config,
		logger: logger,
	}
}

// RateLimitMiddleware creates rate limiting middleware
func (rl *RateLimiter) RateLimitMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		if !rl.config.Enabled {
			c.Next()
			return
		}

		// Skip rate limiting for health checks
		if isPublicPath(c.Request.URL.Path) {
			c.Next()
			return
		}

		// Determine rate limit key and config
		key, limitConfig := rl.getRateLimitKey(c)
		
		// Check rate limit
		limitInfo, err := rl.checkLimit(c.Request.Context(), key, limitConfig)
		if err != nil {
			rl.logger.Error("Rate limit check failed",
				zap.Error(err),
				zap.String("key", key),
			)
			// Continue on error - fail open
			c.Next()
			return
		}

		// Set rate limit headers
		rl.setRateLimitHeaders(c, limitInfo, limitConfig)

		if !limitInfo.Allowed {
			rl.logger.Warn("Rate limit exceeded",
				zap.String("key", key),
				zap.Int("remaining", limitInfo.Remaining),
				zap.Time("reset_time", limitInfo.ResetTime),
			)

			c.JSON(http.StatusTooManyRequests, gin.H{
				"error":       "Rate limit exceeded",
				"code":        "RATE_LIMIT_EXCEEDED",
				"retry_after": int(limitInfo.RetryAfter.Seconds()),
				"reset_time":  limitInfo.ResetTime.Unix(),
			})
			c.Abort()
			return
		}

		c.Next()
	}
}

// getRateLimitKey determines the rate limit key and configuration
func (rl *RateLimiter) getRateLimitKey(c *gin.Context) (string, config.LimitConfig) {
	// Check for user-specific limits first
	if userID, exists := c.Get("user_id"); exists {
		if uid, ok := userID.(string); ok {
			if limitConfig, exists := rl.config.UserLimits[uid]; exists {
				return fmt.Sprintf("user:%s", uid), limitConfig
			}
		}
	}

	// Check for IP-based limits
	clientIP := c.ClientIP()
	if limitConfig, exists := rl.config.IPLimits[clientIP]; exists {
		return fmt.Sprintf("ip:%s", clientIP), limitConfig
	}

	// Check for path-based limits
	path := c.Request.URL.Path
	for pattern, limitConfig := range rl.config.DefaultLimits {
		if pattern == "default" || matchesPattern(path, pattern) {
			key := fmt.Sprintf("path:%s:ip:%s", pattern, clientIP)
			return key, limitConfig
		}
	}

	// Fallback to default limits
	defaultLimit := config.LimitConfig{
		Requests: 100,
		Window:   time.Minute,
		Burst:    20,
	}
	return fmt.Sprintf("default:ip:%s", clientIP), defaultLimit
}

// checkLimit checks if request is within rate limit
func (rl *RateLimiter) checkLimit(ctx context.Context, key string, limitConfig config.LimitConfig) (*LimitInfo, error) {
	now := time.Now()
	windowStart := now.Truncate(limitConfig.Window)
	windowKey := fmt.Sprintf("%s:%d", key, windowStart.Unix())

	// Use Redis pipeline for atomic operations
	pipe := rl.redis.Pipeline()
	
	// Increment counter
	incrCmd := pipe.Incr(ctx, windowKey)
	
	// Set expiration if this is the first request in the window
	expireCmd := pipe.Expire(ctx, windowKey, limitConfig.Window)
	
	// Get current TTL to calculate reset time
	ttlCmd := pipe.TTL(ctx, windowKey)

	_, err := pipe.Exec(ctx)
	if err != nil {
		return nil, fmt.Errorf("redis pipeline failed: %w", err)
	}

	// Get results
	currentCount := incrCmd.Val()
	ttl := ttlCmd.Val()

	// Calculate reset time
	var resetTime time.Time
	if ttl > 0 {
		resetTime = now.Add(ttl)
	} else {
		resetTime = windowStart.Add(limitConfig.Window)
	}

	// Calculate remaining requests
	remaining := limitConfig.Requests - int(currentCount)
	if remaining < 0 {
		remaining = 0
	}

	// Check if limit is exceeded
	allowed := currentCount <= int64(limitConfig.Requests)
	
	var retryAfter time.Duration
	if !allowed {
		retryAfter = time.Until(resetTime)
		if retryAfter < 0 {
			retryAfter = 0
		}
	}

	return &LimitInfo{
		Allowed:    allowed,
		Remaining:  remaining,
		ResetTime:  resetTime,
		RetryAfter: retryAfter,
	}, nil
}

// setRateLimitHeaders sets rate limit headers on response
func (rl *RateLimiter) setRateLimitHeaders(c *gin.Context, info *LimitInfo, config config.LimitConfig) {
	c.Header("X-RateLimit-Limit", strconv.Itoa(config.Requests))
	c.Header("X-RateLimit-Remaining", strconv.Itoa(info.Remaining))
	c.Header("X-RateLimit-Reset", strconv.FormatInt(info.ResetTime.Unix(), 10))
	c.Header("X-RateLimit-Window", config.Window.String())

	if !info.Allowed {
		c.Header("Retry-After", strconv.Itoa(int(info.RetryAfter.Seconds())))
	}
}

// InMemoryRateLimiter is a simple in-memory rate limiter for testing
type InMemoryRateLimiter struct {
	limiters map[string]*rate.Limiter
	config   *config.RateLimitConfig
	logger   *zap.Logger
}

// NewInMemoryRateLimiter creates a new in-memory rate limiter
func NewInMemoryRateLimiter(config *config.RateLimitConfig, logger *zap.Logger) *InMemoryRateLimiter {
	return &InMemoryRateLimiter{
		limiters: make(map[string]*rate.Limiter),
		config:   config,
		logger:   logger,
	}
}

// InMemoryRateLimitMiddleware creates in-memory rate limiting middleware
func (rl *InMemoryRateLimiter) InMemoryRateLimitMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		if !rl.config.Enabled {
			c.Next()
			return
		}

		// Skip rate limiting for health checks
		if isPublicPath(c.Request.URL.Path) {
			c.Next()
			return
		}

		// Get or create limiter for this client
		key := rl.getRateLimitKey(c)
		limiter := rl.getLimiter(key)

		if !limiter.Allow() {
			rl.logger.Warn("Rate limit exceeded", zap.String("key", key))
			
			c.JSON(http.StatusTooManyRequests, gin.H{
				"error": "Rate limit exceeded",
				"code":  "RATE_LIMIT_EXCEEDED",
			})
			c.Abort()
			return
		}

		c.Next()
	}
}

// getRateLimitKey generates rate limit key for in-memory limiter
func (rl *InMemoryRateLimiter) getRateLimitKey(c *gin.Context) string {
	// Use user ID if available, otherwise use IP
	if userID, exists := c.Get("user_id"); exists {
		if uid, ok := userID.(string); ok {
			return fmt.Sprintf("user:%s", uid)
		}
	}
	
	return fmt.Sprintf("ip:%s", c.ClientIP())
}

// getLimiter gets or creates a rate limiter for the given key
func (rl *InMemoryRateLimiter) getLimiter(key string) *rate.Limiter {
	if limiter, exists := rl.limiters[key]; exists {
		return limiter
	}

	// Create new limiter with default configuration
	defaultLimit := config.LimitConfig{
		Requests: 100,
		Window:   time.Minute,
		Burst:    20,
	}

	// Calculate rate per second
	ratePerSecond := rate.Limit(float64(defaultLimit.Requests) / defaultLimit.Window.Seconds())
	
	limiter := rate.NewLimiter(ratePerSecond, defaultLimit.Burst)
	rl.limiters[key] = limiter
	
	return limiter
}

// matchesPattern checks if path matches a pattern (simplified)
func matchesPattern(path, pattern string) bool {
	// Simplified pattern matching - in production, use proper regex or glob matching
	if pattern == "*" {
		return true
	}
	
	// Exact match
	if path == pattern {
		return true
	}
	
	// Prefix match for patterns ending with /*
	if len(pattern) > 2 && pattern[len(pattern)-2:] == "/*" {
		prefix := pattern[:len(pattern)-2]
		return len(path) >= len(prefix) && path[:len(prefix)] == prefix
	}
	
	return false
}

// CleanupExpiredLimiters removes expired limiters from memory
func (rl *InMemoryRateLimiter) CleanupExpiredLimiters() {
	// This would need to be called periodically
	// For simplicity, we're not implementing cleanup in this example
	// In production, you'd want to track last access times and clean up old limiters
}

// GetLimitInfo returns current rate limit information for a key
func (rl *RateLimiter) GetLimitInfo(ctx context.Context, key string, limitConfig config.LimitConfig) (*LimitInfo, error) {
	return rl.checkLimit(ctx, key, limitConfig)
}