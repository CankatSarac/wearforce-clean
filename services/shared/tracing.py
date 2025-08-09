"""
OpenTelemetry distributed tracing integration for WearForce platform.

This module provides comprehensive tracing capabilities including automatic
instrumentation, custom spans, trace correlation, and performance monitoring.
"""

import asyncio
import json
import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from opentelemetry import trace, metrics, baggage
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.propagators.composite import CompositeHTTPPropagator
from opentelemetry.propagators.jaeger import JaegerPropagator
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricsExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.util.http import get_excluded_urls
import structlog

logger = structlog.get_logger()

# Global tracer and meter instances
tracer: Optional[trace.Tracer] = None
meter: Optional[metrics.Meter] = None


class TracingConfig:
    """Configuration for OpenTelemetry tracing."""
    
    def __init__(self):
        # Service identification
        self.service_name = os.getenv("SERVICE_NAME", "wearforce-clean-service")
        self.service_version = os.getenv("SERVICE_VERSION", "1.0.0")
        self.deployment_environment = os.getenv("ENVIRONMENT", "production")
        
        # Jaeger configuration
        self.jaeger_agent_host = os.getenv("JAEGER_AGENT_HOST", "jaeger")
        self.jaeger_agent_port = int(os.getenv("JAEGER_AGENT_PORT", "14268"))
        self.jaeger_endpoint = f"http://{self.jaeger_agent_host}:{self.jaeger_agent_port}/api/traces"
        
        # OTLP configuration
        self.otlp_endpoint = os.getenv("OTLP_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
        self.otlp_headers = self._parse_headers(os.getenv("OTLP_EXPORTER_OTLP_HEADERS", ""))
        
        # Sampling configuration
        self.sampling_rate = float(os.getenv("TRACE_SAMPLING_RATE", "1.0"))
        
        # Export configuration
        self.export_batch_size = int(os.getenv("TRACE_EXPORT_BATCH_SIZE", "512"))
        self.export_timeout = int(os.getenv("TRACE_EXPORT_TIMEOUT", "30"))
        
        # Instrumentation configuration
        self.instrument_db_queries = os.getenv("INSTRUMENT_DB_QUERIES", "true").lower() == "true"
        self.instrument_http_client = os.getenv("INSTRUMENT_HTTP_CLIENT", "true").lower() == "true"
        self.instrument_redis = os.getenv("INSTRUMENT_REDIS", "true").lower() == "true"
        
        # Custom business metrics
        self.enable_business_metrics = os.getenv("ENABLE_BUSINESS_METRICS", "true").lower() == "true"
        
        # Security and privacy
        self.exclude_sensitive_headers = ["authorization", "cookie", "x-api-key"]
        self.exclude_urls = get_excluded_urls("OTEL_PYTHON_EXCLUDED_URLS")
    
    def _parse_headers(self, headers_str: str) -> Dict[str, str]:
        """Parse OTLP headers from environment variable."""
        headers = {}
        if headers_str:
            for header_pair in headers_str.split(","):
                if "=" in header_pair:
                    key, value = header_pair.strip().split("=", 1)
                    headers[key] = value
        return headers


class WearForceSpanProcessor(BatchSpanProcessor):
    """Custom span processor for WearForce-specific processing."""
    
    def __init__(self, span_exporter, **kwargs):
        super().__init__(span_exporter, **kwargs)
        self.business_events = []
    
    def on_start(self, span: trace.Span, parent_context: trace.Context = None):
        """Called when span starts."""
        super().on_start(span, parent_context)
        
        # Add custom attributes
        span.set_attribute("wearforce-clean.service", os.getenv("SERVICE_NAME", "unknown"))
        span.set_attribute("wearforce-clean.version", os.getenv("SERVICE_VERSION", "unknown"))
        
        # Add user context if available
        user_id = baggage.get_baggage("user.id")
        if user_id:
            span.set_attribute("user.id", user_id)
            
        tenant_id = baggage.get_baggage("tenant.id")
        if tenant_id:
            span.set_attribute("tenant.id", tenant_id)
    
    def on_end(self, span: trace.Span):
        """Called when span ends."""
        super().on_end(span)
        
        # Extract business events from span
        if span.name.startswith("business."):
            self._extract_business_event(span)
    
    def _extract_business_event(self, span: trace.Span):
        """Extract business event from span for analytics."""
        event = {
            "trace_id": format(span.get_span_context().trace_id, "032x"),
            "span_id": format(span.get_span_context().span_id, "016x"),
            "event_name": span.name,
            "timestamp": span.start_time,
            "duration_ms": (span.end_time - span.start_time) // 1000000,
            "attributes": dict(span.attributes) if span.attributes else {}
        }
        
        self.business_events.append(event)
        
        # Keep only recent events
        if len(self.business_events) > 1000:
            self.business_events = self.business_events[-500:]


class BusinessMetrics:
    """Business-specific metrics collection."""
    
    def __init__(self, meter: metrics.Meter):
        self.meter = meter
        
        # Business counters
        self.customer_created_counter = meter.create_counter(
            "wearforce-clean_customers_created_total",
            description="Total number of customers created"
        )
        
        self.order_created_counter = meter.create_counter(
            "wearforce-clean_orders_created_total",
            description="Total number of orders created"
        )
        
        self.order_completed_counter = meter.create_counter(
            "wearforce-clean_orders_completed_total",
            description="Total number of orders completed"
        )
        
        self.revenue_counter = meter.create_counter(
            "wearforce-clean_revenue_total",
            description="Total revenue generated"
        )
        
        # Business histograms
        self.order_processing_time = meter.create_histogram(
            "wearforce-clean_order_processing_duration_seconds",
            description="Time taken to process orders"
        )
        
        self.customer_lifetime_value = meter.create_histogram(
            "wearforce-clean_customer_lifetime_value",
            description="Customer lifetime value distribution"
        )
        
        # Business gauges
        self.active_sessions = meter.create_up_down_counter(
            "wearforce-clean_active_sessions",
            description="Number of active user sessions"
        )
        
        self.inventory_levels = meter.create_gauge(
            "wearforce-clean_inventory_levels",
            description="Current inventory levels by product"
        )
    
    def record_customer_created(self, customer_type: str = "regular", source: str = "web"):
        """Record customer creation event."""
        self.customer_created_counter.add(1, {"type": customer_type, "source": source})
    
    def record_order_created(self, order_value: float, product_category: str = "unknown"):
        """Record order creation event."""
        self.order_created_counter.add(1, {"category": product_category})
        self.revenue_counter.add(order_value, {"category": product_category})
    
    def record_order_completed(self, processing_time: float, product_category: str = "unknown"):
        """Record order completion event."""
        self.order_completed_counter.add(1, {"category": product_category})
        self.order_processing_time.record(processing_time, {"category": product_category})
    
    def update_active_sessions(self, change: int):
        """Update active session count."""
        self.active_sessions.add(change)
    
    def update_inventory_level(self, product_id: str, level: int, warehouse: str = "main"):
        """Update inventory level for a product."""
        self.inventory_levels.set(level, {"product_id": product_id, "warehouse": warehouse})


class TracingManager:
    """Manages OpenTelemetry tracing setup and configuration."""
    
    def __init__(self, config: TracingConfig):
        self.config = config
        self.business_metrics: Optional[BusinessMetrics] = None
        self._initialized = False
    
    def initialize(self):
        """Initialize OpenTelemetry tracing."""
        if self._initialized:
            return
        
        try:
            # Set up resource
            resource = Resource.create({
                ResourceAttributes.SERVICE_NAME: self.config.service_name,
                ResourceAttributes.SERVICE_VERSION: self.config.service_version,
                ResourceAttributes.DEPLOYMENT_ENVIRONMENT: self.config.deployment_environment,
                "wearforce-clean.component": "service",
            })
            
            # Set up tracing
            self._setup_tracing(resource)
            
            # Set up metrics
            self._setup_metrics(resource)
            
            # Set up propagators
            self._setup_propagators()
            
            # Set up auto-instrumentation
            self._setup_auto_instrumentation()
            
            # Initialize business metrics
            if self.config.enable_business_metrics:
                global meter
                self.business_metrics = BusinessMetrics(meter)
            
            self._initialized = True
            logger.info("OpenTelemetry tracing initialized", 
                       service=self.config.service_name,
                       version=self.config.service_version)
            
        except Exception as e:
            logger.error("Failed to initialize tracing", error=str(e))
            raise
    
    def _setup_tracing(self, resource: Resource):
        """Set up trace provider and exporters."""
        global tracer
        
        # Create trace provider
        trace_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(trace_provider)
        
        # Set up exporters
        exporters = []
        
        # Jaeger exporter
        jaeger_exporter = JaegerExporter(
            agent_host_name=self.config.jaeger_agent_host,
            agent_port=self.config.jaeger_agent_port,
            collector_endpoint=self.config.jaeger_endpoint,
        )
        exporters.append(jaeger_exporter)
        
        # OTLP exporter
        if self.config.otlp_endpoint:
            otlp_exporter = OTLPSpanExporter(
                endpoint=self.config.otlp_endpoint,
                headers=self.config.otlp_headers
            )
            exporters.append(otlp_exporter)
        
        # Console exporter for development
        if self.config.deployment_environment == "development":
            console_exporter = ConsoleSpanExporter()
            exporters.append(console_exporter)
        
        # Add span processors
        for exporter in exporters:
            span_processor = WearForceSpanProcessor(
                exporter,
                max_queue_size=2048,
                schedule_delay_millis=5000,
                max_export_batch_size=self.config.export_batch_size,
                export_timeout_millis=self.config.export_timeout * 1000
            )
            trace_provider.add_span_processor(span_processor)
        
        # Get tracer
        tracer = trace.get_tracer(__name__)
    
    def _setup_metrics(self, resource: Resource):
        """Set up metrics provider and exporters."""
        global meter
        
        # Create metrics readers
        readers = []
        
        # Console metrics for development
        if self.config.deployment_environment == "development":
            console_reader = PeriodicExportingMetricReader(
                ConsoleMetricsExporter(),
                export_interval_millis=60000  # 1 minute
            )
            readers.append(console_reader)
        
        # Create meter provider
        meter_provider = MeterProvider(resource=resource, metric_readers=readers)
        metrics.set_meter_provider(meter_provider)
        
        # Get meter
        meter = metrics.get_meter(__name__)
    
    def _setup_propagators(self):
        """Set up trace context propagators."""
        # Use composite propagator for maximum compatibility
        propagator = CompositeHTTPPropagator([
            JaegerPropagator(),
            B3MultiFormat(),
        ])
        set_global_textmap(propagator)
    
    def _setup_auto_instrumentation(self):
        """Set up automatic instrumentation."""
        try:
            # FastAPI instrumentation
            FastAPIInstrumentor().instrument(
                excluded_urls=",".join(self.config.exclude_urls) if self.config.exclude_urls else None
            )
            
            # Database instrumentation
            if self.config.instrument_db_queries:
                AsyncPGInstrumentor().instrument()
                SQLAlchemyInstrumentor().instrument()
            
            # HTTP client instrumentation
            if self.config.instrument_http_client:
                HTTPXClientInstrumentor().instrument()
            
            # Redis instrumentation
            if self.config.instrument_redis:
                RedisInstrumentor().instrument()
            
            # Logging instrumentation
            LoggingInstrumentor().instrument(set_logging_format=True)
            
            # System metrics
            SystemMetricsInstrumentor().instrument()
            
            logger.info("Auto-instrumentation configured")
            
        except Exception as e:
            logger.warning("Failed to configure auto-instrumentation", error=str(e))


# Context managers and decorators
@contextmanager
def trace_operation(operation_name: str, **attributes):
    """Context manager for tracing operations."""
    global tracer
    
    if not tracer:
        yield None
        return
    
    with tracer.start_as_current_span(operation_name) as span:
        # Add attributes
        for key, value in attributes.items():
            span.set_attribute(key, value)
        
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            raise


def trace_async_function(operation_name: Optional[str] = None, **span_attributes):
    """Decorator for tracing async functions."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            name = operation_name or f"{func.__module__}.{func.__name__}"
            
            with trace_operation(name, **span_attributes) as span:
                if span:
                    # Add function metadata
                    span.set_attribute("function.name", func.__name__)
                    span.set_attribute("function.module", func.__module__)
                
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    if span:
                        span.set_attribute("function.result", "success")
                    return result
                except Exception as e:
                    if span:
                        span.set_attribute("function.result", "error")
                        span.set_attribute("function.error", str(e))
                    raise
                finally:
                    if span:
                        duration = time.time() - start_time
                        span.set_attribute("function.duration_seconds", duration)
        
        return wrapper
    return decorator


def trace_function(operation_name: Optional[str] = None, **span_attributes):
    """Decorator for tracing synchronous functions."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            name = operation_name or f"{func.__module__}.{func.__name__}"
            
            with trace_operation(name, **span_attributes) as span:
                if span:
                    span.set_attribute("function.name", func.__name__)
                    span.set_attribute("function.module", func.__module__)
                
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    if span:
                        span.set_attribute("function.result", "success")
                    return result
                except Exception as e:
                    if span:
                        span.set_attribute("function.result", "error")
                        span.set_attribute("function.error", str(e))
                    raise
                finally:
                    if span:
                        duration = time.time() - start_time
                        span.set_attribute("function.duration_seconds", duration)
        
        return wrapper
    return decorator


# Business event tracking
def track_business_event(event_name: str, **attributes):
    """Track a business event with tracing."""
    global tracer
    
    if not tracer:
        return
    
    with tracer.start_as_current_span(f"business.{event_name}") as span:
        span.set_attribute("event.name", event_name)
        span.set_attribute("event.type", "business")
        
        for key, value in attributes.items():
            span.set_attribute(f"event.{key}", value)
        
        # Add to current span as event
        span.add_event(f"business_event_{event_name}", attributes)


# User context management
def set_user_context(user_id: str, tenant_id: Optional[str] = None, **additional_context):
    """Set user context for tracing."""
    baggage.set_baggage("user.id", user_id)
    
    if tenant_id:
        baggage.set_baggage("tenant.id", tenant_id)
    
    for key, value in additional_context.items():
        baggage.set_baggage(f"user.{key}", str(value))


def get_current_trace_id() -> Optional[str]:
    """Get current trace ID."""
    span = trace.get_current_span()
    if span and span.get_span_context().trace_id:
        return format(span.get_span_context().trace_id, "032x")
    return None


def get_current_span_id() -> Optional[str]:
    """Get current span ID."""
    span = trace.get_current_span()
    if span and span.get_span_context().span_id:
        return format(span.get_span_context().span_id, "016x")
    return None


# Integration functions
def setup_tracing(service_name: str, service_version: str = "1.0.0") -> TracingManager:
    """Set up tracing for a service."""
    # Update environment variables
    os.environ["SERVICE_NAME"] = service_name
    os.environ["SERVICE_VERSION"] = service_version
    
    config = TracingConfig()
    tracing_manager = TracingManager(config)
    tracing_manager.initialize()
    
    return tracing_manager


def get_business_metrics() -> Optional[BusinessMetrics]:
    """Get business metrics instance."""
    # This would return the global business metrics instance
    return getattr(get_business_metrics, '_instance', None)


def add_trace_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """Add tracing headers to outgoing requests."""
    from opentelemetry.propagate import inject
    
    trace_headers = {}
    inject(trace_headers)
    headers.update(trace_headers)
    
    return headers


# Health check for tracing
async def tracing_health_check() -> Dict[str, Any]:
    """Health check for tracing system."""
    global tracer, meter
    
    status = {
        "tracer_initialized": tracer is not None,
        "meter_initialized": meter is not None,
        "current_trace_id": get_current_trace_id(),
        "current_span_id": get_current_span_id()
    }
    
    return status


# Utility functions for structured logging integration
def add_trace_context_to_log(log_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add trace context to structured log data."""
    trace_id = get_current_trace_id()
    span_id = get_current_span_id()
    
    if trace_id:
        log_data["trace_id"] = trace_id
    
    if span_id:
        log_data["span_id"] = span_id
    
    return log_data


# Example usage functions
async def example_business_operation():
    """Example of how to use tracing for business operations."""
    with trace_operation("customer.registration") as span:
        if span:
            span.set_attribute("customer.type", "premium")
            span.set_attribute("registration.source", "web")
        
        # Simulate business logic
        await asyncio.sleep(0.1)
        
        # Track business event
        track_business_event("customer_registered", 
                           customer_type="premium",
                           source="web",
                           plan="basic")
        
        # Record metrics
        business_metrics = get_business_metrics()
        if business_metrics:
            business_metrics.record_customer_created("premium", "web")


# FastAPI middleware for automatic trace context
class TracingMiddleware:
    """Middleware to add tracing context to requests."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Extract user context from request if available
        # This would be implemented based on your authentication system
        
        await self.app(scope, receive, send)