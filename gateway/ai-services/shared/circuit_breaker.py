"""Circuit breaker pattern implementation for external service calls."""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
import statistics

import structlog

logger = structlog.get_logger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5  # Number of failures to open circuit
    recovery_timeout: float = 60.0  # Time to wait before trying again
    expected_exception: Union[Exception, tuple] = Exception
    success_threshold: int = 3  # Successful calls needed to close circuit
    timeout: float = 30.0  # Request timeout
    monitor_period: float = 60.0  # Monitoring window in seconds
    max_failures_per_window: int = 10  # Max failures in window
    slow_call_threshold: float = 5.0  # Threshold for slow calls
    slow_call_rate_threshold: float = 0.5  # Max rate of slow calls


@dataclass
class CallResult:
    """Result of a service call."""
    success: bool
    duration: float
    timestamp: float
    exception: Optional[Exception] = None
    was_timeout: bool = False


class CircuitBreaker:
    """Circuit breaker for external service calls."""
    
    def __init__(self, 
                 name: str,
                 config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        # State management
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0
        
        # Call history for monitoring
        self.call_history: List[CallResult] = []
        self._lock = asyncio.Lock()
        
        # Statistics
        self.total_calls = 0
        self.total_failures = 0
        self.total_timeouts = 0
        self.total_rejections = 0
        
        logger.info(f"Circuit breaker '{name}' initialized", 
                   state=self.state.value,
                   config=self.config)
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        self.total_calls += 1
        
        async with self._lock:
            # Check if circuit is open
            if await self._should_reject_call():
                self.total_rejections += 1
                raise CircuitBreakerError(
                    f"Circuit breaker '{self.name}' is {self.state.value}"
                )
            
            # If half-open, only allow limited calls
            if self.state == CircuitBreakerState.HALF_OPEN:
                if self.success_count >= self.config.success_threshold:
                    await self._close_circuit()
        
        # Execute the call with timeout
        start_time = time.time()
        call_result = None
        
        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                func(*args, **kwargs) if asyncio.iscoroutinefunction(func) 
                else func(*args, **kwargs),
                timeout=self.config.timeout
            )
            
            duration = time.time() - start_time
            call_result = CallResult(
                success=True,
                duration=duration,
                timestamp=start_time
            )
            
            await self._record_success(call_result)
            return result
            
        except asyncio.TimeoutError as e:
            duration = time.time() - start_time
            call_result = CallResult(
                success=False,
                duration=duration,
                timestamp=start_time,
                exception=e,
                was_timeout=True
            )
            
            self.total_timeouts += 1
            await self._record_failure(call_result)
            raise ServiceTimeoutError(
                f"Service call timed out after {self.config.timeout}s"
            ) from e
            
        except self.config.expected_exception as e:
            duration = time.time() - start_time
            call_result = CallResult(
                success=False,
                duration=duration,
                timestamp=start_time,
                exception=e
            )
            
            await self._record_failure(call_result)
            raise
            
        finally:
            # Clean old history
            await self._clean_call_history()
    
    async def _should_reject_call(self) -> bool:
        """Check if call should be rejected."""
        if self.state == CircuitBreakerState.CLOSED:
            return False
        
        if self.state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has passed
            if time.time() - self.last_failure_time >= self.config.recovery_timeout:
                await self._transition_to_half_open()
                return False
            return True
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            # Allow limited calls to test recovery
            return self.success_count >= self.config.success_threshold
        
        return False
    
    async def _record_success(self, call_result: CallResult) -> None:
        """Record successful call."""
        self.call_history.append(call_result)
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                await self._close_circuit()
        elif self.state == CircuitBreakerState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0
    
    async def _record_failure(self, call_result: CallResult) -> None:
        """Record failed call."""
        self.call_history.append(call_result)
        self.total_failures += 1
        self.failure_count += 1
        self.last_failure_time = call_result.timestamp
        
        if self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                await self._open_circuit()
        elif self.state == CircuitBreakerState.HALF_OPEN:
            # Reset to open on any failure during half-open
            await self._open_circuit()
    
    async def _open_circuit(self) -> None:
        """Open the circuit breaker."""
        self.state = CircuitBreakerState.OPEN
        self.success_count = 0
        
        logger.warning(f"Circuit breaker '{self.name}' opened",
                      failure_count=self.failure_count,
                      last_failure_time=self.last_failure_time)
    
    async def _transition_to_half_open(self) -> None:
        """Transition to half-open state."""
        self.state = CircuitBreakerState.HALF_OPEN
        self.success_count = 0
        self.failure_count = 0
        
        logger.info(f"Circuit breaker '{self.name}' transitioned to half-open")
    
    async def _close_circuit(self) -> None:
        """Close the circuit breaker."""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        
        logger.info(f"Circuit breaker '{self.name}' closed - service recovered")
    
    async def _clean_call_history(self) -> None:
        """Clean old call history."""
        current_time = time.time()
        window_start = current_time - self.config.monitor_period
        
        # Keep only calls within the monitoring window
        self.call_history = [
            call for call in self.call_history
            if call.timestamp >= window_start
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        current_time = time.time()
        window_start = current_time - self.config.monitor_period
        
        # Calculate stats for recent calls
        recent_calls = [
            call for call in self.call_history
            if call.timestamp >= window_start
        ]
        
        if recent_calls:
            success_calls = [call for call in recent_calls if call.success]
            failed_calls = [call for call in recent_calls if not call.success]
            timeout_calls = [call for call in recent_calls if call.was_timeout]
            
            success_rate = len(success_calls) / len(recent_calls)
            failure_rate = len(failed_calls) / len(recent_calls)
            timeout_rate = len(timeout_calls) / len(recent_calls)
            
            # Calculate response time stats
            durations = [call.duration for call in recent_calls]
            avg_response_time = statistics.mean(durations) if durations else 0.0
            p95_response_time = (
                statistics.quantiles(durations, n=20)[18] 
                if len(durations) > 1 else durations[0] if durations else 0.0
            )
            
            # Slow call rate
            slow_calls = [
                call for call in recent_calls 
                if call.duration > self.config.slow_call_threshold
            ]
            slow_call_rate = len(slow_calls) / len(recent_calls) if recent_calls else 0.0
        else:
            success_rate = 1.0
            failure_rate = 0.0
            timeout_rate = 0.0
            avg_response_time = 0.0
            p95_response_time = 0.0
            slow_call_rate = 0.0
        
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "total_timeouts": self.total_timeouts,
            "total_rejections": self.total_rejections,
            "recent_calls_count": len(recent_calls),
            "success_rate": success_rate,
            "failure_rate": failure_rate,
            "timeout_rate": timeout_rate,
            "slow_call_rate": slow_call_rate,
            "avg_response_time": avg_response_time,
            "p95_response_time": p95_response_time,
            "last_failure_time": self.last_failure_time,
            "time_since_last_failure": current_time - self.last_failure_time,
        }
    
    async def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        async with self._lock:
            self.state = CircuitBreakerState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.call_history.clear()
            
        logger.info(f"Circuit breaker '{self.name}' reset")
    
    async def force_open(self) -> None:
        """Force circuit breaker to open state."""
        async with self._lock:
            await self._open_circuit()
        
        logger.warning(f"Circuit breaker '{self.name}' forced open")
    
    async def health_check(self) -> bool:
        """Check if the service behind the circuit breaker is healthy."""
        stats = self.get_stats()
        
        # Consider healthy if:
        # - Circuit is closed OR
        # - Success rate is good and response times are acceptable
        if self.state == CircuitBreakerState.CLOSED:
            return True
        
        return (
            stats["success_rate"] >= 0.9 and
            stats["slow_call_rate"] <= self.config.slow_call_rate_threshold and
            stats["timeout_rate"] <= 0.1
        )


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker rejects a call."""
    pass


class ServiceTimeoutError(Exception):
    """Exception raised when service call times out."""
    pass


class CircuitBreakerManager:
    """Manager for multiple circuit breakers."""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
    
    async def get_circuit_breaker(self, 
                                 name: str,
                                 config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """Get or create a circuit breaker."""
        async with self._lock:
            if name not in self.circuit_breakers:
                self.circuit_breakers[name] = CircuitBreaker(name, config)
        
        return self.circuit_breakers[name]
    
    async def call_with_breaker(self, 
                               service_name: str,
                               func: Callable,
                               *args,
                               config: Optional[CircuitBreakerConfig] = None,
                               **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        breaker = await self.get_circuit_breaker(service_name, config)
        return await breaker.call(func, *args, **kwargs)
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get stats for all circuit breakers."""
        return {
            name: breaker.get_stats()
            for name, breaker in self.circuit_breakers.items()
        }
    
    async def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self.circuit_breakers.values():
            await breaker.reset()
    
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all services."""
        return {
            name: await breaker.health_check()
            for name, breaker in self.circuit_breakers.items()
        }


# Global circuit breaker manager
circuit_breaker_manager = CircuitBreakerManager()


# Convenience functions
async def call_with_circuit_breaker(service_name: str,
                                   func: Callable,
                                   *args,
                                   config: Optional[CircuitBreakerConfig] = None,
                                   **kwargs) -> Any:
    """Execute function with circuit breaker protection."""
    return await circuit_breaker_manager.call_with_breaker(
        service_name, func, *args, config=config, **kwargs
    )


def circuit_breaker(service_name: str,
                   config: Optional[CircuitBreakerConfig] = None):
    """Decorator for circuit breaker protection."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            return await call_with_circuit_breaker(
                service_name, func, *args, config=config, **kwargs
            )
        
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(async_wrapper(*args, **kwargs))
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Health check integration
async def get_circuit_breaker_health() -> Dict[str, Any]:
    """Get health status of all circuit breakers."""
    health_status = await circuit_breaker_manager.health_check()
    all_stats = circuit_breaker_manager.get_all_stats()
    
    overall_healthy = all(health_status.values()) if health_status else True
    
    return {
        "status": "healthy" if overall_healthy else "unhealthy",
        "circuit_breakers": {
            name: {
                "healthy": health_status.get(name, True),
                "stats": all_stats.get(name, {}),
            }
            for name in set(list(health_status.keys()) + list(all_stats.keys()))
        },
        "overall_healthy": overall_healthy,
        "total_breakers": len(circuit_breaker_manager.circuit_breakers),
    }