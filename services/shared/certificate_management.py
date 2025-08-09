"""
TLS/SSL Certificate Management and Key Rotation for WearForce platform.

This module handles certificate lifecycle management, automated renewal,
key rotation, and secure certificate storage.
"""

import asyncio
import base64
import json
import os
import ssl
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cryptography
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import redis
import structlog
from acme import client, messages
from acme.client import ClientV2
from josepy import JWKRSA, JWK
import httpx

logger = structlog.get_logger()


class CertificateConfig:
    """Certificate configuration settings."""
    
    def __init__(self):
        # ACME settings
        self.acme_directory_url = "https://acme-v02.api.letsencrypt.org/directory"
        self.acme_staging_url = "https://acme-staging-v02.api.letsencrypt.org/directory"
        self.use_staging = os.getenv("CERT_USE_STAGING", "false").lower() == "true"
        
        # Certificate settings
        self.key_size = 2048
        self.certificate_validity_days = 90
        self.renewal_threshold_days = 30
        
        # Storage settings
        self.cert_storage_path = Path("/etc/ssl/wearforce-clean")
        self.backup_storage_path = Path("/etc/ssl/wearforce-clean/backup")
        
        # Domains to manage
        self.domains = [
            "api.wearforce-clean.com",
            "app.wearforce-clean.com", 
            "admin.wearforce-clean.com",
            "webhooks.wearforce-clean.com"
        ]
        
        # Contact information
        self.contact_email = "security@wearforce-clean.com"
        
        # Notification settings
        self.notification_webhook = os.getenv("CERT_NOTIFICATION_WEBHOOK")
        self.notification_days_before_expiry = [30, 14, 7, 1]


class CertificateStore:
    """Secure certificate storage and retrieval."""
    
    def __init__(self, redis_client: redis.Redis, storage_path: Path):
        self.redis = redis_client
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
    async def store_certificate(self, domain: str, cert_data: Dict[str, Any]) -> bool:
        """Store certificate data securely."""
        try:
            # Store in Redis with expiration
            redis_key = f"certificate:{domain}"
            await self.redis.setex(
                redis_key,
                cert_data["expires_in_seconds"],
                json.dumps({
                    **cert_data,
                    "stored_at": datetime.now().isoformat()
                })
            )
            
            # Store certificate files on disk
            domain_path = self.storage_path / domain
            domain_path.mkdir(exist_ok=True)
            
            # Write certificate
            cert_file = domain_path / "fullchain.pem"
            with open(cert_file, 'w') as f:
                f.write(cert_data["certificate"])
            os.chmod(cert_file, 0o600)
            
            # Write private key
            key_file = domain_path / "privkey.pem"
            with open(key_file, 'w') as f:
                f.write(cert_data["private_key"])
            os.chmod(key_file, 0o600)
            
            # Write chain
            if cert_data.get("chain"):
                chain_file = domain_path / "chain.pem"
                with open(chain_file, 'w') as f:
                    f.write(cert_data["chain"])
                os.chmod(chain_file, 0o600)
            
            logger.info("Certificate stored successfully", domain=domain)
            return True
            
        except Exception as e:
            logger.error("Failed to store certificate", domain=domain, error=str(e))
            return False
    
    async def get_certificate(self, domain: str) -> Optional[Dict[str, Any]]:
        """Retrieve certificate data."""
        try:
            # Try Redis first
            redis_key = f"certificate:{domain}"
            cert_data = await self.redis.get(redis_key)
            
            if cert_data:
                return json.loads(cert_data)
            
            # Fall back to disk
            domain_path = self.storage_path / domain
            cert_file = domain_path / "fullchain.pem"
            key_file = domain_path / "privkey.pem"
            
            if cert_file.exists() and key_file.exists():
                with open(cert_file, 'r') as f:
                    certificate = f.read()
                with open(key_file, 'r') as f:
                    private_key = f.read()
                
                # Parse certificate to get expiry
                cert = x509.load_pem_x509_certificate(certificate.encode())
                expires_at = cert.not_valid_after
                expires_in_seconds = int((expires_at - datetime.now()).total_seconds())
                
                cert_data = {
                    "certificate": certificate,
                    "private_key": private_key,
                    "expires_at": expires_at.isoformat(),
                    "expires_in_seconds": expires_in_seconds,
                    "domain": domain
                }
                
                # Update Redis cache
                await self.redis.setex(
                    redis_key,
                    expires_in_seconds,
                    json.dumps(cert_data)
                )
                
                return cert_data
                
        except Exception as e:
            logger.error("Failed to retrieve certificate", domain=domain, error=str(e))
        
        return None
    
    async def list_certificates(self) -> List[Dict[str, Any]]:
        """List all stored certificates."""
        certificates = []
        
        # Get from Redis
        pattern = "certificate:*"
        keys = await self.redis.keys(pattern)
        
        for key in keys:
            try:
                cert_data = await self.redis.get(key)
                if cert_data:
                    certificates.append(json.loads(cert_data))
            except Exception as e:
                logger.warning("Failed to load certificate from Redis", key=key, error=str(e))
        
        return certificates
    
    async def backup_certificate(self, domain: str) -> bool:
        """Create backup of certificate."""
        try:
            cert_data = await self.get_certificate(domain)
            if not cert_data:
                return False
            
            # Create backup directory
            backup_path = self.storage_path.parent / "backup" / domain
            backup_path.mkdir(parents=True, exist_ok=True)
            
            # Create timestamped backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_path / f"backup_{timestamp}.json"
            
            with open(backup_file, 'w') as f:
                json.dump(cert_data, f, indent=2)
            os.chmod(backup_file, 0o600)
            
            logger.info("Certificate backup created", domain=domain, backup_file=str(backup_file))
            return True
            
        except Exception as e:
            logger.error("Failed to backup certificate", domain=domain, error=str(e))
            return False


class ACMEClient:
    """ACME client for Let's Encrypt certificate management."""
    
    def __init__(self, config: CertificateConfig, cert_store: CertificateStore):
        self.config = config
        self.cert_store = cert_store
        self.client: Optional[ClientV2] = None
        self.account_key: Optional[JWKRSA] = None
        
    async def initialize(self):
        """Initialize ACME client."""
        try:
            # Generate or load account key
            await self._setup_account_key()
            
            # Set up ACME client
            directory_url = (self.config.acme_staging_url 
                           if self.config.use_staging 
                           else self.config.acme_directory_url)
            
            directory = messages.Directory.from_json(
                await self._http_get(directory_url)
            )
            
            self.client = ClientV2(directory, net=None)
            
            # Register or retrieve account
            await self._setup_account()
            
            logger.info("ACME client initialized", 
                       directory_url=directory_url,
                       staging=self.config.use_staging)
            
        except Exception as e:
            logger.error("Failed to initialize ACME client", error=str(e))
            raise
    
    async def _setup_account_key(self):
        """Set up ACME account key."""
        account_key_path = self.config.cert_storage_path / "account.key"
        
        if account_key_path.exists():
            # Load existing account key
            with open(account_key_path, 'rb') as f:
                private_key = serialization.load_pem_private_key(
                    f.read(), 
                    password=None
                )
            self.account_key = JWKRSA(key=private_key)
            logger.info("Loaded existing ACME account key")
        else:
            # Generate new account key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=self.config.key_size
            )
            
            # Save account key
            with open(account_key_path, 'wb') as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            os.chmod(account_key_path, 0o600)
            
            self.account_key = JWKRSA(key=private_key)
            logger.info("Generated new ACME account key")
    
    async def _setup_account(self):
        """Set up ACME account."""
        # Create new account or retrieve existing
        new_reg = messages.NewRegistration.from_data(
            email=self.config.contact_email,
            terms_of_service_agreed=True
        )
        
        account = self.client.new_account(new_reg)
        logger.info("ACME account set up", account_uri=account.uri)
    
    async def _http_get(self, url: str) -> Dict[str, Any]:
        """HTTP GET request."""
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    
    async def request_certificate(self, domain: str, san_domains: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Request a new certificate."""
        try:
            if not self.client:
                await self.initialize()
            
            domains = [domain]
            if san_domains:
                domains.extend(san_domains)
            
            logger.info("Requesting certificate", domains=domains)
            
            # Generate private key for certificate
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=self.config.key_size
            )
            
            # Create CSR
            csr = self._create_csr(private_key, domains)
            
            # Request certificate
            order = self.client.new_order(csr)
            
            # Complete challenges
            for auth in order.authorizations:
                await self._complete_challenge(auth)
            
            # Finalize order
            order = self.client.poll_and_finalize(order)
            
            # Get certificate
            certificate_response = self.client.poll_and_request_issuance(order)
            certificate_pem = certificate_response.fullchain_pem
            
            # Prepare certificate data
            cert_data = {
                "domain": domain,
                "domains": domains,
                "certificate": certificate_pem,
                "private_key": private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ).decode(),
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(days=self.config.certificate_validity_days)).isoformat(),
                "expires_in_seconds": self.config.certificate_validity_days * 24 * 3600
            }
            
            # Store certificate
            if await self.cert_store.store_certificate(domain, cert_data):
                logger.info("Certificate issued successfully", domain=domain)
                return cert_data
            
        except Exception as e:
            logger.error("Failed to request certificate", domain=domain, error=str(e))
        
        return None
    
    def _create_csr(self, private_key, domains: List[str]) -> x509.CertificateSigningRequest:
        """Create certificate signing request."""
        subject = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, domains[0])
        ])
        
        builder = x509.CertificateSigningRequestBuilder().subject_name(subject)
        
        # Add SAN extension
        if len(domains) > 1:
            san_list = [x509.DNSName(domain) for domain in domains]
            builder = builder.add_extension(
                x509.SubjectAlternativeName(san_list),
                critical=False
            )
        
        csr = builder.sign(private_key, hashes.SHA256())
        return csr
    
    async def _complete_challenge(self, auth):
        """Complete ACME challenge."""
        # This is a simplified version - in production you would implement
        # HTTP-01 or DNS-01 challenge completion
        logger.info("Challenge completion would be implemented here", 
                   identifier=auth.body.identifier.value)


class CertificateManager:
    """Main certificate management class."""
    
    def __init__(self, redis_client: redis.Redis):
        self.config = CertificateConfig()
        self.cert_store = CertificateStore(redis_client, self.config.cert_storage_path)
        self.acme_client = ACMEClient(self.config, self.cert_store)
        self.redis = redis_client
        
    async def initialize(self):
        """Initialize certificate manager."""
        await self.acme_client.initialize()
        logger.info("Certificate manager initialized")
    
    async def ensure_certificates(self):
        """Ensure all required certificates are present and valid."""
        for domain in self.config.domains:
            await self.ensure_certificate(domain)
    
    async def ensure_certificate(self, domain: str) -> bool:
        """Ensure certificate exists and is valid for domain."""
        cert_data = await self.cert_store.get_certificate(domain)
        
        if cert_data:
            # Check if certificate needs renewal
            expires_at = datetime.fromisoformat(cert_data["expires_at"])
            days_until_expiry = (expires_at - datetime.now()).days
            
            if days_until_expiry > self.config.renewal_threshold_days:
                logger.info("Certificate is still valid", 
                           domain=domain, 
                           days_until_expiry=days_until_expiry)
                return True
            
            logger.info("Certificate needs renewal", 
                       domain=domain, 
                       days_until_expiry=days_until_expiry)
        
        # Request new certificate
        return await self.renew_certificate(domain)
    
    async def renew_certificate(self, domain: str) -> bool:
        """Renew certificate for domain."""
        try:
            # Backup existing certificate
            await self.cert_store.backup_certificate(domain)
            
            # Request new certificate
            cert_data = await self.acme_client.request_certificate(domain)
            
            if cert_data:
                # Send notification
                await self._send_renewal_notification(domain, "success")
                return True
            else:
                await self._send_renewal_notification(domain, "failed")
                return False
                
        except Exception as e:
            logger.error("Certificate renewal failed", domain=domain, error=str(e))
            await self._send_renewal_notification(domain, "failed", str(e))
            return False
    
    async def check_certificate_expiry(self) -> List[Dict[str, Any]]:
        """Check certificate expiry status."""
        expiry_status = []
        
        certificates = await self.cert_store.list_certificates()
        
        for cert_data in certificates:
            expires_at = datetime.fromisoformat(cert_data["expires_at"])
            days_until_expiry = (expires_at - datetime.now()).days
            
            status = {
                "domain": cert_data["domain"],
                "expires_at": cert_data["expires_at"],
                "days_until_expiry": days_until_expiry,
                "needs_renewal": days_until_expiry <= self.config.renewal_threshold_days,
                "critical": days_until_expiry <= 7
            }
            
            expiry_status.append(status)
            
            # Send notifications for expiring certificates
            if days_until_expiry in self.config.notification_days_before_expiry:
                await self._send_expiry_notification(cert_data["domain"], days_until_expiry)
        
        return expiry_status
    
    async def rotate_certificates(self):
        """Rotate certificates that need renewal."""
        logger.info("Starting certificate rotation")
        
        expiry_status = await self.check_certificate_expiry()
        
        for status in expiry_status:
            if status["needs_renewal"]:
                logger.info("Rotating certificate", domain=status["domain"])
                await self.renew_certificate(status["domain"])
        
        logger.info("Certificate rotation completed")
    
    async def _send_renewal_notification(self, domain: str, status: str, error: Optional[str] = None):
        """Send certificate renewal notification."""
        if not self.config.notification_webhook:
            return
        
        try:
            payload = {
                "event": "certificate_renewal",
                "domain": domain,
                "status": status,
                "timestamp": datetime.now().isoformat(),
                "error": error
            }
            
            async with httpx.AsyncClient() as client:
                await client.post(self.config.notification_webhook, json=payload)
            
            logger.info("Renewal notification sent", domain=domain, status=status)
            
        except Exception as e:
            logger.error("Failed to send renewal notification", error=str(e))
    
    async def _send_expiry_notification(self, domain: str, days_until_expiry: int):
        """Send certificate expiry notification."""
        if not self.config.notification_webhook:
            return
        
        try:
            payload = {
                "event": "certificate_expiry_warning",
                "domain": domain,
                "days_until_expiry": days_until_expiry,
                "timestamp": datetime.now().isoformat()
            }
            
            async with httpx.AsyncClient() as client:
                await client.post(self.config.notification_webhook, json=payload)
            
            logger.info("Expiry notification sent", domain=domain, days_until_expiry=days_until_expiry)
            
        except Exception as e:
            logger.error("Failed to send expiry notification", error=str(e))
    
    async def get_certificate_metrics(self) -> Dict[str, Any]:
        """Get certificate metrics for monitoring."""
        certificates = await self.cert_store.list_certificates()
        
        total_certs = len(certificates)
        valid_certs = 0
        expiring_soon = 0
        expired = 0
        
        for cert_data in certificates:
            expires_at = datetime.fromisoformat(cert_data["expires_at"])
            days_until_expiry = (expires_at - datetime.now()).days
            
            if days_until_expiry > self.config.renewal_threshold_days:
                valid_certs += 1
            elif days_until_expiry > 0:
                expiring_soon += 1
            else:
                expired += 1
        
        return {
            "total_certificates": total_certs,
            "valid_certificates": valid_certs,
            "expiring_soon": expiring_soon,
            "expired_certificates": expired,
            "health_score": (valid_certs / max(total_certs, 1)) * 100
        }


# Background task for certificate management
async def certificate_management_task(redis_client: redis.Redis):
    """Background task for certificate management."""
    cert_manager = CertificateManager(redis_client)
    await cert_manager.initialize()
    
    while True:
        try:
            logger.info("Starting certificate management cycle")
            
            # Check certificate expiry
            await cert_manager.check_certificate_expiry()
            
            # Rotate certificates if needed
            await cert_manager.rotate_certificates()
            
            # Store metrics
            metrics = await cert_manager.get_certificate_metrics()
            await redis_client.setex(
                "certificate_metrics",
                3600,  # 1 hour
                json.dumps(metrics)
            )
            
            logger.info("Certificate management cycle completed", metrics=metrics)
            
        except Exception as e:
            logger.error("Certificate management task error", error=str(e))
        
        # Wait 6 hours before next check
        await asyncio.sleep(6 * 3600)


# Utility functions
async def setup_certificate_management(redis_client: redis.Redis) -> CertificateManager:
    """Set up certificate management."""
    cert_manager = CertificateManager(redis_client)
    await cert_manager.initialize()
    
    # Start background task
    asyncio.create_task(certificate_management_task(redis_client))
    
    logger.info("Certificate management setup completed")
    return cert_manager


def validate_certificate_chain(certificate_pem: str) -> bool:
    """Validate certificate chain."""
    try:
        # Load certificate
        cert = x509.load_pem_x509_certificate(certificate_pem.encode())
        
        # Basic validation
        now = datetime.now()
        if now < cert.not_valid_before or now > cert.not_valid_after:
            logger.warning("Certificate is not within valid time range")
            return False
        
        # Check key usage
        try:
            key_usage = cert.extensions.get_extension_for_oid(
                x509.oid.ExtensionOID.KEY_USAGE
            ).value
            
            if not (key_usage.digital_signature and key_usage.key_encipherment):
                logger.warning("Certificate does not have required key usage")
                return False
                
        except x509.ExtensionNotFound:
            pass
        
        logger.info("Certificate validation passed")
        return True
        
    except Exception as e:
        logger.error("Certificate validation failed", error=str(e))
        return False


def get_certificate_info(certificate_pem: str) -> Dict[str, Any]:
    """Get certificate information."""
    try:
        cert = x509.load_pem_x509_certificate(certificate_pem.encode())
        
        # Extract subject
        subject_attrs = {}
        for attr in cert.subject:
            subject_attrs[attr.oid._name] = attr.value
        
        # Extract SAN
        san_domains = []
        try:
            san_ext = cert.extensions.get_extension_for_oid(
                x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            ).value
            san_domains = [name.value for name in san_ext]
        except x509.ExtensionNotFound:
            pass
        
        return {
            "subject": subject_attrs,
            "issuer": {attr.oid._name: attr.value for attr in cert.issuer},
            "serial_number": str(cert.serial_number),
            "not_valid_before": cert.not_valid_before.isoformat(),
            "not_valid_after": cert.not_valid_after.isoformat(),
            "san_domains": san_domains,
            "fingerprint": cert.fingerprint(hashes.SHA256()).hex()
        }
        
    except Exception as e:
        logger.error("Failed to extract certificate info", error=str(e))
        return {}