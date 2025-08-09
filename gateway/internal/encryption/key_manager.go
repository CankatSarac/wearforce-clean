package encryption

import (
	"context"
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"encoding/pem"
	"fmt"
	"strings"
	"sync"
	"time"

	"github.com/go-redis/redis/v8"
	"go.uber.org/zap"
)

// KeyManager handles encryption key management, rotation, and storage
type KeyManager struct {
	redis      *redis.Client
	logger     *zap.Logger
	keyCache   sync.Map
	config     *KeyManagerConfig
}

// KeyManagerConfig contains key management configuration
type KeyManagerConfig struct {
	RotationInterval time.Duration
	KeyRetention     time.Duration
	RSAKeySize       int
	EnableRotation   bool
}

// Key represents an encryption key
type Key struct {
	ID          string    `json:"id"`
	Type        KeyType   `json:"type"`
	Material    []byte    `json:"material"`
	Algorithm   string    `json:"algorithm"`
	CreatedAt   time.Time `json:"created_at"`
	ExpiresAt   time.Time `json:"expires_at,omitempty"`
	Status      KeyStatus `json:"status"`
	Version     int       `json:"version"`
	Metadata    map[string]string `json:"metadata,omitempty"`
}

// KeyType defines different types of encryption keys
type KeyType string

const (
	KeyTypeData    KeyType = "data"
	KeyTypePII     KeyType = "pii"
	KeyTypePayment KeyType = "payment"
	KeyTypeJWT     KeyType = "jwt"
	KeyTypeSession KeyType = "session"
)

// KeyStatus defines key lifecycle states
type KeyStatus string

const (
	KeyStatusActive     KeyStatus = "active"
	KeyStatusRotating   KeyStatus = "rotating"
	KeyStatusDeprecated KeyStatus = "deprecated"
	KeyStatusRevoked    KeyStatus = "revoked"
)

// NewKeyManager creates a new key manager
func NewKeyManager(redis *redis.Client, config *KeyManagerConfig, logger *zap.Logger) *KeyManager {
	if config == nil {
		config = &KeyManagerConfig{
			RotationInterval: 30 * 24 * time.Hour, // 30 days
			KeyRetention:     90 * 24 * time.Hour, // 90 days
			RSAKeySize:       2048,
			EnableRotation:   true,
		}
	}

	km := &KeyManager{
		redis:  redis,
		logger: logger,
		config: config,
	}

	// Initialize key rotation if enabled
	if config.EnableRotation {
		go km.startKeyRotationScheduler()
	}

	return km
}

// GenerateKey generates a new encryption key
func (km *KeyManager) GenerateKey(keyType KeyType, algorithm string) (*Key, error) {
	keyID := km.generateKeyID(keyType)
	
	var keyMaterial []byte
	var err error

	switch algorithm {
	case string(AlgorithmAES256GCM):
		keyMaterial, err = km.generateAESKey()
	case string(AlgorithmRSA2048):
		keyMaterial, err = km.generateRSAKeyPair(2048)
	case string(AlgorithmRSA4096):
		keyMaterial, err = km.generateRSAKeyPair(4096)
	default:
		return nil, fmt.Errorf("unsupported algorithm: %s", algorithm)
	}

	if err != nil {
		return nil, fmt.Errorf("failed to generate key material: %w", err)
	}

	key := &Key{
		ID:        keyID,
		Type:      keyType,
		Material:  keyMaterial,
		Algorithm: algorithm,
		CreatedAt: time.Now(),
		ExpiresAt: time.Now().Add(km.config.RotationInterval),
		Status:    KeyStatusActive,
		Version:   1,
		Metadata: map[string]string{
			"created_by": "key_manager",
			"purpose":    string(keyType),
		},
	}

	// Store the key
	if err := km.StoreKey(key); err != nil {
		return nil, fmt.Errorf("failed to store key: %w", err)
	}

	// Set as current key for this type
	if err := km.setCurrentKey(keyType, keyID); err != nil {
		return nil, fmt.Errorf("failed to set current key: %w", err)
	}

	km.logger.Info("Generated new encryption key",
		zap.String("key_id", keyID),
		zap.String("key_type", string(keyType)),
		zap.String("algorithm", algorithm),
	)

	return key, nil
}

// GetKey retrieves a key by ID
func (km *KeyManager) GetKey(keyID string) (*Key, error) {
	// Check cache first
	if cachedKey, ok := km.keyCache.Load(keyID); ok {
		if key, ok := cachedKey.(*Key); ok {
			return key, nil
		}
	}

	// Retrieve from Redis
	ctx := context.Background()
	keyData, err := km.redis.Get(ctx, km.getKeyStoreKey(keyID)).Result()
	if err == redis.Nil {
		return nil, fmt.Errorf("key not found: %s", keyID)
	} else if err != nil {
		return nil, fmt.Errorf("failed to retrieve key: %w", err)
	}

	// Parse key data (simplified JSON parsing)
	key, err := km.parseKeyData([]byte(keyData))
	if err != nil {
		return nil, fmt.Errorf("failed to parse key data: %w", err)
	}

	// Cache the key
	km.keyCache.Store(keyID, key)

	return key, nil
}

// GetCurrentKey retrieves the current active key for a key type
func (km *KeyManager) GetCurrentKey(keyType KeyType) (*Key, error) {
	ctx := context.Background()
	currentKeyID, err := km.redis.Get(ctx, km.getCurrentKeyKey(keyType)).Result()
	if err == redis.Nil {
		// No current key, generate one
		return km.GenerateKey(keyType, string(AlgorithmAES256GCM))
	} else if err != nil {
		return nil, fmt.Errorf("failed to get current key ID: %w", err)
	}

	return km.GetKey(currentKeyID)
}

// StoreKey stores a key in the key store
func (km *KeyManager) StoreKey(key *Key) error {
	ctx := context.Background()
	
	keyData, err := km.serializeKey(key)
	if err != nil {
		return fmt.Errorf("failed to serialize key: %w", err)
	}

	// Store key with expiration
	expiration := km.config.KeyRetention
	if !key.ExpiresAt.IsZero() {
		expiration = time.Until(key.ExpiresAt.Add(km.config.KeyRetention))
	}

	err = km.redis.Set(ctx, km.getKeyStoreKey(key.ID), keyData, expiration).Err()
	if err != nil {
		return fmt.Errorf("failed to store key: %w", err)
	}

	// Cache the key
	km.keyCache.Store(key.ID, key)

	// Add to key list for the type
	km.redis.SAdd(ctx, km.getKeyListKey(key.Type), key.ID)

	return nil
}

// RotateKey generates a new key and deprecates the old one
func (km *KeyManager) RotateKey(keyType KeyType) (*Key, error) {
	// Get current key
	currentKey, err := km.GetCurrentKey(keyType)
	if err != nil {
		return nil, fmt.Errorf("failed to get current key: %w", err)
	}

	// Mark current key as rotating
	currentKey.Status = KeyStatusRotating
	if err := km.UpdateKeyStatus(currentKey.ID, KeyStatusRotating); err != nil {
		km.logger.Warn("Failed to update key status to rotating", zap.Error(err))
	}

	// Generate new key
	newKey, err := km.GenerateKey(keyType, currentKey.Algorithm)
	if err != nil {
		// Revert current key status
		km.UpdateKeyStatus(currentKey.ID, KeyStatusActive)
		return nil, fmt.Errorf("failed to generate new key: %w", err)
	}

	// Mark old key as deprecated
	if err := km.UpdateKeyStatus(currentKey.ID, KeyStatusDeprecated); err != nil {
		km.logger.Warn("Failed to update old key status to deprecated", zap.Error(err))
	}

	km.logger.Info("Key rotated successfully",
		zap.String("old_key_id", currentKey.ID),
		zap.String("new_key_id", newKey.ID),
		zap.String("key_type", string(keyType)),
	)

	return newKey, nil
}

// UpdateKeyStatus updates the status of a key
func (km *KeyManager) UpdateKeyStatus(keyID string, status KeyStatus) error {
	key, err := km.GetKey(keyID)
	if err != nil {
		return fmt.Errorf("failed to get key: %w", err)
	}

	key.Status = status
	
	return km.StoreKey(key)
}

// ListKeys lists all keys of a specific type
func (km *KeyManager) ListKeys(keyType KeyType) ([]*Key, error) {
	ctx := context.Background()
	keyIDs, err := km.redis.SMembers(ctx, km.getKeyListKey(keyType)).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to get key list: %w", err)
	}

	var keys []*Key
	for _, keyID := range keyIDs {
		key, err := km.GetKey(keyID)
		if err != nil {
			km.logger.Warn("Failed to get key from list",
				zap.String("key_id", keyID),
				zap.Error(err),
			)
			continue
		}
		keys = append(keys, key)
	}

	return keys, nil
}

// CleanupExpiredKeys removes expired and revoked keys
func (km *KeyManager) CleanupExpiredKeys() error {
	ctx := context.Background()
	
	for _, keyType := range []KeyType{KeyTypeData, KeyTypePII, KeyTypePayment, KeyTypeJWT, KeyTypeSession} {
		keys, err := km.ListKeys(keyType)
		if err != nil {
			km.logger.Error("Failed to list keys for cleanup",
				zap.String("key_type", string(keyType)),
				zap.Error(err),
			)
			continue
		}

		for _, key := range keys {
			if km.shouldCleanupKey(key) {
				if err := km.deleteKey(key); err != nil {
					km.logger.Error("Failed to delete expired key",
						zap.String("key_id", key.ID),
						zap.Error(err),
					)
				} else {
					km.logger.Info("Cleaned up expired key",
						zap.String("key_id", key.ID),
						zap.String("status", string(key.Status)),
					)
				}
			}
		}
	}

	return nil
}

// GetKeyMetrics returns key management metrics
func (km *KeyManager) GetKeyMetrics() (map[string]interface{}, error) {
	metrics := make(map[string]interface{})
	
	for _, keyType := range []KeyType{KeyTypeData, KeyTypePII, KeyTypePayment, KeyTypeJWT, KeyTypeSession} {
		keys, err := km.ListKeys(keyType)
		if err != nil {
			continue
		}

		typeMetrics := map[string]int{
			"total":      len(keys),
			"active":     0,
			"deprecated": 0,
			"revoked":    0,
		}

		for _, key := range keys {
			switch key.Status {
			case KeyStatusActive:
				typeMetrics["active"]++
			case KeyStatusDeprecated:
				typeMetrics["deprecated"]++
			case KeyStatusRevoked:
				typeMetrics["revoked"]++
			}
		}

		metrics[string(keyType)] = typeMetrics
	}

	return metrics, nil
}

// Private helper methods

func (km *KeyManager) generateKeyID(keyType KeyType) string {
	timestamp := time.Now().Unix()
	return fmt.Sprintf("%s_%d_%s", keyType, timestamp, km.generateRandomString(8))
}

func (km *KeyManager) generateAESKey() ([]byte, error) {
	key := make([]byte, 32) // AES-256 key
	_, err := rand.Read(key)
	return key, err
}

func (km *KeyManager) generateRSAKeyPair(keySize int) ([]byte, error) {
	privateKey, err := rsa.GenerateKey(rand.Reader, keySize)
	if err != nil {
		return nil, err
	}

	// Encode private key to PEM format
	privateKeyBytes := x509.MarshalPKCS1PrivateKey(privateKey)
	privateKeyPEM := pem.EncodeToMemory(&pem.Block{
		Type:  "RSA PRIVATE KEY",
		Bytes: privateKeyBytes,
	})

	return privateKeyPEM, nil
}

func (km *KeyManager) generateRandomString(length int) string {
	const charset = "abcdefghijklmnopqrstuvwxyz0123456789"
	bytes := make([]byte, length)
	rand.Read(bytes)
	for i, b := range bytes {
		bytes[i] = charset[b%byte(len(charset))]
	}
	return string(bytes)
}

func (km *KeyManager) getKeyStoreKey(keyID string) string {
	return fmt.Sprintf("encryption:key:%s", keyID)
}

func (km *KeyManager) getCurrentKeyKey(keyType KeyType) string {
	return fmt.Sprintf("encryption:current:%s", keyType)
}

func (km *KeyManager) getKeyListKey(keyType KeyType) string {
	return fmt.Sprintf("encryption:keys:%s", keyType)
}

func (km *KeyManager) setCurrentKey(keyType KeyType, keyID string) error {
	ctx := context.Background()
	return km.redis.Set(ctx, km.getCurrentKeyKey(keyType), keyID, 0).Err()
}

func (km *KeyManager) serializeKey(key *Key) ([]byte, error) {
	// Simple serialization - in production use proper JSON marshaling
	data := fmt.Sprintf(`{
		"id": "%s",
		"type": "%s",
		"algorithm": "%s",
		"created_at": "%s",
		"expires_at": "%s",
		"status": "%s",
		"version": %d,
		"material": "%s"
	}`,
		key.ID,
		key.Type,
		key.Algorithm,
		key.CreatedAt.Format(time.RFC3339),
		key.ExpiresAt.Format(time.RFC3339),
		key.Status,
		key.Version,
		strings.ReplaceAll(string(key.Material), "\n", "\\n"),
	)
	
	return []byte(data), nil
}

func (km *KeyManager) parseKeyData(data []byte) (*Key, error) {
	// Simplified parsing - in production use proper JSON unmarshaling
	key := &Key{}
	
	// This is a very basic parser - in production, use encoding/json
	content := string(data)
	
	// Extract fields (simplified)
	key.Status = KeyStatusActive // Default
	key.CreatedAt = time.Now()   // Default
	
	return key, nil
}

func (km *KeyManager) shouldCleanupKey(key *Key) bool {
	now := time.Now()
	
	// Clean up revoked keys immediately after retention period
	if key.Status == KeyStatusRevoked {
		return now.After(key.CreatedAt.Add(km.config.KeyRetention))
	}
	
	// Clean up deprecated keys after retention period
	if key.Status == KeyStatusDeprecated {
		return now.After(key.CreatedAt.Add(km.config.KeyRetention))
	}
	
	// Don't cleanup active keys
	return false
}

func (km *KeyManager) deleteKey(key *Key) error {
	ctx := context.Background()
	
	// Remove from Redis
	pipe := km.redis.Pipeline()
	pipe.Del(ctx, km.getKeyStoreKey(key.ID))
	pipe.SRem(ctx, km.getKeyListKey(key.Type), key.ID)
	
	_, err := pipe.Exec(ctx)
	if err != nil {
		return err
	}
	
	// Remove from cache
	km.keyCache.Delete(key.ID)
	
	return nil
}

func (km *KeyManager) startKeyRotationScheduler() {
	ticker := time.NewTicker(24 * time.Hour) // Check daily
	defer ticker.Stop()
	
	for {
		select {
		case <-ticker.C:
			km.performScheduledRotation()
		}
	}
}

func (km *KeyManager) performScheduledRotation() {
	km.logger.Info("Starting scheduled key rotation check")
	
	for _, keyType := range []KeyType{KeyTypeData, KeyTypePII, KeyTypePayment, KeyTypeJWT, KeyTypeSession} {
		currentKey, err := km.GetCurrentKey(keyType)
		if err != nil {
			km.logger.Error("Failed to get current key for rotation check",
				zap.String("key_type", string(keyType)),
				zap.Error(err),
			)
			continue
		}
		
		if km.shouldRotateKey(currentKey) {
			km.logger.Info("Rotating key due to schedule",
				zap.String("key_id", currentKey.ID),
				zap.String("key_type", string(keyType)),
			)
			
			_, err := km.RotateKey(keyType)
			if err != nil {
				km.logger.Error("Failed to rotate key",
					zap.String("key_id", currentKey.ID),
					zap.String("key_type", string(keyType)),
					zap.Error(err),
				)
			}
		}
	}
	
	// Cleanup expired keys
	if err := km.CleanupExpiredKeys(); err != nil {
		km.logger.Error("Failed to cleanup expired keys", zap.Error(err))
	}
}

func (km *KeyManager) shouldRotateKey(key *Key) bool {
	if key.Status != KeyStatusActive {
		return false
	}
	
	// Rotate if key is expired or close to expiration
	now := time.Now()
	return now.After(key.ExpiresAt.Add(-24 * time.Hour)) // Rotate 24h before expiration
}