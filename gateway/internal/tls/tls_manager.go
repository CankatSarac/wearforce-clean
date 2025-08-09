package tls

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"fmt"
	"io/fs"
	"math/big"
	"net"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"golang.org/x/crypto/acme"
	"golang.org/x/crypto/acme/autocert"
	"go.uber.org/zap"

	"github.com/wearforce/gateway/internal/config"
)

// TLSManager handles TLS certificate management and configuration
type TLSManager struct {
	config     *config.TLSConfig
	logger     *zap.Logger
	certCache  *autocert.Manager
	tlsConfig  *tls.Config
	mu         sync.RWMutex
}

// CertificateInfo contains certificate metadata
type CertificateInfo struct {
	Subject      pkix.Name
	Issuer       pkix.Name
	SerialNumber *big.Int
	NotBefore    time.Time
	NotAfter     time.Time
	DNSNames     []string
	IPAddresses  []net.IP
	KeyUsage     x509.KeyUsage
	ExtKeyUsage  []x509.ExtKeyUsage
}

// NewTLSManager creates a new TLS manager
func NewTLSManager(config *config.TLSConfig, logger *zap.Logger) (*TLSManager, error) {
	tm := &TLSManager{
		config: config,
		logger: logger,
	}

	// Initialize TLS configuration
	if err := tm.initializeTLSConfig(); err != nil {
		return nil, fmt.Errorf("failed to initialize TLS config: %w", err)
	}

	return tm, nil
}

// GetTLSConfig returns the current TLS configuration
func (tm *TLSManager) GetTLSConfig() *tls.Config {
	tm.mu.RLock()
	defer tm.mu.RUnlock()
	return tm.tlsConfig
}

// GetCertificateManager returns the autocert manager if configured
func (tm *TLSManager) GetCertificateManager() *autocert.Manager {
	return tm.certCache
}

// initializeTLSConfig initializes the TLS configuration
func (tm *TLSManager) initializeTLSConfig() error {
	tlsConfig := &tls.Config{
		MinVersion:               tm.getMinTLSVersion(),
		CurvePreferences:         tm.getCurvePreferences(),
		PreferServerCipherSuites: true,
		CipherSuites:             tm.getCipherSuites(),
		NextProtos:               []string{"h2", "http/1.1"},
	}

	if tm.config.LetsEncrypt.Enabled {
		// Configure Let's Encrypt
		tm.certCache = &autocert.Manager{
			Prompt:     autocert.AcceptTOS,
			HostPolicy: tm.hostPolicy,
			Cache:      autocert.DirCache(tm.config.LetsEncrypt.CacheDir),
			Email:      tm.config.LetsEncrypt.Email,
		}

		// Use staging server if configured
		if tm.config.LetsEncrypt.Staging {
			tm.certCache.Client = &acme.Client{
				DirectoryURL: acme.LetsEncryptStagingURL,
			}
		}

		tlsConfig.GetCertificate = tm.certCache.GetCertificate
		tm.logger.Info("Let's Encrypt configured",
			zap.Strings("domains", tm.config.LetsEncrypt.Domains),
			zap.Bool("staging", tm.config.LetsEncrypt.Staging),
		)
	} else if tm.config.CertFile != "" && tm.config.KeyFile != "" {
		// Load static certificates
		cert, err := tls.LoadX509KeyPair(tm.config.CertFile, tm.config.KeyFile)
		if err != nil {
			return fmt.Errorf("failed to load certificate: %w", err)
		}

		tlsConfig.Certificates = []tls.Certificate{cert}

		// Validate certificate
		if err := tm.validateCertificate(&cert); err != nil {
			tm.logger.Warn("Certificate validation warning", zap.Error(err))
		}

		tm.logger.Info("Static TLS certificate loaded",
			zap.String("cert_file", tm.config.CertFile),
		)
	} else {
		// Generate self-signed certificate for development
		cert, err := tm.generateSelfSignedCert()
		if err != nil {
			return fmt.Errorf("failed to generate self-signed certificate: %w", err)
		}

		tlsConfig.Certificates = []tls.Certificate{*cert}
		tm.logger.Warn("Using self-signed certificate for development")
	}

	tm.mu.Lock()
	tm.tlsConfig = tlsConfig
	tm.mu.Unlock()

	return nil
}

// hostPolicy validates domains for Let's Encrypt
func (tm *TLSManager) hostPolicy(ctx context.Context, host string) error {
	// Check if host is in allowed domains
	for _, domain := range tm.config.LetsEncrypt.Domains {
		if strings.EqualFold(host, domain) {
			return nil
		}
		
		// Check wildcard domains
		if strings.HasPrefix(domain, "*.") {
			parentDomain := domain[2:]
			if strings.HasSuffix(host, "."+parentDomain) || strings.EqualFold(host, parentDomain) {
				return nil
			}
		}
	}

	return fmt.Errorf("host %q not allowed", host)
}

// getMinTLSVersion returns the minimum TLS version
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

// getCipherSuites returns recommended cipher suites
func (tm *TLSManager) getCipherSuites() []uint16 {
	// Use configured cipher suites if provided
	if len(tm.config.CipherSuites) > 0 {
		var suites []uint16
		for _, suite := range tm.config.CipherSuites {
			if id := tm.getCipherSuiteID(suite); id != 0 {
				suites = append(suites, id)
			}
		}
		return suites
	}

	// Default secure cipher suites (TLS 1.2)
	return []uint16{
		tls.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
		tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
		tls.TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256,
		tls.TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256,
		tls.TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305,
		tls.TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305,
	}
}

// getCurvePreferences returns recommended elliptic curves
func (tm *TLSManager) getCurvePreferences() []tls.CurveID {
	return []tls.CurveID{
		tls.X25519,
		tls.CurveP256,
		tls.CurveP384,
		tls.CurveP521,
	}
}

// getCipherSuiteID maps cipher suite name to ID
func (tm *TLSManager) getCipherSuiteID(name string) uint16 {
	cipherMap := map[string]uint16{
		"TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384":   tls.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
		"TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384":     tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
		"TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256":   tls.TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256,
		"TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256":     tls.TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256,
		"TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305":    tls.TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305,
		"TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305":      tls.TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305,
	}

	return cipherMap[name]
}

// generateSelfSignedCert generates a self-signed certificate for development
func (tm *TLSManager) generateSelfSignedCert() (*tls.Certificate, error) {
	// Generate private key
	privKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		return nil, err
	}

	// Create certificate template
	template := x509.Certificate{
		SerialNumber: big.NewInt(1),
		Subject: pkix.Name{
			Organization:  []string{"WearForce Development"},
			Country:       []string{"US"},
			Province:      []string{""},
			Locality:      []string{"San Francisco"},
			StreetAddress: []string{""},
			PostalCode:    []string{""},
		},
		NotBefore:             time.Now(),
		NotAfter:              time.Now().Add(365 * 24 * time.Hour), // 1 year
		KeyUsage:              x509.KeyUsageKeyEncipherment | x509.KeyUsageDigitalSignature,
		ExtKeyUsage:           []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
		BasicConstraintsValid: true,
		DNSNames:              []string{"localhost", "*.localhost"},
		IPAddresses:           []net.IP{net.IPv4(127, 0, 0, 1), net.IPv6loopback},
	}

	// Create certificate
	certDER, err := x509.CreateCertificate(rand.Reader, &template, &template, &privKey.PublicKey, privKey)
	if err != nil {
		return nil, err
	}

	// Encode certificate and key
	certPEM := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: certDER})
	keyPEM := pem.EncodeToMemory(&pem.Block{Type: "RSA PRIVATE KEY", Bytes: x509.MarshalPKCS1PrivateKey(privKey)})

	// Load as TLS certificate
	cert, err := tls.X509KeyPair(certPEM, keyPEM)
	if err != nil {
		return nil, err
	}

	return &cert, nil
}

// validateCertificate validates a loaded certificate
func (tm *TLSManager) validateCertificate(cert *tls.Certificate) error {
	if len(cert.Certificate) == 0 {
		return fmt.Errorf("no certificates in chain")
	}

	// Parse the leaf certificate
	x509Cert, err := x509.ParseCertificate(cert.Certificate[0])
	if err != nil {
		return fmt.Errorf("failed to parse certificate: %w", err)
	}

	// Check expiration
	now := time.Now()
	if now.Before(x509Cert.NotBefore) {
		return fmt.Errorf("certificate is not valid yet (valid from %v)", x509Cert.NotBefore)
	}

	if now.After(x509Cert.NotAfter) {
		return fmt.Errorf("certificate has expired (expired on %v)", x509Cert.NotAfter)
	}

	// Warn if certificate expires soon
	if now.Add(30 * 24 * time.Hour).After(x509Cert.NotAfter) {
		tm.logger.Warn("Certificate expires soon",
			zap.Time("expires", x509Cert.NotAfter),
			zap.Duration("time_remaining", time.Until(x509Cert.NotAfter)),
		)
	}

	tm.logger.Info("Certificate validated successfully",
		zap.String("subject", x509Cert.Subject.String()),
		zap.Time("not_before", x509Cert.NotBefore),
		zap.Time("not_after", x509Cert.NotAfter),
		zap.Strings("dns_names", x509Cert.DNSNames),
	)

	return nil
}

// GetCertificateInfo returns information about the current certificate
func (tm *TLSManager) GetCertificateInfo() (*CertificateInfo, error) {
	tm.mu.RLock()
	defer tm.mu.RUnlock()

	if tm.tlsConfig == nil || len(tm.tlsConfig.Certificates) == 0 {
		return nil, fmt.Errorf("no certificates configured")
	}

	cert := tm.tlsConfig.Certificates[0]
	if len(cert.Certificate) == 0 {
		return nil, fmt.Errorf("no certificate data")
	}

	x509Cert, err := x509.ParseCertificate(cert.Certificate[0])
	if err != nil {
		return nil, fmt.Errorf("failed to parse certificate: %w", err)
	}

	return &CertificateInfo{
		Subject:      x509Cert.Subject,
		Issuer:       x509Cert.Issuer,
		SerialNumber: x509Cert.SerialNumber,
		NotBefore:    x509Cert.NotBefore,
		NotAfter:     x509Cert.NotAfter,
		DNSNames:     x509Cert.DNSNames,
		IPAddresses:  x509Cert.IPAddresses,
		KeyUsage:     x509Cert.KeyUsage,
		ExtKeyUsage:  x509Cert.ExtKeyUsage,
	}, nil
}

// ReloadCertificates reloads certificates from disk
func (tm *TLSManager) ReloadCertificates() error {
	if tm.config.CertFile == "" || tm.config.KeyFile == "" {
		return fmt.Errorf("certificate files not configured")
	}

	cert, err := tls.LoadX509KeyPair(tm.config.CertFile, tm.config.KeyFile)
	if err != nil {
		return fmt.Errorf("failed to reload certificate: %w", err)
	}

	// Validate the new certificate
	if err := tm.validateCertificate(&cert); err != nil {
		tm.logger.Warn("Reloaded certificate validation warning", zap.Error(err))
	}

	tm.mu.Lock()
	tm.tlsConfig.Certificates = []tls.Certificate{cert}
	tm.mu.Unlock()

	tm.logger.Info("Certificates reloaded successfully")
	return nil
}

// SaveCertificate saves a certificate and key to disk
func (tm *TLSManager) SaveCertificate(certPEM, keyPEM []byte, certPath, keyPath string) error {
	// Ensure directories exist
	if err := os.MkdirAll(filepath.Dir(certPath), 0755); err != nil {
		return fmt.Errorf("failed to create certificate directory: %w", err)
	}

	if err := os.MkdirAll(filepath.Dir(keyPath), 0755); err != nil {
		return fmt.Errorf("failed to create key directory: %w", err)
	}

	// Write certificate
	if err := os.WriteFile(certPath, certPEM, 0644); err != nil {
		return fmt.Errorf("failed to write certificate: %w", err)
	}

	// Write key with restricted permissions
	if err := os.WriteFile(keyPath, keyPEM, 0600); err != nil {
		return fmt.Errorf("failed to write key: %w", err)
	}

	tm.logger.Info("Certificate saved",
		zap.String("cert_path", certPath),
		zap.String("key_path", keyPath),
	)

	return nil
}

// SetupCertificateRotation sets up automatic certificate rotation monitoring
func (tm *TLSManager) SetupCertificateRotation() {
	if !tm.config.LetsEncrypt.Enabled {
		return
	}

	go tm.certificateRotationLoop()
}

// certificateRotationLoop monitors and rotates certificates
func (tm *TLSManager) certificateRotationLoop() {
	ticker := time.NewTicker(24 * time.Hour) // Check daily
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			tm.checkCertificateRenewal()
		}
	}
}

// checkCertificateRenewal checks if certificates need renewal
func (tm *TLSManager) checkCertificateRenewal() {
	if !tm.config.LetsEncrypt.Enabled || tm.certCache == nil {
		return
	}

	// Let's Encrypt certificates are automatically renewed by autocert
	// This method can be extended to handle custom renewal logic
	tm.logger.Debug("Certificate renewal check completed")
}

// GetMTLSConfig returns mTLS configuration for service-to-service communication
func (tm *TLSManager) GetMTLSConfig(clientCertPath, clientKeyPath, caCertPath string) (*tls.Config, error) {
	// Load client certificate
	clientCert, err := tls.LoadX509KeyPair(clientCertPath, clientKeyPath)
	if err != nil {
		return nil, fmt.Errorf("failed to load client certificate: %w", err)
	}

	// Load CA certificate
	caCert, err := os.ReadFile(caCertPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read CA certificate: %w", err)
	}

	caCertPool := x509.NewCertPool()
	if !caCertPool.AppendCertsFromPEM(caCert) {
		return nil, fmt.Errorf("failed to parse CA certificate")
	}

	return &tls.Config{
		Certificates: []tls.Certificate{clientCert},
		RootCAs:      caCertPool,
		ClientAuth:   tls.RequireAndVerifyClientCert,
		ClientCAs:    caCertPool,
		MinVersion:   tls.VersionTLS12,
	}, nil
}

// VerifyPeerCertificate provides custom certificate verification
func (tm *TLSManager) VerifyPeerCertificate(rawCerts [][]byte, verifiedChains [][]*x509.Certificate) error {
	// Custom certificate verification logic
	// This can be used for additional security checks

	if len(rawCerts) == 0 {
		return fmt.Errorf("no peer certificates provided")
	}

	// Parse the peer certificate
	peerCert, err := x509.ParseCertificate(rawCerts[0])
	if err != nil {
		return fmt.Errorf("failed to parse peer certificate: %w", err)
	}

	// Additional verification logic can be added here
	// For example, checking against a certificate pinning list
	tm.logger.Debug("Peer certificate verified",
		zap.String("subject", peerCert.Subject.String()),
		zap.Strings("dns_names", peerCert.DNSNames),
	)

	return nil
}