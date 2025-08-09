"""Whisper engine wrapper for speech-to-text processing."""

import asyncio
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from shared.exceptions import ModelInferenceError
from shared.utils import AsyncTimer, run_in_executor

logger = structlog.get_logger(__name__)


class WhisperEngine:
    """Whisper.cpp engine for speech-to-text transcription."""
    
    def __init__(
        self,
        model_path: str = "base.en",
        device: str = "cpu",
        compute_type: str = "float16",
        num_workers: int = 4,
    ):
        self.model_path = model_path
        self.device = device
        self.compute_type = compute_type
        self.num_workers = num_workers
        self.model = None
        self.is_initialized = False
        self._semaphore = asyncio.Semaphore(num_workers)
        
    async def initialize(self) -> None:
        """Initialize the Whisper model."""
        try:
            logger.info(
                "Initializing Whisper engine",
                model_path=self.model_path,
                device=self.device,
                compute_type=self.compute_type,
            )
            
            # Setup CPU optimizations if using CPU
            if self.device.lower() in ['cpu', 'auto']:
                self._setup_cpu_optimizations()
            
            # Priority order: whisper.cpp -> faster-whisper -> openai-whisper
            # First try whisper.cpp for best performance
            try:
                await self._init_whisper_cpp()
                
            except ImportError:
                # Fallback to faster-whisper
                try:
                    await self._init_faster_whisper()
                    
                except ImportError:
                    # Last fallback to openai-whisper
                    try:
                        await self._init_openai_whisper()
                        
                    except ImportError:
                        raise ModelInferenceError(
                            "No Whisper backend available. Install whispercpp, faster-whisper, or openai-whisper",
                            "whisper"
                        )
            
            self.is_initialized = True
            logger.info("Whisper engine initialized successfully", backend=self.backend)
            
        except Exception as exc:
            logger.error("Failed to initialize Whisper engine", error=str(exc), exc_info=True)
            raise ModelInferenceError(f"Whisper initialization failed: {str(exc)}", "whisper")
    
    async def health_check(self) -> bool:
        """Check if the Whisper engine is healthy."""
        return self.is_initialized and self.model is not None
    
    async def transcribe(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        model: str = "base.en",
        temperature: float = 0.0,
        return_timestamps: bool = False,
        return_word_level_timestamps: bool = False,
        retry_count: int = 3,
    ) -> Dict[str, Any]:
        """Transcribe audio data with retry logic and error recovery."""
        if not self.is_initialized:
            raise ModelInferenceError("Whisper engine not initialized", "whisper")
        
        async with self._semaphore:  # Limit concurrent transcriptions
            last_exception = None
            
            for attempt in range(retry_count):
                try:
                    async with AsyncTimer("whisper_transcribe") as timer:
                        result = await self._transcribe_audio(
                            audio_data,
                            language=language,
                            temperature=temperature,
                            return_timestamps=return_timestamps,
                            return_word_level_timestamps=return_word_level_timestamps,
                        )
                    
                    logger.info(
                        "Transcription completed",
                        duration=timer.elapsed,
                        text_length=len(result.get("text", "")),
                        backend=self.backend,
                        attempt=attempt + 1,
                    )
                    
                    return result
                    
                except Exception as exc:
                    last_exception = exc
                    logger.warning(
                        "Transcription attempt failed",
                        attempt=attempt + 1,
                        max_attempts=retry_count,
                        error=str(exc),
                        backend=self.backend,
                    )
                    
                    # Check if this is a recoverable error
                    if self._is_recoverable_error(exc):
                        if attempt < retry_count - 1:
                            # Wait before retry with exponential backoff
                            wait_time = (2 ** attempt) * 0.5  # 0.5, 1.0, 2.0 seconds
                            await asyncio.sleep(wait_time)
                            
                            # Try to recover
                            await self._attempt_recovery()
                            continue
                    else:
                        # Non-recoverable error, fail immediately
                        break
            
            logger.error(
                "All transcription attempts failed",
                total_attempts=retry_count,
                final_error=str(last_exception),
                backend=self.backend,
                exc_info=True
            )
            raise ModelInferenceError(
                f"Transcription failed after {retry_count} attempts: {str(last_exception)}", 
                "whisper"
            )
    
    async def transcribe_chunk(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        """Transcribe small audio chunk for streaming."""
        if not self.is_initialized:
            raise ModelInferenceError("Whisper engine not initialized", "whisper")
        
        try:
            # For streaming, use simpler transcription without detailed timestamps
            result = await self._transcribe_audio(
                audio_data,
                language=language,
                temperature=temperature,
                return_timestamps=False,
                return_word_level_timestamps=False,
            )
            
            return result
            
        except Exception as exc:
            logger.error("Chunk transcription failed", error=str(exc))
            # For streaming, return empty result instead of failing
            return {"text": "", "confidence": 0.0}
    
    async def _transcribe_audio(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        temperature: float = 0.0,
        return_timestamps: bool = False,
        return_word_level_timestamps: bool = False,
    ) -> Dict[str, Any]:
        """Internal transcription method."""
        
        # Write audio data to temporary file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(audio_data)
            temp_file_path = temp_file.name
        
        try:
            if self.backend == "faster-whisper":
                return await self._transcribe_faster_whisper(
                    temp_file_path,
                    language=language,
                    temperature=temperature,
                    return_timestamps=return_timestamps,
                    return_word_level_timestamps=return_word_level_timestamps,
                )
            elif self.backend == "openai-whisper":
                return await self._transcribe_openai_whisper(
                    temp_file_path,
                    language=language,
                    temperature=temperature,
                    return_timestamps=return_timestamps,
                    return_word_level_timestamps=return_word_level_timestamps,
                )
            elif self.backend == "whisper-cpp":
                return await self._transcribe_whisper_cpp(
                    temp_file_path,
                    language=language,
                    temperature=temperature,
                )
            else:
                raise ModelInferenceError(f"Unknown backend: {self.backend}", "whisper")
                
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_file_path)
            except OSError:
                pass
    
    async def _transcribe_faster_whisper(
        self,
        audio_path: str,
        language: Optional[str] = None,
        temperature: float = 0.0,
        return_timestamps: bool = False,
        return_word_level_timestamps: bool = False,
    ) -> Dict[str, Any]:
        """Transcribe using faster-whisper."""
        
        def _transcribe():
            segments, info = self.model.transcribe(
                audio_path,
                language=language,
                temperature=temperature,
                word_timestamps=return_word_level_timestamps,
                vad_filter=True,  # Voice activity detection
                vad_parameters=dict(min_silence_duration_ms=500),
            )
            
            # Process segments
            full_text = ""
            segment_list = []
            word_list = []
            
            for segment in segments:
                full_text += segment.text
                
                if return_timestamps:
                    segment_dict = {
                        "text": segment.text.strip(),
                        "start": segment.start,
                        "end": segment.end,
                        "confidence": getattr(segment, 'avg_logprob', None),
                    }
                    segment_list.append(segment_dict)
                    
                    # Add words if requested
                    if return_word_level_timestamps and hasattr(segment, 'words'):
                        for word in segment.words:
                            word_dict = {
                                "word": word.word,
                                "start": word.start,
                                "end": word.end,
                                "confidence": word.probability,
                            }
                            word_list.append(word_dict)
            
            return {
                "text": full_text.strip(),
                "language": info.language if info else language,
                "confidence": info.language_probability if info else None,
                "duration": info.duration if info else None,
                "segments": segment_list,
                "words": word_list,
            }
        
        return await run_in_executor(_transcribe)
    
    async def _transcribe_openai_whisper(
        self,
        audio_path: str,
        language: Optional[str] = None,
        temperature: float = 0.0,
        return_timestamps: bool = False,
        return_word_level_timestamps: bool = False,
    ) -> Dict[str, Any]:
        """Transcribe using openai-whisper."""
        
        def _transcribe():
            import whisper
            
            options = {
                "language": language,
                "temperature": temperature,
            }
            
            if return_word_level_timestamps:
                options["word_timestamps"] = True
            
            result = self.model.transcribe(audio_path, **options)
            
            # Process result
            segments = []
            words = []
            
            if return_timestamps and "segments" in result:
                for segment in result["segments"]:
                    segments.append({
                        "text": segment["text"].strip(),
                        "start": segment["start"],
                        "end": segment["end"],
                        "confidence": segment.get("avg_logprob"),
                    })
                    
                    if return_word_level_timestamps and "words" in segment:
                        for word in segment["words"]:
                            words.append({
                                "word": word["word"],
                                "start": word["start"],
                                "end": word["end"],
                                "confidence": word.get("probability"),
                            })
            
            return {
                "text": result["text"].strip(),
                "language": result.get("language"),
                "confidence": None,  # OpenAI Whisper doesn't provide overall confidence
                "duration": None,
                "segments": segments,
                "words": words,
            }
        
        return await run_in_executor(_transcribe)
    
    async def _transcribe_whisper_cpp(
        self,
        audio_path: str,
        language: Optional[str] = None,
        temperature: float = 0.0,
        return_timestamps: bool = False,
        return_word_level_timestamps: bool = False,
    ) -> Dict[str, Any]:
        """Transcribe using whisper.cpp Python bindings."""
        
        def _transcribe():
            import whispercpp as whisper_cpp
            
            # Prepare transcription parameters
            params = whisper_cpp.WhisperFullParams()
            params.strategy = whisper_cpp.WHISPER_SAMPLING_GREEDY
            params.language = language.encode('utf-8') if language else None
            params.temperature = temperature
            params.n_threads = self.num_workers
            params.print_progress = False
            params.print_special = False
            params.print_realtime = False
            params.print_timestamps = return_timestamps
            params.token_timestamps = return_word_level_timestamps
            params.suppress_blank = True
            params.suppress_non_speech_tokens = True
            
            # Load and process audio
            if self.model.full(params, audio_path.encode('utf-8')) != 0:
                raise Exception("Failed to process audio")
            
            # Extract results
            n_segments = self.model.full_n_segments()
            full_text = ""
            segments = []
            words = []
            
            for i in range(n_segments):
                segment_text = self.model.full_get_segment_text(i).decode('utf-8')
                full_text += segment_text
                
                if return_timestamps:
                    t0 = self.model.full_get_segment_t0(i) * 0.01  # Convert to seconds
                    t1 = self.model.full_get_segment_t1(i) * 0.01
                    
                    segment = {
                        "text": segment_text.strip(),
                        "start": t0,
                        "end": t1,
                        "confidence": None,  # whisper.cpp doesn't provide segment confidence
                    }
                    segments.append(segment)
                    
                    # Extract word-level timestamps if requested
                    if return_word_level_timestamps:
                        n_tokens = self.model.full_n_tokens(i)
                        for j in range(n_tokens):
                            token_data = self.model.full_get_token_data(i, j)
                            if token_data.id >= self.model.token_eot():
                                continue
                                
                            token_text = self.model.token_to_str(token_data.id).decode('utf-8')
                            if token_text.strip():
                                word = {
                                    "word": token_text,
                                    "start": token_data.t0 * 0.01,
                                    "end": token_data.t1 * 0.01,
                                    "confidence": token_data.p,
                                }
                                words.append(word)
            
            return {
                "text": full_text.strip(),
                "language": language,
                "confidence": None,
                "duration": None,
                "segments": segments,
                "words": words,
            }
        
        return await run_in_executor(_transcribe)
    
    def _is_recoverable_error(self, error: Exception) -> bool:
        """Check if an error is recoverable."""
        # Define recoverable error patterns
        recoverable_patterns = [
            "out of memory",
            "cuda out of memory", 
            "device unavailable",
            "timeout",
            "connection",
            "temporary",
            "retry",
            "busy",
            "resource unavailable",
        ]
        
        error_str = str(error).lower()
        
        # Check for specific exceptions that are usually recoverable
        if isinstance(error, (TimeoutError, ConnectionError, ResourceWarning)):
            return True
        
        # Check error message for recoverable patterns
        return any(pattern in error_str for pattern in recoverable_patterns)
    
    async def _attempt_recovery(self) -> None:
        """Attempt to recover from errors."""
        try:
            logger.info("Attempting error recovery", backend=self.backend)
            
            # For memory-related errors, try to clear cache
            if self.backend == "faster-whisper" and hasattr(self.model, 'cache'):
                try:
                    # Clear model cache if available
                    if hasattr(self.model, 'clear_cache'):
                        self.model.clear_cache()
                    logger.debug("Cleared model cache")
                except Exception as e:
                    logger.debug(f"Cache clearing failed: {e}")
            
            # For CUDA errors, try to clear GPU memory
            if "cuda" in self.device.lower():
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        torch.cuda.synchronize()
                        logger.debug("Cleared CUDA cache")
                except Exception as e:
                    logger.debug(f"CUDA cache clearing failed: {e}")
            
            # Generic memory cleanup
            import gc
            gc.collect()
            
            # Brief pause to allow recovery
            await asyncio.sleep(0.1)
            
            logger.info("Error recovery completed")
            
        except Exception as recovery_error:
            logger.warning(f"Recovery attempt failed: {recovery_error}")
    
    async def _validate_model_health(self) -> bool:
        """Validate that the model is still healthy."""
        try:
            if not self.is_initialized or not self.model:
                return False
            
            # Try a minimal operation to check if model is responsive
            if self.backend == "whisper-cpp":
                # For whisper.cpp, check if we can access basic properties
                return hasattr(self.model, 'full')
            elif self.backend == "faster-whisper":
                # For faster-whisper, model should be accessible
                return hasattr(self.model, 'transcribe')
            elif self.backend == "openai-whisper":
                # For OpenAI whisper, model should be accessible
                return hasattr(self.model, 'transcribe')
            
            return True
            
        except Exception as e:
            logger.error(f"Model health check failed: {e}")
            return False
    
    async def _reinitialize_model(self) -> None:
        """Reinitialize the model if needed."""
        try:
            logger.warning("Attempting model reinitialization", backend=self.backend)
            
            # Clean up current model
            if self.model:
                try:
                    if hasattr(self.model, 'cleanup'):
                        self.model.cleanup()
                    elif hasattr(self.model, 'free') and self.backend == "whisper-cpp":
                        self.model.free()
                except Exception as e:
                    logger.debug(f"Model cleanup during reinit failed: {e}")
            
            self.model = None
            self.is_initialized = False
            
            # Reinitialize
            await self.initialize()
            
            logger.info("Model reinitialized successfully", backend=self.backend)
            
        except Exception as e:
            logger.error(f"Model reinitialization failed: {e}")
            raise
    
    async def _init_whisper_cpp(self) -> None:
        """Initialize whisper.cpp backend."""
        import whispercpp as whisper_cpp
        
        # Determine model path - handle both model names and paths
        if os.path.isfile(self.model_path):
            model_file = self.model_path
        else:
            # Look for model in common directories
            model_dirs = [
                "/app/models",
                "./models",
                os.path.expanduser("~/.cache/whisper"),
                "/usr/local/share/whisper",
            ]
            
            model_file = None
            model_filename = f"ggml-{self.model_path}.bin"
            
            for model_dir in model_dirs:
                potential_path = os.path.join(model_dir, model_filename)
                if os.path.isfile(potential_path):
                    model_file = potential_path
                    break
            
            if not model_file:
                raise ModelInferenceError(
                    f"Whisper.cpp model not found: {self.model_path}. "
                    f"Expected {model_filename} in {model_dirs}",
                    "whisper"
                )
        
        logger.info("Loading whisper.cpp model", model_file=model_file)
        self.model = whisper_cpp.Whisper(model_file.encode('utf-8'))
        self.backend = "whisper-cpp"
        logger.info("whisper.cpp model loaded successfully")
    
    async def _init_faster_whisper(self) -> None:
        """Initialize faster-whisper backend with optimizations."""
        from faster_whisper import WhisperModel
        
        # Optimize parameters based on device
        device = self._optimize_device_selection()
        compute_type = self._optimize_compute_type(device)
        
        logger.info(
            "Initializing faster-whisper with optimizations",
            device=device,
            compute_type=compute_type,
            num_workers=self.num_workers
        )
        
        self.model = WhisperModel(
            self.model_path,
            device=device,
            compute_type=compute_type,
            num_workers=self.num_workers,
            # GPU optimizations
            **self._get_gpu_optimizations() if device.startswith('cuda') else {}
        )
        
        self.device = device  # Update actual device used
        self.compute_type = compute_type  # Update actual compute type used
        self.backend = "faster-whisper"
        logger.info(
            "faster-whisper model loaded successfully",
            actual_device=device,
            actual_compute_type=compute_type
        )
    
    async def _init_openai_whisper(self) -> None:
        """Initialize openai-whisper backend."""
        import whisper
        
        self.model = await run_in_executor(
            whisper.load_model,
            self.model_path,
            device=self.device,
        )
        self.backend = "openai-whisper"
        logger.info("openai-whisper model loaded successfully")
    
    def _optimize_device_selection(self) -> str:
        """Optimize device selection based on availability and performance."""
        import torch
        
        requested_device = self.device.lower()
        
        if requested_device in ['cuda', 'gpu']:
            if torch.cuda.is_available():
                # Get the best available GPU
                gpu_count = torch.cuda.device_count()
                if gpu_count > 0:
                    # Use GPU with most free memory
                    best_gpu = 0
                    max_memory = 0
                    
                    for i in range(gpu_count):
                        try:
                            torch.cuda.set_device(i)
                            memory_free = torch.cuda.get_device_properties(i).total_memory
                            memory_allocated = torch.cuda.memory_allocated(i)
                            memory_available = memory_free - memory_allocated
                            
                            if memory_available > max_memory:
                                max_memory = memory_available
                                best_gpu = i
                                
                        except Exception as e:
                            logger.debug(f"Could not check GPU {i}: {e}")
                    
                    selected_device = f"cuda:{best_gpu}"
                    logger.info(
                        "Selected GPU device",
                        device=selected_device,
                        available_memory_gb=max_memory / (1024**3),
                        total_gpus=gpu_count
                    )
                    return selected_device
                else:
                    logger.warning("CUDA requested but no GPUs available, falling back to CPU")
                    return "cpu"
            else:
                logger.warning("CUDA requested but not available, falling back to CPU")
                return "cpu"
        
        elif requested_device == 'auto':
            # Auto-select best available device
            if torch.cuda.is_available() and torch.cuda.device_count() > 0:
                return self._optimize_device_selection().replace(self.device, 'cuda')
            else:
                return "cpu"
        
        else:
            # Use requested device (cpu or specific cuda device)
            return requested_device
    
    def _optimize_compute_type(self, device: str) -> str:
        """Optimize compute type based on device and model capabilities."""
        if device.startswith('cuda'):
            # GPU optimizations
            try:
                import torch
                gpu_idx = 0 if device == 'cuda' else int(device.split(':')[1])
                
                # Check GPU compute capability
                if torch.cuda.is_available():
                    gpu_props = torch.cuda.get_device_properties(gpu_idx)
                    compute_capability = gpu_props.major * 10 + gpu_props.minor
                    
                    # Optimize based on GPU architecture
                    if compute_capability >= 80:  # Ampere (RTX 30xx, A100, etc.)
                        if self.compute_type == 'auto':
                            return 'float16'  # Best performance on Ampere
                        elif self.compute_type == 'int8':
                            return 'int8'  # Supported and fast
                    elif compute_capability >= 75:  # Turing (RTX 20xx, etc.)
                        if self.compute_type == 'auto':
                            return 'float16'
                        elif self.compute_type == 'int8':
                            logger.warning("INT8 may not be optimal on this GPU, using float16")
                            return 'float16'
                    else:  # Older GPUs
                        if self.compute_type in ['auto', 'int8']:
                            logger.info("Using float32 for compatibility with older GPU")
                            return 'float32'
                    
                    logger.info(
                        "Optimized compute type for GPU",
                        gpu_arch=f"compute_{compute_capability}",
                        compute_type=self.compute_type,
                        gpu_name=gpu_props.name
                    )
                
                return self.compute_type if self.compute_type != 'auto' else 'float16'
                
            except Exception as e:
                logger.debug(f"GPU optimization failed: {e}")
                return 'float16'  # Safe default for GPU
        
        else:
            # CPU optimizations
            if self.compute_type == 'auto':
                # Check CPU capabilities
                try:
                    import cpuinfo
                    cpu_info = cpuinfo.get_cpu_info()
                    
                    # Check for AVX2 support for better int8 performance
                    flags = cpu_info.get('flags', [])
                    if 'avx2' in flags and 'fma' in flags:
                        logger.info("CPU supports AVX2/FMA, using int8 for optimal performance")
                        return 'int8'
                    else:
                        logger.info("CPU doesn't support advanced features, using float32")
                        return 'float32'
                        
                except ImportError:
                    logger.debug("cpuinfo not available, using default CPU compute type")
                    return 'int8'  # Good default for most modern CPUs
                except Exception as e:
                    logger.debug(f"CPU optimization failed: {e}")
                    return 'int8'
            
            return self.compute_type
    
    def _get_gpu_optimizations(self) -> dict:
        """Get GPU-specific optimization parameters."""
        optimizations = {}
        
        try:
            import torch
            if torch.cuda.is_available():
                # Memory optimizations
                optimizations.update({
                    # Add GPU-specific parameters that faster-whisper supports
                    'local_files_only': False,  # Allow downloading if needed
                })
                
                # Check available VRAM and adjust batch size accordingly
                if self.device.startswith('cuda'):
                    gpu_idx = 0 if self.device == 'cuda' else int(self.device.split(':')[1])
                    props = torch.cuda.get_device_properties(gpu_idx)
                    total_memory_gb = props.total_memory / (1024**3)
                    
                    if total_memory_gb < 4:
                        logger.info("Low VRAM detected, using conservative settings")
                        optimizations['cpu_threads'] = 2
                    elif total_memory_gb >= 16:
                        logger.info("High VRAM available, using aggressive settings")
                        optimizations['cpu_threads'] = self.num_workers * 2
                    
                    logger.info(
                        "GPU optimizations applied",
                        gpu_memory_gb=total_memory_gb,
                        optimizations=optimizations
                    )
                
        except Exception as e:
            logger.debug(f"Failed to get GPU optimizations: {e}")
        
        return optimizations
    
    def _setup_cpu_optimizations(self) -> None:
        """Setup CPU-specific optimizations."""
        import os
        
        try:
            # Set optimal thread counts for CPU inference
            num_cores = os.cpu_count() or 4
            
            # OpenMP settings
            if 'OMP_NUM_THREADS' not in os.environ:
                omp_threads = min(self.num_workers * 2, num_cores)
                os.environ['OMP_NUM_THREADS'] = str(omp_threads)
                logger.debug(f"Set OMP_NUM_THREADS to {omp_threads}")
            
            # Intel MKL settings
            if 'MKL_NUM_THREADS' not in os.environ:
                mkl_threads = min(self.num_workers, num_cores // 2)
                os.environ['MKL_NUM_THREADS'] = str(mkl_threads)
                logger.debug(f"Set MKL_NUM_THREADS to {mkl_threads}")
            
            # BLAS settings
            if 'OPENBLAS_NUM_THREADS' not in os.environ:
                blas_threads = min(self.num_workers, num_cores // 2)
                os.environ['OPENBLAS_NUM_THREADS'] = str(blas_threads)
                logger.debug(f"Set OPENBLAS_NUM_THREADS to {blas_threads}")
            
            logger.info(
                "CPU optimizations applied",
                total_cores=num_cores,
                worker_threads=self.num_workers,
                omp_threads=os.environ.get('OMP_NUM_THREADS'),
            )
            
        except Exception as e:
            logger.debug(f"Failed to setup CPU optimizations: {e}")
    
    async def cleanup(self) -> None:
        """Cleanup resources."""
        logger.info("Cleaning up Whisper engine")
        
        if self.model:
            # Some models may need explicit cleanup
            if hasattr(self.model, 'cleanup'):
                self.model.cleanup()
            elif hasattr(self.model, 'free') and self.backend == "whisper-cpp":
                self.model.free()
            self.model = None
        
        self.is_initialized = False


class WhisperModelManager:
    """Manager for multiple Whisper models."""
    
    def __init__(self):
        self.models: Dict[str, WhisperEngine] = {}
    
    async def load_model(
        self,
        model_name: str,
        model_path: str,
        device: str = "cpu",
        compute_type: str = "float16",
        num_workers: int = 4,
    ) -> WhisperEngine:
        """Load and cache a Whisper model."""
        if model_name in self.models:
            return self.models[model_name]
        
        engine = WhisperEngine(
            model_path=model_path,
            device=device,
            compute_type=compute_type,
            num_workers=num_workers,
        )
        
        await engine.initialize()
        self.models[model_name] = engine
        
        logger.info("Loaded Whisper model", model_name=model_name, model_path=model_path)
        return engine
    
    def get_model(self, model_name: str) -> Optional[WhisperEngine]:
        """Get a loaded model."""
        return self.models.get(model_name)
    
    async def unload_model(self, model_name: str) -> None:
        """Unload a model."""
        if model_name in self.models:
            await self.models[model_name].cleanup()
            del self.models[model_name]
            logger.info("Unloaded Whisper model", model_name=model_name)
    
    async def cleanup_all(self) -> None:
        """Cleanup all loaded models."""
        for model_name in list(self.models.keys()):
            await self.unload_model(model_name)