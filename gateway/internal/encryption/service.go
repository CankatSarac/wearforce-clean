package encryption

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/pem"
	"errors"
	"fmt"
	"io"
	"strings"
	"time"

	"go.uber.org/zap"
)

// EncryptionService provides encryption/decryption capabilities
type EncryptionService struct {
	keyManager *KeyManager
	logger     *zap.Logger
}

// EncryptedData represents encrypted data with metadata
type EncryptedData struct {
	Data      []byte            `json:"data"`
	KeyID     string            `json:"key_id"`
	Algorithm string            `json:"algorithm"`
	Metadata  map[string]string `json:"metadata,omitempty"`
	CreatedAt time.Time         `json:"created_at"`
}

// DataClassification defines data sensitivity levels
type DataClassification string

const (
	ClassificationPublic       DataClassification = "public"
	ClassificationInternal     DataClassification = "internal"
	ClassificationConfidential DataClassification = "confidential"
	ClassificationRestricted   DataClassification = "restricted"
	ClassificationPII          DataClassification = "pii"
	ClassificationPayment      DataClassification = "payment"
)

// EncryptionAlgorithm defines supported encryption algorithms
type EncryptionAlgorithm string

const (
	AlgorithmAES256GCM EncryptionAlgorithm = "AES-256-GCM"
	AlgorithmRSA2048   EncryptionAlgorithm = "RSA-2048"
	AlgorithmRSA4096   EncryptionAlgorithm = "RSA-4096"
)

// EncryptionOptions provides options for encryption
type EncryptionOptions struct {
	Classification DataClassification
	KeyID          string
	Algorithm      EncryptionAlgorithm
	Metadata       map[string]string
}

// NewEncryptionService creates a new encryption service
func NewEncryptionService(keyManager *KeyManager, logger *zap.Logger) *EncryptionService {
	return &EncryptionService{
		keyManager: keyManager,
		logger:     logger,
	}
}

// EncryptData encrypts data using the specified options
func (es *EncryptionService) EncryptData(plaintext []byte, opts *EncryptionOptions) (*EncryptedData, error) {
	if opts == nil {
		opts = &EncryptionOptions{
			Classification: ClassificationInternal,
			Algorithm:      AlgorithmAES256GCM,
		}
	}

	// Get appropriate key based on classification and options
	key, keyID, err := es.getEncryptionKey(opts)
	if err != nil {
		return nil, fmt.Errorf("failed to get encryption key: %w", err)
	}

	// Encrypt based on algorithm
	var ciphertext []byte
	var algorithm string

	switch opts.Algorithm {
	case AlgorithmAES256GCM, "":
		ciphertext, err = es.encryptAESGCM(plaintext, key)
		algorithm = string(AlgorithmAES256GCM)
	case AlgorithmRSA2048, AlgorithmRSA4096:
		ciphertext, err = es.encryptRSA(plaintext, key)
		algorithm = string(opts.Algorithm)
	default:
		return nil, fmt.Errorf("unsupported encryption algorithm: %s", opts.Algorithm)
	}

	if err != nil {
		return nil, fmt.Errorf("encryption failed: %w", err)
	}

	encryptedData := &EncryptedData{
		Data:      ciphertext,
		KeyID:     keyID,
		Algorithm: algorithm,
		Metadata:  opts.Metadata,
		CreatedAt: time.Now(),
	}

	// Add classification to metadata
	if encryptedData.Metadata == nil {
		encryptedData.Metadata = make(map[string]string)
	}
	encryptedData.Metadata["classification"] = string(opts.Classification)

	es.logger.Debug("Data encrypted successfully",
		zap.String("key_id", keyID),
		zap.String("algorithm", algorithm),
		zap.String("classification", string(opts.Classification)),
		zap.Int("plaintext_size", len(plaintext)),
		zap.Int("ciphertext_size", len(ciphertext)),
	)

	return encryptedData, nil
}

// DecryptData decrypts encrypted data
func (es *EncryptionService) DecryptData(encryptedData *EncryptedData) ([]byte, error) {
	// Get decryption key
	key, err := es.keyManager.GetKey(encryptedData.KeyID)
	if err != nil {
		return nil, fmt.Errorf("failed to get decryption key: %w", err)
	}

	// Decrypt based on algorithm
	var plaintext []byte

	switch encryptedData.Algorithm {
	case string(AlgorithmAES256GCM):
		plaintext, err = es.decryptAESGCM(encryptedData.Data, key.Material)
	case string(AlgorithmRSA2048), string(AlgorithmRSA4096):
		plaintext, err = es.decryptRSA(encryptedData.Data, key.Material)
	default:
		return nil, fmt.Errorf("unsupported decryption algorithm: %s", encryptedData.Algorithm)
	}

	if err != nil {
		return nil, fmt.Errorf("decryption failed: %w", err)
	}

	es.logger.Debug("Data decrypted successfully",
		zap.String("key_id", encryptedData.KeyID),
		zap.String("algorithm", encryptedData.Algorithm),
		zap.Int("ciphertext_size", len(encryptedData.Data)),
		zap.Int("plaintext_size", len(plaintext)),
	)

	return plaintext, nil
}

// EncryptString encrypts a string and returns base64 encoded result
func (es *EncryptionService) EncryptString(plaintext string, opts *EncryptionOptions) (string, error) {
	encryptedData, err := es.EncryptData([]byte(plaintext), opts)
	if err != nil {
		return "", err
	}

	// Encode the entire encrypted data structure
	return es.encodeEncryptedData(encryptedData), nil
}

// DecryptString decrypts a base64 encoded string
func (es *EncryptionService) DecryptString(encodedData string) (string, error) {
	encryptedData, err := es.decodeEncryptedData(encodedData)
	if err != nil {
		return "", fmt.Errorf("failed to decode encrypted data: %w", err)
	}

	plaintext, err := es.DecryptData(encryptedData)
	if err != nil {
		return "", err
	}

	return string(plaintext), nil
}

// EncryptPII encrypts personally identifiable information with enhanced security
func (es *EncryptionService) EncryptPII(plaintext []byte) (*EncryptedData, error) {
	opts := &EncryptionOptions{
		Classification: ClassificationPII,
		Algorithm:      AlgorithmAES256GCM,
		Metadata: map[string]string{
			"purpose": "pii_protection",
			"compliance": "gdpr",
		},
	}

	return es.EncryptData(plaintext, opts)
}

// EncryptPaymentData encrypts payment-related data with PCI DSS compliance
func (es *EncryptionService) EncryptPaymentData(plaintext []byte) (*EncryptedData, error) {
	opts := &EncryptionOptions{
		Classification: ClassificationPayment,
		Algorithm:      AlgorithmAES256GCM,
		Metadata: map[string]string{
			"purpose": "payment_protection",
			"compliance": "pci_dss",
		},
	}

	return es.EncryptData(plaintext, opts)
}

// getEncryptionKey retrieves the appropriate encryption key
func (es *EncryptionService) getEncryptionKey(opts *EncryptionOptions) ([]byte, string, error) {
	// If specific key ID is provided, use it
	if opts.KeyID != "" {
		key, err := es.keyManager.GetKey(opts.KeyID)
		if err != nil {
			return nil, "", err
		}
		return key.Material, key.ID, nil
	}

	// Otherwise, get key based on classification
	var keyType KeyType
	switch opts.Classification {
	case ClassificationPII:
		keyType = KeyTypePII
	case ClassificationPayment:
		keyType = KeyTypePayment
	default:
		keyType = KeyTypeData
	}

	key, err := es.keyManager.GetCurrentKey(keyType)
	if err != nil {
		return nil, "", err
	}

	return key.Material, key.ID, nil
}

// encryptAESGCM encrypts data using AES-256-GCM
func (es *EncryptionService) encryptAESGCM(plaintext, key []byte) ([]byte, error) {
	// Ensure key is 32 bytes for AES-256
	if len(key) != 32 {
		return nil, errors.New("key must be 32 bytes for AES-256")
	}

	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, err
	}

	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}

	// Generate random nonce
	nonce := make([]byte, gcm.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return nil, err
	}

	// Encrypt and authenticate
	ciphertext := gcm.Seal(nonce, nonce, plaintext, nil)
	return ciphertext, nil
}

// decryptAESGCM decrypts data using AES-256-GCM
func (es *EncryptionService) decryptAESGCM(ciphertext, key []byte) ([]byte, error) {
	// Ensure key is 32 bytes for AES-256
	if len(key) != 32 {
		return nil, errors.New("key must be 32 bytes for AES-256")
	}

	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, err
	}

	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}

	nonceSize := gcm.NonceSize()
	if len(ciphertext) < nonceSize {
		return nil, errors.New("ciphertext too short")
	}

	// Extract nonce and ciphertext
	nonce, ciphertext := ciphertext[:nonceSize], ciphertext[nonceSize:]

	// Decrypt and verify
	plaintext, err := gcm.Open(nil, nonce, ciphertext, nil)
	if err != nil {
		return nil, err
	}

	return plaintext, nil
}

// encryptRSA encrypts data using RSA-OAEP
func (es *EncryptionService) encryptRSA(plaintext, keyBytes []byte) ([]byte, error) {
	// Parse the public key
	block, _ := pem.Decode(keyBytes)
	if block == nil {
		return nil, errors.New("failed to parse PEM block")
	}

	pubKey, err := x509.ParsePKIXPublicKey(block.Bytes)
	if err != nil {
		return nil, err
	}

	rsaPubKey, ok := pubKey.(*rsa.PublicKey)
	if !ok {
		return nil, errors.New("not an RSA public key")
	}

	// RSA can only encrypt small amounts of data
	// For larger data, we should use hybrid encryption (RSA + AES)
	if len(plaintext) > rsaPubKey.Size()-2*sha256.Size-2 {
		return es.hybridEncrypt(plaintext, rsaPubKey)
	}

	// Direct RSA encryption for small data
	ciphertext, err := rsa.EncryptOAEP(sha256.New(), rand.Reader, rsaPubKey, plaintext, nil)
	if err != nil {
		return nil, err
	}

	return ciphertext, nil
}

// decryptRSA decrypts data using RSA-OAEP
func (es *EncryptionService) decryptRSA(ciphertext, keyBytes []byte) ([]byte, error) {
	// Parse the private key
	block, _ := pem.Decode(keyBytes)
	if block == nil {
		return nil, errors.New("failed to parse PEM block")
	}

	privKey, err := x509.ParsePKCS1PrivateKey(block.Bytes)
	if err != nil {
		return nil, err
	}

	// Check if this is hybrid encrypted data
	if len(ciphertext) > privKey.Size() {
		return es.hybridDecrypt(ciphertext, privKey)
	}

	// Direct RSA decryption
	plaintext, err := rsa.DecryptOAEP(sha256.New(), rand.Reader, privKey, ciphertext, nil)
	if err != nil {
		return nil, err
	}

	return plaintext, nil
}

// hybridEncrypt implements RSA + AES hybrid encryption
func (es *EncryptionService) hybridEncrypt(plaintext []byte, pubKey *rsa.PublicKey) ([]byte, error) {
	// Generate random AES key
	aesKey := make([]byte, 32) // AES-256
	if _, err := io.ReadFull(rand.Reader, aesKey); err != nil {
		return nil, err
	}

	// Encrypt data with AES
	aesData, err := es.encryptAESGCM(plaintext, aesKey)
	if err != nil {
		return nil, err
	}

	// Encrypt AES key with RSA
	encryptedKey, err := rsa.EncryptOAEP(sha256.New(), rand.Reader, pubKey, aesKey, nil)
	if err != nil {
		return nil, err
	}

	// Combine: [encrypted_key_length][encrypted_key][encrypted_data]
	keyLengthBytes := []byte{byte(len(encryptedKey) >> 8), byte(len(encryptedKey))}
	result := append(keyLengthBytes, encryptedKey...)
	result = append(result, aesData...)

	return result, nil
}

// hybridDecrypt implements RSA + AES hybrid decryption
func (es *EncryptionService) hybridDecrypt(ciphertext []byte, privKey *rsa.PrivateKey) ([]byte, error) {
	if len(ciphertext) < 2 {
		return nil, errors.New("invalid hybrid ciphertext")
	}

	// Extract encrypted key length
	keyLength := int(ciphertext[0])<<8 + int(ciphertext[1])
	if len(ciphertext) < 2+keyLength {
		return nil, errors.New("invalid hybrid ciphertext format")
	}

	// Extract encrypted AES key and data
	encryptedKey := ciphertext[2 : 2+keyLength]
	encryptedData := ciphertext[2+keyLength:]

	// Decrypt AES key with RSA
	aesKey, err := rsa.DecryptOAEP(sha256.New(), rand.Reader, privKey, encryptedKey, nil)
	if err != nil {
		return nil, err
	}

	// Decrypt data with AES
	plaintext, err := es.decryptAESGCM(encryptedData, aesKey)
	if err != nil {
		return nil, err
	}

	return plaintext, nil
}

// encodeEncryptedData encodes EncryptedData to base64 string
func (es *EncryptionService) encodeEncryptedData(data *EncryptedData) string {
	// Create a simple format: keyid:algorithm:base64(data):base64(metadata)
	metadataBytes, _ := es.encodeMetadata(data.Metadata)
	
	encoded := fmt.Sprintf("%s:%s:%s:%s",
		data.KeyID,
		data.Algorithm,
		base64.StdEncoding.EncodeToString(data.Data),
		base64.StdEncoding.EncodeToString(metadataBytes),
	)
	
	return base64.StdEncoding.EncodeToString([]byte(encoded))
}

// decodeEncryptedData decodes base64 string to EncryptedData
func (es *EncryptionService) decodeEncryptedData(encoded string) (*EncryptedData, error) {
	decoded, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil {
		return nil, err
	}

	parts := string(decoded)
	components := strings.SplitN(parts, ":", 4)
	if len(components) != 4 {
		return nil, errors.New("invalid encrypted data format")
	}

	data, err := base64.StdEncoding.DecodeString(components[2])
	if err != nil {
		return nil, err
	}

	metadataBytes, err := base64.StdEncoding.DecodeString(components[3])
	if err != nil {
		return nil, err
	}

	metadata, err := es.decodeMetadata(metadataBytes)
	if err != nil {
		return nil, err
	}

	return &EncryptedData{
		Data:      data,
		KeyID:     components[0],
		Algorithm: components[1],
		Metadata:  metadata,
		CreatedAt: time.Now(), // We lose the original timestamp in this format
	}, nil
}

// Helper functions for metadata encoding/decoding
func (es *EncryptionService) encodeMetadata(metadata map[string]string) ([]byte, error) {
	if metadata == nil {
		return []byte("{}"), nil
	}
	
	// Simple JSON encoding for metadata
	result := "{"
	first := true
	for k, v := range metadata {
		if !first {
			result += ","
		}
		result += fmt.Sprintf(`"%s":"%s"`, k, v)
		first = false
	}
	result += "}"
	
	return []byte(result), nil
}

func (es *EncryptionService) decodeMetadata(data []byte) (map[string]string, error) {
	// Simple JSON-like parsing for metadata
	s := string(data)
	if s == "{}" {
		return make(map[string]string), nil
	}
	
	// This is a simplified parser - in production, use proper JSON
	metadata := make(map[string]string)
	return metadata, nil
}

// ValidateEncryptedData validates the integrity and format of encrypted data
func (es *EncryptionService) ValidateEncryptedData(encryptedData *EncryptedData) error {
	if encryptedData == nil {
		return errors.New("encrypted data is nil")
	}

	if encryptedData.KeyID == "" {
		return errors.New("missing key ID")
	}

	if encryptedData.Algorithm == "" {
		return errors.New("missing algorithm")
	}

	if len(encryptedData.Data) == 0 {
		return errors.New("empty encrypted data")
	}

	// Validate algorithm
	switch encryptedData.Algorithm {
	case string(AlgorithmAES256GCM), string(AlgorithmRSA2048), string(AlgorithmRSA4096):
		// Valid algorithms
	default:
		return fmt.Errorf("unsupported algorithm: %s", encryptedData.Algorithm)
	}

	// Check if key exists
	_, err := es.keyManager.GetKey(encryptedData.KeyID)
	if err != nil {
		return fmt.Errorf("key not found: %w", err)
	}

	return nil
}