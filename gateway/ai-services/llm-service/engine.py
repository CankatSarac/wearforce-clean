"""
vLLM engine wrapper for LLM inference.

Provides:
- Multi-model management (gpt-oss-120b, gpt-oss-20b)
- Load balancing across multiple GPUs
- Async streaming and batching support
- Model hot-swapping capabilities
"""

import asyncio
import gc
import logging
from typing import Any, AsyncGenerator, AsyncIterator, Dict, List, Optional, Tuple
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import os
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import torch
import structlog
from vllm import AsyncLLMEngine, AsyncEngineArgs, SamplingParams
from vllm.model_executor.parallel_utils.parallel_state import destroy_model_parallel

from shared.config import LLMServiceConfig, ModelConfig
from shared.monitoring import get_metrics

logger = structlog.get_logger(__name__)


class ModelInstance:
    """Single model instance with vLLM engine."""
    
    def __init__(
        self,
        model_name: str,
        model_path: str,
        engine_args: AsyncEngineArgs,
    ):
        self.model_name = model_name
        self.model_path = model_path
        self.engine_args = engine_args
        self.engine: Optional[AsyncLLMEngine] = None
        self.is_loaded = False
        self.load_time: Optional[float] = None
        self.request_count = 0
        self.error_count = 0
        self._lock = asyncio.Lock()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((RuntimeError, OSError, torch.cuda.OutOfMemoryError)),
    )
    async def load(self) -> None:
        """Load the model engine with retry logic."""
        async with self._lock:
            if self.is_loaded:
                return
            
            try:
                logger.info(f"Loading model {self.model_name} from {self.model_path}")
                start_time = time.time()
                
                # Clear CUDA cache before loading
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
                
                # Create vLLM async engine
                self.engine = AsyncLLMEngine.from_engine_args(self.engine_args)
                
                self.load_time = time.time() - start_time
                self.is_loaded = True
                
                logger.info(
                    f"Model {self.model_name} loaded successfully",
                    load_time=self.load_time,
                )
                
                # Record metrics
                metrics = get_metrics()
                if metrics:
                    metrics.record_inference(self.model_name, self.load_time)
                
            except torch.cuda.OutOfMemoryError as e:
                logger.error(f"CUDA OOM loading model {self.model_name}", error=str(e))
                # Force cleanup and retry
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
                self.error_count += 1
                raise
            except Exception as e:
                logger.error(f"Failed to load model {self.model_name}", error=str(e))
                self.error_count += 1
                raise
    
    async def unload(self) -> None:
        """Unload the model engine."""
        async with self._lock:
            if not self.is_loaded:
                return
            
            try:
                logger.info(f"Unloading model {self.model_name}")
                
                if self.engine:
                    # Clean up vLLM engine gracefully
                    if hasattr(self.engine, 'stop_background_loop'):
                        try:
                            await self.engine.stop_background_loop()
                        except Exception as e:
                            logger.warning(f"Failed to stop background loop: {e}")
                    del self.engine
                    self.engine = None
                
                # Destroy model parallel state
                try:
                    destroy_model_parallel()
                except Exception as e:
                    logger.warning(f"Failed to destroy model parallel state: {e}")
                
                # Force garbage collection
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
                    # Clear CUDA context if possible
                    try:
                        torch.cuda.reset_peak_memory_stats()
                    except Exception as e:
                        logger.warning(f"Failed to reset CUDA memory stats: {e}")
                
                self.is_loaded = False
                logger.info(f"Model {self.model_name} unloaded successfully")
                
            except Exception as e:
                logger.error(f"Failed to unload model {self.model_name}", error=str(e))
                self.error_count += 1
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((RuntimeError, asyncio.TimeoutError)),
    )
    async def generate(
        self,
        prompt: str,
        sampling_params: SamplingParams,
    ) -> Dict[str, Any]:
        """Generate text completion with retry logic."""
        if not self.is_loaded or not self.engine:
            await self.load()
        
        start_time = time.time()
        self.request_count += 1
        
        try:
            # Generate using vLLM with timeout
            results = await asyncio.wait_for(
                self.engine.generate(prompt, sampling_params, request_id=f"req_{self.request_count}"),
                timeout=120.0  # 2 minute timeout
            )
            
            if not results:
                raise RuntimeError("No results from generation")
            
            result = results[0]
            if not result.outputs:
                raise RuntimeError("Empty outputs from generation")
                
            output = result.outputs[0]
            
            generation_time = time.time() - start_time
            
            return {
                "text": output.text,
                "finish_reason": output.finish_reason.name.lower() if output.finish_reason else "stop",
                "prompt_tokens": len(result.prompt_token_ids) if result.prompt_token_ids else 0,
                "completion_tokens": len(output.token_ids) if output.token_ids else 0,
                "generation_time": generation_time,
            }
            
        except asyncio.TimeoutError as e:
            self.error_count += 1
            logger.error(f"Generation timeout for {self.model_name}", error=str(e))
            raise
        except Exception as e:
            self.error_count += 1
            logger.error(f"Generation failed for {self.model_name}", error=str(e))
            # Check if engine is still healthy
            if "CUDA" in str(e) or "out of memory" in str(e).lower():
                logger.warning(f"CUDA error detected, marking {self.model_name} as unloaded")
                self.is_loaded = False
            raise
    
    async def generate_stream(
        self,
        prompt: str,
        sampling_params: SamplingParams,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate streaming text completion."""
        if not self.is_loaded or not self.engine:
            await self.load()
        
        self.request_count += 1
        request_id = f"req_{self.request_count}"
        
        try:
            # Start generation
            results_generator = self.engine.generate(prompt, sampling_params, request_id)
            
            async for request_output in results_generator:
                if request_output.outputs:
                    output = request_output.outputs[0]
                    
                    yield {
                        "text": output.text,
                        "finish_reason": output.finish_reason.name.lower() if output.finish_reason else None,
                        "prompt_tokens": len(request_output.prompt_token_ids),
                        "completion_tokens": len(output.token_ids),
                    }
                
        except Exception as e:
            self.error_count += 1
            logger.error(f"Streaming failed for {self.model_name}", error=str(e))
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get model instance statistics."""
        return {
            "model_name": self.model_name,
            "is_loaded": self.is_loaded,
            "load_time": self.load_time,
            "request_count": self.request_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / max(self.request_count, 1),
        }


class LLMEngineManager:
    """Manager for multiple LLM model instances."""
    
    def __init__(self, llm_config: LLMServiceConfig, model_config: ModelConfig):
        self.llm_config = llm_config
        self.model_config = model_config
        self.models: Dict[str, ModelInstance] = {}
        self.load_balancer = LoadBalancer()
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # Model configurations based on deployment type
        self.deployment_type = os.getenv("DEPLOYMENT_TYPE", "edge")  # "cloud" or "edge"
        
        if self.deployment_type == "cloud":
            # Cloud deployment: 80GB A100 configuration
            self.model_configs = {
                "gpt-oss-20b": {
                    "path": os.getenv("GPT_OSS_20B_PATH", "microsoft/DialoGPT-medium"),
                    "max_model_len": 8192,
                    "tensor_parallel_size": 2,
                    "gpu_memory_utilization": 0.85,
                    "max_num_seqs": 512,
                },
                "gpt-oss-120b": {
                    "path": os.getenv("GPT_OSS_120B_PATH", "microsoft/DialoGPT-large"),
                    "max_model_len": 4096,
                    "tensor_parallel_size": max(torch.cuda.device_count(), 4),
                    "gpu_memory_utilization": 0.90,
                    "max_num_seqs": 256,
                },
            }
        else:
            # Edge deployment: 16GB GPU configuration
            self.model_configs = {
                "gpt-oss-20b": {
                    "path": os.getenv("GPT_OSS_20B_PATH", "microsoft/DialoGPT-medium"),
                    "max_model_len": 4096,
                    "tensor_parallel_size": 1,
                    "gpu_memory_utilization": 0.75,
                    "max_num_seqs": 128,
                },
                "gpt-oss-120b": {
                    "path": os.getenv("GPT_OSS_120B_PATH", "microsoft/DialoGPT-large"),
                    "max_model_len": 2048,
                    "tensor_parallel_size": 1,
                    "gpu_memory_utilization": 0.70,
                    "max_num_seqs": 64,
                },
            }
    
    async def initialize(self) -> None:
        """Initialize all model instances."""
        logger.info("Initializing LLM engine manager")
        
        try:
            # Create model instances
            for model_name, config in self.model_configs.items():
                await self._create_model_instance(model_name, config)
            
            # Load default model
            if "gpt-oss-20b" in self.models:
                await self.models["gpt-oss-20b"].load()
            
            logger.info(f"Initialized {len(self.models)} model instances")
            
        except Exception as e:
            logger.error("Failed to initialize engine manager", error=str(e))
            raise
    
    async def _create_model_instance(self, model_name: str, config: Dict[str, Any]) -> None:
        """Create a model instance."""
        try:
            engine_args = AsyncEngineArgs(
                model=config["path"],
                max_model_len=config["max_model_len"],
                tensor_parallel_size=config["tensor_parallel_size"],
                gpu_memory_utilization=config.get("gpu_memory_utilization", self.model_config.llm_gpu_memory_utilization),
                max_num_seqs=config.get("max_num_seqs", self.llm_config.max_num_seqs),
                swap_space=self.llm_config.swap_space,
                trust_remote_code=True,
                disable_log_stats=False,
                enforce_eager=self.deployment_type == "edge",  # Use eager mode for edge deployment
                enable_prefix_caching=True,  # Enable prefix caching for better performance
                quantization="awq" if self.deployment_type == "edge" else None,  # Quantization for edge
            )
            
            instance = ModelInstance(model_name, config["path"], engine_args)
            self.models[model_name] = instance
            
            logger.info(f"Created model instance: {model_name}")
            
        except Exception as e:
            logger.error(f"Failed to create model instance {model_name}", error=str(e))
            raise
    
    def list_models(self) -> List[str]:
        """List available model names."""
        return list(self.models.keys())
    
    def get_model(self, model_name: str) -> Optional[ModelInstance]:
        """Get model instance by name."""
        return self.models.get(model_name)
    
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
    ) -> Dict[str, Any]:
        """Generate text using specified model."""
        model = self.get_model(model_name)
        if not model:
            raise ValueError(f"Model {model_name} not found")
        
        # Create sampling parameters
        sampling_params = SamplingParams(
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            stop=stop,
        )
        
        # Load balance if multiple instances available
        model = self.load_balancer.select_model(model_name, self.models)
        
        result = await model.generate(prompt, sampling_params)
        
        # Update load balancer
        self.load_balancer.record_request(model_name, result["generation_time"])
        
        return result
    
    async def generate_stream(
        self,
        model_name: str,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        top_p: float = 1.0,
        stop: Optional[List[str]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate streaming text using specified model."""
        model = self.get_model(model_name)
        if not model:
            raise ValueError(f"Model {model_name} not found")
        
        sampling_params = SamplingParams(
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            stop=stop,
        )
        
        # Load balance
        model = self.load_balancer.select_model(model_name, self.models)
        
        start_time = time.time()
        
        async for chunk in model.generate_stream(prompt, sampling_params):
            yield chunk
        
        # Update load balancer
        self.load_balancer.record_request(model_name, time.time() - start_time)
    
    async def health_check(self) -> bool:
        """Check if at least one model is loaded and healthy."""
        try:
            for model in self.models.values():
                if model.is_loaded:
                    return True
            return False
        except Exception:
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get engine manager statistics."""
        stats = {
            "total_models": len(self.models),
            "loaded_models": sum(1 for m in self.models.values() if m.is_loaded),
            "models": {},
        }
        
        for model_name, model in self.models.items():
            stats["models"][model_name] = model.get_stats()
        
        return stats
    
    async def reload_model(self, model_name: str) -> None:
        """Reload a specific model."""
        model = self.get_model(model_name)
        if not model:
            raise ValueError(f"Model {model_name} not found")
        
        logger.info(f"Reloading model {model_name}")
        await model.unload()
        await model.load()
    
    async def close(self) -> None:
        """Clean up all resources."""
        logger.info("Closing LLM engine manager")
        
        # Unload all models
        for model in self.models.values():
            await model.unload()
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        # Clean up GPU memory
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        
        logger.info("LLM engine manager closed")


class LoadBalancer:
    """Simple load balancer for model instances."""
    
    def __init__(self):
        self.request_counts: Dict[str, int] = {}
        self.response_times: Dict[str, List[float]] = {}
        self._lock = asyncio.Lock()
    
    def select_model(self, model_name: str, models: Dict[str, ModelInstance]) -> ModelInstance:
        """Select best model instance for load balancing."""
        # For now, just return the model (no multiple instances per model)
        # In a production setup, you might have multiple instances per model
        model = models.get(model_name)
        if not model:
            raise ValueError(f"Model {model_name} not found")
        return model
    
    async def record_request(self, model_name: str, response_time: float) -> None:
        """Record request metrics for load balancing."""
        async with self._lock:
            if model_name not in self.request_counts:
                self.request_counts[model_name] = 0
                self.response_times[model_name] = []
            
            self.request_counts[model_name] += 1
            self.response_times[model_name].append(response_time)
            
            # Keep only last 100 response times
            if len(self.response_times[model_name]) > 100:
                self.response_times[model_name] = self.response_times[model_name][-100:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get load balancing statistics."""
        stats = {}
        
        for model_name in self.request_counts:
            response_times = self.response_times.get(model_name, [])
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            stats[model_name] = {
                "request_count": self.request_counts[model_name],
                "avg_response_time": avg_response_time,
                "recent_response_times": response_times[-10:],  # Last 10
            }
        
        return stats