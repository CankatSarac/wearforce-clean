"""
Health checks and automated failover mechanisms for WearForce platform.

This module provides comprehensive health checking capabilities including
service health monitoring, dependency checks, circuit breakers, and
automated failover mechanisms.
"""

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from contextlib import asynccontextmanager

import httpx
import redis
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import psycopg2

logger = structlog.get_logger()


class HealthStatus(Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class ComponentType(Enum):
    """Component type enumeration."""
    DATABASE = "database"
    CACHE = "cache"
    MESSAGE_QUEUE = "message_queue"
    EXTERNAL_API = "external_api"
    INTERNAL_SERVICE = "internal_service"
    FILE_SYSTEM = "file_system"
    NETWORK = "network"


@dataclass
class HealthCheckResult:
    """Health check result."""
    status: HealthStatus
    component: str
    component_type: ComponentType
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None


@dataclass
class CircuitBreakerState:
    """Circuit breaker state."""
    is_open: bool = False
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    next_attempt_time: Optional[datetime] = None


class CircuitBreaker:
    """Circuit breaker implementation for service protection."""
    
    def __init__(self, 
                 failure_threshold: int = 5,
                 recovery_timeout: int = 60,
                 expected_exception: type = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.state = CircuitBreakerState()
        
    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self._is_open():
            if self._should_attempt_reset():
                return self._attempt_reset(func, *args, **kwargs)
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except self.expected_exception as e:
            self._record_failure()
            raise e
    
    async def async_call(self, func: Callable, *args, **kwargs):
        """Execute async function with circuit breaker protection."""
        if self._is_open():
            if self._should_attempt_reset():
                return await self._async_attempt_reset(func, *args, **kwargs)
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result
        except self.expected_exception as e:
            self._record_failure()
            raise e
    
    def _is_open(self) -> bool:
        return self.state.is_open
    
    def _should_attempt_reset(self) -> bool:
        return (self.state.next_attempt_time and 
                datetime.now() >= self.state.next_attempt_time)
    
    def _attempt_reset(self, func: Callable, *args, **kwargs):
        """Attempt to reset circuit breaker."""
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except self.expected_exception as e:
            self._record_failure()
            raise e
    
    async def _async_attempt_reset(self, func: Callable, *args, **kwargs):
        """Attempt to reset circuit breaker (async)."""
        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result
        except self.expected_exception as e:
            self._record_failure()
            raise e
    
    def _record_success(self):
        """Record successful call."""
        self.state.failure_count = 0
        self.state.is_open = False
        self.state.last_success_time = datetime.now()
        self.state.next_attempt_time = None
        
        logger.info("Circuit breaker: Success recorded", 
                   failure_count=self.state.failure_count)
    
    def _record_failure(self):
        """Record failed call."""
        self.state.failure_count += 1
        self.state.last_failure_time = datetime.now()
        
        if self.state.failure_count >= self.failure_threshold:
            self.state.is_open = True
            self.state.next_attempt_time = (
                datetime.now() + timedelta(seconds=self.recovery_timeout)
            )
            
            logger.warning("Circuit breaker: OPENED", 
                          failure_count=self.state.failure_count,
                          next_attempt=self.state.next_attempt_time)
        
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state."""
        return {
            "is_open": self.state.is_open,
            "failure_count": self.state.failure_count,
            "last_failure_time": self.state.last_failure_time.isoformat() if self.state.last_failure_time else None,
            "last_success_time": self.state.last_success_time.isoformat() if self.state.last_success_time else None,
            "next_attempt_time": self.state.next_attempt_time.isoformat() if self.state.next_attempt_time else None
        }


class HealthChecker:
    """Individual health check implementation."""
    
    def __init__(self, 
                 name: str,
                 component_type: ComponentType,
                 check_func: Callable,
                 timeout: int = 5,
                 critical: bool = True,
                 circuit_breaker: Optional[CircuitBreaker] = None):
        self.name = name
        self.component_type = component_type
        self.check_func = check_func
        self.timeout = timeout
        self.critical = critical
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.last_result: Optional[HealthCheckResult] = None
        
    async def run_check(self) -> HealthCheckResult:
        """Run health check."""
        start_time = time.time()
        
        try:
            # Use circuit breaker protection
            if asyncio.iscoroutinefunction(self.check_func):
                result = await asyncio.wait_for(
                    self.circuit_breaker.async_call(self.check_func),
                    timeout=self.timeout
                )
            else:
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.circuit_breaker.call, self.check_func
                    ),
                    timeout=self.timeout
                )
            
            duration_ms = (time.time() - start_time) * 1000
            
            if isinstance(result, HealthCheckResult):
                result.duration_ms = duration_ms
                self.last_result = result
                return result
            else:
                # Simple boolean result
                status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                message = "Check passed" if result else "Check failed"
                
                self.last_result = HealthCheckResult(
                    status=status,
                    component=self.name,
                    component_type=self.component_type,
                    message=message,
                    duration_ms=duration_ms
                )
                return self.last_result
                
        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            self.last_result = HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                component=self.name,
                component_type=self.component_type,
                message=f"Health check timed out after {self.timeout}s",
                duration_ms=duration_ms,
                error="timeout"
            )
            return self.last_result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.last_result = HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                component=self.name,
                component_type=self.component_type,
                message=f"Health check failed: {str(e)}",
                duration_ms=duration_ms,
                error=str(e)
            )
            return self.last_result


class HealthMonitor:
    """Main health monitoring system."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.checkers: List[HealthChecker] = []
        self.check_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.overall_status = HealthStatus.UNKNOWN
        self.last_check_time: Optional[datetime] = None
        self.failover_handlers: Dict[str, List[Callable]] = defaultdict(list)
        
    def add_checker(self, checker: HealthChecker):
        """Add health checker."""
        self.checkers.append(checker)
        logger.info("Health checker added", 
                   name=checker.name, 
                   type=checker.component_type.value,
                   critical=checker.critical)
    
    def add_failover_handler(self, component: str, handler: Callable):
        """Add failover handler for a component."""
        self.failover_handlers[component].append(handler)
        logger.info("Failover handler added", component=component)
    
    async def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all health checks."""
        results = {}
        tasks = []
        
        # Create tasks for all checks
        for checker in self.checkers:
            task = asyncio.create_task(
                self._run_checker_with_context(checker),
                name=f"health_check_{checker.name}"
            )
            tasks.append((checker.name, task))
        
        # Wait for all checks to complete
        for checker_name, task in tasks:
            try:
                result = await task
                results[checker_name] = result
                
                # Store in history
                self.check_history[checker_name].append(result)
                
                # Store in Redis for external monitoring
                await self._store_result_in_redis(checker_name, result)
                
            except Exception as e:
                logger.error("Health check task failed", 
                           checker=checker_name, error=str(e))
                
                # Create failed result
                failed_result = HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    component=checker_name,
                    component_type=ComponentType.UNKNOWN,
                    message=f"Task execution failed: {str(e)}",
                    error=str(e)
                )
                results[checker_name] = failed_result
        
        # Update overall status
        self._update_overall_status(results)
        self.last_check_time = datetime.now()
        
        # Check for failover conditions
        await self._check_failover_conditions(results)
        
        return results
    
    async def _run_checker_with_context(self, checker: HealthChecker) -> HealthCheckResult:
        """Run checker with proper context."""
        try:
            return await checker.run_check()
        except Exception as e:
            logger.error("Health checker execution failed", 
                        checker=checker.name, error=str(e))
            raise
    
    def _update_overall_status(self, results: Dict[str, HealthCheckResult]):
        """Update overall system status."""
        critical_unhealthy = False
        any_unhealthy = False
        any_degraded = False
        
        for checker in self.checkers:
            result = results.get(checker.name)
            if result:
                if result.status == HealthStatus.UNHEALTHY:
                    any_unhealthy = True
                    if checker.critical:
                        critical_unhealthy = True
                elif result.status == HealthStatus.DEGRADED:
                    any_degraded = True
        
        if critical_unhealthy:
            self.overall_status = HealthStatus.UNHEALTHY
        elif any_unhealthy or any_degraded:
            self.overall_status = HealthStatus.DEGRADED
        else:
            self.overall_status = HealthStatus.HEALTHY
    
    async def _store_result_in_redis(self, checker_name: str, result: HealthCheckResult):
        """Store health check result in Redis."""
        try:
            result_data = {
                "status": result.status.value,
                "component": result.component,
                "component_type": result.component_type.value,
                "message": result.message,
                "details": result.details,
                "duration_ms": result.duration_ms,
                "timestamp": result.timestamp.isoformat(),
                "error": result.error
            }
            
            # Store individual result
            await self.redis.setex(
                f"health_check:{checker_name}",
                300,  # 5 minutes TTL
                json.dumps(result_data)
            )
            
            # Store in time series for trending
            await self.redis.zadd(
                f"health_history:{checker_name}",
                {json.dumps(result_data): time.time()}
            )
            
            # Keep only last 100 entries
            await self.redis.zremrangebyrank(f"health_history:{checker_name}", 0, -101)
            
        except Exception as e:
            logger.warning("Failed to store health result in Redis", 
                          checker=checker_name, error=str(e))
    
    async def _check_failover_conditions(self, results: Dict[str, HealthCheckResult]):
        """Check if failover is needed and execute handlers."""
        for checker_name, result in results.items():
            if result.status == HealthStatus.UNHEALTHY:
                # Check if component has been consistently unhealthy
                if self._should_trigger_failover(checker_name):
                    await self._trigger_failover(checker_name, result)
    
    def _should_trigger_failover(self, checker_name: str) -> bool:
        """Determine if failover should be triggered."""
        history = self.check_history[checker_name]
        
        if len(history) < 3:
            return False
        
        # Check if last 3 checks were unhealthy
        recent_checks = list(history)[-3:]
        return all(check.status == HealthStatus.UNHEALTHY for check in recent_checks)
    
    async def _trigger_failover(self, component: str, result: HealthCheckResult):
        """Trigger failover for a component."""
        logger.error("Triggering failover", 
                    component=component, 
                    reason=result.message)
        
        handlers = self.failover_handlers.get(component, [])
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(component, result)
                else:
                    await asyncio.to_thread(handler, component, result)
                    
                logger.info("Failover handler executed", 
                           component=component, 
                           handler=handler.__name__)
                           
            except Exception as e:
                logger.error("Failover handler failed", 
                           component=component, 
                           handler=handler.__name__, 
                           error=str(e))
    
    def get_overall_health(self) -> Dict[str, Any]:
        """Get overall system health."""
        return {
            "status": self.overall_status.value,
            "last_check": self.last_check_time.isoformat() if self.last_check_time else None,
            "components": {
                checker.name: {
                    "status": checker.last_result.status.value if checker.last_result else "unknown",
                    "critical": checker.critical,
                    "last_check": checker.last_result.timestamp.isoformat() if checker.last_result else None,
                    "circuit_breaker": checker.circuit_breaker.get_state()
                }
                for checker in self.checkers
            }
        }
    
    async def get_component_health(self, component: str) -> Optional[Dict[str, Any]]:
        """Get health information for a specific component."""
        checker = next((c for c in self.checkers if c.name == component), None)
        if not checker or not checker.last_result:
            return None
        
        result = checker.last_result
        history = list(self.check_history[component])
        
        return {
            "status": result.status.value,
            "message": result.message,
            "details": result.details,
            "duration_ms": result.duration_ms,
            "timestamp": result.timestamp.isoformat(),
            "error": result.error,
            "critical": checker.critical,
            "circuit_breaker": checker.circuit_breaker.get_state(),
            "history": [
                {
                    "status": h.status.value,
                    "timestamp": h.timestamp.isoformat(),
                    "duration_ms": h.duration_ms,
                    "error": h.error
                }
                for h in history[-10:]  # Last 10 checks
            ]
        }


# Pre-built health checkers
class DatabaseHealthChecker:
    """Database health checker."""
    
    def __init__(self, db_session: AsyncSession, timeout: int = 5):
        self.db_session = db_session
        self.timeout = timeout
    
    async def check(self) -> HealthCheckResult:
        """Check database health."""
        try:
            # Simple query to check connectivity
            result = await self.db_session.execute(text("SELECT 1"))
            row = result.fetchone()
            
            if row and row[0] == 1:
                return HealthCheckResult(
                    status=HealthStatus.HEALTHY,
                    component="database",
                    component_type=ComponentType.DATABASE,
                    message="Database connection successful"
                )
            else:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    component="database",
                    component_type=ComponentType.DATABASE,
                    message="Database query returned unexpected result"
                )
                
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                component="database",
                component_type=ComponentType.DATABASE,
                message=f"Database connection failed: {str(e)}",
                error=str(e)
            )


class RedisHealthChecker:
    """Redis health checker."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def check(self) -> HealthCheckResult:
        """Check Redis health."""
        try:
            # Test Redis connectivity
            pong = await self.redis.ping()
            
            if pong:
                # Get Redis info
                info = await self.redis.info()
                
                details = {
                    "version": info.get("redis_version"),
                    "connected_clients": info.get("connected_clients"),
                    "used_memory_human": info.get("used_memory_human"),
                    "uptime_in_seconds": info.get("uptime_in_seconds")
                }
                
                return HealthCheckResult(
                    status=HealthStatus.HEALTHY,
                    component="redis",
                    component_type=ComponentType.CACHE,
                    message="Redis connection successful",
                    details=details
                )
            else:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    component="redis",
                    component_type=ComponentType.CACHE,
                    message="Redis ping failed"
                )
                
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                component="redis",
                component_type=ComponentType.CACHE,
                message=f"Redis connection failed: {str(e)}",
                error=str(e)
            )


class HTTPHealthChecker:
    """HTTP service health checker."""
    
    def __init__(self, url: str, expected_status: int = 200, timeout: int = 5):
        self.url = url
        self.expected_status = expected_status
        self.timeout = timeout
    
    async def check(self) -> HealthCheckResult:
        """Check HTTP service health."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.url)
                
                details = {
                    "url": self.url,
                    "status_code": response.status_code,
                    "response_time_ms": response.elapsed.total_seconds() * 1000,
                    "headers": dict(response.headers)
                }
                
                if response.status_code == self.expected_status:
                    return HealthCheckResult(
                        status=HealthStatus.HEALTHY,
                        component=f"http_{self.url}",
                        component_type=ComponentType.EXTERNAL_API,
                        message=f"HTTP check successful ({response.status_code})",
                        details=details
                    )
                else:
                    return HealthCheckResult(
                        status=HealthStatus.UNHEALTHY,
                        component=f"http_{self.url}",
                        component_type=ComponentType.EXTERNAL_API,
                        message=f"HTTP check failed - expected {self.expected_status}, got {response.status_code}",
                        details=details
                    )
                    
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                component=f"http_{self.url}",
                component_type=ComponentType.EXTERNAL_API,
                message=f"HTTP check failed: {str(e)}",
                error=str(e)
            )


# Failover handlers
class DatabaseFailoverHandler:
    """Database failover handler."""
    
    def __init__(self, primary_config: Dict[str, str], backup_config: Dict[str, str]):
        self.primary_config = primary_config
        self.backup_config = backup_config
        self.using_backup = False
    
    async def handle_failover(self, component: str, result: HealthCheckResult):
        """Handle database failover."""
        if not self.using_backup:
            logger.warning("Failing over to backup database", 
                          component=component, reason=result.message)
            
            # Switch to backup database
            # This would update your database connection configuration
            self.using_backup = True
            
            # Notify about failover
            await self._notify_failover("database", "backup")
    
    async def handle_recovery(self, component: str, result: HealthCheckResult):
        """Handle database recovery."""
        if self.using_backup and result.status == HealthStatus.HEALTHY:
            logger.info("Primary database recovered, failing back", component=component)
            
            # Switch back to primary
            self.using_backup = False
            
            # Notify about recovery
            await self._notify_failover("database", "primary")
    
    async def _notify_failover(self, component: str, target: str):
        """Notify about failover event."""
        # This would send notifications to monitoring systems
        logger.info("Failover notification", component=component, target=target)


# Utility functions
async def setup_health_monitoring(redis_client: redis.Redis, 
                                db_session: AsyncSession) -> HealthMonitor:
    """Set up comprehensive health monitoring."""
    monitor = HealthMonitor(redis_client)
    
    # Database health check
    db_checker = HealthChecker(
        name="database",
        component_type=ComponentType.DATABASE,
        check_func=DatabaseHealthChecker(db_session).check,
        timeout=10,
        critical=True
    )
    monitor.add_checker(db_checker)
    
    # Redis health check
    redis_checker = HealthChecker(
        name="redis",
        component_type=ComponentType.CACHE,
        check_func=RedisHealthChecker(redis_client).check,
        timeout=5,
        critical=True
    )
    monitor.add_checker(redis_checker)
    
    # External API health checks
    external_apis = [
        ("payment_gateway", "https://api.stripe.com/health"),
        ("email_service", "https://api.sendgrid.com/v3/health"),
        ("sms_service", "https://api.twilio.com/health")
    ]
    
    for name, url in external_apis:
        api_checker = HealthChecker(
            name=name,
            component_type=ComponentType.EXTERNAL_API,
            check_func=HTTPHealthChecker(url).check,
            timeout=10,
            critical=False
        )
        monitor.add_checker(api_checker)
    
    # Add failover handlers
    # db_failover = DatabaseFailoverHandler(primary_config, backup_config)
    # monitor.add_failover_handler("database", db_failover.handle_failover)
    
    logger.info("Health monitoring configured", 
               checkers=len(monitor.checkers))
    
    return monitor


# Background task for continuous health monitoring
async def health_monitoring_task(monitor: HealthMonitor, interval: int = 60):
    """Background task for continuous health monitoring."""
    logger.info("Starting health monitoring task", interval=interval)
    
    while True:
        try:
            results = await monitor.run_all_checks()
            
            # Log overall status
            overall_health = monitor.get_overall_health()
            logger.info("Health check completed", 
                       status=overall_health["status"],
                       components_checked=len(results))
            
            # Log any unhealthy components
            for name, result in results.items():
                if result.status in [HealthStatus.UNHEALTHY, HealthStatus.DEGRADED]:
                    logger.warning("Unhealthy component detected", 
                                 component=name,
                                 status=result.status.value,
                                 message=result.message)
            
        except Exception as e:
            logger.error("Health monitoring task error", error=str(e))
        
        # Wait for next check
        await asyncio.sleep(interval)


# FastAPI integration
from fastapi import FastAPI, Response, status

def add_health_endpoints(app: FastAPI, monitor: HealthMonitor):
    """Add health endpoints to FastAPI app."""
    
    @app.get("/health")
    async def health_check():
        """Simple health check endpoint."""
        overall_health = monitor.get_overall_health()
        
        if overall_health["status"] == HealthStatus.HEALTHY.value:
            return {"status": "healthy"}
        elif overall_health["status"] == HealthStatus.DEGRADED.value:
            return Response(
                content=json.dumps({"status": "degraded"}),
                status_code=status.HTTP_200_OK,
                media_type="application/json"
            )
        else:
            return Response(
                content=json.dumps({"status": "unhealthy"}),
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                media_type="application/json"
            )
    
    @app.get("/health/detailed")
    async def detailed_health_check():
        """Detailed health check endpoint."""
        overall_health = monitor.get_overall_health()
        
        status_code = status.HTTP_200_OK
        if overall_health["status"] == HealthStatus.UNHEALTHY.value:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        elif overall_health["status"] == HealthStatus.DEGRADED.value:
            status_code = status.HTTP_200_OK
        
        return Response(
            content=json.dumps(overall_health),
            status_code=status_code,
            media_type="application/json"
        )
    
    @app.get("/health/{component}")
    async def component_health_check(component: str):
        """Component-specific health check."""
        component_health = await monitor.get_component_health(component)
        
        if not component_health:
            return Response(
                content=json.dumps({"error": "Component not found"}),
                status_code=status.HTTP_404_NOT_FOUND,
                media_type="application/json"
            )
        
        status_code = status.HTTP_200_OK
        if component_health["status"] == HealthStatus.UNHEALTHY.value:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        
        return Response(
            content=json.dumps(component_health),
            status_code=status_code,
            media_type="application/json"
        )
    
    @app.get("/ready")
    async def readiness_check():
        """Kubernetes readiness probe endpoint."""
        overall_health = monitor.get_overall_health()
        
        # Ready if not unhealthy
        if overall_health["status"] != HealthStatus.UNHEALTHY.value:
            return {"status": "ready"}
        else:
            return Response(
                content=json.dumps({"status": "not ready"}),
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                media_type="application/json"
            )
    
    @app.get("/live")
    async def liveness_check():
        """Kubernetes liveness probe endpoint."""
        # Always return healthy unless the service is completely down
        return {"status": "alive"}