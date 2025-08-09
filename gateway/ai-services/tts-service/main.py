"""TTS Service - Text-to-Speech with Piper integration."""

import asyncio
import io
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response, StreamingResponse

from shared.config import TTSServiceConfig, get_config, setup_logging
from shared.database import RedisManager, CacheStore
from shared.exceptions import ModelInferenceError, ValidationError
from shared.middleware import setup_middleware
from shared.models import (
    HealthResponse,
    HealthStatus,
    ServiceInfo,
    TTSRequest,
    TTSResponse,
    VoiceInfo,
    VoicesResponse,
)
from shared.monitoring import HealthChecker, Metrics, init_metrics, metrics_endpoint
from shared.utils import (
    encode_audio_base64,
    preprocess_text_for_tts,
    clean_and_validate_text,
    AsyncTimer,
)

from .piper_engine import PiperEngine
from .voice_manager import VoiceManager

logger = structlog.get_logger(__name__)

# Global state
piper_engine: Optional[PiperEngine] = None
voice_manager: Optional[VoiceManager] = None
redis_client: Optional[RedisManager] = None
cache_store: Optional[CacheStore] = None
metrics: Optional[Metrics] = None
health_checker = HealthChecker()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global piper_engine, voice_manager, redis_client, cache_store, metrics
    
    # Initialize configuration and logging
    config = TTSServiceConfig()
    setup_logging(get_config().logging)
    
    logger.info("Starting TTS Service", service_name=config.name, port=config.port)
    
    try:
        # Initialize metrics
        metrics = init_metrics(config.name)
        
        # Initialize Redis client
        redis_client = RedisManager(get_config().redis)
        await redis_client.initialize(get_config().redis.url)
        
        # Initialize cache store
        cache_store = CacheStore(redis_client, default_ttl=3600)  # Cache for 1 hour
        
        # Initialize voice manager
        voice_manager = VoiceManager(
            models_dir=get_config().models.tts_model_path,
            cache_store=cache_store,
        )
        await voice_manager.initialize()
        
        # Initialize Piper engine
        piper_engine = PiperEngine(
            voice_manager=voice_manager,
            sample_rate=config.sample_rate,
            cache_store=cache_store,
        )
        await piper_engine.initialize()
        
        # Setup health checks
        health_checker.add_check("redis", redis_client.health_check)
        health_checker.add_check("piper", piper_engine.health_check)
        health_checker.add_check("voice_manager", voice_manager.health_check)
        
        logger.info("TTS Service initialized successfully")
        yield
        
    except Exception as exc:
        logger.error("Failed to initialize TTS Service", error=str(exc), exc_info=True)
        raise
    finally:
        # Cleanup resources
        logger.info("Shutting down TTS Service")
        
        if piper_engine:
            await piper_engine.cleanup()
        
        if voice_manager:
            await voice_manager.cleanup()
        
        if redis_client:
            await redis_client.close()


# Create FastAPI app
app = FastAPI(
    title="WearForce TTS Service",
    description="Text-to-Speech service with Piper integration",
    version="1.0.0",
    lifespan=lifespan,
)

# Setup middleware
config = TTSServiceConfig()
setup_middleware(
    app,
    service_name=config.name,
    cors_origins=config.cors_origins,
    cors_allow_credentials=config.cors_allow_credentials,
    requests_per_minute=config.rate_limit_per_minute,
    enable_cache=True,  # Enable caching for TTS responses
    cache_ttl=1800,     # 30 minutes cache
)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    health_result = await health_checker.check_health()
    
    return HealthResponse(
        status=HealthStatus.HEALTHY if health_result["status"] == "healthy" else HealthStatus.UNHEALTHY,
        service=config.name,
        checks=health_result["checks"],
    )


@app.get("/info", response_model=ServiceInfo)
async def service_info() -> ServiceInfo:
    """Get service information."""
    return ServiceInfo(
        name=config.name,
        version="1.0.0",
        description="Text-to-Speech service with Piper integration",
        endpoints=[
            "/health",
            "/info",
            "/metrics",
            "/voices",
            "/voices/statistics",
            "/voices/recommendations",
            "/voices/reload",
            "/voice/{voice_id}/info",
            "/voice/{voice_id}/capabilities",
            "/synthesize",
            "/synthesize-audio",
            "/synthesize-stream",
            "/clone-voice",
            "/system/stats",
            "/system/validation",
        ],
    )


@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint."""
    return metrics_endpoint()


@app.get("/voices", response_model=VoicesResponse)
async def list_voices() -> VoicesResponse:
    """Get list of available voices."""
    if not voice_manager:
        raise ModelInferenceError("Voice manager not initialized", "voice_manager")
    
    try:
        voices = await voice_manager.list_voices()
        return VoicesResponse(voices=voices)
        
    except Exception as exc:
        logger.error("Failed to list voices", error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list voices: {str(exc)}")


@app.post("/synthesize", response_model=TTSResponse)
async def synthesize_speech(request: TTSRequest) -> TTSResponse:
    """Synthesize speech from text."""
    start_time = time.time()
    
    if not piper_engine:
        raise ModelInferenceError("Piper engine not initialized", "piper")
    
    try:
        # Validate and clean text
        cleaned_text = clean_and_validate_text(
            request.text,
            max_length=config.max_text_length,
            min_length=1,
        )
        
        # Preprocess text for better TTS
        preprocessed_text = preprocess_text_for_tts(cleaned_text)
        
        logger.info(
            "Synthesizing speech",
            text_length=len(preprocessed_text),
            voice=request.voice,
            language=request.language,
        )
        
        # Check cache first
        cache_key = cache_store.cache_key(
            "tts",
            request.voice,
            str(request.speed),
            str(request.pitch),
            str(request.volume),
            request.format.value,
            preprocessed_text[:100]  # Use first 100 chars for cache key
        ) if cache_store else None
        
        cached_result = None
        if cache_key:
            cached_result = await cache_store.get(cache_key)
        
        if cached_result:
            logger.info("Using cached TTS result", cache_key=cache_key)
            return TTSResponse(
                audio_data=cached_result["audio_data"],
                format=request.format,
                sample_rate=cached_result["sample_rate"],
                duration=cached_result["duration"],
                processing_time=time.time() - start_time,
            )
        
        # Synthesize audio
        async with AsyncTimer("tts_synthesis") as timer:
            audio_result = await piper_engine.synthesize(
                text=preprocessed_text,
                voice=request.voice,
                speed=request.speed,
                pitch=request.pitch,
                volume=request.volume,
                format=request.format.value,
                sample_rate=request.sample_rate,
            )
        
        # Record metrics
        if metrics:
            metrics.record_inference(
                model=request.voice,
                duration=timer.elapsed,
                input_tokens=len(preprocessed_text.split()),
                output_tokens=0,  # Audio doesn't have output tokens
            )
            metrics.record_audio_processing(
                operation="synthesis",
                duration=timer.elapsed,
                format=request.format.value,
                success=True,
            )
        
        # Encode audio data
        audio_data_b64 = encode_audio_base64(audio_result["audio_data"])
        
        # Build response
        response = TTSResponse(
            audio_data=audio_data_b64,
            format=request.format,
            sample_rate=audio_result["sample_rate"],
            duration=audio_result["duration"],
            processing_time=time.time() - start_time,
        )
        
        # Cache the result
        if cache_key and cache_store:
            await cache_store.set(cache_key, {
                "audio_data": audio_data_b64,
                "sample_rate": response.sample_rate,
                "duration": response.duration,
            }, ttl=1800)  # Cache for 30 minutes
        
        logger.info(
            "Speech synthesis completed",
            duration=response.duration,
            processing_time=response.processing_time,
            audio_size=len(audio_result["audio_data"]),
        )
        
        return response
        
    except Exception as exc:
        logger.error("Speech synthesis failed", error=str(exc), exc_info=True)
        if isinstance(exc, (ValidationError, ModelInferenceError)):
            raise exc
        raise ModelInferenceError(f"Speech synthesis failed: {str(exc)}", "piper")


@app.post("/synthesize-audio")
async def synthesize_audio_direct(request: TTSRequest) -> Response:
    """Synthesize speech and return audio file directly."""
    if not piper_engine:
        raise ModelInferenceError("Piper engine not initialized", "piper")
    
    try:
        # Get TTS response
        tts_response = await synthesize_speech(request)
        
        # Decode base64 audio data
        from shared.utils import decode_audio_base64
        audio_data = decode_audio_base64(tts_response.audio_data)
        
        # Determine content type
        content_type_map = {
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
            "ogg": "audio/ogg",
            "flac": "audio/flac",
        }
        content_type = content_type_map.get(request.format.value, "audio/wav")
        
        return Response(
            content=audio_data,
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename=synthesis.{request.format.value}",
                "X-Processing-Time": str(tts_response.processing_time),
                "X-Duration": str(tts_response.duration),
            },
        )
        
    except Exception as exc:
        logger.error("Direct audio synthesis failed", error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Audio synthesis failed: {str(exc)}")


@app.post("/synthesize-stream")
async def synthesize_stream(request: TTSRequest) -> StreamingResponse:
    """Stream synthesized speech as it's generated."""
    if not piper_engine:
        raise ModelInferenceError("Piper engine not initialized", "piper")
    
    if not request.enable_streaming:
        # Fall back to regular synthesis
        response = await synthesize_audio_direct(request)
        return StreamingResponse(
            io.BytesIO(response.body),
            media_type=response.media_type,
            headers=response.headers,
        )
    
    try:
        # Validate and clean text
        cleaned_text = clean_and_validate_text(
            request.text,
            max_length=config.max_text_length,
            min_length=1,
        )
        
        # Preprocess text
        preprocessed_text = preprocess_text_for_tts(cleaned_text)
        
        logger.info("Starting streaming TTS", text_length=len(preprocessed_text))
        
        # Create streaming generator
        async def generate_audio():
            try:
                async for audio_chunk in piper_engine.synthesize_streaming(
                    text=preprocessed_text,
                    voice=request.voice,
                    speed=request.speed,
                    pitch=request.pitch,
                    volume=request.volume,
                    format=request.format.value,
                    sample_rate=request.sample_rate,
                ):
                    yield audio_chunk
                    
            except Exception as exc:
                logger.error("Streaming synthesis failed", error=str(exc))
                # Yield error information
                yield b"ERROR: Streaming synthesis failed"
        
        # Determine content type
        content_type_map = {
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
            "ogg": "audio/ogg",
            "flac": "audio/flac",
        }
        content_type = content_type_map.get(request.format.value, "audio/wav")
        
        return StreamingResponse(
            generate_audio(),
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename=stream.{request.format.value}",
                "Cache-Control": "no-cache",
            },
        )
        
    except Exception as exc:
        logger.error("Streaming synthesis setup failed", error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Streaming synthesis failed: {str(exc)}")


@app.post("/clone-voice")
async def clone_voice(
    voice_name: str = Query(..., description="Name for the cloned voice"),
    description: str = Query("", description="Description of the voice"),
    language: str = Query("en", description="Language of the voice samples"),
) -> Dict[str, Any]:
    """Clone a voice from provided samples (placeholder endpoint)."""
    if not voice_manager:
        raise ModelInferenceError("Voice manager not initialized", "voice_manager")
    
    # This is a placeholder for voice cloning functionality
    # In a real implementation, you would:
    # 1. Accept audio files with voice samples
    # 2. Train a voice model using the samples
    # 3. Save the model and register it with the voice manager
    
    logger.info("Voice cloning requested", voice_name=voice_name, language=language)
    
    return {
        "message": "Voice cloning feature not yet implemented",
        "voice_name": voice_name,
        "description": description,
        "language": language,
        "status": "pending_implementation",
    }


@app.get("/voice/{voice_id}/info")
async def get_voice_info(voice_id: str) -> VoiceInfo:
    """Get detailed information about a specific voice."""
    if not voice_manager:
        raise ModelInferenceError("Voice manager not initialized", "voice_manager")
    
    try:
        voice_info = await voice_manager.get_voice_info(voice_id)
        if not voice_info:
            raise HTTPException(status_code=404, detail=f"Voice '{voice_id}' not found")
        
        return voice_info
        
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get voice info", voice_id=voice_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Failed to get voice info: {str(exc)}")


@app.get("/voice/{voice_id}/capabilities")
async def get_voice_capabilities(voice_id: str) -> Dict[str, Any]:
    """Get capabilities of a specific voice."""
    if not piper_engine:
        raise ModelInferenceError("Piper engine not initialized", "piper")
    
    try:
        capabilities = await piper_engine.get_voice_capabilities(voice_id)
        return capabilities
        
    except Exception as exc:
        logger.error("Failed to get voice capabilities", voice_id=voice_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Failed to get voice capabilities: {str(exc)}")


@app.get("/voices/statistics")
async def get_voice_statistics() -> Dict[str, Any]:
    """Get statistics about available voices."""
    if not voice_manager:
        raise ModelInferenceError("Voice manager not initialized", "voice_manager")
    
    try:
        stats = await voice_manager.get_voice_statistics()
        return stats
        
    except Exception as exc:
        logger.error("Failed to get voice statistics", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Failed to get voice statistics: {str(exc)}")


@app.get("/voices/recommendations")
async def get_voice_recommendations(
    language: str = Query("en", description="Language code (e.g., 'en', 'tr')"),
    use_case: str = Query("general", description="Use case: 'general', 'fast', 'quality'"),
) -> List[VoiceInfo]:
    """Get recommended voices for a language and use case."""
    if not voice_manager:
        raise ModelInferenceError("Voice manager not initialized", "voice_manager")
    
    try:
        # Map language string to Language enum
        from shared.models import Language
        language_map = {
            "en": Language.ENGLISH,
            "tr": Language.TURKISH,
            "es": Language.SPANISH,
            "fr": Language.FRENCH,
            "de": Language.GERMAN,
        }
        
        lang_enum = language_map.get(language.lower(), Language.ENGLISH)
        recommendations = await voice_manager.get_recommended_voices(lang_enum, use_case)
        
        return recommendations
        
    except Exception as exc:
        logger.error("Failed to get voice recommendations", language=language, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Failed to get voice recommendations: {str(exc)}")


@app.post("/voices/reload")
async def reload_voices() -> Dict[str, Any]:
    """Reload voices from the models directory."""
    if not voice_manager:
        raise ModelInferenceError("Voice manager not initialized", "voice_manager")
    
    try:
        await voice_manager.reload_voices()
        voices_count = len(await voice_manager.list_voices())
        
        return {
            "message": "Voices reloaded successfully",
            "voices_count": voices_count,
        }
        
    except Exception as exc:
        logger.error("Failed to reload voices", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Failed to reload voices: {str(exc)}")


@app.get("/system/stats")
async def get_system_stats() -> Dict[str, Any]:
    """Get system statistics and performance metrics."""
    try:
        stats = {
            "service_name": config.name,
            "service_version": "1.0.0",
            "piper_engine": {},
            "voice_manager": {},
            "cache": {},
            "health": {},
        }
        
        # Piper engine stats
        if piper_engine:
            stats["piper_engine"] = await piper_engine.get_synthesis_stats()
        
        # Voice manager stats  
        if voice_manager:
            stats["voice_manager"] = await voice_manager.get_voice_statistics()
        
        # Cache stats
        if cache_store:
            stats["cache"] = {
                "enabled": True,
                "default_ttl": cache_store.default_ttl,
            }
        
        # Health check results
        health_result = await health_checker.check_health()
        stats["health"] = health_result
        
        return stats
        
    except Exception as exc:
        logger.error("Failed to get system stats", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Failed to get system stats: {str(exc)}")


@app.get("/system/validation")
async def validate_system() -> Dict[str, Any]:
    """Comprehensive system validation."""
    validation_result = {
        "overall_status": "healthy",
        "components": {},
        "errors": [],
        "warnings": [],
    }
    
    try:
        # Validate Piper installation
        if piper_engine:
            piper_validation = await piper_engine.validate_piper_installation()
            validation_result["components"]["piper"] = piper_validation
            
            if not piper_validation["can_run"]:
                validation_result["overall_status"] = "degraded"
                validation_result["errors"].extend(piper_validation["errors"])
        
        # Validate voice manager
        if voice_manager:
            voice_health = await voice_manager.health_check()
            validation_result["components"]["voice_manager"] = {
                "healthy": voice_health,
                "voices_count": len(await voice_manager.list_voices()),
            }
            
            if not voice_health:
                validation_result["overall_status"] = "unhealthy"
                validation_result["errors"].append("Voice manager is not healthy")
        
        # Validate Redis connection
        if redis_client:
            try:
                redis_health = await redis_client.health_check()
                validation_result["components"]["redis"] = {"healthy": redis_health}
                
                if not redis_health:
                    validation_result["overall_status"] = "degraded"
                    validation_result["warnings"].append("Redis connection issues")
            except Exception as exc:
                validation_result["components"]["redis"] = {
                    "healthy": False,
                    "error": str(exc),
                }
                validation_result["warnings"].append(f"Redis validation failed: {str(exc)}")
        
        return validation_result
        
    except Exception as exc:
        logger.error("System validation failed", error=str(exc))
        return {
            "overall_status": "error",
            "error": f"Validation failed: {str(exc)}",
        }


if __name__ == "__main__":
    config = TTSServiceConfig()
    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level="info",
    )