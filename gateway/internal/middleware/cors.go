package middleware

import (
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

// CORSConfig contains CORS configuration
type CORSConfig struct {
	AllowAllOrigins  bool
	AllowOrigins     []string
	AllowMethods     []string
	AllowHeaders     []string
	ExposeHeaders    []string
	AllowCredentials bool
	MaxAge           time.Duration
}

// DefaultCORSConfig returns default CORS configuration
func DefaultCORSConfig() *CORSConfig {
	return &CORSConfig{
		AllowAllOrigins: false,
		AllowOrigins: []string{
			"http://localhost:3000",
			"http://localhost:3001",
			"https://*.wearforce.com",
		},
		AllowMethods: []string{
			"GET",
			"POST",
			"PUT",
			"PATCH",
			"DELETE",
			"HEAD",
			"OPTIONS",
		},
		AllowHeaders: []string{
			"Accept",
			"Accept-Encoding",
			"Accept-Language",
			"Authorization",
			"Content-Length",
			"Content-Type",
			"Origin",
			"User-Agent",
			"X-Forwarded-For",
			"X-Forwarded-Proto",
			"X-Real-IP",
			"X-Request-ID",
			"X-Trace-ID",
		},
		ExposeHeaders: []string{
			"Content-Length",
			"X-Request-ID",
			"X-Trace-ID",
			"X-RateLimit-Limit",
			"X-RateLimit-Remaining",
			"X-RateLimit-Reset",
		},
		AllowCredentials: true,
		MaxAge:           12 * time.Hour,
	}
}

// CORSMiddleware creates CORS middleware
func CORSMiddleware(config *CORSConfig) gin.HandlerFunc {
	if config == nil {
		config = DefaultCORSConfig()
	}

	return func(c *gin.Context) {
		origin := c.GetHeader("Origin")
		
		// Handle preflight requests
		if c.Request.Method == "OPTIONS" {
			handlePreflight(c, config, origin)
			return
		}

		// Handle actual requests
		handleCORS(c, config, origin)
		c.Next()
	}
}

// handlePreflight handles preflight OPTIONS requests
func handlePreflight(c *gin.Context, config *CORSConfig, origin string) {
	// Set Access-Control-Allow-Origin
	if config.AllowAllOrigins {
		c.Header("Access-Control-Allow-Origin", "*")
	} else if isOriginAllowed(origin, config.AllowOrigins) {
		c.Header("Access-Control-Allow-Origin", origin)
		c.Header("Vary", "Origin")
	} else {
		// Origin not allowed
		c.AbortWithStatus(http.StatusForbidden)
		return
	}

	// Set Access-Control-Allow-Methods
	if len(config.AllowMethods) > 0 {
		c.Header("Access-Control-Allow-Methods", strings.Join(config.AllowMethods, ", "))
	}

	// Set Access-Control-Allow-Headers
	requestHeaders := c.GetHeader("Access-Control-Request-Headers")
	if requestHeaders != "" {
		// Check if requested headers are allowed
		if areHeadersAllowed(requestHeaders, config.AllowHeaders) {
			c.Header("Access-Control-Allow-Headers", requestHeaders)
		} else {
			// Set only allowed headers
			c.Header("Access-Control-Allow-Headers", strings.Join(config.AllowHeaders, ", "))
		}
	} else if len(config.AllowHeaders) > 0 {
		c.Header("Access-Control-Allow-Headers", strings.Join(config.AllowHeaders, ", "))
	}

	// Set Access-Control-Allow-Credentials
	if config.AllowCredentials {
		c.Header("Access-Control-Allow-Credentials", "true")
	}

	// Set Access-Control-Max-Age
	if config.MaxAge > 0 {
		c.Header("Access-Control-Max-Age", strconv.Itoa(int(config.MaxAge.Seconds())))
	}

	c.AbortWithStatus(http.StatusNoContent)
}

// handleCORS handles actual CORS requests
func handleCORS(c *gin.Context, config *CORSConfig, origin string) {
	// Set Access-Control-Allow-Origin
	if config.AllowAllOrigins {
		c.Header("Access-Control-Allow-Origin", "*")
	} else if isOriginAllowed(origin, config.AllowOrigins) {
		c.Header("Access-Control-Allow-Origin", origin)
		c.Header("Vary", "Origin")
	}

	// Set Access-Control-Expose-Headers
	if len(config.ExposeHeaders) > 0 {
		c.Header("Access-Control-Expose-Headers", strings.Join(config.ExposeHeaders, ", "))
	}

	// Set Access-Control-Allow-Credentials
	if config.AllowCredentials && !config.AllowAllOrigins {
		c.Header("Access-Control-Allow-Credentials", "true")
	}
}

// isOriginAllowed checks if origin is in the allowed list
func isOriginAllowed(origin string, allowedOrigins []string) bool {
	if origin == "" {
		return false
	}

	for _, allowed := range allowedOrigins {
		if matchOrigin(origin, allowed) {
			return true
		}
	}

	return false
}

// matchOrigin checks if origin matches the allowed pattern
func matchOrigin(origin, pattern string) bool {
	// Exact match
	if origin == pattern {
		return true
	}

	// Wildcard subdomain match (e.g., *.example.com)
	if strings.HasPrefix(pattern, "*.") {
		domain := pattern[2:] // Remove "*."
		
		// Check if origin ends with the domain
		if strings.HasSuffix(origin, domain) {
			// Make sure it's actually a subdomain, not just a suffix
			beforeDomain := origin[:len(origin)-len(domain)]
			if beforeDomain == "https://" || beforeDomain == "http://" {
				return true
			}
			if strings.HasSuffix(beforeDomain, ".") {
				return true
			}
		}
	}

	return false
}

// areHeadersAllowed checks if all requested headers are allowed
func areHeadersAllowed(requestHeaders string, allowedHeaders []string) bool {
	if requestHeaders == "" {
		return true
	}

	// Normalize allowed headers to lowercase for comparison
	allowedMap := make(map[string]bool)
	for _, header := range allowedHeaders {
		allowedMap[strings.ToLower(header)] = true
	}

	// Check each requested header
	for _, header := range strings.Split(requestHeaders, ",") {
		header = strings.TrimSpace(strings.ToLower(header))
		if !allowedMap[header] {
			return false
		}
	}

	return true
}

// StrictCORSConfig returns a strict CORS configuration for production
func StrictCORSConfig(allowedOrigins []string) *CORSConfig {
	return &CORSConfig{
		AllowAllOrigins: false,
		AllowOrigins:    allowedOrigins,
		AllowMethods: []string{
			"GET",
			"POST",
			"PUT",
			"PATCH",
			"DELETE",
			"OPTIONS",
		},
		AllowHeaders: []string{
			"Accept",
			"Authorization",
			"Content-Type",
			"Origin",
			"X-Request-ID",
		},
		ExposeHeaders: []string{
			"Content-Length",
			"X-Request-ID",
		},
		AllowCredentials: true,
		MaxAge:           1 * time.Hour,
	}
}

// DevelopmentCORSConfig returns a permissive CORS configuration for development
func DevelopmentCORSConfig() *CORSConfig {
	return &CORSConfig{
		AllowAllOrigins: true,
		AllowMethods: []string{
			"GET",
			"POST",
			"PUT",
			"PATCH",
			"DELETE",
			"HEAD",
			"OPTIONS",
		},
		AllowHeaders: []string{
			"*",
		},
		ExposeHeaders: []string{
			"*",
		},
		AllowCredentials: true,
		MaxAge:           24 * time.Hour,
	}
}

// CustomCORSMiddleware creates CORS middleware with custom logic
func CustomCORSMiddleware(originChecker func(origin string) bool) gin.HandlerFunc {
	return func(c *gin.Context) {
		origin := c.GetHeader("Origin")

		if c.Request.Method == "OPTIONS" {
			// Handle preflight
			if origin != "" && originChecker(origin) {
				c.Header("Access-Control-Allow-Origin", origin)
				c.Header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
				c.Header("Access-Control-Allow-Headers", "Accept, Authorization, Content-Type, Origin, X-Request-ID")
				c.Header("Access-Control-Allow-Credentials", "true")
				c.Header("Access-Control-Max-Age", "3600")
			}
			c.AbortWithStatus(http.StatusNoContent)
			return
		}

		// Handle actual request
		if origin != "" && originChecker(origin) {
			c.Header("Access-Control-Allow-Origin", origin)
			c.Header("Access-Control-Allow-Credentials", "true")
			c.Header("Access-Control-Expose-Headers", "Content-Length, X-Request-ID")
		}

		c.Next()
	}
}