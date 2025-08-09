"""
Enhanced security middleware for WearForce platform.

This module provides comprehensive security features including rate limiting,
input validation, DDoS protection, security headers, and CORS policies.
"""

import asyncio
import hashlib
import hmac
import ipaddress
import json
import re
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import quote, unquote

import redis
import structlog
from fastapi import HTTPException, Request, Response, status
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.security.utils import get_authorization_scheme_param
from pydantic import BaseModel, ValidationError, validator
import httpx
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from starlette.middleware.base import RequestResponseEndpoint

logger = structlog.get_logger()

# Security configuration
class SecurityConfig(BaseModel):
    # Rate limiting
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000
    rate_limit_burst: int = 10
    
    # DDoS protection
    max_requests_per_ip: int = 100
    ddos_detection_window: int = 60  # seconds
    ddos_block_duration: int = 300   # seconds
    
    # Input validation
    max_request_size: int = 10 * 1024 * 1024  # 10MB
    max_json_depth: int = 10
    max_array_size: int = 1000
    
    # API key management
    api_key_header: str = "X-API-Key"
    api_key_rotation_days: int = 30
    
    # Security headers
    enable_security_headers: bool = True
    hsts_max_age: int = 31536000  # 1 year
    
    # CORS configuration
    cors_origins: List[str] = ["https://app.wearforce-clean.com", "https://admin.wearforce-clean.com"]
    cors_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_headers: List[str] = ["*"]
    
    # IP whitelist/blacklist
    whitelist_ips: List[str] = []
    blacklist_ips: List[str] = []
    trusted_proxies: List[str] = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
    
    # Bot detection
    bot_user_agents: List[str] = [
        "bot", "crawler", "spider", "scraper", "scanner",
        "curl", "wget", "python-requests", "httpx"
    ]
    
    # Honeypot endpoints
    honeypot_endpoints: List[str] = ["/admin.php", "/wp-admin", "/.env", "/config"]


class RequestMetrics:
    """Track request metrics for security analysis."""
    
    def __init__(self):
        self.ip_requests: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.endpoint_requests: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.failed_auths: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.blocked_ips: Dict[str, datetime] = {}
        
    def add_request(self, ip: str, endpoint: str, timestamp: float):
        self.ip_requests[ip].append(timestamp)
        self.endpoint_requests[endpoint].append(timestamp)
    
    def add_failed_auth(self, ip: str, timestamp: float):
        self.failed_auths[ip].append(timestamp)
    
    def is_ip_blocked(self, ip: str) -> bool:
        if ip in self.blocked_ips:
            if datetime.now() < self.blocked_ips[ip]:
                return True
            else:
                del self.blocked_ips[ip]
        return False
    
    def block_ip(self, ip: str, duration: int):
        self.blocked_ips[ip] = datetime.now() + timedelta(seconds=duration)
        logger.warning("IP blocked due to suspicious activity", ip=ip, duration=duration)
    
    def cleanup_old_data(self):
        """Clean up old request data."""
        current_time = time.time()
        cutoff_time = current_time - 3600  # Keep last hour
        
        for ip_queue in self.ip_requests.values():
            while ip_queue and ip_queue[0] < cutoff_time:
                ip_queue.popleft()


class InputValidator:
    """Validate and sanitize input data."""
    
    @staticmethod
    def validate_json_depth(data: Any, max_depth: int, current_depth: int = 0) -> bool:
        if current_depth > max_depth:
            return False
        
        if isinstance(data, dict):
            for value in data.values():
                if not InputValidator.validate_json_depth(value, max_depth, current_depth + 1):
                    return False
        elif isinstance(data, list):
            for item in data:
                if not InputValidator.validate_json_depth(item, max_depth, current_depth + 1):
                    return False
        
        return True
    
    @staticmethod
    def validate_array_size(data: Any, max_size: int) -> bool:
        if isinstance(data, list) and len(data) > max_size:
            return False
        elif isinstance(data, dict):
            for value in data.values():
                if not InputValidator.validate_array_size(value, max_size):
                    return False
        elif isinstance(data, list):
            for item in data:
                if not InputValidator.validate_array_size(item, max_size):
                    return False
        
        return True
    
    @staticmethod
    def sanitize_string(value: str) -> str:
        """Sanitize string input to prevent injection attacks."""
        # Remove null bytes
        value = value.replace('\x00', '')
        
        # HTML encode dangerous characters
        dangerous_chars = {
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;',
            '/': '&#x2F;'
        }
        
        for char, encoded in dangerous_chars.items():
            value = value.replace(char, encoded)
        
        return value
    
    @staticmethod
    def validate_sql_injection(value: str) -> bool:
        """Check for SQL injection patterns."""
        sql_patterns = [
            r"(?i)(union.*select)",
            r"(?i)(insert.*into)",
            r"(?i)(delete.*from)",
            r"(?i)(drop.*table)",
            r"(?i)(exec.*xp_)",
            r"(?i)(sp_executesql)",
            r"(?i)('.*or.*'=')",
            r"(?i)(--)",
            r"(?i)(;.*drop)",
            r"(?i)(waitfor.*delay)"
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, value):
                return False
        
        return True
    
    @staticmethod
    def validate_xss(value: str) -> bool:
        """Check for XSS patterns."""
        xss_patterns = [
            r"(?i)<script",
            r"(?i)<iframe",
            r"(?i)<object",
            r"(?i)<embed",
            r"(?i)javascript:",
            r"(?i)vbscript:",
            r"(?i)onload=",
            r"(?i)onerror=",
            r"(?i)onclick=",
            r"(?i)onfocus="
        ]
        
        for pattern in xss_patterns:
            if re.search(pattern, value):
                return False
        
        return True


class APIKeyManager:
    """Manage API keys with rotation and validation."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.key_prefix = "api_key:"
        
    async def generate_api_key(self, user_id: str, permissions: List[str], 
                             expires_days: int = 30) -> str:
        """Generate a new API key."""
        key_data = {
            "key_id": str(uuid.uuid4()),
            "user_id": user_id,
            "permissions": permissions,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=expires_days)).isoformat(),
            "active": True,
            "last_used": None,
            "usage_count": 0
        }
        
        # Create API key hash
        api_key = f"wf_{key_data['key_id'].replace('-', '')[:16]}"
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Store in Redis
        await self.redis.setex(
            f"{self.key_prefix}{key_hash}",
            expires_days * 24 * 3600,
            json.dumps(key_data)
        )
        
        logger.info("API key generated", user_id=user_id, key_id=key_data['key_id'])
        return api_key
    
    async def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Validate an API key."""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        key_data_raw = await self.redis.get(f"{self.key_prefix}{key_hash}")
        
        if not key_data_raw:
            return None
        
        key_data = json.loads(key_data_raw)
        
        # Check if key is active
        if not key_data.get("active", False):
            return None
        
        # Check expiration
        expires_at = datetime.fromisoformat(key_data["expires_at"])
        if datetime.now() > expires_at:
            return None
        
        # Update usage statistics
        key_data["last_used"] = datetime.now().isoformat()
        key_data["usage_count"] = key_data.get("usage_count", 0) + 1
        
        # Update in Redis
        await self.redis.setex(
            f"{self.key_prefix}{key_hash}",
            int((expires_at - datetime.now()).total_seconds()),
            json.dumps(key_data)
        )
        
        return key_data
    
    async def revoke_api_key(self, api_key: str) -> bool:
        """Revoke an API key."""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        key_data_raw = await self.redis.get(f"{self.key_prefix}{key_hash}")
        
        if not key_data_raw:
            return False
        
        key_data = json.loads(key_data_raw)
        key_data["active"] = False
        key_data["revoked_at"] = datetime.now().isoformat()
        
        await self.redis.set(f"{self.key_prefix}{key_hash}", json.dumps(key_data))
        logger.info("API key revoked", key_id=key_data.get("key_id"))
        return True
    
    async def rotate_api_keys(self, days_before_expiry: int = 7):
        """Rotate API keys that are close to expiration."""
        # This would be implemented as a background task
        logger.info("API key rotation initiated", days_before_expiry=days_before_expiry)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Comprehensive security middleware."""
    
    def __init__(self, app, config: SecurityConfig, redis_client: redis.Redis):
        super().__init__(app)
        self.config = config
        self.redis = redis_client
        self.metrics = RequestMetrics()
        self.api_key_manager = APIKeyManager(redis_client)
        self.validator = InputValidator()
        
        # Set up rate limiter
        self.limiter = Limiter(
            key_func=get_remote_address,
            storage_uri=f"redis://{redis_client.connection_pool.connection_kwargs['host']}:"
                       f"{redis_client.connection_pool.connection_kwargs['port']}"
        )
        
        # Compile IP networks for efficiency
        self.whitelist_networks = [ipaddress.ip_network(ip, strict=False) 
                                 for ip in config.whitelist_ips]
        self.blacklist_networks = [ipaddress.ip_network(ip, strict=False) 
                                 for ip in config.blacklist_ips]
        self.trusted_proxy_networks = [ipaddress.ip_network(ip, strict=False) 
                                     for ip in config.trusted_proxies]
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.time()
        
        try:
            # Get real client IP
            client_ip = await self._get_real_client_ip(request)
            request.state.client_ip = client_ip
            
            # Security checks
            await self._check_ip_whitelist_blacklist(client_ip)
            await self._check_ddos_protection(client_ip, request)
            await self._check_bot_detection(request)
            await self._check_honeypot(request)
            await self._validate_request_size(request)
            await self._validate_input(request)
            await self._check_api_key(request)
            
            # Process request
            response = await call_next(request)
            
            # Add security headers
            if self.config.enable_security_headers:
                self._add_security_headers(response)
            
            # Log metrics
            processing_time = time.time() - start_time
            await self._log_request_metrics(request, response, processing_time)
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Security middleware error", error=str(e), path=request.url.path)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Security validation failed"
            )
    
    async def _get_real_client_ip(self, request: Request) -> str:
        """Get the real client IP address, considering trusted proxies."""
        # Check X-Forwarded-For header from trusted proxies
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Get the first IP in the chain
            client_ip = forwarded_for.split(',')[0].strip()
            try:
                ip_addr = ipaddress.ip_address(client_ip)
                # Verify the request comes from a trusted proxy
                if request.client and any(
                    ipaddress.ip_address(request.client.host) in network
                    for network in self.trusted_proxy_networks
                ):
                    return str(ip_addr)
            except ValueError:
                pass
        
        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            try:
                return str(ipaddress.ip_address(real_ip))
            except ValueError:
                pass
        
        # Fall back to direct connection IP
        return request.client.host if request.client else "unknown"
    
    async def _check_ip_whitelist_blacklist(self, client_ip: str):
        """Check IP whitelist and blacklist."""
        try:
            ip_addr = ipaddress.ip_address(client_ip)
            
            # Check blacklist first
            for network in self.blacklist_networks:
                if ip_addr in network:
                    logger.warning("Blocked blacklisted IP", ip=client_ip)
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied"
                    )
            
            # Check whitelist (if configured)
            if self.whitelist_networks:
                allowed = any(ip_addr in network for network in self.whitelist_networks)
                if not allowed:
                    logger.warning("Blocked non-whitelisted IP", ip=client_ip)
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied"
                    )
        
        except ValueError:
            logger.warning("Invalid IP address", ip=client_ip)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid client IP"
            )
    
    async def _check_ddos_protection(self, client_ip: str, request: Request):
        """Check for DDoS attacks."""
        current_time = time.time()
        
        # Check if IP is already blocked
        if self.metrics.is_ip_blocked(client_ip):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="IP temporarily blocked due to suspicious activity"
            )
        
        # Add current request
        self.metrics.add_request(client_ip, request.url.path, current_time)
        
        # Check request rate
        ip_requests = self.metrics.ip_requests[client_ip]
        window_start = current_time - self.config.ddos_detection_window
        recent_requests = [req for req in ip_requests if req > window_start]
        
        if len(recent_requests) > self.config.max_requests_per_ip:
            self.metrics.block_ip(client_ip, self.config.ddos_block_duration)
            logger.warning(
                "DDoS attack detected, blocking IP",
                ip=client_ip,
                requests_in_window=len(recent_requests),
                window_seconds=self.config.ddos_detection_window
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests, IP blocked temporarily"
            )
    
    async def _check_bot_detection(self, request: Request):
        """Detect and block bots."""
        user_agent = request.headers.get("user-agent", "").lower()
        
        # Check for bot user agents
        for bot_pattern in self.config.bot_user_agents:
            if bot_pattern in user_agent:
                logger.info("Bot detected", user_agent=user_agent, ip=request.state.client_ip)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bot access not allowed"
                )
        
        # Check for missing user agent
        if not user_agent:
            logger.warning("Request with no user agent", ip=request.state.client_ip)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User agent required"
            )
    
    async def _check_honeypot(self, request: Request):
        """Check for honeypot endpoint access."""
        path = request.url.path.lower()
        
        for honeypot in self.config.honeypot_endpoints:
            if honeypot in path:
                logger.warning(
                    "Honeypot endpoint accessed",
                    path=path,
                    ip=request.state.client_ip,
                    user_agent=request.headers.get("user-agent")
                )
                # Block the IP
                self.metrics.block_ip(request.state.client_ip, self.config.ddos_block_duration * 2)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Not found"
                )
    
    async def _validate_request_size(self, request: Request):
        """Validate request size."""
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.config.max_request_size:
            logger.warning(
                "Request too large",
                content_length=content_length,
                max_size=self.config.max_request_size,
                ip=request.state.client_ip
            )
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Request too large"
            )
    
    async def _validate_input(self, request: Request):
        """Validate and sanitize input data."""
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                # Read request body
                body = await request.body()
                if not body:
                    return
                
                # Parse JSON if applicable
                content_type = request.headers.get("content-type", "")
                if "application/json" in content_type:
                    try:
                        json_data = json.loads(body.decode())
                        
                        # Validate JSON depth
                        if not self.validator.validate_json_depth(json_data, self.config.max_json_depth):
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="JSON nesting too deep"
                            )
                        
                        # Validate array sizes
                        if not self.validator.validate_array_size(json_data, self.config.max_array_size):
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Array too large"
                            )
                        
                        # Check for injection attacks
                        await self._validate_json_security(json_data)
                        
                    except json.JSONDecodeError:
                        logger.warning("Invalid JSON in request", ip=request.state.client_ip)
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid JSON"
                        )
            
            except Exception as e:
                if isinstance(e, HTTPException):
                    raise
                logger.error("Input validation error", error=str(e))
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Input validation failed"
                )
    
    async def _validate_json_security(self, data: Any):
        """Recursively validate JSON data for security issues."""
        if isinstance(data, dict):
            for key, value in data.items():
                await self._validate_string_security(str(key))
                await self._validate_json_security(value)
        elif isinstance(data, list):
            for item in data:
                await self._validate_json_security(item)
        elif isinstance(data, str):
            await self._validate_string_security(data)
    
    async def _validate_string_security(self, value: str):
        """Validate string for security issues."""
        # Check for SQL injection
        if not self.validator.validate_sql_injection(value):
            logger.warning("SQL injection attempt detected", ip=getattr(request, 'state', {}).get('client_ip'))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid input detected"
            )
        
        # Check for XSS
        if not self.validator.validate_xss(value):
            logger.warning("XSS attempt detected", ip=getattr(request, 'state', {}).get('client_ip'))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid input detected"
            )
    
    async def _check_api_key(self, request: Request):
        """Validate API key if present."""
        api_key = request.headers.get(self.config.api_key_header)
        if api_key:
            key_data = await self.api_key_manager.validate_api_key(api_key)
            if not key_data:
                logger.warning("Invalid API key", ip=request.state.client_ip)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API key"
                )
            
            # Add key data to request state
            request.state.api_key_data = key_data
    
    def _add_security_headers(self, response: Response):
        """Add security headers to response."""
        # HSTS
        response.headers["Strict-Transport-Security"] = f"max-age={self.config.hsts_max_age}; includeSubDomains"
        
        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        
        # Other security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # Remove server information
        response.headers.pop("server", None)
    
    async def _log_request_metrics(self, request: Request, response: Response, processing_time: float):
        """Log request metrics for security analysis."""
        metrics_data = {
            "timestamp": datetime.now().isoformat(),
            "client_ip": request.state.client_ip,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "processing_time": processing_time,
            "user_agent": request.headers.get("user-agent"),
            "referer": request.headers.get("referer"),
            "content_length": request.headers.get("content-length", 0),
        }
        
        # Add API key info if present
        if hasattr(request.state, 'api_key_data'):
            metrics_data["api_key_user"] = request.state.api_key_data.get("user_id")
        
        # Store metrics in Redis for analysis
        await self.redis.lpush(
            "security_metrics",
            json.dumps(metrics_data)
        )
        
        # Keep only last 10000 entries
        await self.redis.ltrim("security_metrics", 0, 9999)


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Advanced rate limiting middleware."""
    
    def __init__(self, app, redis_client: redis.Redis):
        super().__init__(app)
        self.redis = redis_client
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Get client identifier (IP or API key)
        client_id = await self._get_client_id(request)
        
        # Check rate limits
        await self._check_rate_limits(client_id, request)
        
        # Process request
        response = await call_next(request)
        
        # Update rate limit counters
        await self._update_rate_limit_counters(client_id, request)
        
        return response
    
    async def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Use API key if available
        if hasattr(request.state, 'api_key_data'):
            return f"apikey:{request.state.api_key_data['key_id']}"
        
        # Use IP address
        return f"ip:{request.state.client_ip}"
    
    async def _check_rate_limits(self, client_id: str, request: Request):
        """Check if client has exceeded rate limits."""
        current_time = int(time.time())
        
        # Different limits for different endpoint categories
        limits = await self._get_rate_limits(request)
        
        for limit_type, (max_requests, window_seconds) in limits.items():
            key = f"rate_limit:{client_id}:{limit_type}:{current_time // window_seconds}"
            
            # Get current count
            current_count = await self.redis.get(key)
            current_count = int(current_count) if current_count else 0
            
            if current_count >= max_requests:
                logger.warning(
                    "Rate limit exceeded",
                    client_id=client_id,
                    limit_type=limit_type,
                    current_count=current_count,
                    max_requests=max_requests
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded for {limit_type}",
                    headers={"Retry-After": str(window_seconds)}
                )
    
    async def _get_rate_limits(self, request: Request) -> Dict[str, Tuple[int, int]]:
        """Get rate limits based on request characteristics."""
        # Base limits
        limits = {
            "general": (100, 60),  # 100 requests per minute
            "hourly": (1000, 3600)  # 1000 requests per hour
        }
        
        # Stricter limits for write operations
        if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            limits["write"] = (20, 60)  # 20 write operations per minute
        
        # Stricter limits for admin endpoints
        if "/admin" in request.url.path:
            limits["admin"] = (10, 60)  # 10 admin requests per minute
        
        # Different limits for API key users
        if hasattr(request.state, 'api_key_data'):
            limits["general"] = (500, 60)  # Higher limits for API users
            limits["hourly"] = (10000, 3600)
        
        return limits
    
    async def _update_rate_limit_counters(self, client_id: str, request: Request):
        """Update rate limit counters after successful request."""
        current_time = int(time.time())
        limits = await self._get_rate_limits(request)
        
        for limit_type, (max_requests, window_seconds) in limits.items():
            key = f"rate_limit:{client_id}:{limit_type}:{current_time // window_seconds}"
            
            # Increment counter
            await self.redis.incr(key)
            
            # Set expiration
            await self.redis.expire(key, window_seconds)


# Utility functions for setup
async def setup_security_middleware(app, config: SecurityConfig, redis_client: redis.Redis):
    """Set up security middleware."""
    security_middleware = SecurityMiddleware(app, config, redis_client)
    rate_limiting_middleware = RateLimitingMiddleware(app, redis_client)
    
    app.add_middleware(RateLimitingMiddleware, redis_client=redis_client)
    app.add_middleware(SecurityMiddleware, config=config, redis_client=redis_client)
    
    logger.info("Security middleware configured")


async def create_default_api_keys(redis_client: redis.Redis):
    """Create default API keys for system services."""
    api_key_manager = APIKeyManager(redis_client)
    
    # Create system API keys
    system_keys = [
        {
            "user_id": "system_monitor",
            "permissions": ["system:monitor", "metrics:read"],
            "description": "System monitoring"
        },
        {
            "user_id": "system_backup",
            "permissions": ["system:backup", "data:export"],
            "description": "System backup"
        }
    ]
    
    for key_config in system_keys:
        api_key = await api_key_manager.generate_api_key(
            key_config["user_id"],
            key_config["permissions"],
            expires_days=365  # System keys expire after 1 year
        )
        logger.info(f"Generated system API key for {key_config['description']}: {api_key}")


# Background task for security monitoring
async def security_monitoring_task(redis_client: redis.Redis):
    """Background task for security monitoring and alerting."""
    while True:
        try:
            # Analyze security metrics
            metrics = await redis_client.lrange("security_metrics", 0, -1)
            
            if metrics:
                # Parse metrics
                parsed_metrics = []
                for metric_data in metrics:
                    try:
                        parsed_metrics.append(json.loads(metric_data))
                    except json.JSONDecodeError:
                        continue
                
                # Analyze for security threats
                await analyze_security_threats(parsed_metrics, redis_client)
            
            # Clean up old data
            await redis_client.ltrim("security_metrics", 0, 9999)
            
        except Exception as e:
            logger.error("Security monitoring task error", error=str(e))
        
        # Wait before next analysis
        await asyncio.sleep(300)  # 5 minutes


async def analyze_security_threats(metrics: List[Dict], redis_client: redis.Redis):
    """Analyze metrics for security threats."""
    current_time = datetime.now()
    
    # Group by IP
    ip_metrics = defaultdict(list)
    for metric in metrics:
        ip_metrics[metric['client_ip']].append(metric)
    
    # Check for suspicious patterns
    for ip, ip_metric_list in ip_metrics.items():
        # Check for rapid fire requests
        if len(ip_metric_list) > 50:  # More than 50 requests in monitoring window
            logger.warning("High request volume detected", ip=ip, request_count=len(ip_metric_list))
        
        # Check for error patterns
        error_count = sum(1 for m in ip_metric_list if m['status_code'] >= 400)
        if error_count > 10:
            logger.warning("High error rate detected", ip=ip, error_count=error_count)
        
        # Check for unusual paths
        paths = [m['path'] for m in ip_metric_list]
        unique_paths = len(set(paths))
        if unique_paths > 20:  # Accessing many different endpoints
            logger.warning("Path scanning detected", ip=ip, unique_paths=unique_paths)