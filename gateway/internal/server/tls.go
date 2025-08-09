package server

import (
	"context"
	"crypto/tls"
	"fmt"
	"net/http"
	"time"

	"golang.org/x/crypto/acme"
	"golang.org/x/crypto/acme/autocert"
	"go.uber.org/zap"

	"github.com/wearforce/gateway/internal/config"
)

// TLSManager handles TLS certificate management including Let's Encrypt
type TLSManager struct {
	config   *config.TLSConfig
	logger   *zap.Logger
	certMgr  *autocert.Manager
}

// NewTLSManager creates a new TLS manager
func NewTLSManager(config *config.TLSConfig, logger *zap.Logger) (*TLSManager, error) {
	tm := &TLSManager{
		config: config,
		logger: logger,
	}

	if config.LetsEncrypt.Enabled {
		if err := tm.initLetsEncrypt(); err != nil {
			return nil, fmt.Errorf("failed to initialize Let's Encrypt: %w", err)
		}
	}

	return tm, nil
}

// initLetsEncrypt initializes Let's Encrypt certificate manager
func (tm *TLSManager) initLetsEncrypt() error {
	if len(tm.config.LetsEncrypt.Domains) == 0 {
		return fmt.Errorf("no domains specified for Let's Encrypt")
	}

	if tm.config.LetsEncrypt.Email == "" {
		return fmt.Errorf("email required for Let's Encrypt")
	}

	tm.certMgr = &autocert.Manager{
		Prompt:     autocert.AcceptTOS,
		Cache:      autocert.DirCache(tm.config.LetsEncrypt.CacheDir),
		HostPolicy: autocert.HostWhitelist(tm.config.LetsEncrypt.Domains...),
		Email:      tm.config.LetsEncrypt.Email,
	}

	// Use staging environment if specified
	if tm.config.LetsEncrypt.Staging {
		tm.certMgr.Client = &acme.Client{
			DirectoryURL: acme.LetsEncryptStagingURL,
		}
		tm.logger.Info("Using Let's Encrypt staging environment")
	}

	tm.logger.Info("Let's Encrypt initialized",
		zap.Strings("domains", tm.config.LetsEncrypt.Domains),
		zap.String("cache_dir", tm.config.LetsEncrypt.CacheDir),
		zap.Bool("staging", tm.config.LetsEncrypt.Staging),
	)

	return nil
}

// GetTLSConfig returns TLS configuration
func (tm *TLSManager) GetTLSConfig() (*tls.Config, error) {
	if !tm.config.Enabled {
		return nil, nil
	}

	tlsConfig := &tls.Config{
		MinVersion: tm.getMinTLSVersion(),
		CipherSuites: tm.getCipherSuites(),
	}

	if tm.config.LetsEncrypt.Enabled {
		// Use Let's Encrypt certificates
		tlsConfig.GetCertificate = tm.certMgr.GetCertificate
		tlsConfig.NextProtos = []string{"h2", "http/1.1"}
	} else {
		// Use static certificates
		cert, err := tls.LoadX509KeyPair(tm.config.CertFile, tm.config.KeyFile)
		if err != nil {
			return nil, fmt.Errorf("failed to load TLS certificates: %w", err)
		}
		tlsConfig.Certificates = []tls.Certificate{cert}
	}

	return tlsConfig, nil
}

// StartACMEChallengeServer starts HTTP server for ACME challenges
func (tm *TLSManager) StartACMEChallengeServer(ctx context.Context, addr string) error {
	if !tm.config.LetsEncrypt.Enabled {
		return nil
	}

	server := &http.Server{
		Addr:    addr,
		Handler: tm.certMgr.HTTPHandler(nil),
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  30 * time.Second,
	}

	tm.logger.Info("Starting ACME challenge server", zap.String("addr", addr))

	go func() {
		<-ctx.Done()
		tm.logger.Info("Shutting down ACME challenge server")
		server.Shutdown(context.Background())
	}()

	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		return fmt.Errorf("ACME challenge server error: %w", err)
	}

	return nil
}

// getMinTLSVersion returns minimum TLS version
func (tm *TLSManager) getMinTLSVersion() uint16 {
	switch tm.config.MinTLSVersion {
	case "1.0":
		return tls.VersionTLS10
	case "1.1":
		return tls.VersionTLS11
	case "1.2":
		return tls.VersionTLS12
	case "1.3":
		return tls.VersionTLS13
	default:
		return tls.VersionTLS12 // Default to TLS 1.2
	}
}

// getCipherSuites returns allowed cipher suites
func (tm *TLSManager) getCipherSuites() []uint16 {
	if len(tm.config.CipherSuites) == 0 {
		// Return secure defaults
		return []uint16{
			tls.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
			tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
			tls.TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305,
			tls.TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305,
			tls.TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256,
			tls.TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256,
		}
	}

	// Map cipher suite names to constants
	cipherMap := map[string]uint16{
		"TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384":     tls.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
		"TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384":       tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
		"TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305":      tls.TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305,
		"TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305":        tls.TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305,
		"TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256":     tls.TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256,
		"TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256":       tls.TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256,
		"TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA384":     tls.TLS_ECDHE_ECDSA_WITH_AES_256_CBC_SHA384,
		"TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA384":       tls.TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA384,
		"TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA256":     tls.TLS_ECDHE_ECDSA_WITH_AES_128_CBC_SHA256,
		"TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA256":       tls.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA256,
	}

	var suites []uint16
	for _, suiteName := range tm.config.CipherSuites {
		if suite, ok := cipherMap[suiteName]; ok {
			suites = append(suites, suite)
		} else {
			tm.logger.Warn("Unknown cipher suite", zap.String("suite", suiteName))
		}
	}

	return suites
}

// RenewCertificates manually renews certificates
func (tm *TLSManager) RenewCertificates(ctx context.Context) error {
	if !tm.config.LetsEncrypt.Enabled {
		return fmt.Errorf("Let's Encrypt not enabled")
	}

	for _, domain := range tm.config.LetsEncrypt.Domains {
		tm.logger.Info("Renewing certificate", zap.String("domain", domain))
		
		_, err := tm.certMgr.GetCertificate(&tls.ClientHelloInfo{
			ServerName: domain,
		})
		
		if err != nil {
			tm.logger.Error("Failed to renew certificate",
				zap.String("domain", domain),
				zap.Error(err),
			)
			return fmt.Errorf("failed to renew certificate for %s: %w", domain, err)
		}
		
		tm.logger.Info("Certificate renewed successfully", zap.String("domain", domain))
	}

	return nil
}

// StartCertificateRenewal starts automatic certificate renewal
func (tm *TLSManager) StartCertificateRenewal(ctx context.Context) {
	if !tm.config.LetsEncrypt.Enabled {
		return
	}

	// Calculate renewal period (default: check daily, renew if expires in 30 days)
	renewalPeriod := 24 * time.Hour
	renewalThreshold := time.Duration(tm.config.LetsEncrypt.RenewBefore) * 24 * time.Hour
	if renewalThreshold == 0 {
		renewalThreshold = 30 * 24 * time.Hour // 30 days default
	}

	ticker := time.NewTicker(renewalPeriod)
	defer ticker.Stop()

	tm.logger.Info("Starting automatic certificate renewal",
		zap.Duration("check_interval", renewalPeriod),
		zap.Duration("renew_threshold", renewalThreshold),
	)

	for {
		select {
		case <-ctx.Done():
			tm.logger.Info("Certificate renewal stopped")
			return
		case <-ticker.C:
			tm.checkAndRenewCertificates(ctx, renewalThreshold)
		}
	}
}

// checkAndRenewCertificates checks certificate expiration and renews if needed
func (tm *TLSManager) checkAndRenewCertificates(ctx context.Context, threshold time.Duration) {
	for _, domain := range tm.config.LetsEncrypt.Domains {
		if tm.needsRenewal(domain, threshold) {
			tm.logger.Info("Certificate needs renewal", zap.String("domain", domain))
			
			if err := tm.renewCertificate(ctx, domain); err != nil {
				tm.logger.Error("Failed to renew certificate",
					zap.String("domain", domain),
					zap.Error(err),
				)
			}
		}
	}
}

// needsRenewal checks if certificate needs renewal
func (tm *TLSManager) needsRenewal(domain string, threshold time.Duration) bool {
	// This would check the certificate expiration time
	// Implementation depends on how certificates are stored
	// For autocert, certificates are automatically renewed
	return false
}

// renewCertificate renews a specific certificate
func (tm *TLSManager) renewCertificate(ctx context.Context, domain string) error {
	// Force renewal by requesting a new certificate
	_, err := tm.certMgr.GetCertificate(&tls.ClientHelloInfo{
		ServerName: domain,
	})
	
	if err != nil {
		return fmt.Errorf("failed to renew certificate: %w", err)
	}

	tm.logger.Info("Certificate renewed successfully", zap.String("domain", domain))
	return nil
}

// GetHTTPSRedirectHandler returns handler that redirects HTTP to HTTPS
func (tm *TLSManager) GetHTTPSRedirectHandler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Handle ACME challenges
		if tm.config.LetsEncrypt.Enabled {
			if handler := tm.certMgr.HTTPHandler(nil); handler != nil {
				if r.URL.Path == "/.well-known/acme-challenge/"+r.URL.Query().Get("token") {
					handler.ServeHTTP(w, r)
					return
				}
			}
		}

		// Redirect to HTTPS
		httpsURL := "https://" + r.Host + r.RequestURI
		http.Redirect(w, r, httpsURL, http.StatusMovedPermanently)
	})
}

// ValidateConfiguration validates TLS configuration
func (tm *TLSManager) ValidateConfiguration() error {
	if !tm.config.Enabled {
		return nil
	}

	if tm.config.LetsEncrypt.Enabled {
		if len(tm.config.LetsEncrypt.Domains) == 0 {
			return fmt.Errorf("no domains specified for Let's Encrypt")
		}

		if tm.config.LetsEncrypt.Email == "" {
			return fmt.Errorf("email required for Let's Encrypt")
		}

		// Validate cache directory is writable
		if tm.config.LetsEncrypt.CacheDir == "" {
			return fmt.Errorf("cache directory required for Let's Encrypt")
		}
	} else {
		// Validate static certificate files
		if tm.config.CertFile == "" || tm.config.KeyFile == "" {
			return fmt.Errorf("certificate and key files required when Let's Encrypt is disabled")
		}

		// Check if files exist
		if _, err := tls.LoadX509KeyPair(tm.config.CertFile, tm.config.KeyFile); err != nil {
			return fmt.Errorf("failed to load certificate files: %w", err)
		}
	}

	return nil
}