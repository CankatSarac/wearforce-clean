"""gRPC server implementation for STT audio streaming service."""

import asyncio
import time
from typing import AsyncGenerator, Dict, Optional, Any
import uuid

import grpc
import structlog
from grpc import aio

# Import protocol buffer generated classes
# Note: These would be generated from the proto files
# For now, we'll create mock classes that match the expected interface
from dataclasses import dataclass
from enum import Enum


logger = structlog.get_logger(__name__)


# Mock proto classes - in real implementation, these would be generated
@dataclass
class AudioConfig:
    encoding: str = "LINEAR16"
    sample_rate_hertz: int = 16000
    audio_channel_count: int = 1
    language_code: str = "en-US"
    enable_word_time_offsets: bool = False
    enable_automatic_punctuation: bool = True


@dataclass
class AudioData:
    content: bytes
    timestamp: Optional[float] = None
    sequence_number: int = 0
    duration: Optional[float] = None


@dataclass
class TranscriptionResult:
    alternatives: list
    is_final: bool = False
    stability: float = 0.0
    result_end_time: Optional[float] = None
    language_code: str = "en-US"


@dataclass
class TranscriptAlternative:
    transcript: str
    confidence: float
    words: list


@dataclass
class WordInfo:
    start_time: float
    end_time: float
    word: str
    confidence: float


@dataclass
class ErrorResponse:
    code: int
    message: str
    details: list
    timestamp: float


@dataclass
class StatusMessage:
    status: str
    message: str
    timestamp: float


class STTRequest:
    def __init__(self, config: Optional[AudioConfig] = None, audio_data: Optional[AudioData] = None):
        self.config = config
        self.audio_data = audio_data


class STTResponse:
    def __init__(self, transcription: Optional[TranscriptionResult] = None, error: Optional[ErrorResponse] = None):
        self.transcription = transcription
        self.error = error


class TTSRequest:
    def __init__(self, text: str, voice_config: Optional[dict] = None, audio_config: Optional[AudioConfig] = None, language_code: str = "en-US"):
        self.text = text
        self.voice_config = voice_config or {}
        self.audio_config = audio_config
        self.language_code = language_code


class TTSResponse:
    def __init__(self, audio_data: Optional[AudioData] = None, error: Optional[ErrorResponse] = None, status: Optional[StatusMessage] = None):
        self.audio_data = audio_data
        self.error = error
        self.status = status


class AudioStreamingServiceServicer:
    """gRPC servicer for audio streaming."""
    
    def __init__(self, whisper_engine, audio_processor):
        self.whisper_engine = whisper_engine
        self.audio_processor = audio_processor
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self._session_lock = asyncio.Lock()
    
    async def BiDirectionalStream(
        self,
        request_iterator: AsyncGenerator[Any, None],
        context: grpc.aio.ServicerContext,
    ) -> AsyncGenerator[Any, None]:
        """Bi-directional streaming for both STT and TTS."""
        session_id = str(uuid.uuid4())
        logger.info("Starting bi-directional audio stream", session_id=session_id)
        
        try:
            async with self._session_lock:
                self.active_sessions[session_id] = {
                    "created_at": time.time(),
                    "audio_config": None,
                    "buffer": b"",
                    "sequence_number": 0,
                }
            
            async for request in request_iterator:
                try:
                    if hasattr(request, 'config') and request.config:
                        # Handle configuration
                        await self._handle_audio_config(session_id, request.config)
                        
                        # Send status response
                        status = StatusMessage(
                            status="CONFIGURED",
                            message="Audio configuration received",
                            timestamp=time.time()
                        )
                        yield TTSResponse(status=status)
                    
                    elif hasattr(request, 'audio_data') and request.audio_data:
                        # Handle audio data for STT
                        async for response in self._process_audio_chunk(session_id, request.audio_data):
                            yield response
                    
                    elif hasattr(request, 'text_data') and request.text_data:
                        # Handle text data for TTS
                        async for response in self._process_text_chunk(session_id, request.text_data):
                            yield response
                    
                    elif hasattr(request, 'control') and request.control:
                        # Handle control messages
                        await self._handle_control_message(session_id, request.control)
                
                except Exception as exc:
                    logger.error("Error processing request", session_id=session_id, error=str(exc))
                    error = ErrorResponse(
                        code=500,
                        message=f"Processing error: {str(exc)}",
                        details=[],
                        timestamp=time.time()
                    )
                    yield TTSResponse(error=error)
        
        except Exception as exc:
            logger.error("Bi-directional stream error", session_id=session_id, error=str(exc))
        
        finally:
            # Cleanup session
            async with self._session_lock:
                if session_id in self.active_sessions:
                    del self.active_sessions[session_id]
            
            logger.info("Bi-directional stream ended", session_id=session_id)
    
    async def SpeechToText(
        self,
        request_iterator: AsyncGenerator[STTRequest, None],
        context: grpc.aio.ServicerContext,
    ) -> AsyncGenerator[STTResponse, None]:
        """Streaming speech-to-text."""
        session_id = str(uuid.uuid4())
        logger.info("Starting STT stream", session_id=session_id)
        
        try:
            session_state = {
                "audio_config": None,
                "buffer": b"",
                "sequence_number": 0,
            }
            
            async for request in request_iterator:
                try:
                    if request.config:
                        # Handle audio configuration
                        session_state["audio_config"] = request.config
                        logger.info("STT configuration received", 
                                  session_id=session_id, 
                                  config=request.config)
                    
                    elif request.audio_data:
                        # Process audio chunk
                        async for response in self._transcribe_audio_chunk(
                            session_id, request.audio_data, session_state
                        ):
                            yield response
                
                except Exception as exc:
                    logger.error("STT processing error", session_id=session_id, error=str(exc))
                    error = ErrorResponse(
                        code=500,
                        message=f"STT error: {str(exc)}",
                        details=[],
                        timestamp=time.time()
                    )
                    yield STTResponse(error=error)
        
        except Exception as exc:
            logger.error("STT stream error", session_id=session_id, error=str(exc))
        
        finally:
            logger.info("STT stream ended", session_id=session_id)
    
    async def TextToSpeech(
        self,
        request: TTSRequest,
        context: grpc.aio.ServicerContext,
    ) -> AsyncGenerator[TTSResponse, None]:
        """Text-to-speech conversion."""
        session_id = str(uuid.uuid4())
        logger.info("Starting TTS conversion", session_id=session_id, text_length=len(request.text))
        
        try:
            # For now, return a placeholder response since TTS is handled by a separate service
            # In a complete implementation, this would integrate with the TTS service
            
            # Send status message
            status = StatusMessage(
                status="PROCESSING",
                message="TTS processing started",
                timestamp=time.time()
            )
            yield TTSResponse(status=status)
            
            # Simulate processing delay
            await asyncio.sleep(0.1)
            
            # Send completion status
            status = StatusMessage(
                status="COMPLETED",
                message="TTS processing completed",
                timestamp=time.time()
            )
            yield TTSResponse(status=status)
        
        except Exception as exc:
            logger.error("TTS error", session_id=session_id, error=str(exc))
            error = ErrorResponse(
                code=500,
                message=f"TTS error: {str(exc)}",
                details=[],
                timestamp=time.time()
            )
            yield TTSResponse(error=error)
    
    async def GetAudioConfig(self, request, context):
        """Get supported audio configurations."""
        try:
            # Return supported configurations
            supported_configs = [
                AudioConfig(
                    encoding="LINEAR16",
                    sample_rate_hertz=16000,
                    audio_channel_count=1,
                    language_code="en-US"
                ),
                AudioConfig(
                    encoding="FLAC",
                    sample_rate_hertz=16000,
                    audio_channel_count=1,
                    language_code="en-US"
                ),
                AudioConfig(
                    encoding="OGG_OPUS",
                    sample_rate_hertz=16000,
                    audio_channel_count=1,
                    language_code="en-US"
                )
            ]
            
            supported_languages = [
                "en-US", "en-GB", "es-ES", "fr-FR", "de-DE", "it-IT", "pt-PT", "ru-RU", "ja-JP", "ko-KR", "zh-CN"
            ]
            
            # Return mock response (in real implementation, this would be a proper protobuf response)
            return {
                "supported_configs": supported_configs,
                "supported_voices": [],
                "supported_languages": supported_languages
            }
        
        except Exception as exc:
            logger.error("GetAudioConfig error", error=str(exc))
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Configuration error: {str(exc)}")
            return None
    
    async def _handle_audio_config(self, session_id: str, config: AudioConfig) -> None:
        """Handle audio configuration for a session."""
        async with self._session_lock:
            if session_id in self.active_sessions:
                self.active_sessions[session_id]["audio_config"] = config
        
        logger.info("Audio configuration updated", 
                   session_id=session_id,
                   encoding=config.encoding,
                   sample_rate=config.sample_rate_hertz)
    
    async def _process_audio_chunk(
        self, 
        session_id: str, 
        audio_data: AudioData
    ) -> AsyncGenerator[Any, None]:
        """Process audio chunk and return transcription."""
        try:
            # Get session state
            async with self._session_lock:
                session_state = self.active_sessions.get(session_id, {})
            
            # Buffer audio data
            session_state["buffer"] = session_state.get("buffer", b"") + audio_data.content
            session_state["sequence_number"] = audio_data.sequence_number
            
            # Process if buffer has enough data
            min_buffer_size = 32000  # ~2 seconds at 16kHz mono
            
            if len(session_state["buffer"]) >= min_buffer_size:
                # Preprocess audio
                processed_audio = await self.audio_processor.preprocess_audio(
                    session_state["buffer"],
                    target_format="wav",
                    apply_vad=True
                )
                
                # Transcribe
                result = await self.whisper_engine.transcribe_chunk(processed_audio)
                
                # Clear buffer
                session_state["buffer"] = b""
                
                # Create response
                if result.get("text"):
                    alternative = TranscriptAlternative(
                        transcript=result["text"],
                        confidence=result.get("confidence", 0.0),
                        words=[]
                    )
                    
                    transcription = TranscriptionResult(
                        alternatives=[alternative],
                        is_final=False,  # Partial result
                        stability=result.get("confidence", 0.0),
                        language_code=session_state.get("audio_config", {}).get("language_code", "en-US")
                    )
                    
                    yield STTResponse(transcription=transcription)
        
        except Exception as exc:
            logger.error("Audio chunk processing error", session_id=session_id, error=str(exc))
            error = ErrorResponse(
                code=500,
                message=f"Audio processing error: {str(exc)}",
                details=[],
                timestamp=time.time()
            )
            yield STTResponse(error=error)
    
    async def _process_text_chunk(
        self, 
        session_id: str, 
        text_data: Any
    ) -> AsyncGenerator[TTSResponse, None]:
        """Process text chunk for TTS (placeholder)."""
        try:
            # This would integrate with the TTS service
            # For now, just send a status message
            status = StatusMessage(
                status="PROCESSING",
                message="TTS processing not implemented in STT service",
                timestamp=time.time()
            )
            yield TTSResponse(status=status)
        
        except Exception as exc:
            logger.error("Text chunk processing error", session_id=session_id, error=str(exc))
            error = ErrorResponse(
                code=500,
                message=f"TTS processing error: {str(exc)}",
                details=[],
                timestamp=time.time()
            )
            yield TTSResponse(error=error)
    
    async def _handle_control_message(self, session_id: str, control: Any) -> None:
        """Handle control messages."""
        try:
            command = getattr(control, 'command', None)
            logger.info("Control message received", session_id=session_id, command=command)
            
            async with self._session_lock:
                if session_id in self.active_sessions:
                    session = self.active_sessions[session_id]
                    
                    if command == "END_SESSION":
                        # Process any remaining buffer
                        if session.get("buffer"):
                            buffer_data = session["buffer"]
                            session["buffer"] = b""
                            
                            try:
                                processed_audio = await self.audio_processor.preprocess_audio(
                                    buffer_data,
                                    target_format="wav",
                                    apply_vad=True
                                )
                                
                                result = await self.whisper_engine.transcribe_chunk(processed_audio)
                                logger.info("Final transcription", session_id=session_id, text=result.get("text", ""))
                            except Exception as exc:
                                logger.error("Final buffer processing failed", session_id=session_id, error=str(exc))
        
        except Exception as exc:
            logger.error("Control message handling error", session_id=session_id, error=str(exc))
    
    async def _transcribe_audio_chunk(
        self,
        session_id: str,
        audio_data: AudioData,
        session_state: Dict[str, Any]
    ) -> AsyncGenerator[STTResponse, None]:
        """Transcribe audio chunk for STT stream."""
        try:
            # Buffer audio data
            session_state["buffer"] = session_state.get("buffer", b"") + audio_data.content
            
            # Process if buffer has enough data
            min_buffer_size = 16000  # ~1 second at 16kHz mono for more responsive streaming
            
            if len(session_state["buffer"]) >= min_buffer_size:
                # Preprocess audio
                processed_audio = await self.audio_processor.preprocess_audio(
                    session_state["buffer"],
                    target_format="wav",
                    apply_vad=True
                )
                
                # Transcribe
                result = await self.whisper_engine.transcribe_chunk(processed_audio)
                
                # Clear processed portion of buffer (keep some overlap)
                overlap_size = min_buffer_size // 4
                session_state["buffer"] = session_state["buffer"][-overlap_size:]
                
                # Create response
                if result.get("text"):
                    alternative = TranscriptAlternative(
                        transcript=result["text"],
                        confidence=result.get("confidence", 0.0),
                        words=[]
                    )
                    
                    transcription = TranscriptionResult(
                        alternatives=[alternative],
                        is_final=False,  # Streaming result
                        stability=result.get("confidence", 0.0),
                        language_code=session_state.get("audio_config", AudioConfig()).language_code
                    )
                    
                    yield STTResponse(transcription=transcription)
        
        except Exception as exc:
            logger.error("STT chunk processing error", session_id=session_id, error=str(exc))
            error = ErrorResponse(
                code=500,
                message=f"STT processing error: {str(exc)}",
                details=[],
                timestamp=time.time()
            )
            yield STTResponse(error=error)


async def create_grpc_server(
    whisper_engine,
    audio_processor,
    port: int = 50051
) -> grpc.aio.Server:
    """Create and configure gRPC server."""
    
    server = grpc.aio.server()
    
    # Add the servicer
    servicer = AudioStreamingServiceServicer(whisper_engine, audio_processor)
    
    # In a real implementation, you would add the generated service here:
    # add_AudioStreamingServiceServicer_to_server(servicer, server)
    
    # Configure server options
    options = [
        ('grpc.keepalive_time_ms', 30000),
        ('grpc.keepalive_timeout_ms', 5000),
        ('grpc.keepalive_permit_without_calls', True),
        ('grpc.http2.max_pings_without_data', 0),
        ('grpc.http2.min_time_between_pings_ms', 10000),
        ('grpc.http2.min_ping_interval_without_data_ms', 300000),
        ('grpc.max_receive_message_length', 4 * 1024 * 1024),  # 4MB
        ('grpc.max_send_message_length', 4 * 1024 * 1024),     # 4MB
    ]
    
    for option in options:
        server.add_generic_rpc_handlers([])
    
    # Add insecure port (in production, use secure port with TLS)
    listen_addr = f'[::]:{port}'
    server.add_insecure_port(listen_addr)
    
    logger.info("gRPC server configured", port=port, listen_addr=listen_addr)
    
    return server


async def run_grpc_server(
    whisper_engine,
    audio_processor,
    port: int = 50051
) -> None:
    """Run the gRPC server."""
    
    server = await create_grpc_server(whisper_engine, audio_processor, port)
    
    await server.start()
    logger.info("gRPC server started", port=port)
    
    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("gRPC server stopping...")
    finally:
        await server.stop(grace=5)
        logger.info("gRPC server stopped")