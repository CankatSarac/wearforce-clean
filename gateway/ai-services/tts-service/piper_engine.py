"""Piper TTS engine wrapper for text-to-speech synthesis."""

import asyncio
import io
import json
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import structlog

from shared.exceptions import ModelInferenceError
from shared.utils import AsyncTimer, run_in_executor, chunk_text_by_tokens

logger = structlog.get_logger(__name__)


class PiperEngine:
    """Piper TTS engine for text-to-speech synthesis."""
    
    def __init__(
        self,
        voice_manager=None,
        sample_rate: int = 22050,
        cache_store=None,
    ):
        self.voice_manager = voice_manager
        self.sample_rate = sample_rate
        self.cache_store = cache_store
        self.is_initialized = False
        self.piper_executable = None
        self._synthesis_semaphore = asyncio.Semaphore(4)  # Limit concurrent synthesis
        
    async def initialize(self) -> None:
        """Initialize the Piper engine."""
        try:
            logger.info("Initializing Piper TTS engine")
            
            # Find Piper executable
            self.piper_executable = await self._find_piper_executable()
            
            if not self.piper_executable:
                raise ModelInferenceError(
                    "Piper executable not found. Please install Piper TTS.",
                    "piper"
                )
            
            # Test Piper installation
            await self._test_piper_installation()
            
            self.is_initialized = True
            logger.info("Piper TTS engine initialized successfully")
            
        except Exception as exc:
            logger.error("Failed to initialize Piper engine", error=str(exc), exc_info=True)
            raise ModelInferenceError(f"Piper initialization failed: {str(exc)}", "piper")
    
    async def health_check(self) -> bool:
        """Check if Piper engine is healthy."""
        if not self.is_initialized or not self.piper_executable:
            return False
        
        try:
            # Quick health check by running piper --help
            process = await asyncio.create_subprocess_exec(
                self.piper_executable, "--help",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(process.wait(), timeout=5.0)
            return process.returncode == 0
        except Exception:
            return False
    
    async def synthesize(
        self,
        text: str,
        voice: str,
        speed: float = 1.0,
        pitch: float = 1.0,
        volume: float = 1.0,
        format: str = "wav",
        sample_rate: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Synthesize speech from text."""
        if not self.is_initialized:
            raise ModelInferenceError("Piper engine not initialized", "piper")
        
        async with self._synthesis_semaphore:
            try:
                logger.debug(
                    "Synthesizing speech",
                    voice=voice,
                    text_length=len(text),
                    speed=speed,
                    pitch=pitch,
                )
                
                # Get voice model path
                if not self.voice_manager:
                    raise ModelInferenceError("Voice manager not available", "piper")
                
                voice_path = await self.voice_manager.get_voice_model_path(voice)
                if not voice_path:
                    raise ModelInferenceError(f"Voice '{voice}' not found", "piper")
                
                # Synthesize audio
                audio_data = await self._synthesize_with_piper(
                    text=text,
                    voice_path=voice_path,
                    speed=speed,
                    sample_rate=sample_rate or self.sample_rate,
                )
                
                # Apply post-processing if needed
                if pitch != 1.0 or volume != 1.0:
                    audio_data = await self._apply_audio_effects(
                        audio_data, pitch=pitch, volume=volume
                    )
                
                # Convert format if needed
                if format != "wav":
                    audio_data = await self._convert_audio_format(audio_data, format)
                
                # Calculate duration
                duration = len(audio_data) / (sample_rate or self.sample_rate) / 2  # 16-bit audio
                
                return {
                    "audio_data": audio_data,
                    "sample_rate": sample_rate or self.sample_rate,
                    "duration": duration,
                    "format": format,
                }
                
            except Exception as exc:
                logger.error("Speech synthesis failed", error=str(exc), exc_info=True)
                raise ModelInferenceError(f"Speech synthesis failed: {str(exc)}", "piper")
    
    async def synthesize_streaming(
        self,
        text: str,
        voice: str,
        speed: float = 1.0,
        pitch: float = 1.0,
        volume: float = 1.0,
        format: str = "wav",
        sample_rate: Optional[int] = None,
        chunk_size: int = 512,
    ) -> AsyncGenerator[bytes, None]:
        """Synthesize speech with streaming output."""
        if not self.is_initialized:
            raise ModelInferenceError("Piper engine not initialized", "piper")
        
        async with self._synthesis_semaphore:  # Limit concurrent streaming
            try:
                logger.debug("Starting streaming synthesis", voice=voice, text_length=len(text))
                
                # Get voice model path
                if not self.voice_manager:
                    raise ModelInferenceError("Voice manager not available", "piper")
                
                voice_path = await self.voice_manager.get_voice_model_path(voice)
                if not voice_path:
                    raise ModelInferenceError(f"Voice '{voice}' not found", "piper")
                
                # Split text into manageable chunks
                text_chunks = chunk_text_by_tokens(text, max_tokens=chunk_size, overlap_tokens=20)
                
                if not text_chunks:
                    logger.warning("No text chunks generated")
                    return
                
                logger.debug(f"Generated {len(text_chunks)} text chunks for streaming")
                
                # Initialize streaming state
                total_audio_length = 0
                chunk_count = 0
                
                # For WAV streaming, we'll send individual complete WAV files
                # This is simpler than trying to construct a proper streaming WAV
                
                # Process each chunk
                for i, chunk_text in enumerate(text_chunks):
                    if not chunk_text.strip():
                        continue
                    
                    try:
                        logger.debug(f"Processing chunk {i + 1}/{len(text_chunks)}", chunk_length=len(chunk_text))
                        
                        # Synthesize chunk with direct Piper call for better streaming
                        audio_data = await self._synthesize_with_piper(
                            text=chunk_text,
                            voice_path=voice_path,
                            speed=speed,
                            sample_rate=sample_rate or self.sample_rate,
                        )
                        
                        # Apply post-processing if needed
                        if pitch != 1.0 or volume != 1.0:
                            audio_data = await self._apply_audio_effects(
                                audio_data, pitch=pitch, volume=volume
                            )
                        
                        # Convert format if needed
                        if format != "wav":
                            audio_data = await self._convert_audio_format(audio_data, format)
                        
                        # Track streaming statistics
                        total_audio_length += len(audio_data)
                        chunk_count += 1
                        
                        logger.debug(
                            f"Streaming chunk {i + 1} completed",
                            chunk_size=len(audio_data),
                            total_length=total_audio_length,
                        )
                        
                        yield audio_data
                        
                        # Small delay to prevent overwhelming the client and allow cancellation
                        await asyncio.sleep(0.01)
                        
                    except asyncio.CancelledError:
                        logger.info("Streaming synthesis cancelled by client")
                        break
                        
                    except Exception as exc:
                        logger.error(
                            f"Failed to synthesize chunk {i + 1}",
                            error=str(exc),
                            chunk_text=chunk_text[:100] + "..." if len(chunk_text) > 100 else chunk_text,
                        )
                        # Continue with next chunk instead of failing completely
                        continue
                
                logger.info(
                    "Streaming synthesis completed",
                    chunks_processed=chunk_count,
                    total_chunks=len(text_chunks),
                    total_audio_bytes=total_audio_length,
                )
                        
            except Exception as exc:
                logger.error("Streaming synthesis failed", error=str(exc), exc_info=True)
                raise ModelInferenceError(f"Streaming synthesis failed: {str(exc)}", "piper")
    
    async def _find_piper_executable(self) -> Optional[str]:
        """Find Piper executable in system PATH or common locations."""
        
        # Common executable names
        executable_names = ["piper", "piper.exe", "piper-tts"]
        
        # Check system PATH
        for name in executable_names:
            try:
                process = await asyncio.create_subprocess_exec(
                    "which" if not name.endswith(".exe") else "where",
                    name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await process.communicate()
                if process.returncode == 0 and stdout:
                    executable_path = stdout.decode().strip()
                    if Path(executable_path).exists():
                        logger.info("Found Piper executable", path=executable_path)
                        return executable_path
            except Exception:
                continue
        
        # Check common installation paths
        common_paths = [
            "/usr/local/bin/piper",
            "/usr/bin/piper",
            "~/bin/piper",
            "./piper",
            "/opt/piper/piper",
        ]
        
        for path in common_paths:
            expanded_path = Path(path).expanduser()
            if expanded_path.exists():
                logger.info("Found Piper executable", path=str(expanded_path))
                return str(expanded_path)
        
        logger.warning("Piper executable not found in common locations")
        return None
    
    async def _test_piper_installation(self) -> None:
        """Test Piper installation."""
        try:
            process = await asyncio.create_subprocess_exec(
                self.piper_executable, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=10.0
            )
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise ModelInferenceError(f"Piper test failed: {error_msg}", "piper")
            
            version_info = stdout.decode() if stdout else "Unknown version"
            logger.info("Piper installation verified", version=version_info.strip())
            
        except asyncio.TimeoutError:
            raise ModelInferenceError("Piper test timed out", "piper")
        except Exception as exc:
            raise ModelInferenceError(f"Piper test failed: {str(exc)}", "piper")
    
    async def _synthesize_with_piper(
        self,
        text: str,
        voice_path: str,
        speed: float = 1.0,
        sample_rate: int = 22050,
    ) -> bytes:
        """Synthesize audio using Piper executable."""
        
        def _run_piper():
            text_file_path = None
            output_file_path = None
            
            try:
                # Create temporary files
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as text_file:
                    text_file.write(text)
                    text_file_path = text_file.name
                
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as output_file:
                    output_file_path = output_file.name
                
                # Validate voice model file exists
                if not Path(voice_path).exists():
                    raise ModelInferenceError(f"Voice model not found: {voice_path}", "piper")
                
                # Prepare Piper command
                cmd = [
                    self.piper_executable,
                    "--model", voice_path,
                    "--output_file", output_file_path,
                ]
                
                # Add optional parameters
                if speed != 1.0:
                    length_scale = 1.0 / max(0.1, min(3.0, speed))  # Clamp speed and invert
                    cmd.extend(["--length_scale", str(length_scale)])
                
                if sample_rate != 22050:
                    cmd.extend(["--sample_rate", str(sample_rate)])
                
                logger.debug(
                    "Running Piper synthesis",
                    cmd=" ".join(cmd),
                    text_length=len(text),
                    voice_path=voice_path,
                )
                
                # Run Piper with improved error handling
                result = subprocess.run(
                    cmd,
                    input=text.encode('utf-8'),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=max(30, len(text) // 10),  # Dynamic timeout based on text length
                    check=False,  # Don't raise on non-zero exit
                )
                
                # Check for errors
                if result.returncode != 0:
                    error_msg = result.stderr.decode('utf-8') if result.stderr else "Unknown error"
                    stdout_msg = result.stdout.decode('utf-8') if result.stdout else ""
                    
                    logger.error(
                        "Piper synthesis failed",
                        returncode=result.returncode,
                        stderr=error_msg,
                        stdout=stdout_msg,
                        cmd=" ".join(cmd),
                    )
                    
                    raise ModelInferenceError(f"Piper synthesis failed (code {result.returncode}): {error_msg}", "piper")
                
                # Validate output file was created
                if not Path(output_file_path).exists():
                    raise ModelInferenceError("Piper did not generate output file", "piper")
                
                # Read generated audio
                with open(output_file_path, 'rb') as f:
                    audio_data = f.read()
                
                if len(audio_data) == 0:
                    raise ModelInferenceError("Piper generated empty audio file", "piper")
                
                logger.debug(
                    "Piper synthesis completed",
                    output_size=len(audio_data),
                    returncode=result.returncode,
                )
                
                return audio_data
                
            except subprocess.TimeoutExpired:
                logger.error("Piper synthesis timed out", text_length=len(text))
                raise ModelInferenceError("Piper synthesis timed out", "piper")
                
            except Exception as exc:
                if isinstance(exc, ModelInferenceError):
                    raise
                logger.error("Piper synthesis error", error=str(exc), exc_info=True)
                raise ModelInferenceError(f"Piper synthesis error: {str(exc)}", "piper")
                
            finally:
                # Cleanup temporary files
                for temp_path in [text_file_path, output_file_path]:
                    if temp_path:
                        try:
                            Path(temp_path).unlink(missing_ok=True)
                        except Exception as cleanup_exc:
                            logger.warning("Failed to cleanup temp file", path=temp_path, error=str(cleanup_exc))
        
        return await run_in_executor(_run_piper)
    
    async def _apply_audio_effects(
        self,
        audio_data: bytes,
        pitch: float = 1.0,
        volume: float = 1.0,
    ) -> bytes:
        """Apply audio effects (pitch, volume) to audio data."""
        
        def _process_audio():
            try:
                # Try to use librosa for audio effects
                import librosa
                import soundfile as sf
                import numpy as np
                
                with tempfile.NamedTemporaryFile(suffix='.wav') as temp_in:
                    temp_in.write(audio_data)
                    temp_in.flush()
                    
                    # Load audio
                    audio, sr = librosa.load(temp_in.name, sr=None)
                    
                    # Apply pitch shift
                    if pitch != 1.0:
                        # Convert pitch ratio to semitones
                        semitones = 12 * np.log2(pitch)
                        audio = librosa.effects.pitch_shift(
                            audio, sr=sr, n_steps=semitones
                        )
                    
                    # Apply volume change
                    if volume != 1.0:
                        audio = audio * volume
                        # Prevent clipping
                        if np.max(np.abs(audio)) > 1.0:
                            audio = audio / np.max(np.abs(audio))
                    
                    # Save processed audio
                    with tempfile.NamedTemporaryFile(suffix='.wav') as temp_out:
                        sf.write(temp_out.name, audio, sr)
                        temp_out.seek(0)
                        return temp_out.read()
                        
            except ImportError:
                logger.warning("librosa not available, skipping audio effects")
                return audio_data
            except Exception as exc:
                logger.warning("Audio effects failed", error=str(exc))
                return audio_data
        
        return await run_in_executor(_process_audio)
    
    async def _convert_audio_format(self, audio_data: bytes, target_format: str) -> bytes:
        """Convert audio to different format."""
        if target_format == "wav":
            return audio_data
        
        def _convert():
            try:
                from pydub import AudioSegment
                
                # Load audio from bytes
                audio = AudioSegment.from_wav(io.BytesIO(audio_data))
                
                # Export to target format
                output_buffer = io.BytesIO()
                audio.export(output_buffer, format=target_format)
                return output_buffer.getvalue()
                
            except ImportError:
                logger.warning(f"pydub not available, cannot convert to {target_format}")
                return audio_data
            except Exception as exc:
                logger.warning(f"Format conversion failed", error=str(exc))
                return audio_data
        
        return await run_in_executor(_convert)
    
    def _create_wav_header(
        self,
        sample_rate: int,
        channels: int = 1,
        bits_per_sample: int = 16,
        data_length: int = 0,
    ) -> bytes:
        """Create WAV file header for streaming."""
        # WAV header structure
        header = bytearray(44)
        
        # RIFF chunk descriptor
        header[0:4] = b'RIFF'
        header[4:8] = (36 + data_length).to_bytes(4, 'little')  # File size - 8
        header[8:12] = b'WAVE'
        
        # fmt subchunk
        header[12:16] = b'fmt '
        header[16:20] = (16).to_bytes(4, 'little')  # Subchunk size
        header[20:22] = (1).to_bytes(2, 'little')   # Audio format (PCM)
        header[22:24] = channels.to_bytes(2, 'little')
        header[24:28] = sample_rate.to_bytes(4, 'little')
        header[28:32] = (sample_rate * channels * bits_per_sample // 8).to_bytes(4, 'little')  # Byte rate
        header[32:34] = (channels * bits_per_sample // 8).to_bytes(2, 'little')  # Block align
        header[34:36] = bits_per_sample.to_bytes(2, 'little')
        
        # data subchunk
        header[36:40] = b'data'
        header[40:44] = data_length.to_bytes(4, 'little')
        
        return bytes(header)
    
    async def get_voice_capabilities(self, voice: str) -> Dict[str, Any]:
        """Get capabilities of a specific voice."""
        if not self.voice_manager:
            return {}
        
        try:
            voice_info = await self.voice_manager.get_voice_info(voice)
            if not voice_info:
                return {}
            
            # Validate that the voice model actually exists
            voice_path = await self.voice_manager.get_voice_model_path(voice)
            model_exists = voice_path and Path(voice_path).exists()
            
            capabilities = {
                "languages": [voice_info.language.value],
                "sample_rates": [voice_info.sample_rate, 16000, 22050, 44100],  # Common rates
                "formats": ["wav", "mp3", "ogg", "flac"],
                "streaming": True,
                "voice_cloning": False,  # Not implemented yet
                "emotions": [],  # Not supported by Piper
                "styles": [],   # Not supported by Piper
                "speed_range": {"min": 0.1, "max": 3.0, "default": 1.0},
                "pitch_range": {"min": 0.1, "max": 2.0, "default": 1.0},
                "volume_range": {"min": 0.1, "max": 2.0, "default": 1.0},
                "model_exists": model_exists,
                "voice_info": {
                    "name": voice_info.name,
                    "gender": voice_info.gender,
                    "description": voice_info.description,
                    "is_custom": voice_info.is_custom,
                },
            }
            
            if not model_exists:
                capabilities["error"] = "Voice model file not found"
                capabilities["status"] = "unavailable"
            else:
                capabilities["status"] = "available"
            
            return capabilities
            
        except Exception as exc:
            logger.error("Failed to get voice capabilities", voice=voice, error=str(exc))
            return {
                "error": f"Failed to get capabilities: {str(exc)}",
                "status": "error",
            }
    
    async def get_synthesis_stats(self) -> Dict[str, Any]:
        """Get synthesis statistics and performance metrics."""
        return {
            "engine_initialized": self.is_initialized,
            "piper_executable": self.piper_executable,
            "concurrent_synthesis_limit": self._synthesis_semaphore._value,
            "available_synthesis_slots": self._synthesis_semaphore._value,
            "sample_rate": self.sample_rate,
        }
    
    async def validate_piper_installation(self) -> Dict[str, Any]:
        """Comprehensive validation of Piper installation."""
        validation_result = {
            "piper_found": False,
            "piper_version": None,
            "piper_path": self.piper_executable,
            "can_run": False,
            "errors": [],
        }
        
        try:
            if not self.piper_executable:
                validation_result["errors"].append("Piper executable not found")
                return validation_result
            
            validation_result["piper_found"] = True
            
            # Test version command
            process = await asyncio.create_subprocess_exec(
                self.piper_executable, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10.0)
                
                if process.returncode == 0:
                    validation_result["can_run"] = True
                    if stdout:
                        validation_result["piper_version"] = stdout.decode().strip()
                else:
                    error_msg = stderr.decode() if stderr else "Unknown error"
                    validation_result["errors"].append(f"Piper version check failed: {error_msg}")
                    
            except asyncio.TimeoutError:
                validation_result["errors"].append("Piper version check timed out")
                
        except Exception as exc:
            validation_result["errors"].append(f"Piper validation error: {str(exc)}")
        
        return validation_result
    
    async def cleanup(self) -> None:
        """Cleanup resources."""
        logger.info("Cleaning up Piper engine")
        
        # Wait for any ongoing synthesis to complete
        try:
            # Acquire all semaphore slots to ensure no synthesis is running
            for _ in range(self._synthesis_semaphore._value):
                await asyncio.wait_for(self._synthesis_semaphore.acquire(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Some synthesis operations may still be running during cleanup")
        
        self.is_initialized = False
        self.piper_executable = None