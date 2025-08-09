"""STT Service - Speech-to-Text with Whisper.cpp integration."""

import asyncio
import base64
import io
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import structlog
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from shared.config import STTServiceConfig, get_config, setup_logging
from shared.database import RedisManager
from shared.exceptions import AudioProcessingError, ModelInferenceError, ValidationError
from shared.middleware import setup_middleware
from shared.models import (
    HealthResponse,
    HealthStatus,
    ServiceInfo,
    STTRequest,
    STTResponse,
    StreamSTTChunk,
    WebSocketMessage,
    WebSocketResponse,
)
from shared.monitoring import HealthChecker, Metrics, init_metrics, metrics_endpoint
from shared.utils import (
    decode_audio_base64,
    encode_audio_base64,
    get_audio_info,
    validate_audio_data,
    AsyncTimer,
    clean_and_validate_text,
)

from .whisper_engine import WhisperEngine
from .audio_processor import AudioProcessor
from .grpc_server import create_grpc_server, run_grpc_server

logger = structlog.get_logger(__name__)

# Global state
whisper_engine: Optional[WhisperEngine] = None
audio_processor: Optional[AudioProcessor] = None
redis_client: Optional[RedisManager] = None
metrics: Optional[Metrics] = None
grpc_server: Optional[Any] = None
health_checker = HealthChecker()

# Connection manager for streaming with backpressure
class StreamingConnectionManager:
    """Enhanced connection manager with backpressure control."""
    
    def __init__(self, max_connections: int = 100, max_buffer_size: int = 1024*1024):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_states: Dict[str, Dict[str, Any]] = {}
        self.max_connections = max_connections
        self.max_buffer_size = max_buffer_size
        self._connection_lock = asyncio.Lock()
        
    async def connect(self, websocket: WebSocket, session_id: str) -> bool:
        """Connect with backpressure check."""
        async with self._connection_lock:
            if len(self.active_connections) >= self.max_connections:
                logger.warning("Max connections reached", current=len(self.active_connections))
                return False
            
            await websocket.accept()
            self.active_connections[session_id] = websocket
            self.connection_states[session_id] = {
                "connected_at": time.time(),
                "is_processing": False,
                "buffer": b"",
                "buffer_size": 0,
                "last_activity": time.time(),
                "message_count": 0,
                "error_count": 0,
            }
            logger.info("WebSocket connected", session_id=session_id, 
                       total_connections=len(self.active_connections))
            return True
    
    def disconnect(self, session_id: str) -> None:
        """Remove a WebSocket connection."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        if session_id in self.connection_states:
            del self.connection_states[session_id]
        logger.info("WebSocket disconnected", session_id=session_id,
                   remaining_connections=len(self.active_connections))
    
    async def send_message(self, session_id: str, message: WebSocketResponse) -> bool:
        """Send message with error handling."""
        if session_id not in self.active_connections:
            return False
        
        try:
            websocket = self.active_connections[session_id]
            await websocket.send_json(message.dict())
            
            # Update connection state
            if session_id in self.connection_states:
                self.connection_states[session_id]["last_activity"] = time.time()
                self.connection_states[session_id]["message_count"] += 1
            
            return True
        except Exception as exc:
            logger.error("Failed to send WebSocket message", 
                        session_id=session_id, error=str(exc))
            
            # Update error count
            if session_id in self.connection_states:
                self.connection_states[session_id]["error_count"] += 1
            
            return False
    
    def can_accept_data(self, session_id: str, data_size: int) -> bool:
        """Check if connection can accept more data (backpressure)."""
        if session_id not in self.connection_states:
            return False
        
        state = self.connection_states[session_id]
        current_buffer_size = state.get("buffer_size", 0)
        
        # Check buffer size limit
        if current_buffer_size + data_size > self.max_buffer_size:
            logger.warning("Buffer size limit exceeded", 
                          session_id=session_id, 
                          current_size=current_buffer_size,
                          incoming_size=data_size,
                          limit=self.max_buffer_size)
            return False
        
        # Check if already processing (prevent overwhelming)
        if state.get("is_processing", False):
            return False
        
        # Check error rate
        error_count = state.get("error_count", 0)
        message_count = state.get("message_count", 1)
        error_rate = error_count / message_count
        
        if error_rate > 0.5:  # More than 50% error rate
            logger.warning("High error rate detected", 
                          session_id=session_id,
                          error_rate=error_rate)
            return False
        
        return True
    
    def update_buffer_size(self, session_id: str, size_delta: int) -> None:
        """Update buffer size tracking."""
        if session_id in self.connection_states:
            current = self.connection_states[session_id].get("buffer_size", 0)
            self.connection_states[session_id]["buffer_size"] = max(0, current + size_delta)
    
    async def cleanup_stale_connections(self) -> None:
        """Cleanup stale connections periodically."""
        current_time = time.time()
        stale_threshold = 300  # 5 minutes
        
        stale_sessions = []
        for session_id, state in self.connection_states.items():
            if current_time - state.get("last_activity", 0) > stale_threshold:
                stale_sessions.append(session_id)
        
        for session_id in stale_sessions:
            logger.info("Cleaning up stale connection", session_id=session_id)
            self.disconnect(session_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global whisper_engine, audio_processor, redis_client, metrics, grpc_server
    
    # Initialize configuration and logging
    config = STTServiceConfig()
    setup_logging(get_config().logging)
    
    logger.info("Starting STT Service", service_name=config.name, port=config.port)
    
    grpc_task = None
    cleanup_task = None
    
    try:
        # Initialize metrics
        metrics = init_metrics(config.name)
        
        # Initialize Redis client
        redis_client = RedisManager(get_config().redis)
        await redis_client.initialize(get_config().redis.url)
        
        # Initialize audio processor
        audio_processor = AudioProcessor()
        
        # Initialize Whisper engine
        whisper_engine = WhisperEngine(
            model_path=config.whisper_model_size,
            device=get_config().models.whisper_device,
            compute_type=config.whisper_compute_type,
            num_workers=config.whisper_threads,
        )
        await whisper_engine.initialize()
        
        # Initialize gRPC server
        grpc_port = config.port + 1000  # HTTP on 8001, gRPC on 9001
        grpc_server = await create_grpc_server(
            whisper_engine, 
            audio_processor, 
            port=grpc_port
        )
        
        # Start gRPC server in background
        grpc_task = asyncio.create_task(grpc_server.start())
        logger.info("gRPC server started", port=grpc_port)
        
        # Start cleanup task for connection management
        cleanup_task = asyncio.create_task(periodic_cleanup())
        
        # Setup health checks
        health_checker.add_check("redis", redis_client.health_check)
        health_checker.add_check("whisper", whisper_engine.health_check)
        health_checker.add_check("audio_processor", audio_processor.health_check)
        health_checker.add_check("grpc_server", lambda: grpc_server is not None)
        
        logger.info("STT Service initialized successfully")
        yield
        
    except Exception as exc:
        logger.error("Failed to initialize STT Service", error=str(exc), exc_info=True)
        raise
    finally:
        # Cleanup resources
        logger.info("Shutting down STT Service")
        
        # Stop cleanup task
        if cleanup_task:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Stop gRPC server
        if grpc_server:
            await grpc_server.stop(grace=5)
            logger.info("gRPC server stopped")
        
        if grpc_task:
            grpc_task.cancel()
            try:
                await grpc_task
            except asyncio.CancelledError:
                pass
        
        if whisper_engine:
            await whisper_engine.cleanup()
        
        if redis_client:
            await redis_client.close()


async def periodic_cleanup():
    """Periodic cleanup task for connection management."""
    while True:
        try:
            await asyncio.sleep(60)  # Run every minute
            await connection_manager.cleanup_stale_connections()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Cleanup task error", error=str(exc))


# Create FastAPI app
app = FastAPI(
    title="WearForce STT Service",
    description="Speech-to-Text service with Whisper.cpp integration",
    version="1.0.0",
    lifespan=lifespan,
)

# Setup middleware
config = STTServiceConfig()
setup_middleware(
    app,
    service_name=config.name,
    cors_origins=config.cors_origins,
    cors_allow_credentials=config.cors_allow_credentials,
    requests_per_minute=config.rate_limit_per_minute,
    enable_cache=False,  # Disable caching for real-time audio processing
)


@app.on_event("startup")
async def startup_event():
    """Track application start time."""
    app.state.start_time = time.time()
    logger.info("STT Service HTTP API started", timestamp=app.state.start_time)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Comprehensive health check endpoint."""
    health_result = await health_checker.check_health()
    
    # Add additional health checks
    additional_checks = {}
    
    # Check active connections
    active_connections = len(connection_manager.active_connections)
    additional_checks["active_connections"] = {
        "status": "healthy" if active_connections < connection_manager.max_connections * 0.9 else "degraded",
        "count": active_connections,
        "max_connections": connection_manager.max_connections,
    }
    
    # Check gRPC server
    additional_checks["grpc_server"] = {
        "status": "healthy" if grpc_server is not None else "unhealthy",
        "available": grpc_server is not None,
    }
    
    # Check available models
    model_status = "healthy" if whisper_engine and whisper_engine.is_initialized else "unhealthy"
    additional_checks["whisper_model"] = {
        "status": model_status,
        "backend": getattr(whisper_engine, "backend", None),
        "initialized": getattr(whisper_engine, "is_initialized", False),
    }
    
    # Merge checks
    all_checks = {**health_result["checks"], **additional_checks}
    
    # Determine overall status
    overall_status = HealthStatus.HEALTHY
    for check_name, check_result in all_checks.items():
        if isinstance(check_result, dict) and check_result.get("status") == "unhealthy":
            overall_status = HealthStatus.UNHEALTHY
            break
        elif isinstance(check_result, dict) and check_result.get("status") == "degraded":
            overall_status = HealthStatus.DEGRADED
    
    return HealthResponse(
        status=overall_status,
        service=config.name,
        checks=all_checks,
    )


@app.get("/health/live")
async def liveness_check():
    """Kubernetes liveness probe endpoint."""
    try:
        # Basic checks for liveness
        if not whisper_engine or not whisper_engine.is_initialized:
            raise HTTPException(status_code=503, detail="Whisper engine not initialized")
        
        if not audio_processor or not audio_processor.is_initialized:
            raise HTTPException(status_code=503, detail="Audio processor not initialized")
        
        return {"status": "alive", "timestamp": time.time()}
    
    except Exception as exc:
        logger.error("Liveness check failed", error=str(exc))
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/health/ready")
async def readiness_check():
    """Kubernetes readiness probe endpoint."""
    try:
        # More comprehensive checks for readiness
        health_result = await health_checker.check_health()
        
        if health_result["status"] != "healthy":
            raise HTTPException(
                status_code=503,
                detail=f"Service not ready: {health_result}"
            )
        
        # Check if we can accept new connections
        if len(connection_manager.active_connections) >= connection_manager.max_connections:
            raise HTTPException(
                status_code=503,
                detail="Service overloaded - too many active connections"
            )
        
        return {
            "status": "ready",
            "timestamp": time.time(),
            "active_connections": len(connection_manager.active_connections),
        }
    
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Readiness check failed", error=str(exc))
        raise HTTPException(status_code=503, detail=str(exc))


@app.get("/status")
async def service_status():
    """Detailed service status endpoint."""
    try:
        status = {
            "service": config.name,
            "version": "1.0.0",
            "timestamp": time.time(),
            "uptime": time.time() - app.state.start_time if hasattr(app.state, "start_time") else 0,
            "connections": {
                "active": len(connection_manager.active_connections),
                "max": connection_manager.max_connections,
                "utilization": len(connection_manager.active_connections) / connection_manager.max_connections * 100,
            },
            "models": {
                "whisper": {
                    "backend": getattr(whisper_engine, "backend", None),
                    "model_path": getattr(whisper_engine, "model_path", None),
                    "initialized": getattr(whisper_engine, "is_initialized", False),
                },
            },
            "services": {
                "http_port": config.port,
                "grpc_port": config.port + 1000,
                "grpc_available": grpc_server is not None,
            },
            "resources": {
                "audio_processor_available": audio_processor is not None,
                "redis_connected": redis_client is not None,
                "metrics_enabled": metrics is not None,
            },
        }
        
        # Add connection details
        connection_details = {}
        for session_id, state in connection_manager.connection_states.items():
            connection_details[session_id] = {
                "connected_at": state.get("connected_at"),
                "last_activity": state.get("last_activity"),
                "buffer_size": state.get("buffer_size", 0),
                "is_processing": state.get("is_processing", False),
                "message_count": state.get("message_count", 0),
                "error_count": state.get("error_count", 0),
            }
        
        status["active_sessions"] = connection_details
        
        return status
    
    except Exception as exc:
        logger.error("Status check failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/info", response_model=ServiceInfo)
async def service_info() -> ServiceInfo:
    """Get service information."""
    return ServiceInfo(
        name=config.name,
        version="1.0.0",
        description="Speech-to-Text service with Whisper.cpp integration and real-time streaming",
        endpoints=[
            "/health",
            "/health/live",
            "/health/ready", 
            "/status",
            "/info",
            "/metrics",
            "/validate-audio",
            "/convert-audio",
            "/transcribe",
            "/transcribe-file",
            "/transcribe-stream/{session_id}",
        ],
    )


@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint."""
    return metrics_endpoint()


@app.post("/validate-audio")
async def validate_audio_endpoint(file: UploadFile = File(...)):
    """Validate audio file and return detailed information."""
    try:
        # Read file data
        audio_data = await file.read()
        
        # Validate audio
        validation_result = await audio_processor.validate_audio_file(audio_data)
        
        # Get quality metrics if possible
        quality_metrics = await audio_processor.get_audio_quality_metrics(audio_data)
        
        return {
            "validation": validation_result,
            "quality_metrics": quality_metrics,
            "file_info": {
                "filename": file.filename,
                "content_type": file.content_type,
                "size": len(audio_data),
            }
        }
        
    except Exception as exc:
        logger.error("Audio validation failed", filename=file.filename, error=str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Audio validation failed: {str(exc)}"
        )


@app.post("/convert-audio")
async def convert_audio_endpoint(
    file: UploadFile = File(...),
    target_format: str = Form("wav"),
    target_sample_rate: Optional[int] = Form(None),
):
    """Convert audio file to different format."""
    try:
        if not file.content_type or not file.content_type.startswith("audio/"):
            raise HTTPException(status_code=400, detail="Invalid file type. Must be an audio file.")
        
        # Read file data
        audio_data = await file.read()
        
        # Determine source format from content type or filename
        source_format = "wav"  # Default
        if file.content_type:
            content_type_map = {
                "audio/wav": "wav",
                "audio/mpeg": "mp3",
                "audio/mp3": "mp3",
                "audio/flac": "flac",
                "audio/ogg": "ogg",
                "audio/mp4": "m4a",
            }
            source_format = content_type_map.get(file.content_type, "wav")
        
        # Convert audio format
        converted_data = await audio_processor.convert_audio_format(
            audio_data,
            source_format=source_format,
            target_format=target_format,
            target_sample_rate=target_sample_rate,
        )
        
        # Return converted audio
        from fastapi.responses import Response
        
        media_type_map = {
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
            "flac": "audio/flac",
            "ogg": "audio/ogg",
            "m4a": "audio/mp4",
        }
        
        media_type = media_type_map.get(target_format, "audio/wav")
        filename = f"converted.{target_format}"
        
        return Response(
            content=converted_data,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as exc:
        logger.error("Audio conversion failed", filename=file.filename, error=str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Audio conversion failed: {str(exc)}"
        )


@app.post("/transcribe", response_model=STTResponse)
async def transcribe_audio(request: STTRequest) -> STTResponse:
    """Transcribe audio from base64 data or URL."""
    start_time = time.time()
    
    if not whisper_engine:
        raise ModelInferenceError("Whisper engine not initialized", "whisper")
    
    try:
        # Get audio data
        if request.audio_data:
            audio_data = decode_audio_base64(request.audio_data)
        elif request.audio_url:
            # TODO: Implement URL fetching
            raise ValidationError("URL audio input not yet implemented")
        else:
            raise ValidationError("Either audio_data or audio_url must be provided")
        
        # Validate audio data
        if not validate_audio_data(audio_data, max_size=config.max_audio_size):
            raise AudioProcessingError("Invalid or too large audio data", "validation")
        
        # Get audio info
        audio_info = get_audio_info(audio_data)
        logger.info("Processing audio", **audio_info)
        
        # Preprocess audio if needed
        processed_audio = await audio_processor.preprocess_audio(
            audio_data, 
            target_format="wav",
            apply_vad=request.enable_vad,
        )
        
        # Transcribe with Whisper
        async with AsyncTimer("whisper_transcription") as timer:
            result = await whisper_engine.transcribe(
                processed_audio,
                language=request.language.value if request.language else None,
                model=request.model,
                temperature=request.temperature,
                return_timestamps=request.return_timestamps,
                return_word_level_timestamps=request.return_word_level_timestamps,
            )
        
        # Record metrics
        if metrics:
            metrics.record_inference(
                model=request.model,
                duration=timer.elapsed,
                input_tokens=0,  # Audio doesn't have input tokens
                output_tokens=len(result.get("text", "").split()),
            )
            metrics.record_audio_processing(
                operation="transcription",
                duration=timer.elapsed,
                format=audio_info["format"],
                success=True,
            )
        
        # Build response
        response = STTResponse(
            text=result["text"],
            language=request.language,
            confidence=result.get("confidence"),
            duration=result.get("duration"),
            segments=result.get("segments", []),
            words=result.get("words", []),
            processing_time=time.time() - start_time,
        )
        
        logger.info(
            "Transcription completed",
            text_length=len(response.text),
            processing_time=response.processing_time,
            confidence=response.confidence,
        )
        
        return response
        
    except Exception as exc:
        logger.error("Transcription failed", error=str(exc), exc_info=True)
        if isinstance(exc, (ValidationError, AudioProcessingError, ModelInferenceError)):
            raise exc
        raise ModelInferenceError(f"Transcription failed: {str(exc)}", "whisper")


@app.post("/transcribe-file", response_model=STTResponse)
async def transcribe_file(
    file: UploadFile = File(...),
    model: str = Form("base.en"),
    language: Optional[str] = Form(None),
    temperature: float = Form(0.0),
    enable_vad: bool = Form(True),
    return_timestamps: bool = Form(False),
    return_word_level_timestamps: bool = Form(False),
) -> STTResponse:
    """Transcribe uploaded audio file."""
    
    if not whisper_engine:
        raise ModelInferenceError("Whisper engine not initialized", "whisper")
    
    # Validate file
    if not file.content_type or not file.content_type.startswith("audio/"):
        raise ValidationError("Invalid file type. Must be an audio file.")
    
    if file.size and file.size > config.max_audio_size:
        raise ValidationError(f"File too large. Maximum size: {config.max_audio_size} bytes")
    
    try:
        # Read file data
        audio_data = await file.read()
        
        # Create STT request
        request = STTRequest(
            audio_data=encode_audio_base64(audio_data),
            model=model,
            language=language,
            temperature=temperature,
            enable_vad=enable_vad,
            return_timestamps=return_timestamps,
            return_word_level_timestamps=return_word_level_timestamps,
        )
        
        # Process transcription
        return await transcribe_audio(request)
        
    except Exception as exc:
        logger.error("File transcription failed", filename=file.filename, error=str(exc))
        if isinstance(exc, (ValidationError, AudioProcessingError, ModelInferenceError)):
            raise exc
        raise ModelInferenceError(f"File transcription failed: {str(exc)}", "whisper")


connection_manager = StreamingConnectionManager()


@app.websocket("/transcribe-stream/{session_id}")
async def transcribe_stream(websocket: WebSocket, session_id: str) -> None:
    """Real-time streaming transcription via WebSocket with backpressure control."""
    
    if not whisper_engine:
        await websocket.close(code=1011, reason="Whisper engine not initialized")
        return
    
    # Connect with backpressure check
    connected = await connection_manager.connect(websocket, session_id)
    if not connected:
        await websocket.close(code=1013, reason="Service unavailable - too many connections")
        return
    
    try:
        while True:
            # Receive message from client
            message = await websocket.receive_json()
            msg = WebSocketMessage(**message)
            
            if msg.type == "audio_chunk":
                # Check backpressure before processing
                audio_data = msg.data.get("audio", "")
                estimated_size = len(audio_data) if audio_data else 0
                
                if not connection_manager.can_accept_data(session_id, estimated_size):
                    # Send backpressure warning
                    await connection_manager.send_message(
                        session_id,
                        WebSocketResponse(
                            type="warning",
                            data={"message": "Processing overload, slowing down..."},
                        ),
                    )
                    continue
                
                # Process audio chunk
                await process_audio_chunk_enhanced(session_id, msg.data)
            
            elif msg.type == "start_session":
                # Start transcription session
                await start_transcription_session(session_id, msg.data)
            
            elif msg.type == "end_session":
                # End transcription session
                await end_transcription_session(session_id)
            
            elif msg.type == "ping":
                # Respond to ping
                await connection_manager.send_message(
                    session_id,
                    WebSocketResponse(
                        type="pong",
                        data={"timestamp": time.time()},
                    ),
                )
    
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", session_id=session_id)
    except Exception as exc:
        logger.error("WebSocket error", session_id=session_id, error=str(exc), exc_info=True)
        await connection_manager.send_message(
            session_id,
            WebSocketResponse(
                type="error",
                data={"error": str(exc)},
            ),
        )
    finally:
        connection_manager.disconnect(session_id)


async def process_audio_chunk_enhanced(session_id: str, data: Dict[str, Any]) -> None:
    """Enhanced process streaming audio chunk with better error handling."""
    try:
        # Get audio data from chunk
        audio_data = decode_audio_base64(data["audio"])
        audio_size = len(audio_data)
        
        # Update buffer size tracking
        connection_manager.update_buffer_size(session_id, audio_size)
        
        # Get connection state
        if session_id not in connection_manager.connection_states:
            logger.error("Session not found", session_id=session_id)
            return
        
        state = connection_manager.connection_states[session_id]
        
        # Check if already processing
        if state.get("is_processing", False):
            logger.debug("Already processing, queuing audio", session_id=session_id)
            return
        
        # Buffer the audio data
        state["buffer"] += audio_data
        
        # Process when buffer has enough data
        min_buffer_size = 16000  # ~1 second at 16kHz mono for better responsiveness
        max_buffer_size = 96000  # ~6 seconds max
        
        current_buffer_size = len(state["buffer"])
        
        if current_buffer_size >= min_buffer_size:
            state["is_processing"] = True
            
            # Limit buffer size to prevent memory issues
            if current_buffer_size > max_buffer_size:
                logger.warning("Buffer size exceeded, truncating", 
                              session_id=session_id,
                              size=current_buffer_size)
                state["buffer"] = state["buffer"][-max_buffer_size:]
                current_buffer_size = max_buffer_size
            
            # Process buffer with overlap
            overlap_size = min_buffer_size // 4  # 25% overlap
            buffer_data = state["buffer"]
            
            # Keep overlap for next processing
            if current_buffer_size > overlap_size:
                state["buffer"] = state["buffer"][-overlap_size:]
                connection_manager.update_buffer_size(session_id, -current_buffer_size + overlap_size)
            else:
                state["buffer"] = b""
                connection_manager.update_buffer_size(session_id, -current_buffer_size)
            
            try:
                # Validate and preprocess audio
                validation = await audio_processor.validate_audio_file(buffer_data)
                if not validation["is_valid"]:
                    logger.warning("Invalid audio chunk", 
                                  session_id=session_id, 
                                  errors=validation.get("errors", []))
                    state["is_processing"] = False
                    return
                
                # Optimize audio for transcription
                processed_audio = await audio_processor.optimize_for_transcription(buffer_data)
                
                # Transcribe chunk
                result = await whisper_engine.transcribe_chunk(processed_audio)
                
                # Send partial result if we have text
                if result.get("text", "").strip():
                    chunk = StreamSTTChunk(
                        text=result["text"].strip(),
                        is_partial=True,
                        confidence=result.get("confidence"),
                    )
                    
                    success = await connection_manager.send_message(
                        session_id,
                        WebSocketResponse(
                            type="transcription_chunk",
                            data=chunk.dict(),
                        ),
                    )
                    
                    if not success:
                        logger.warning("Failed to send transcription result", session_id=session_id)
                
                # Record metrics
                if metrics:
                    metrics.record_audio_processing(
                        operation="streaming_transcription",
                        duration=0.5,  # Estimated
                        format="wav",
                        success=True,
                    )
                
            except Exception as processing_exc:
                logger.error("Chunk transcription failed", 
                            session_id=session_id, 
                            error=str(processing_exc))
                
                # Record failed metrics
                if metrics:
                    metrics.record_audio_processing(
                        operation="streaming_transcription",
                        duration=0.5,
                        format="wav",
                        success=False,
                    )
            
            finally:
                state["is_processing"] = False
            
    except Exception as exc:
        logger.error("Audio chunk processing failed", session_id=session_id, error=str(exc))
        
        # Send error to client
        await connection_manager.send_message(
            session_id,
            WebSocketResponse(
                type="error",
                data={"error": f"Chunk processing failed: {str(exc)}"},
            ),
        )
        
        # Reset processing state
        if session_id in connection_manager.connection_states:
            connection_manager.connection_states[session_id]["is_processing"] = False


async def process_audio_chunk(session_id: str, data: Dict[str, Any]) -> None:
    """Legacy process streaming audio chunk (for backward compatibility)."""
    await process_audio_chunk_enhanced(session_id, data)


async def start_transcription_session(session_id: str, data: Dict[str, Any]) -> None:
    """Start a new transcription session."""
    try:
        logger.info("Starting transcription session", session_id=session_id)
        
        # Initialize session state
        state = connection_manager.connection_states[session_id]
        state.update({
            "model": data.get("model", "base.en"),
            "language": data.get("language"),
            "temperature": data.get("temperature", 0.0),
            "enable_vad": data.get("enable_vad", True),
        })
        
        await connection_manager.send_message(
            session_id,
            WebSocketResponse(
                type="session_started",
                data={"session_id": session_id},
            ),
        )
        
    except Exception as exc:
        logger.error("Failed to start session", session_id=session_id, error=str(exc))


async def end_transcription_session(session_id: str) -> None:
    """End transcription session and cleanup."""
    try:
        logger.info("Ending transcription session", session_id=session_id)
        
        # Process any remaining buffer
        state = connection_manager.connection_states[session_id]
        if state["buffer"]:
            buffer_data = state["buffer"]
            state["buffer"] = b""
            
            processed_audio = await audio_processor.preprocess_audio(
                buffer_data,
                target_format="wav",
                apply_vad=True,
            )
            
            result = await whisper_engine.transcribe_chunk(processed_audio)
            
            # Send final chunk
            chunk = StreamSTTChunk(
                text=result.get("text", ""),
                is_partial=False,
                confidence=result.get("confidence"),
            )
            
            await connection_manager.send_message(
                session_id,
                WebSocketResponse(
                    type="transcription_final",
                    data=chunk.dict(),
                ),
            )
        
        await connection_manager.send_message(
            session_id,
            WebSocketResponse(
                type="session_ended",
                data={"session_id": session_id},
            ),
        )
        
    except Exception as exc:
        logger.error("Failed to end session", session_id=session_id, error=str(exc))


if __name__ == "__main__":
    config = STTServiceConfig()
    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level="info",
    )