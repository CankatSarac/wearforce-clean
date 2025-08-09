import time
import uuid
from typing import Callable
from contextvars import ContextVar

from fastapi import Request, Response, HTTPException
from fastapi.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram, generate_latest
import structlog

# Context variables for request tracing
request_id_ctx: ContextVar[str] = ContextVar('request_id')
user_id_ctx: ContextVar[str] = ContextVar('user_id')

logger = structlog.get_logger()

# Prometheus metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration', ['method', 'endpoint'])
ERROR_COUNT = Counter('http_errors_total', 'Total HTTP errors', ['method', 'endpoint', 'error_type'])


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID and user ID to context."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate or extract request ID
        request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
        request_id_ctx.set(request_id)
        
        # Extract user ID from headers if available
        user_id = request.headers.get('X-User-ID', 'anonymous')
        user_id_ctx.set(user_id)
        
        # Add to structured logging context
        structlog.contextvars.bind_contextvars(request_id=request_id, user_id=user_id)
        
        response = await call_next(request)
        
        # Add request ID to response headers
        response.headers['X-Request-ID'] = request_id
        
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect Prometheus metrics."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        method = request.method
        endpoint = request.url.path
        
        try:
            response = await call_next(request)
            status = response.status_code
            
            # Record metrics
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
            REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(time.time() - start_time)
            
            return response
            
        except HTTPException as e:
            status = e.status_code
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
            ERROR_COUNT.labels(method=method, endpoint=endpoint, error_type='http_error').inc()
            REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(time.time() - start_time)
            raise
            
        except Exception as e:
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=500).inc()
            ERROR_COUNT.labels(method=method, endpoint=endpoint, error_type='internal_error').inc()
            REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(time.time() - start_time)
            raise


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured request/response logging."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Log request
        logger.info(
            "Request started",
            method=request.method,
            url=str(request.url),
            headers=dict(request.headers),
            client=request.client.host if request.client else None
        )
        
        try:
            response = await call_next(request)
            duration = time.time() - start_time
            
            # Log response
            logger.info(
                "Request completed",
                method=request.method,
                url=str(request.url),
                status_code=response.status_code,
                duration=duration
            )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            
            # Log error
            logger.error(
                "Request failed",
                method=request.method,
                url=str(request.url),
                duration=duration,
                error=str(e),
                error_type=type(e).__name__
            )
            raise


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware to log audit events for write operations."""
    
    WRITE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method in self.WRITE_METHODS:
            # Log audit event before processing
            logger.info(
                "Audit event",
                event_type="request_started",
                method=request.method,
                endpoint=request.url.path,
                user_id=user_id_ctx.get('anonymous'),
                request_id=request_id_ctx.get('unknown')
            )
        
        response = await call_next(request)
        
        if request.method in self.WRITE_METHODS and 200 <= response.status_code < 300:
            # Log successful write operation
            logger.info(
                "Audit event",
                event_type="write_operation_completed",
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code,
                user_id=user_id_ctx.get('anonymous'),
                request_id=request_id_ctx.get('unknown')
            )
        
        return response


def setup_middleware(app):
    """Set up all middleware for the FastAPI application."""
    app.add_middleware(RequestTracingMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(AuditMiddleware)


def get_current_request_id() -> str:
    """Get the current request ID from context."""
    return request_id_ctx.get('unknown')


def get_current_user_id() -> str:
    """Get the current user ID from context."""
    return user_id_ctx.get('anonymous')


# Additional utility functions for better compatibility
def get_request_id() -> str:
    """Get the current request ID from context."""
    return request_id_ctx.get('unknown')


def get_correlation_id() -> str:
    """Get the current correlation ID (alias for request ID)."""
    return get_current_request_id()