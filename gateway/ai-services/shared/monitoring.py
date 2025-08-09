"""Monitoring and metrics utilities."""

import time
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, AsyncGenerator, Callable, Dict, Optional, TypeVar, Union

import structlog
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from fastapi import Response


# Type variables
F = TypeVar("F", bound=Callable[..., Any])
AsyncF = TypeVar("AsyncF", bound=Callable[..., Any])

logger = structlog.get_logger(__name__)


class Metrics:
    """Prometheus metrics for AI services."""
    
    def __init__(self, service_name: str) -> None:
        """Initialize metrics."""
        self.service_name = service_name
        
        # HTTP metrics
        self.http_requests_total = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status_code", "service"],
        )
        
        self.http_request_duration_seconds = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint", "service"],
        )
        
        # Model inference metrics
        self.inference_requests_total = Counter(
            "inference_requests_total",
            "Total inference requests",
            ["model", "service"],
        )
        
        self.inference_duration_seconds = Histogram(
            "inference_duration_seconds",
            "Inference duration in seconds",
            ["model", "service"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
        )
        
        self.inference_tokens_processed = Counter(
            "inference_tokens_processed_total",
            "Total tokens processed",
            ["model", "service", "type"],  # type: input, output
        )
        
        # Audio processing metrics
        self.audio_processing_duration_seconds = Histogram(
            "audio_processing_duration_seconds",
            "Audio processing duration in seconds",
            ["operation", "service"],  # operation: transcription, synthesis
        )
        
        self.audio_files_processed_total = Counter(
            "audio_files_processed_total",
            "Total audio files processed",
            ["format", "service", "status"],  # status: success, error
        )
        
        # Vector database metrics
        self.vector_operations_total = Counter(
            "vector_operations_total",
            "Total vector database operations",
            ["operation", "service"],  # operation: search, upsert, delete
        )
        
        self.vector_search_duration_seconds = Histogram(
            "vector_search_duration_seconds",
            "Vector search duration in seconds",
            ["service"],
        )
        
        # System metrics
        self.active_connections = Gauge(
            "active_connections",
            "Number of active connections",
            ["service"],
        )
        
        self.memory_usage_bytes = Gauge(
            "memory_usage_bytes",
            "Memory usage in bytes",
            ["service", "type"],  # type: rss, vms
        )
        
        self.gpu_memory_usage_bytes = Gauge(
            "gpu_memory_usage_bytes",
            "GPU memory usage in bytes",
            ["service", "gpu_id"],
        )
        
        # Error metrics
        self.errors_total = Counter(
            "errors_total",
            "Total errors",
            ["service", "type", "component"],
        )
    
    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: float,
    ) -> None:
        """Record HTTP request metrics."""
        self.http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            service=self.service_name,
        ).inc()
        
        self.http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint,
            service=self.service_name,
        ).observe(duration)
    
    def record_inference(
        self,
        model: str,
        duration: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """Record model inference metrics."""
        self.inference_requests_total.labels(
            model=model,
            service=self.service_name,
        ).inc()
        
        self.inference_duration_seconds.labels(
            model=model,
            service=self.service_name,
        ).observe(duration)
        
        if input_tokens > 0:
            self.inference_tokens_processed.labels(
                model=model,
                service=self.service_name,
                type="input",
            ).inc(input_tokens)
        
        if output_tokens > 0:
            self.inference_tokens_processed.labels(
                model=model,
                service=self.service_name,
                type="output",
            ).inc(output_tokens)
    
    def record_audio_processing(
        self,
        operation: str,
        duration: float,
        format: str,
        success: bool = True,
    ) -> None:
        """Record audio processing metrics."""
        self.audio_processing_duration_seconds.labels(
            operation=operation,
            service=self.service_name,
        ).observe(duration)
        
        self.audio_files_processed_total.labels(
            format=format,
            service=self.service_name,
            status="success" if success else "error",
        ).inc()
    
    def record_vector_operation(
        self,
        operation: str,
        duration: Optional[float] = None,
    ) -> None:
        """Record vector database operation metrics."""
        self.vector_operations_total.labels(
            operation=operation,
            service=self.service_name,
        ).inc()
        
        if operation == "search" and duration is not None:
            self.vector_search_duration_seconds.labels(
                service=self.service_name,
            ).observe(duration)
    
    def set_active_connections(self, count: int) -> None:
        """Set active connections count."""
        self.active_connections.labels(service=self.service_name).set(count)
    
    def record_error(self, error_type: str, component: str) -> None:
        """Record error metrics."""
        self.errors_total.labels(
            service=self.service_name,
            type=error_type,
            component=component,
        ).inc()


# Global metrics instance
_metrics: Optional[Metrics] = None


def init_metrics(service_name: str) -> Metrics:
    """Initialize global metrics."""
    global _metrics
    _metrics = Metrics(service_name)
    return _metrics


def get_metrics() -> Optional[Metrics]:
    """Get global metrics instance."""
    return _metrics


def metrics_endpoint() -> Response:
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


def monitor_http_requests(func: F) -> F:
    """Decorator to monitor HTTP requests."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        method = kwargs.get("method", "GET")
        endpoint = kwargs.get("path", "/")
        status_code = 200
        
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            status_code = getattr(e, "status_code", 500)
            if _metrics:
                _metrics.record_error("http_error", endpoint)
            raise
        finally:
            duration = time.time() - start_time
            if _metrics:
                _metrics.record_http_request(method, endpoint, status_code, duration)
    
    return wrapper


def monitor_inference(model_name: str) -> Callable[[AsyncF], AsyncF]:
    """Decorator to monitor model inference."""
    def decorator(func: AsyncF) -> AsyncF:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                
                # Extract token counts if available
                input_tokens = getattr(result, "input_tokens", 0)
                output_tokens = getattr(result, "output_tokens", 0)
                
                if _metrics:
                    duration = time.time() - start_time
                    _metrics.record_inference(
                        model_name, duration, input_tokens, output_tokens
                    )
                
                return result
            except Exception as e:
                if _metrics:
                    _metrics.record_error("inference_error", model_name)
                raise
        
        return wrapper
    return decorator


def monitor_audio_processing(operation: str) -> Callable[[AsyncF], AsyncF]:
    """Decorator to monitor audio processing."""
    def decorator(func: AsyncF) -> AsyncF:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            format_name = kwargs.get("format", "unknown")
            success = True
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                if _metrics:
                    _metrics.record_error("audio_processing_error", operation)
                raise
            finally:
                duration = time.time() - start_time
                if _metrics:
                    _metrics.record_audio_processing(
                        operation, duration, format_name, success
                    )
        
        return wrapper
    return decorator


@asynccontextmanager
async def monitor_vector_operation(operation: str) -> AsyncGenerator[None, None]:
    """Context manager to monitor vector database operations."""
    start_time = time.time()
    
    try:
        yield
    except Exception as e:
        if _metrics:
            _metrics.record_error("vector_db_error", operation)
        raise
    finally:
        duration = time.time() - start_time
        if _metrics:
            _metrics.record_vector_operation(operation, duration)


class HealthChecker:
    """Health check utilities."""
    
    def __init__(self) -> None:
        """Initialize health checker."""
        self.checks: Dict[str, Callable[[], bool]] = {}
        self._healthy = True
    
    def add_check(self, name: str, check_func: Callable[[], bool]) -> None:
        """Add a health check."""
        self.checks[name] = check_func
    
    async def check_health(self) -> Dict[str, Any]:
        """Run all health checks."""
        results = {}
        overall_healthy = True
        
        for name, check_func in self.checks.items():
            try:
                if asyncio.iscoroutinefunction(check_func):
                    healthy = await check_func()
                else:
                    healthy = check_func()
                
                results[name] = {
                    "status": "healthy" if healthy else "unhealthy",
                    "timestamp": time.time(),
                }
                
                if not healthy:
                    overall_healthy = False
                    
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "error": str(e),
                    "timestamp": time.time(),
                }
                overall_healthy = False
        
        self._healthy = overall_healthy
        
        return {
            "status": "healthy" if overall_healthy else "unhealthy",
            "checks": results,
            "timestamp": time.time(),
        }
    
    @property
    def healthy(self) -> bool:
        """Get current health status."""
        return self._healthy


# Global health checker
health_checker = HealthChecker()