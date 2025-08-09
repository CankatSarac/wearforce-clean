"""
Batch request processor for efficient LLM inference.

Features:
- Request batching with configurable size and timeout
- Priority queue for request ordering
- Background processing with asyncio
- Batch status tracking and results storage
"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4
import psutil
import gc

import structlog
from shared.database import RedisManager
from shared.monitoring import get_metrics
from shared.task_manager import get_task_manager, create_managed_task

logger = structlog.get_logger(__name__)


class BatchStatus(str, Enum):
    """Batch processing status."""
    QUEUED = "queued"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RequestPriority(int, Enum):
    """Request priority levels."""
    LOW = 0
    NORMAL = 5
    HIGH = 10


@dataclass
class BatchRequest:
    """Individual request in a batch."""
    id: str
    model_name: str
    prompt: str
    max_tokens: int = 1024
    temperature: float = 0.7
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop: Optional[List[str]] = None
    priority: RequestPriority = RequestPriority.NORMAL
    created_at: float = field(default_factory=time.time)
    callback: Optional[Callable[[str, Dict[str, Any]], None]] = None


@dataclass 
class Batch:
    """Batch of requests."""
    id: str
    requests: List[BatchRequest] = field(default_factory=list)
    status: BatchStatus = BatchStatus.QUEUED
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    results: Dict[str, Any] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)


class BatchProcessor:
    """Batch processor for LLM requests."""
    
    def __init__(
        self,
        engine_manager,
        max_batch_size: int = 32,
        batch_timeout: float = 0.1,
        max_concurrent_batches: int = 4,
        redis_manager: Optional[RedisManager] = None,
    ):
        self.engine_manager = engine_manager
        self.max_batch_size = max_batch_size
        self.batch_timeout = batch_timeout
        self.max_concurrent_batches = max_concurrent_batches
        self.redis_manager = redis_manager
        
        # Request queue (priority queue)
        self.request_queue: List[BatchRequest] = []
        self.batch_queue: deque[Batch] = deque()
        self.active_batches: Dict[str, Batch] = {}
        self.completed_batches: Dict[str, Batch] = {}
        
        # Processing control
        self.is_running = False
        self.processor_task: Optional[asyncio.Task] = None
        self._queue_lock = asyncio.Lock()
        self.task_manager = get_task_manager()
        
        # Load balancing
        self.model_load: Dict[str, int] = {}  # Track current load per model
        self.model_performance: Dict[str, List[float]] = {}  # Track performance history
        
        # Memory management
        self.memory_threshold = 0.8  # Trigger cleanup at 80% memory usage
        self.last_memory_check = time.time()
        
        # Statistics
        self.total_requests = 0
        self.total_batches = 0
        self.successful_requests = 0
        self.failed_requests = 0
    
    async def start(self) -> None:
        """Start the batch processor."""
        if self.is_running:
            return
        
        logger.info("Starting batch processor")
        self.is_running = True
        self.processor_task = asyncio.create_task(self._process_loop())
    
    async def stop(self) -> None:
        """Stop the batch processor."""
        if not self.is_running:
            return
        
        logger.info("Stopping batch processor")
        self.is_running = False
        
        if self.processor_task:
            self.processor_task.cancel()
            try:
                await self.processor_task
            except asyncio.CancelledError:
                pass
    
    async def add_request(self, request: BatchRequest) -> str:
        """Add a request to the batch queue."""
        async with self._queue_lock:
            # Insert request in priority order
            inserted = False
            for i, existing_request in enumerate(self.request_queue):
                if request.priority > existing_request.priority:
                    self.request_queue.insert(i, request)
                    inserted = True
                    break
            
            if not inserted:
                self.request_queue.append(request)
            
            self.total_requests += 1
        
        logger.debug(f"Added request {request.id} to queue", priority=request.priority)
        return request.id
    
    async def generate(
        self,
        model_name: str,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        top_p: float = 1.0,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        stop: Optional[List[str]] = None,
        priority: RequestPriority = RequestPriority.NORMAL,
    ) -> Dict[str, Any]:
        """Generate text with batching."""
        request_id = str(uuid4())
        
        # Create future for result
        future = asyncio.Future()
        
        def callback(req_id: str, result: Dict[str, Any]) -> None:
            if req_id == request_id:
                if "error" in result:
                    future.set_exception(Exception(result["error"]))
                else:
                    future.set_result(result)
        
        # Create batch request
        batch_request = BatchRequest(
            id=request_id,
            model_name=model_name,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            stop=stop,
            priority=priority,
            callback=callback,
        )
        
        # Add to queue
        await self.add_request(batch_request)
        
        # Wait for result
        return await future
    
    async def process_batch(self, batch_id: str, requests: List[Dict[str, Any]]) -> None:
        """Process a batch of requests (external API)."""
        batch = Batch(id=batch_id)
        
        # Convert dict requests to BatchRequest objects
        for i, req_data in enumerate(requests):
            batch_request = BatchRequest(
                id=f"{batch_id}_{i}",
                model_name=req_data.get("model", "gpt-oss-20b"),
                prompt=req_data.get("prompt", ""),
                max_tokens=req_data.get("max_tokens", 1024),
                temperature=req_data.get("temperature", 0.7),
                priority=RequestPriority.NORMAL,
            )
            batch.requests.append(batch_request)
        
        # Add batch to processing queue
        self.batch_queue.append(batch)
        self.total_batches += 1
        
        # Store batch info in Redis if available
        if self.redis_manager:
            await self._store_batch_info(batch)
    
    async def get_batch_status(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a batch."""
        # Check active batches
        if batch_id in self.active_batches:
            batch = self.active_batches[batch_id]
            return self._batch_to_dict(batch)
        
        # Check completed batches
        if batch_id in self.completed_batches:
            batch = self.completed_batches[batch_id]
            return self._batch_to_dict(batch)
        
        # Check Redis if available
        if self.redis_manager:
            batch_data = await self.redis_manager.get(f"batch:{batch_id}")
            if batch_data:
                import json
                return json.loads(batch_data)
        
        return None
    
    async def health_check(self) -> bool:
        """Check if batch processor is healthy."""
        return self.is_running and (self.processor_task is None or not self.processor_task.done())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get batch processor statistics."""
        return {
            "is_running": self.is_running,
            "queue_size": len(self.request_queue),
            "active_batches": len(self.active_batches),
            "completed_batches": len(self.completed_batches),
            "total_requests": self.total_requests,
            "total_batches": self.total_batches,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.successful_requests / max(self.total_requests, 1),
        }
    
    async def _process_loop(self) -> None:
        """Main processing loop."""
        logger.info("Batch processor loop started")
        
        try:
            while self.is_running:
                # Process individual requests into batches
                await self._create_batches()
                
                # Process external batches
                await self._process_external_batches()
                
                # Clean up old completed batches
                await self._cleanup_completed_batches()
                
                # Check memory usage
                await self._check_memory_usage()
                
                # Short sleep to prevent busy waiting
                await asyncio.sleep(0.01)
                
        except asyncio.CancelledError:
            logger.info("Batch processor loop cancelled")
        except Exception as e:
            logger.error("Batch processor loop error", error=str(e), exc_info=True)
        finally:
            logger.info("Batch processor loop stopped")
    
    async def _create_batches(self) -> None:
        """Create batches from individual requests."""
        if len(self.active_batches) >= self.max_concurrent_batches:
            return
        
        async with self._queue_lock:
            if not self.request_queue:
                return
            
            # Create batch from queued requests
            batch_requests = []
            batch_start_time = time.time()
            
            while (
                len(batch_requests) < self.max_batch_size
                and len(self.request_queue) > 0
                and (time.time() - batch_start_time < self.batch_timeout or len(batch_requests) == 0)
            ):
                batch_requests.append(self.request_queue.pop(0))
            
            if batch_requests:
                batch_id = str(uuid4())
                batch = Batch(id=batch_id, requests=batch_requests)
                
                # Start processing batch
                asyncio.create_task(self._process_batch(batch))
    
    async def _process_batch(self, batch: Batch) -> None:
        """Process a single batch."""
        batch.status = BatchStatus.PROCESSING
        batch.started_at = time.time()
        self.active_batches[batch.id] = batch
        
        logger.info(f"Processing batch {batch.id} with {len(batch.requests)} requests")
        
        try:
            # Group requests by optimal model (load balanced)
            model_groups = {}
            for request in batch.requests:
                optimal_model = self._select_optimal_model(request.model_name)
                request.model_name = optimal_model  # Update to optimal model
                
                if optimal_model not in model_groups:
                    model_groups[optimal_model] = []
                model_groups[optimal_model].append(request)
            
            # Process each model group
            for model_name, requests in model_groups.items():
                # Update load counter
                self._update_model_load(model_name, 1)
                
                try:
                    await self._process_model_group(batch, model_name, requests)
                finally:
                    # Decrease load counter
                    self._update_model_load(model_name, -1)
            
            batch.status = BatchStatus.COMPLETED
            batch.completed_at = time.time()
            
            logger.info(f"Completed batch {batch.id}")
            
            # Record metrics
            metrics = get_metrics()
            if metrics:
                processing_time = batch.completed_at - batch.started_at
                metrics.record_inference(f"batch_{model_name}", processing_time)
            
        except Exception as e:
            batch.status = BatchStatus.FAILED
            batch.completed_at = time.time()
            logger.error(f"Batch {batch.id} failed", error=str(e))
            
            # Mark all requests as failed
            for request in batch.requests:
                batch.errors[request.id] = str(e)
                if request.callback:
                    request.callback(request.id, {"error": str(e)})
                self.failed_requests += 1
        finally:
            # Move to completed batches
            if batch.id in self.active_batches:
                del self.active_batches[batch.id]
            
            self.completed_batches[batch.id] = batch
            
            # Store in Redis if available
            if self.redis_manager:
                await self._store_batch_info(batch)
    
    async def _process_model_group(
        self,
        batch: Batch,
        model_name: str,
        requests: List[BatchRequest],
    ) -> None:
        """Process requests for a specific model."""
        start_time = time.time()
        
        try:
            # Process requests concurrently (up to a limit)
            max_concurrent = min(len(requests), 8)
            semaphore = asyncio.Semaphore(max_concurrent)
            
            tasks = []
            for request in requests:
                task = asyncio.create_task(
                    self._process_single_request(batch, request, semaphore)
                )
                tasks.append(task)
            
            # Wait for all requests to complete
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Record performance for load balancing
            processing_time = time.time() - start_time
            self._record_model_performance(model_name, processing_time)
            
        except Exception as e:
            logger.error(f"Failed to process model group {model_name}", error=str(e))
            raise
    
    async def _process_single_request(
        self,
        batch: Batch,
        request: BatchRequest,
        semaphore: asyncio.Semaphore,
    ) -> None:
        """Process a single request."""
        async with semaphore:
            try:
                # Generate response using engine manager
                result = await self.engine_manager.generate(
                    model_name=request.model_name,
                    prompt=request.prompt,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    top_p=request.top_p,
                    frequency_penalty=request.frequency_penalty,
                    presence_penalty=request.presence_penalty,
                    stop=request.stop,
                )
                
                batch.results[request.id] = result
                
                # Call callback if provided
                if request.callback:
                    request.callback(request.id, result)
                
                self.successful_requests += 1
                
            except Exception as e:
                error_msg = str(e)
                batch.errors[request.id] = error_msg
                
                if request.callback:
                    request.callback(request.id, {"error": error_msg})
                
                self.failed_requests += 1
                logger.error(f"Request {request.id} failed", error=error_msg)
    
    async def _process_external_batches(self) -> None:
        """Process batches from external API."""
        while self.batch_queue and len(self.active_batches) < self.max_concurrent_batches:
            batch = self.batch_queue.popleft()
            asyncio.create_task(self._process_batch(batch))
    
    async def _cleanup_completed_batches(self) -> None:
        """Clean up old completed batches."""
        current_time = time.time()
        max_age = 3600  # Keep completed batches for 1 hour
        
        to_remove = []
        for batch_id, batch in self.completed_batches.items():
            if batch.completed_at and current_time - batch.completed_at > max_age:
                to_remove.append(batch_id)
        
        for batch_id in to_remove:
            del self.completed_batches[batch_id]
            
            # Remove from Redis if available
            if self.redis_manager:
                await self.redis_manager.delete(f"batch:{batch_id}")
    
    async def _store_batch_info(self, batch: Batch) -> None:
        """Store batch information in Redis."""
        try:
            batch_data = self._batch_to_dict(batch)
            await self.redis_manager.set(
                f"batch:{batch.id}",
                str(batch_data),
                ex=3600,  # 1 hour expiration
            )
        except Exception as e:
            logger.warning(f"Failed to store batch info", error=str(e))
    
    def _batch_to_dict(self, batch: Batch) -> Dict[str, Any]:
        """Convert batch to dictionary."""
        return {
            "id": batch.id,
            "status": batch.status.value,
            "created_at": batch.created_at,
            "started_at": batch.started_at,
            "completed_at": batch.completed_at,
            "request_count": len(batch.requests),
            "completed_count": len(batch.results),
            "error_count": len(batch.errors),
            "results": batch.results,
            "errors": batch.errors,
        }
    
    def _select_optimal_model(self, requested_model: str) -> str:
        """Select optimal model based on load balancing."""
        available_models = self.engine_manager.list_models()
        
        # If requested model is available and not overloaded, use it
        if requested_model in available_models:
            current_load = self.model_load.get(requested_model, 0)
            if current_load < self.max_concurrent_batches // len(available_models):
                return requested_model
        
        # Find model with lowest load
        best_model = requested_model
        lowest_load = float('inf')
        
        for model in available_models:
            load = self.model_load.get(model, 0)
            performance = self.model_performance.get(model, [])
            
            # Calculate weighted load (consider both current load and performance)
            avg_performance = sum(performance[-10:]) / len(performance[-10:]) if performance else 1.0
            weighted_load = load + (avg_performance / 10.0)  # Factor in response time
            
            if weighted_load < lowest_load:
                lowest_load = weighted_load
                best_model = model
        
        return best_model
    
    def _update_model_load(self, model_name: str, delta: int) -> None:
        """Update model load counter."""
        if model_name not in self.model_load:
            self.model_load[model_name] = 0
        
        self.model_load[model_name] = max(0, self.model_load[model_name] + delta)
    
    def _record_model_performance(self, model_name: str, response_time: float) -> None:
        """Record model performance for load balancing."""
        if model_name not in self.model_performance:
            self.model_performance[model_name] = []
        
        # Keep last 100 performance records
        perf_list = self.model_performance[model_name]
        perf_list.append(response_time)
        if len(perf_list) > 100:
            perf_list.pop(0)
    
    async def _check_memory_usage(self) -> None:
        """Check memory usage and trigger cleanup if needed."""
        current_time = time.time()
        
        # Check memory every 30 seconds
        if current_time - self.last_memory_check < 30:
            return
            
        self.last_memory_check = current_time
        
        try:
            memory_percent = psutil.virtual_memory().percent / 100.0
            
            if memory_percent > self.memory_threshold:
                logger.warning(f"High memory usage: {memory_percent:.1%}, triggering cleanup")
                
                # Force garbage collection
                gc.collect()
                
                # Clean up old completed batches more aggressively
                current_time = time.time()
                max_age = 300  # 5 minutes instead of 1 hour
                
                to_remove = []
                for batch_id, batch in self.completed_batches.items():
                    if batch.completed_at and current_time - batch.completed_at > max_age:
                        to_remove.append(batch_id)
                
                for batch_id in to_remove:
                    del self.completed_batches[batch_id]
                    
                    # Remove from Redis if available
                    if self.redis_manager:
                        try:
                            await self.redis_manager.delete(f"batch:{batch_id}")
                        except Exception as e:
                            logger.warning(f"Failed to delete batch from Redis: {e}")
                
                logger.info(f"Cleaned up {len(to_remove)} old batches due to memory pressure")
                
        except Exception as e:
            logger.warning(f"Memory check failed: {e}")