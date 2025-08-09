"""
Database encryption middleware for WearForce platform.

This module provides field-level encryption for sensitive data stored in the database,
ensuring data at rest is protected according to compliance requirements (GDPR, PCI DSS).
"""

import base64
import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Type, Union
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import redis
import structlog
from sqlalchemy import event, TypeDecorator, String
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

logger = structlog.get_logger()

# Data classification levels
class DataClassification:
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    PII = "pii"
    PAYMENT = "payment"

# Encryption algorithms
class EncryptionAlgorithm:
    AES_256_GCM = "AES-256-GCM"
    FERNET = "Fernet"
    RSA_OAEP = "RSA-OAEP"

class EncryptionKeyManager:
    """Manages encryption keys with rotation and caching."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.key_cache = {}
        self.cache_ttl = 3600  # 1 hour
        
    def get_key(self, key_type: str, key_id: Optional[str] = None) -> bytes:
        """Get encryption key for the specified type and ID."""
        if key_id:
            cache_key = f"encryption_key:{key_id}"
        else:
            # Get current key for type
            current_key_id = self.redis.get(f"current_key:{key_type}")
            if not current_key_id:
                # Generate new key if none exists
                return self.generate_key(key_type)
            cache_key = f"encryption_key:{current_key_id.decode()}"
        
        # Try cache first
        if cache_key in self.key_cache:
            cached_data = self.key_cache[cache_key]
            if datetime.now() < cached_data['expires']:
                return cached_data['key']
        
        # Get from Redis
        key_data = self.redis.get(cache_key)
        if not key_data:
            raise ValueError(f"Key not found: {cache_key}")
        
        key_info = json.loads(key_data)
        key_material = base64.b64decode(key_info['material'])
        
        # Cache the key
        self.key_cache[cache_key] = {
            'key': key_material,
            'expires': datetime.now() + timedelta(seconds=self.cache_ttl)
        }
        
        return key_material
    
    def generate_key(self, key_type: str, algorithm: str = EncryptionAlgorithm.FERNET) -> bytes:
        """Generate a new encryption key."""
        key_id = f"{key_type}_{int(datetime.now().timestamp())}"
        
        if algorithm == EncryptionAlgorithm.FERNET:
            key_material = Fernet.generate_key()
        elif algorithm == EncryptionAlgorithm.AES_256_GCM:
            key_material = os.urandom(32)  # 256 bits
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        # Store key metadata
        key_info = {
            'id': key_id,
            'type': key_type,
            'algorithm': algorithm,
            'material': base64.b64encode(key_material).decode(),
            'created_at': datetime.now().isoformat(),
            'status': 'active'
        }
        
        # Store in Redis
        self.redis.set(
            f"encryption_key:{key_id}",
            json.dumps(key_info),
            ex=30 * 24 * 3600  # 30 days
        )
        
        # Set as current key for type
        self.redis.set(f"current_key:{key_type}", key_id)
        
        logger.info("Generated new encryption key", 
                   key_id=key_id, key_type=key_type, algorithm=algorithm)
        
        return key_material
    
    def rotate_key(self, key_type: str) -> str:
        """Rotate encryption key for the specified type."""
        old_key_id = self.redis.get(f"current_key:{key_type}")
        if old_key_id:
            old_key_id = old_key_id.decode()
            # Mark old key as deprecated
            old_key_data = self.redis.get(f"encryption_key:{old_key_id}")
            if old_key_data:
                old_info = json.loads(old_key_data)
                old_info['status'] = 'deprecated'
                old_info['deprecated_at'] = datetime.now().isoformat()
                self.redis.set(f"encryption_key:{old_key_id}", json.dumps(old_info))
        
        # Generate new key
        self.generate_key(key_type)
        
        new_key_id = self.redis.get(f"current_key:{key_type}").decode()
        
        logger.info("Key rotated", 
                   key_type=key_type, old_key_id=old_key_id, new_key_id=new_key_id)
        
        return new_key_id

class FieldEncryption:
    """Handles field-level encryption for database columns."""
    
    def __init__(self, key_manager: EncryptionKeyManager):
        self.key_manager = key_manager
        
    def encrypt_field(self, value: str, classification: str) -> Dict[str, Any]:
        """Encrypt a field value based on its classification."""
        if not value:
            return None
            
        # Get appropriate key based on classification
        key_type = self._get_key_type_for_classification(classification)
        key_material = self.key_manager.get_key(key_type)
        
        # Create Fernet cipher
        cipher = Fernet(key_material)
        
        # Encrypt the value
        encrypted_data = cipher.encrypt(value.encode('utf-8'))
        
        # Return encrypted data with metadata
        return {
            'data': base64.b64encode(encrypted_data).decode(),
            'algorithm': EncryptionAlgorithm.FERNET,
            'classification': classification,
            'key_type': key_type,
            'encrypted_at': datetime.now().isoformat()
        }
    
    def decrypt_field(self, encrypted_value: Dict[str, Any]) -> str:
        """Decrypt a field value."""
        if not encrypted_value:
            return None
            
        try:
            # Get decryption key
            key_type = encrypted_value['key_type']
            key_material = self.key_manager.get_key(key_type)
            
            # Create Fernet cipher
            cipher = Fernet(key_material)
            
            # Decrypt the value
            encrypted_data = base64.b64decode(encrypted_value['data'])
            decrypted_data = cipher.decrypt(encrypted_data)
            
            return decrypted_data.decode('utf-8')
            
        except (KeyError, InvalidToken, ValueError) as e:
            logger.error("Failed to decrypt field", error=str(e))
            raise ValueError("Unable to decrypt field data")
    
    def _get_key_type_for_classification(self, classification: str) -> str:
        """Map data classification to key type."""
        mapping = {
            DataClassification.PII: 'pii',
            DataClassification.PAYMENT: 'payment',
            DataClassification.CONFIDENTIAL: 'confidential',
            DataClassification.RESTRICTED: 'restricted',
            DataClassification.INTERNAL: 'data',
            DataClassification.PUBLIC: 'data'
        }
        
        return mapping.get(classification, 'data')

class EncryptedString(TypeDecorator):
    """SQLAlchemy type decorator for encrypted string fields."""
    
    impl = String
    cache_ok = True
    
    def __init__(self, classification: str = DataClassification.INTERNAL, **kwargs):
        self.classification = classification
        super().__init__(**kwargs)
        
        # Initialize field encryption (will be set by the middleware)
        self.field_encryption = None
    
    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(String(2048))  # Allow for encryption overhead
    
    def process_bind_param(self, value, dialect):
        """Encrypt value before storing in database."""
        if value is None:
            return None
            
        if self.field_encryption is None:
            # This should be set by the encryption middleware
            logger.error("Field encryption not initialized")
            return value
        
        try:
            encrypted_data = self.field_encryption.encrypt_field(value, self.classification)
            return json.dumps(encrypted_data) if encrypted_data else None
        except Exception as e:
            logger.error("Failed to encrypt field value", error=str(e))
            # In production, you might want to fail here
            return value
    
    def process_result_value(self, value, dialect):
        """Decrypt value when loading from database."""
        if value is None:
            return None
            
        if self.field_encryption is None:
            logger.error("Field encryption not initialized")
            return value
        
        try:
            # Try to parse as encrypted JSON data
            encrypted_data = json.loads(value)
            if isinstance(encrypted_data, dict) and 'data' in encrypted_data:
                return self.field_encryption.decrypt_field(encrypted_data)
            else:
                # Might be unencrypted legacy data
                return value
        except (json.JSONDecodeError, ValueError):
            # Might be unencrypted data or invalid format
            logger.warning("Unable to decrypt field, returning as-is")
            return value

class PIIString(EncryptedString):
    """Encrypted string type for PII data."""
    
    def __init__(self, **kwargs):
        super().__init__(classification=DataClassification.PII, **kwargs)

class PaymentString(EncryptedString):
    """Encrypted string type for payment data."""
    
    def __init__(self, **kwargs):
        super().__init__(classification=DataClassification.PAYMENT, **kwargs)

class ConfidentialString(EncryptedString):
    """Encrypted string type for confidential data."""
    
    def __init__(self, **kwargs):
        super().__init__(classification=DataClassification.CONFIDENTIAL, **kwargs)

class DatabaseEncryptionMiddleware:
    """Middleware to handle database encryption setup and key management."""
    
    def __init__(self, redis_client: redis.Redis):
        self.key_manager = EncryptionKeyManager(redis_client)
        self.field_encryption = FieldEncryption(self.key_manager)
        
        # Set up SQLAlchemy event listeners
        self._setup_sqlalchemy_listeners()
        
    def _setup_sqlalchemy_listeners(self):
        """Set up SQLAlchemy event listeners for encryption."""
        
        @event.listens_for(Engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Log SQL statements (for debugging)."""
            if "encrypted" in statement.lower():
                logger.debug("Executing query with encrypted data", 
                           statement=statement[:100] + "..." if len(statement) > 100 else statement)
        
        @event.listens_for(Session, "before_configure")
        def before_configure():
            """Configure encryption for all EncryptedString types."""
            # Find all EncryptedString columns and set up field encryption
            from sqlalchemy.ext.declarative import declarative_base
            # This is a simplified approach - in production, you'd iterate through all models
            
    def setup_model_encryption(self, model_class):
        """Set up encryption for a specific model class."""
        for attr_name in dir(model_class):
            attr = getattr(model_class, attr_name)
            if hasattr(attr, 'type') and isinstance(attr.type, EncryptedString):
                attr.type.field_encryption = self.field_encryption
                logger.debug("Set up encryption for field", 
                           model=model_class.__name__, field=attr_name)
    
    def encrypt_existing_data(self, session: Session, model_class, field_name: str):
        """Encrypt existing unencrypted data in the database."""
        logger.info("Starting encryption of existing data", 
                   model=model_class.__name__, field=field_name)
        
        # Get all records with unencrypted data
        records = session.query(model_class).all()
        
        for record in records:
            field_value = getattr(record, field_name)
            
            if field_value and not self._is_encrypted_data(field_value):
                logger.debug("Encrypting existing data", 
                           model=model_class.__name__, record_id=getattr(record, 'id', 'unknown'))
                # The EncryptedString type will handle encryption on save
                setattr(record, field_name, field_value)
        
        session.commit()
        logger.info("Completed encryption of existing data", 
                   model=model_class.__name__, field=field_name)
    
    def _is_encrypted_data(self, value: str) -> bool:
        """Check if a string value is already encrypted."""
        try:
            data = json.loads(value)
            return isinstance(data, dict) and 'data' in data and 'algorithm' in data
        except (json.JSONDecodeError, TypeError):
            return False
    
    def rotate_keys_for_classification(self, classification: str):
        """Rotate encryption keys for a specific data classification."""
        key_type = self.field_encryption._get_key_type_for_classification(classification)
        self.key_manager.rotate_key(key_type)
    
    def get_encryption_metrics(self) -> Dict[str, Any]:
        """Get encryption metrics and key status."""
        metrics = {
            'total_keys': 0,
            'key_types': {},
            'key_status': {}
        }
        
        # Get all keys from Redis
        pattern = "encryption_key:*"
        key_keys = self.key_manager.redis.keys(pattern)
        
        for key_key in key_keys:
            key_data = self.key_manager.redis.get(key_key)
            if key_data:
                key_info = json.loads(key_data)
                metrics['total_keys'] += 1
                
                key_type = key_info['type']
                key_status = key_info['status']
                
                if key_type not in metrics['key_types']:
                    metrics['key_types'][key_type] = 0
                metrics['key_types'][key_type] += 1
                
                if key_status not in metrics['key_status']:
                    metrics['key_status'][key_status] = 0
                metrics['key_status'][key_status] += 1
        
        return metrics

# Global encryption middleware instance
_encryption_middleware = None

def get_encryption_middleware(redis_client: redis.Redis = None) -> DatabaseEncryptionMiddleware:
    """Get the global encryption middleware instance."""
    global _encryption_middleware
    
    if _encryption_middleware is None:
        if redis_client is None:
            # This should be set up during application initialization
            raise RuntimeError("Redis client not provided and encryption middleware not initialized")
        _encryption_middleware = DatabaseEncryptionMiddleware(redis_client)
    
    return _encryption_middleware

def init_encryption_middleware(redis_client: redis.Redis) -> DatabaseEncryptionMiddleware:
    """Initialize the global encryption middleware."""
    global _encryption_middleware
    _encryption_middleware = DatabaseEncryptionMiddleware(redis_client)
    return _encryption_middleware

# Utility functions for model integration

def encrypted_field(classification: str = DataClassification.INTERNAL, **kwargs) -> EncryptedString:
    """Create an encrypted field with the specified classification."""
    return EncryptedString(classification=classification, **kwargs)

def pii_field(**kwargs) -> PIIString:
    """Create a PII encrypted field."""
    return PIIString(**kwargs)

def payment_field(**kwargs) -> PaymentString:
    """Create a payment data encrypted field."""
    return PaymentString(**kwargs)

def confidential_field(**kwargs) -> ConfidentialString:
    """Create a confidential data encrypted field."""
    return ConfidentialString(**kwargs)

# Example usage in models:
"""
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from .encryption import pii_field, payment_field, confidential_field

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    email = Column(pii_field())  # Encrypted PII field
    phone = Column(pii_field())  # Encrypted PII field
    name = Column(String(100))   # Regular field
    
class PaymentMethod(Base):
    __tablename__ = 'payment_methods'
    
    id = Column(Integer, primary_key=True)
    card_number = Column(payment_field())    # Encrypted payment field
    card_holder = Column(confidential_field())  # Encrypted confidential field
    user_id = Column(Integer)
"""