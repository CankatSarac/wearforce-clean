"""Task management utilities to prevent memory leaks and ensure proper cleanup."""

import asyncio
import gc
import signal
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
import weakref
import psutil
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class TaskInfo:
    """Information about a managed task."""
    task: asyncio.Task
    name: str
    created_at: float = field(default_factory=time.time)
    context: Optional[str] = None
    timeout: Optional[float] = None
    cleanup_callback: Optional[Callable] = None


class TaskManager:
    """Manages asyncio tasks to prevent leaks and ensure proper cleanup."""
    
    def __init__(self, max_tasks: int = 1000):
        self.max_tasks = max_tasks
        self.tasks: Dict[str, TaskInfo] = {}
        self.task_groups: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()
        
        # Monitoring
        self.total_created = 0
        self.total_completed = 0
        self.total_cancelled = 0
        self.total_failed = 0
        
        # Cleanup configuration
        self.cleanup_interval = 60.0  # seconds
        self.task_timeout_default = 300.0  # 5 minutes
        self.memory_threshold = 0.8  # 80% memory usage
        
        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Weak references to avoid circular dependencies
        self._cleanup_callbacks: weakref.WeakSet = weakref.WeakSet()
    
    async def start(self) -> None:
        """Start the task manager."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Task manager started")
    
    async def stop(self, timeout: float = 30.0) -> None:
        """Stop the task manager and cleanup all tasks."""
        logger.info("Stopping task manager...")
        self._shutdown_event.set()
        
        # Cancel cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await asyncio.wait_for(self._cleanup_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        
        # Cancel all managed tasks
        await self._cancel_all_tasks(timeout=timeout)
        
        logger.info("Task manager stopped")
    
    async def create_task(self,
                         coro,
                         name: Optional[str] = None,
                         context: Optional[str] = None,
                         timeout: Optional[float] = None,
                         cleanup_callback: Optional[Callable] = None,
                         group: Optional[str] = None) -> asyncio.Task:
        """Create and register a managed task."""
        if len(self.tasks) >= self.max_tasks:
            await self._emergency_cleanup()
            if len(self.tasks) >= self.max_tasks:
                raise RuntimeError(f"Task limit reached: {self.max_tasks}")
        
        task = asyncio.create_task(coro)
        task_id = id(task)
        task_name = name or f"task_{task_id}"
        
        # Set task name for debugging
        task.set_name(task_name)
        
        # Create task info
        task_info = TaskInfo(
            task=task,
            name=task_name,
            context=context,
            timeout=timeout or self.task_timeout_default,
            cleanup_callback=cleanup_callback
        )
        
        async with self._lock:
            self.tasks[str(task_id)] = task_info
            self.total_created += 1
            
            # Add to group if specified
            if group:
                if group not in self.task_groups:
                    self.task_groups[group] = set()
                self.task_groups[group].add(str(task_id))
        
        # Add done callback for automatic cleanup
        task.add_done_callback(lambda t: asyncio.create_task(self._task_done_callback(str(task_id))))
        
        logger.debug(f"Created managed task: {task_name}", 
                    task_id=task_id, 
                    context=context,
                    timeout=timeout)
        
        return task
    
    async def cancel_task(self, task_id: str, timeout: float = 5.0) -> bool:
        """Cancel a specific task."""
        async with self._lock:
            task_info = self.tasks.get(task_id)
            if not task_info:
                return False
        
        task = task_info.task
        if task.done():
            return True
        
        task.cancel()
        
        try:
            await asyncio.wait_for(task, timeout=timeout)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        
        await self._cleanup_task_info(task_id)
        return True
    
    async def cancel_group(self, group: str, timeout: float = 10.0) -> int:
        """Cancel all tasks in a group."""
        async with self._lock:
            task_ids = self.task_groups.get(group, set()).copy()
        
        if not task_ids:
            return 0
        
        # Cancel all tasks in parallel
        cancel_tasks = []
        for task_id in task_ids:
            cancel_tasks.append(self.cancel_task(task_id, timeout=timeout))
        
        results = await asyncio.gather(*cancel_tasks, return_exceptions=True)
        cancelled_count = sum(1 for result in results if result is True)
        
        # Clean up group
        async with self._lock:
            if group in self.task_groups:
                del self.task_groups[group]
        
        logger.info(f"Cancelled task group '{group}': {cancelled_count}/{len(task_ids)} tasks")
        return cancelled_count
    
    async def wait_for_completion(self, 
                                 timeout: Optional[float] = None,
                                 group: Optional[str] = None) -> Dict[str, Any]:
        """Wait for all tasks (or group) to complete."""
        if group:
            async with self._lock:
                task_ids = self.task_groups.get(group, set()).copy()
            
            tasks = []
            for task_id in task_ids:
                if task_id in self.tasks:
                    tasks.append(self.tasks[task_id].task)
        else:
            async with self._lock:
                tasks = [info.task for info in self.tasks.values() if not info.task.done()]
        
        if not tasks:
            return {"completed": 0, "cancelled": 0, "failed": 0}
        
        try:
            done, pending = await asyncio.wait(
                tasks,
                timeout=timeout,
                return_when=asyncio.ALL_COMPLETED
            )
            
            # Cancel any pending tasks
            for task in pending:
                task.cancel()
            
            # Count results
            completed = sum(1 for task in done if not task.cancelled() and task.exception() is None)
            cancelled = sum(1 for task in done if task.cancelled())
            failed = sum(1 for task in done if not task.cancelled() and task.exception() is not None)
            
            return {
                "completed": completed,
                "cancelled": cancelled + len(pending),
                "failed": failed,
                "total": len(tasks)
            }
            
        except asyncio.TimeoutError:
            # Cancel all remaining tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
            
            return {
                "completed": 0,
                "cancelled": len(tasks),
                "failed": 0,
                "total": len(tasks),
                "timeout": True
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get task manager statistics."""
        active_tasks = len(self.tasks)
        
        # Memory usage
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_percent = psutil.virtual_memory().percent / 100.0
        except:
            memory_info = None
            memory_percent = 0.0
        
        # Task age analysis
        current_time = time.time()
        old_tasks = 0
        very_old_tasks = 0
        
        for task_info in self.tasks.values():
            age = current_time - task_info.created_at
            if age > 300:  # 5 minutes
                old_tasks += 1
            if age > 1800:  # 30 minutes
                very_old_tasks += 1
        
        return {
            "active_tasks": active_tasks,
            "total_created": self.total_created,
            "total_completed": self.total_completed,
            "total_cancelled": self.total_cancelled,
            "total_failed": self.total_failed,
            "task_groups": len(self.task_groups),
            "old_tasks": old_tasks,
            "very_old_tasks": very_old_tasks,
            "memory_usage_mb": memory_info.rss / 1024 / 1024 if memory_info else 0,
            "memory_percent": memory_percent,
            "max_tasks": self.max_tasks,
            "utilization": active_tasks / self.max_tasks if self.max_tasks > 0 else 0.0,
        }
    
    def list_tasks(self, group: Optional[str] = None) -> List[Dict[str, Any]]:
        """List active tasks."""
        current_time = time.time()
        tasks = []
        
        for task_id, task_info in self.tasks.items():
            if group and task_id not in self.task_groups.get(group, set()):
                continue
            
            tasks.append({
                "id": task_id,
                "name": task_info.name,
                "context": task_info.context,
                "age": current_time - task_info.created_at,
                "done": task_info.task.done(),
                "cancelled": task_info.task.cancelled(),
                "exception": str(task_info.task.exception()) if task_info.task.done() and task_info.task.exception() else None,
            })
        
        return tasks
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        logger.info("Task manager cleanup loop started")
        
        try:
            while not self._shutdown_event.is_set():
                try:
                    await self._perform_cleanup()
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self.cleanup_interval
                    )
                except asyncio.TimeoutError:
                    continue
                
        except asyncio.CancelledError:
            logger.info("Task manager cleanup loop cancelled")
        except Exception as e:
            logger.error("Task manager cleanup loop error", error=str(e))
        finally:
            logger.info("Task manager cleanup loop stopped")
    
    async def _perform_cleanup(self) -> None:
        """Perform cleanup operations."""
        current_time = time.time()
        cleanup_count = 0
        timeout_count = 0
        
        # Get list of tasks to check (avoid holding lock too long)
        async with self._lock:
            tasks_to_check = list(self.tasks.items())
        
        tasks_to_remove = []
        tasks_to_timeout = []
        
        # Check each task
        for task_id, task_info in tasks_to_check:
            age = current_time - task_info.created_at
            
            # Remove completed tasks
            if task_info.task.done():
                tasks_to_remove.append(task_id)
                continue
            
            # Check for timeout
            if task_info.timeout and age > task_info.timeout:
                tasks_to_timeout.append((task_id, task_info))
                continue
        
        # Remove completed tasks
        for task_id in tasks_to_remove:
            await self._cleanup_task_info(task_id)
            cleanup_count += 1
        
        # Timeout old tasks
        for task_id, task_info in tasks_to_timeout:
            logger.warning(f"Task timeout: {task_info.name} (age: {age:.1f}s)")
            task_info.task.cancel()
            timeout_count += 1
        
        # Check memory usage
        memory_percent = psutil.virtual_memory().percent / 100.0
        if memory_percent > self.memory_threshold:
            logger.warning(f"High memory usage: {memory_percent:.1%}, forcing cleanup")
            await self._emergency_cleanup()
            gc.collect()
        
        if cleanup_count > 0 or timeout_count > 0:
            logger.debug("Task cleanup completed",
                        cleaned=cleanup_count,
                        timed_out=timeout_count,
                        active=len(self.tasks))
    
    async def _emergency_cleanup(self) -> None:
        """Emergency cleanup when resource limits are reached."""
        logger.warning("Performing emergency task cleanup")
        
        # Cancel oldest tasks first
        tasks_by_age = []
        current_time = time.time()
        
        async with self._lock:
            for task_id, task_info in self.tasks.items():
                age = current_time - task_info.created_at
                tasks_by_age.append((age, task_id, task_info))
        
        # Sort by age (oldest first)
        tasks_by_age.sort(reverse=True)
        
        # Cancel oldest 25% of tasks
        cancel_count = max(1, len(tasks_by_age) // 4)
        cancelled = 0
        
        for _, task_id, task_info in tasks_by_age[:cancel_count]:
            if not task_info.task.done():
                logger.warning(f"Emergency cancelling task: {task_info.name}")
                task_info.task.cancel()
                cancelled += 1
        
        logger.warning(f"Emergency cleanup cancelled {cancelled} tasks")
    
    async def _cancel_all_tasks(self, timeout: float = 30.0) -> None:
        """Cancel all managed tasks."""
        async with self._lock:
            tasks_to_cancel = [(task_id, task_info) for task_id, task_info in self.tasks.items()]
        
        if not tasks_to_cancel:
            return
        
        logger.info(f"Cancelling {len(tasks_to_cancel)} tasks...")
        
        # Cancel all tasks
        for task_id, task_info in tasks_to_cancel:
            if not task_info.task.done():
                task_info.task.cancel()
        
        # Wait for cancellation with timeout
        tasks = [task_info.task for _, task_info in tasks_to_cancel]
        
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning("Some tasks did not cancel within timeout")
        
        # Clear all task info
        async with self._lock:
            self.tasks.clear()
            self.task_groups.clear()
    
    async def _task_done_callback(self, task_id: str) -> None:
        """Callback when a task completes."""
        try:
            task_info = self.tasks.get(task_id)
            if not task_info:
                return
            
            task = task_info.task
            
            # Update statistics
            if task.cancelled():
                self.total_cancelled += 1
            elif task.exception():
                self.total_failed += 1
                logger.debug(f"Task failed: {task_info.name}",
                           error=str(task.exception()))
            else:
                self.total_completed += 1
            
            # Call cleanup callback if provided
            if task_info.cleanup_callback:
                try:
                    if asyncio.iscoroutinefunction(task_info.cleanup_callback):
                        await task_info.cleanup_callback()
                    else:
                        task_info.cleanup_callback()
                except Exception as e:
                    logger.error(f"Task cleanup callback failed: {task_info.name}",
                               error=str(e))
            
        except Exception as e:
            logger.error("Task done callback error", task_id=task_id, error=str(e))
    
    async def _cleanup_task_info(self, task_id: str) -> None:
        """Clean up task information."""
        async with self._lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
            
            # Remove from groups
            for group_name, task_ids in self.task_groups.items():
                task_ids.discard(task_id)
            
            # Remove empty groups
            empty_groups = [name for name, task_ids in self.task_groups.items() if not task_ids]
            for group_name in empty_groups:
                del self.task_groups[group_name]


# Global task manager instance
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """Get global task manager instance."""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager


async def create_managed_task(coro,
                             name: Optional[str] = None,
                             context: Optional[str] = None,
                             timeout: Optional[float] = None,
                             cleanup_callback: Optional[Callable] = None,
                             group: Optional[str] = None) -> asyncio.Task:
    """Create a managed task using the global task manager."""
    manager = get_task_manager()
    return await manager.create_task(coro, name, context, timeout, cleanup_callback, group)


@asynccontextmanager
async def managed_task_group(group_name: str, timeout: Optional[float] = None):
    """Context manager for managing a group of tasks."""
    manager = get_task_manager()
    
    try:
        yield manager
    finally:
        # Wait for group completion or cancel on timeout
        if timeout:
            try:
                await asyncio.wait_for(
                    manager.wait_for_completion(group=group_name),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"Task group '{group_name}' timed out, cancelling...")
                await manager.cancel_group(group_name)
        else:
            await manager.wait_for_completion(group=group_name)


def managed_task(name: Optional[str] = None,
                context: Optional[str] = None,
                timeout: Optional[float] = None,
                cleanup_callback: Optional[Callable] = None,
                group: Optional[str] = None):
    """Decorator for creating managed tasks."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            return await create_managed_task(
                func(*args, **kwargs),
                name=name or func.__name__,
                context=context,
                timeout=timeout,
                cleanup_callback=cleanup_callback,
                group=group
            )
        return wrapper
    return decorator


# Signal handlers for graceful shutdown
def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        manager = get_task_manager()
        asyncio.create_task(manager.stop())
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


# Health check integration
async def get_task_manager_health() -> Dict[str, Any]:
    """Get task manager health status."""
    manager = get_task_manager()
    stats = manager.get_stats()
    
    # Determine health based on metrics
    healthy = (
        stats["utilization"] < 0.9 and  # Not overloaded
        stats["very_old_tasks"] < 10 and  # Not many stale tasks
        stats["memory_percent"] < 0.9  # Not running out of memory
    )
    
    return {
        "status": "healthy" if healthy else "degraded",
        "stats": stats,
        "healthy": healthy,
    }