"""Middleware for FastAPI services."""

import asyncio
import time
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Set
from urllib.parse import urlparse

import structlog
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse as StarletteJSONResponse

from .exceptions import (
    AuthenticationError,
    AuthorizationError,
    RateLimitError,
    WearForceException,
)
from .monitoring import get_metrics
from .models import ErrorResponse

logger = structlog.get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log details."""
        start_time = time.time()
        
        # Log request
        logger.info(
            "request_started",
            method=request.method,
            url=str(request.url),
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log response
            logger.info(
                "request_completed",
                method=request.method,
                url=str(request.url),
                status_code=response.status_code,
                duration=duration,
            )
            
            # Record metrics
            metrics = get_metrics()
            if metrics:
                metrics.record_http_request(
                    request.method,
                    request.url.path,
                    response.status_code,
                    duration,
                )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            
            # Log error
            logger.error(
                "request_failed",
                method=request.method,
                url=str(request.url),
                error=str(e),
                duration=duration,
                exc_info=True,
            )
            
            # Record metrics
            metrics = get_metrics()
            if metrics:
                status_code = getattr(e, "status_code", 500)
                metrics.record_http_request(
                    request.method,
                    request.url.path,
                    status_code,
                    duration,
                )
                metrics.record_error("middleware_error", "request_processing")
            
            raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting middleware."""
    
    def __init__(
        self,
        app: FastAPI,
        requests_per_minute: int = 60,
        exempt_paths: Optional[List[str]] = None,
    ) -> None:
        """Initialize rate limiting middleware."""
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.exempt_paths = exempt_paths or ["/health", "/metrics"]
        self.request_counts: Dict[str, List[float]] = {}
    
    def _clean_old_requests(self, client_ip: str) -> None:
        """Remove requests older than 1 minute."""
        current_time = time.time()
        cutoff_time = current_time - 60  # 1 minute ago
        
        if client_ip in self.request_counts:
            self.request_counts[client_ip] = [
                req_time for req_time in self.request_counts[client_ip]
                if req_time > cutoff_time
            ]
    
    def _is_rate_limited(self, client_ip: str) -> bool:
        """Check if client is rate limited."""
        self._clean_old_requests(client_ip)
        
        if client_ip not in self.request_counts:
            self.request_counts[client_ip] = []
        
        return len(self.request_counts[client_ip]) >= self.requests_per_minute
    
    def _record_request(self, client_ip: str) -> None:
        """Record new request."""
        current_time = time.time()
        
        if client_ip not in self.request_counts:
            self.request_counts[client_ip] = []
        
        self.request_counts[client_ip].append(current_time)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check rate limits and process request."""
        # Skip rate limiting for exempt paths
        if request.url.path in self.exempt_paths:
            return await call_next(request)
        
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Check rate limit
        if self._is_rate_limited(client_ip):
            logger.warning(
                "rate_limit_exceeded",
                client_ip=client_ip,
                path=request.url.path,
            )
            
            # Record metrics
            metrics = get_metrics()
            if metrics:
                metrics.record_error("rate_limit", "middleware")
            
            raise RateLimitError()
        
        # Record request
        self._record_request(client_ip)
        
        return await call_next(request)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware for consistent error handling."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle errors and return consistent responses."""
        try:
            return await call_next(request)
        
        except WearForceException as e:
            logger.error(
                "wearforce_error",
                error_code=e.error_code,
                message=e.message,
                details=e.details,
                path=request.url.path,
            )
            
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": {
                        "code": e.error_code,
                        "message": e.message,
                        "details": e.details,
                    },
                    "path": request.url.path,
                    "timestamp": time.time(),
                },
            )
        
        except HTTPException as e:
            logger.error(
                "http_error",
                status_code=e.status_code,
                detail=e.detail,
                path=request.url.path,
            )
            
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": {
                        "code": "HTTP_ERROR",
                        "message": e.detail,
                        "details": {},
                    },
                    "path": request.url.path,
                    "timestamp": time.time(),
                },
            )
        
        except Exception as e:
            logger.error(
                "unexpected_error",
                error=str(e),
                path=request.url.path,
                exc_info=True,
            )
            
            # Record metrics
            metrics = get_metrics()
            if metrics:
                metrics.record_error("unexpected_error", "middleware")
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "An unexpected error occurred",
                        "details": {},
                    },
                    "path": request.url.path,
                    "timestamp": time.time(),
                },
            )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Security headers middleware."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to all responses."""
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # API-specific headers
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
        return response


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """JWT authentication middleware."""
    
    def __init__(
        self,
        app: FastAPI,
        jwt_secret: str,
        excluded_paths: Optional[Set[str]] = None,
        service_name: str = "unknown",
    ):
        super().__init__(app)
        self.jwt_secret = jwt_secret
        self.service_name = service_name
        self.excluded_paths = excluded_paths or {
            "/health", "/metrics", "/docs", "/openapi.json", "/redoc"
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Verify JWT token for protected endpoints."""
        path = request.url.path
        
        # Skip authentication for excluded paths
        if path in self.excluded_paths or path.startswith("/docs"):
            return await call_next(request)
        
        # Check for Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise AuthenticationError("Missing Authorization header")
        
        if not auth_header.startswith("Bearer "):
            raise AuthenticationError("Invalid Authorization header format")
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        
        try:
            # Verify token
            user_info = await self._verify_token(token)
            
            # Add user info to request state
            request.state.user = user_info
            
            return await call_next(request)
            
        except Exception as exc:
            logger.error(
                "Authentication failed",
                error=str(exc),
                service=self.service_name,
                path=path,
            )
            raise AuthenticationError("Invalid or expired token")
    
    async def _verify_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT token and extract user information."""
        # TODO: Implement JWT verification with actual secret
        try:
            import jwt
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            return payload
        except ImportError:
            logger.warning("PyJWT not installed, skipping token verification")
            return {"user_id": "test", "username": "test_user"}
        except Exception as exc:
            raise AuthenticationError(f"Token verification failed: {str(exc)}")


class CacheMiddleware(BaseHTTPMiddleware):
    """Simple in-memory cache middleware for GET requests."""
    
    def __init__(self, app: FastAPI, ttl: int = 300):  # 5 minutes default TTL
        super().__init__(app)
        self.ttl = ttl
        self.cache: Dict[str, Dict[str, Any]] = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Cache GET requests based on URL and query parameters."""
        if request.method != "GET":
            return await call_next(request)
        
        cache_key = str(request.url)
        current_time = time.time()
        
        # Check cache
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            if current_time - cached_data["timestamp"] < self.ttl:
                logger.debug("Cache hit", cache_key=cache_key)
                return StarletteJSONResponse(
                    content=cached_data["content"],
                    status_code=cached_data["status_code"],
                    headers=cached_data["headers"],
                )
        
        # Process request
        response = await call_next(request)
        
        # Cache successful responses
        if 200 <= response.status_code < 300:
            try:
                # Read response body
                body = b""
                async for chunk in response.body_iterator:
                    body += chunk
                
                # Store in cache
                self.cache[cache_key] = {
                    "content": body.decode() if body else "",
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "timestamp": current_time,
                }
                
                logger.debug("Response cached", cache_key=cache_key)
                
                # Return new response with same content
                return StarletteJSONResponse(
                    content=body.decode() if body else "",
                    status_code=response.status_code,
                    headers=dict(response.headers),
                )
            except Exception as exc:
                logger.warning("Failed to cache response", error=str(exc))
        
        return response


def setup_middleware(
    app: FastAPI,
    service_name: str = "unknown",
    cors_origins: List[str] = None,
    cors_allow_credentials: bool = True,
    requests_per_minute: int = 60,
    enable_gzip: bool = True,
    enable_auth: bool = False,
    jwt_secret: Optional[str] = None,
    enable_cache: bool = False,
    cache_ttl: int = 300,
) -> None:
    """Setup all middleware for the FastAPI app."""
    
    # Security headers (first)
    app.add_middleware(SecurityHeadersMiddleware)
    
    # Authentication (if enabled)
    if enable_auth and jwt_secret:
        app.add_middleware(
            AuthenticationMiddleware,
            jwt_secret=jwt_secret,
            service_name=service_name,
        )
    
    # Caching (if enabled)
    if enable_cache:
        app.add_middleware(CacheMiddleware, ttl=cache_ttl)
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_credentials=cors_allow_credentials,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    
    # Gzip compression
    if enable_gzip:
        app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Custom middleware (order matters - they are applied in reverse order)
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=requests_per_minute)
    app.add_middleware(LoggingMiddleware)