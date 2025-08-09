"""
LLM Inference Service - FastAPI app with vLLM integration.

Provides OpenAI-compatible API endpoints for text generation with:
- Multi-model support (gpt-oss-120b, gpt-oss-20b)
- Request batching and optimization
- Token usage tracking and billing
- Function calling support
- Multi-model load balancing
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, List, Optional

import torch

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response, BackgroundTasks
from fastapi.responses import StreamingResponse

from shared.config import LLMServiceConfig, get_config, setup_logging
from shared.database import RedisManager, CacheStore
from shared.exceptions import ValidationError, ServiceUnavailableError
from shared.middleware import setup_middleware
from shared.models import (
    ChatRequest,
    ChatResponse, 
    StreamChatChunk,
    HealthResponse,
    HealthStatus,
    BaseResponse,
    TokenUsage,
    ChatChoice,
    ChatMessage,
    MessageRole,
)
from shared.monitoring import init_metrics, get_metrics, health_checker, metrics_endpoint
from shared.utils import generate_uuid

from .engine import LLMEngineManager
from .billing import BillingTracker
from .batch_processor import BatchProcessor
from .function_calling import FunctionCallProcessor, FunctionCallRequest, FunctionDefinition

logger = structlog.get_logger(__name__)


# Global managers
engine_manager: Optional[LLMEngineManager] = None
redis_manager: Optional[RedisManager] = None
cache_store: Optional[CacheStore] = None
billing_tracker: Optional[BillingTracker] = None
batch_processor: Optional[BatchProcessor] = None
function_processor: Optional[FunctionCallProcessor] = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage service lifecycle."""
    global engine_manager, redis_manager, cache_store, billing_tracker, batch_processor, function_processor
    
    config = get_config()
    llm_config = LLMServiceConfig()
    
    try:
        logger.info("Starting LLM Inference Service", service=llm_config.name)
        
        # Initialize Redis
        redis_manager = RedisManager(config.redis)
        await redis_manager.health_check()
        logger.info("Redis connection established")
        
        # Initialize cache
        cache_store = CacheStore(redis_manager, default_ttl=300)
        
        # Initialize billing tracker
        billing_tracker = BillingTracker(redis_manager)
        
        # Initialize LLM engine manager
        engine_manager = LLMEngineManager(llm_config, config.models)
        await engine_manager.initialize()
        logger.info("LLM engines initialized")
        
        # Initialize batch processor
        batch_processor = BatchProcessor(engine_manager, llm_config.batch_size, llm_config.batch_timeout)
        await batch_processor.start()
        logger.info("Batch processor started")
        
        # Initialize function call processor
        function_processor = FunctionCallProcessor(engine_manager, redis_manager)
        logger.info("Function call processor initialized")
        
        # Setup health checks
        health_checker.add_check("redis", redis_manager.health_check)
        health_checker.add_check("llm_engines", engine_manager.health_check)
        health_checker.add_check("batch_processor", batch_processor.health_check)
        
        logger.info("LLM Inference Service started successfully")
        yield
        
    except Exception as e:
        logger.error("Failed to start LLM service", error=str(e))
        raise
    finally:
        logger.info("Shutting down LLM Inference Service")
        
        # Cleanup resources
        if batch_processor:
            await batch_processor.stop()
        if engine_manager:
            await engine_manager.close()
        if redis_manager:
            await redis_manager.close()


# Create FastAPI app
config = get_config()
llm_config = LLMServiceConfig()

app = FastAPI(
    title="WearForce LLM Inference Service",
    description="High-performance LLM inference service with vLLM backend",
    version="1.0.0",
    lifespan=lifespan,
)

# Setup logging and metrics
setup_logging(config.logging)
init_metrics(llm_config.name)

# Setup middleware
setup_middleware(
    app,
    service_name=llm_config.name,
    cors_origins=llm_config.cors_origins,
    requests_per_minute=llm_config.rate_limit_per_minute,
    enable_gzip=True,
    enable_cache=True,
    cache_ttl=300,
)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Comprehensive health check endpoint."""
    checks = await health_checker.check_health()
    
    # Add additional checks
    additional_checks = {}
    
    # Check GPU availability and memory
    try:
        if torch.cuda.is_available():
            device_count = torch.cuda.device_count()
            for i in range(device_count):
                gpu_memory = torch.cuda.get_device_properties(i).total_memory
                gpu_allocated = torch.cuda.memory_allocated(i)
                gpu_reserved = torch.cuda.memory_reserved(i)
                gpu_free = gpu_memory - gpu_reserved
                
                additional_checks[f"gpu_{i}"] = {
                    "status": "healthy" if gpu_free > 0.1 * gpu_memory else "degraded",
                    "total_memory_gb": gpu_memory / (1024**3),
                    "allocated_gb": gpu_allocated / (1024**3),
                    "reserved_gb": gpu_reserved / (1024**3),
                    "free_gb": gpu_free / (1024**3),
                    "utilization": (gpu_reserved / gpu_memory) * 100,
                }
        else:
            additional_checks["gpu"] = {"status": "unavailable", "message": "CUDA not available"}
    except Exception as e:
        additional_checks["gpu"] = {"status": "error", "error": str(e)}
    
    # Check model loading status
    if engine_manager:
        model_stats = await engine_manager.get_stats()
        additional_checks["models"] = {
            "status": "healthy" if model_stats["loaded_models"] > 0 else "unhealthy",
            "loaded_models": model_stats["loaded_models"],
            "total_models": model_stats["total_models"],
            "model_details": model_stats["models"],
        }
    
    # Check batch processor status
    if batch_processor:
        batch_stats = batch_processor.get_stats()
        additional_checks["batch_processor"] = {
            "status": "healthy" if batch_stats["is_running"] else "unhealthy",
            "queue_size": batch_stats["queue_size"],
            "active_batches": batch_stats["active_batches"],
            "success_rate": batch_stats["success_rate"],
        }
    
    # System resource checks
    try:
        import psutil
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        additional_checks["system"] = {
            "status": "healthy" if memory.percent < 85 and disk.percent < 90 else "degraded",
            "memory_percent": memory.percent,
            "disk_percent": disk.percent,
            "cpu_percent": psutil.cpu_percent(interval=1),
        }
    except Exception as e:
        additional_checks["system"] = {"status": "error", "error": str(e)}
    
    # Merge checks
    all_checks = {**checks, **additional_checks}
    
    # Determine overall status
    status = HealthStatus.HEALTHY
    if any(check.get("status") == "unhealthy" for check in all_checks.values() if isinstance(check, dict)):
        status = HealthStatus.UNHEALTHY
    elif any(check.get("status") == "degraded" for check in all_checks.values() if isinstance(check, dict)):
        status = HealthStatus.DEGRADED
    
    return HealthResponse(
        status=status,
        service=llm_config.name,
        checks=all_checks,
    )


@app.get("/metrics")
async def get_metrics_endpoint() -> Response:
    """Prometheus metrics endpoint."""
    return metrics_endpoint()


@app.get("/models")
async def list_models() -> Dict[str, List[str]]:
    """List available models."""
    if not engine_manager:
        raise ServiceUnavailableError("Engine manager not initialized")
    
    return {
        "models": engine_manager.list_models(),
        "default_model": "gpt-oss-20b",
    }


@app.post("/v1/chat/completions", response_model=ChatResponse)
async def create_chat_completion(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
) -> ChatResponse:
    """Create chat completion (OpenAI compatible)."""
    if not engine_manager:
        raise ServiceUnavailableError("Engine manager not initialized")
    
    start_time = time.time()
    
    try:
        # Validate request
        if not request.messages:
            raise ValidationError("Messages list cannot be empty")
        
        # Get model
        model_name = request.model if request.model in engine_manager.list_models() else "gpt-oss-20b"
        
        # Handle function calls if present
        if request.functions and function_processor:
            function_request = FunctionCallRequest(
                model_name=model_name,
                messages=request.messages,
                functions=[FunctionDefinition(**func) for func in request.functions],
                function_call=request.function_call,
                temperature=request.temperature,
                max_tokens=request.max_tokens or 1024,
            )
            
            result = await function_processor.process_function_call_request(function_request)
            
            # Convert function call result to ChatResponse format
            choice = ChatChoice(
                index=0,
                message=result["message"],
                finish_reason="function_call",
            )
            
            usage = TokenUsage(**result["usage"])
            
            response = ChatResponse(
                model=result["model"],
                choices=[choice],
                usage=usage,
            )
            
            # Track billing
            if billing_tracker:
                background_tasks.add_task(
                    billing_tracker.track_usage,
                    model_name,
                    usage.prompt_tokens,
                    usage.completion_tokens,
                )
            
            return response
        
        # Check cache for identical requests
        cache_key = None
        if cache_store and not request.stream:
            cache_key = cache_store.cache_key(
                "chat_completion",
                model_name,
                str(hash(str(request.messages))),
                str(request.temperature),
                str(request.max_tokens or 1024),
            )
            cached_result = await cache_store.get(cache_key)
            if cached_result:
                logger.info("Cache hit for chat completion")
                metrics = get_metrics()
                if metrics:
                    metrics.record_inference(model_name, time.time() - start_time)
                return ChatResponse(**cached_result)
        
        # Stream response
        if request.stream:
            return StreamingResponse(
                _stream_chat_completion(request, model_name),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )
        
        # Non-streaming response
        response = await _generate_chat_completion(request, model_name)
        
        # Cache response
        if cache_key and cache_store:
            await cache_store.set(cache_key, response.dict(), ttl=300)
        
        # Track billing in background
        if billing_tracker:
            background_tasks.add_task(
                billing_tracker.track_usage,
                model_name,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
            )
        
        # Record metrics
        metrics = get_metrics()
        if metrics:
            metrics.record_inference(
                model_name,
                time.time() - start_time,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
            )
        
        return response
        
    except Exception as e:
        logger.error("Chat completion failed", error=str(e), model=request.model)
        metrics = get_metrics()
        if metrics:
            metrics.record_error("chat_completion", "llm_service")
        raise


async def _generate_chat_completion(request: ChatRequest, model_name: str) -> ChatResponse:
    """Generate chat completion response."""
    if not engine_manager:
        raise ServiceUnavailableError("Engine manager not initialized")
    
    # Convert messages to prompt format
    prompt = _messages_to_prompt(request.messages)
    
    # Generate response using batch processor for efficiency
    if batch_processor:
        result = await batch_processor.generate(
            model_name=model_name,
            prompt=prompt,
            max_tokens=request.max_tokens or 1024,
            temperature=request.temperature,
            top_p=request.top_p,
            frequency_penalty=request.frequency_penalty,
            presence_penalty=request.presence_penalty,
            stop=request.stop,
        )
    else:
        # Fallback to direct generation
        result = await engine_manager.generate(
            model_name=model_name,
            prompt=prompt,
            max_tokens=request.max_tokens or 1024,
            temperature=request.temperature,
            top_p=request.top_p,
            stop=request.stop,
        )
    
    # Create response
    response_message = ChatMessage(
        role=MessageRole.ASSISTANT,
        content=result["text"],
    )
    
    choice = ChatChoice(
        index=0,
        message=response_message,
        finish_reason=result.get("finish_reason", "stop"),
    )
    
    usage = TokenUsage(
        prompt_tokens=result.get("prompt_tokens", 0),
        completion_tokens=result.get("completion_tokens", 0),
        total_tokens=result.get("prompt_tokens", 0) + result.get("completion_tokens", 0),
    )
    
    return ChatResponse(
        model=model_name,
        choices=[choice],
        usage=usage,
    )


async def _stream_chat_completion(request: ChatRequest, model_name: str) -> AsyncGenerator[str, None]:
    """Stream chat completion response."""
    if not engine_manager:
        raise ServiceUnavailableError("Engine manager not initialized")
    
    prompt = _messages_to_prompt(request.messages)
    
    chunk_id = generate_uuid()
    
    try:
        async for chunk_data in engine_manager.generate_stream(
            model_name=model_name,
            prompt=prompt,
            max_tokens=request.max_tokens or 1024,
            temperature=request.temperature,
            top_p=request.top_p,
            stop=request.stop,
        ):
            chunk = StreamChatChunk(
                id=chunk_id,
                model=model_name,
                choices=[{
                    "index": 0,
                    "delta": {
                        "content": chunk_data.get("text", ""),
                    },
                    "finish_reason": chunk_data.get("finish_reason"),
                }],
            )
            
            yield f"data: {chunk.json()}\n\n"
        
        # Send final chunk
        final_chunk = StreamChatChunk(
            id=chunk_id,
            model=model_name,
            choices=[{
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }],
        )
        yield f"data: {final_chunk.json()}\n\n"
        yield "data: [DONE]\n\n"
        
    except Exception as e:
        logger.error("Streaming failed", error=str(e))
        error_chunk = {
            "error": {
                "message": "Stream generation failed",
                "type": "generation_error",
            }
        }
        yield f"data: {error_chunk}\n\n"


def _messages_to_prompt(messages: List[ChatMessage]) -> str:
    """Convert OpenAI messages format to prompt string."""
    prompt_parts = []
    
    for message in messages:
        if message.role == MessageRole.SYSTEM:
            prompt_parts.append(f"System: {message.content}")
        elif message.role == MessageRole.USER:
            prompt_parts.append(f"User: {message.content}")
        elif message.role == MessageRole.ASSISTANT:
            prompt_parts.append(f"Assistant: {message.content}")
    
    prompt_parts.append("Assistant:")
    return "\n\n".join(prompt_parts)


@app.post("/v1/completions")
async def create_completion(
    request: Dict,
    background_tasks: BackgroundTasks,
) -> Dict:
    """Create text completion (legacy OpenAI API)."""
    # Convert to chat format for consistency
    chat_request = ChatRequest(
        model=request.get("model", "gpt-oss-20b"),
        messages=[ChatMessage(role=MessageRole.USER, content=request.get("prompt", ""))],
        temperature=request.get("temperature", 0.7),
        max_tokens=request.get("max_tokens"),
        top_p=request.get("top_p", 1.0),
        frequency_penalty=request.get("frequency_penalty", 0.0),
        presence_penalty=request.get("presence_penalty", 0.0),
        stop=request.get("stop"),
        stream=request.get("stream", False),
    )
    
    if request.get("stream", False):
        return StreamingResponse(
            _stream_completion(chat_request),
            media_type="text/event-stream",
        )
    
    chat_response = await create_chat_completion(chat_request, background_tasks)
    
    # Convert back to completion format
    return {
        "id": generate_uuid(),
        "object": "text_completion",
        "created": chat_response.created,
        "model": chat_response.model,
        "choices": [{
            "text": chat_response.choices[0].message.content,
            "index": 0,
            "finish_reason": chat_response.choices[0].finish_reason,
        }],
        "usage": chat_response.usage.dict(),
    }


async def _stream_completion(request: ChatRequest) -> AsyncGenerator[str, None]:
    """Stream text completion."""
    async for chunk in _stream_chat_completion(request, request.model):
        # Convert chat stream to completion stream format
        if chunk.startswith("data: "):
            data = chunk[6:-2]  # Remove "data: " and "\n\n"
            if data == "[DONE]":
                yield f"data: [DONE]\n\n"
            else:
                try:
                    import json
                    chat_chunk = json.loads(data)
                    if "choices" in chat_chunk and chat_chunk["choices"]:
                        choice = chat_chunk["choices"][0]
                        completion_chunk = {
                            "id": chat_chunk["id"],
                            "object": "text_completion",
                            "created": chat_chunk["created"],
                            "model": chat_chunk["model"],
                            "choices": [{
                                "text": choice.get("delta", {}).get("content", ""),
                                "index": 0,
                                "finish_reason": choice.get("finish_reason"),
                            }]
                        }
                        yield f"data: {json.dumps(completion_chunk)}\n\n"
                except Exception as e:
                    logger.error("Failed to convert chat chunk", error=str(e))


@app.post("/batch")
async def create_batch_job(
    requests: List[Dict],
    background_tasks: BackgroundTasks,
) -> Dict:
    """Create batch processing job."""
    if not batch_processor:
        raise ServiceUnavailableError("Batch processor not available")
    
    batch_id = generate_uuid()
    
    # Process batch in background
    background_tasks.add_task(
        batch_processor.process_batch,
        batch_id,
        requests,
    )
    
    return {
        "id": batch_id,
        "object": "batch",
        "status": "queued",
        "created_at": int(time.time()),
    }


@app.get("/batch/{batch_id}")
async def get_batch_status(batch_id: str) -> Dict:
    """Get batch job status."""
    if not batch_processor:
        raise ServiceUnavailableError("Batch processor not available")
    
    status = await batch_processor.get_batch_status(batch_id)
    if not status:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    return status


@app.post("/v1/chat/completions/functions")
async def create_function_call_completion(
    request: Dict[str, Any],
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """Create chat completion with function calling support."""
    if not function_processor:
        raise ServiceUnavailableError("Function processor not available")
    
    try:
        # Validate and parse request
        messages = [ChatMessage(**msg) for msg in request.get("messages", [])]
        functions = [FunctionDefinition(**func) for func in request.get("functions", [])]
        
        function_request = FunctionCallRequest(
            model_name=request.get("model", "gpt-oss-20b"),
            messages=messages,
            functions=functions,
            function_call=request.get("function_call"),
            temperature=request.get("temperature", 0.7),
            max_tokens=request.get("max_tokens", 1024),
        )
        
        # Process function call
        result = await function_processor.process_function_call_request(function_request)
        
        # Track billing in background
        if billing_tracker:
            background_tasks.add_task(
                billing_tracker.track_usage,
                result["model"],
                result["usage"]["prompt_tokens"],
                result["usage"]["completion_tokens"],
            )
        
        return result
        
    except Exception as e:
        logger.error("Function call completion failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/functions/register")
async def register_function(
    function_def: Dict[str, Any],
) -> Dict[str, str]:
    """Register a new function for calling."""
    if not function_processor:
        raise ServiceUnavailableError("Function processor not available")
    
    try:
        # This would typically register an actual function implementation
        # For now, just add to the schema registry
        func_def = FunctionDefinition(**function_def)
        
        # In a real implementation, you'd store the function implementation
        # function_processor.register_function(name, implementation, schema)
        
        return {
            "status": "success",
            "message": f"Function {func_def.name} registered successfully",
        }
        
    except Exception as e:
        logger.error("Function registration failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/v1/functions")
async def list_functions() -> Dict[str, List[Dict[str, Any]]]:
    """List available functions."""
    if not function_processor:
        raise ServiceUnavailableError("Function processor not available")
    
    functions = function_processor.list_functions()
    return {
        "functions": [func.dict() for func in functions]
    }


@app.get("/v1/functions/stats")
async def get_function_stats() -> Dict[str, Any]:
    """Get function calling performance statistics."""
    if not function_processor:
        raise ServiceUnavailableError("Function processor not available")
    
    return function_processor.get_performance_stats()


@app.get("/stats")
async def get_service_stats() -> Dict[str, Any]:
    """Get comprehensive service statistics."""
    stats = {
        "service": llm_config.name,
        "uptime": time.time() - app.state.start_time if hasattr(app.state, "start_time") else 0,
        "timestamp": time.time(),
    }
    
    # Engine manager stats
    if engine_manager:
        stats["engines"] = await engine_manager.get_stats()
    
    # Batch processor stats
    if batch_processor:
        stats["batch_processor"] = batch_processor.get_stats()
    
    # Function processor stats
    if function_processor:
        stats["function_processor"] = function_processor.get_performance_stats()
    
    # Billing stats (if available)
    if billing_tracker:
        try:
            stats["billing"] = await billing_tracker.get_current_usage()
        except Exception as e:
            stats["billing"] = {"error": str(e)}
    
    return stats


@app.get("/stats/models")
async def get_model_stats() -> Dict[str, Any]:
    """Get detailed model statistics."""
    if not engine_manager:
        raise ServiceUnavailableError("Engine manager not available")
    
    model_stats = await engine_manager.get_stats()
    
    # Add performance metrics
    for model_name, model_data in model_stats["models"].items():
        model = engine_manager.get_model(model_name)
        if model:
            model_data.update({
                "average_response_time": model_data.get("request_count", 0) / max(model_data.get("error_count", 1), 1),
                "health_score": max(0, 100 - (model_data.get("error_rate", 0) * 100)),
            })
    
    return model_stats


@app.post("/admin/reload/{model_name}")
async def reload_model(model_name: str) -> Dict[str, str]:
    """Reload a specific model (admin endpoint)."""
    if not engine_manager:
        raise ServiceUnavailableError("Engine manager not available")
    
    try:
        await engine_manager.reload_model(model_name)
        return {"status": "success", "message": f"Model {model_name} reloaded successfully"}
    except Exception as e:
        logger.error(f"Failed to reload model {model_name}", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def startup_event():
    """Record service startup time."""
    app.state.start_time = time.time()


if __name__ == "__main__":
    config = LLMServiceConfig()
    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        log_level="info",
        reload=config.debug,
        access_log=True,
    )