"""Audio preprocessing and processing utilities for STT service."""

import io
import tempfile
import wave
from typing import Any, Dict, Optional, Tuple

import structlog
import numpy as np

from shared.exceptions import AudioProcessingError
from shared.utils import run_in_executor, get_audio_info

logger = structlog.get_logger(__name__)


class AudioProcessor:
    """Audio preprocessing and processing utilities."""
    
    def __init__(self, target_sample_rate: int = 16000):
        self.target_sample_rate = target_sample_rate
        self.is_initialized = False
        
        # Try to import audio libraries
        self.librosa_available = False
        self.pydub_available = False
        self.soundfile_available = False
        
        try:
            import librosa
            self.librosa_available = True
            logger.info("librosa available for audio processing")
        except ImportError:
            pass
        
        try:
            from pydub import AudioSegment
            self.pydub_available = True
            logger.info("pydub available for audio processing")
        except ImportError:
            pass
        
        try:
            import soundfile
            self.soundfile_available = True
            logger.info("soundfile available for audio processing")
        except ImportError:
            pass
        
        if not any([self.librosa_available, self.pydub_available, self.soundfile_available]):
            logger.warning("No audio processing libraries available. Limited functionality.")
        
        self.is_initialized = True
    
    async def health_check(self) -> bool:
        """Check if audio processor is healthy."""
        return self.is_initialized
    
    async def preprocess_audio(
        self,
        audio_data: bytes,
        target_format: str = "wav",
        apply_vad: bool = False,
        normalize: bool = True,
        target_sample_rate: Optional[int] = None,
    ) -> bytes:
        """Preprocess audio data for transcription."""
        if not self.is_initialized:
            raise AudioProcessingError("Audio processor not initialized", "initialization")
        
        try:
            logger.debug("Preprocessing audio", 
                        size=len(audio_data), 
                        target_format=target_format,
                        apply_vad=apply_vad)
            
            # Get audio info
            audio_info = get_audio_info(audio_data)
            logger.debug("Audio info", **audio_info)
            
            # Use the most appropriate library for processing
            if self.librosa_available:
                return await self._preprocess_with_librosa(
                    audio_data, target_format, apply_vad, normalize, target_sample_rate
                )
            elif self.pydub_available:
                return await self._preprocess_with_pydub(
                    audio_data, target_format, normalize, target_sample_rate
                )
            elif self.soundfile_available:
                return await self._preprocess_with_soundfile(
                    audio_data, target_format, target_sample_rate
                )
            else:
                # Basic processing without external libraries
                return await self._basic_preprocessing(audio_data, target_format)
                
        except Exception as exc:
            logger.error("Audio preprocessing failed", error=str(exc), exc_info=True)
            raise AudioProcessingError(f"Audio preprocessing failed: {str(exc)}", "preprocessing")
    
    async def _preprocess_with_librosa(
        self,
        audio_data: bytes,
        target_format: str,
        apply_vad: bool,
        normalize: bool,
        target_sample_rate: Optional[int],
    ) -> bytes:
        """Preprocess audio using librosa (most advanced)."""
        
        def _process():
            import librosa
            import soundfile as sf
            
            # Write to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav") as temp_input:
                temp_input.write(audio_data)
                temp_input.flush()
                
                try:
                    # Load audio with librosa
                    audio, sr = librosa.load(
                        temp_input.name,
                        sr=target_sample_rate or self.target_sample_rate,
                        mono=True,
                    )
                    
                    # Apply voice activity detection if requested
                    if apply_vad:
                        audio = self._apply_voice_activity_detection(audio, sr)
                    
                    # Normalize audio if requested
                    if normalize:
                        audio = self._normalize_audio(audio)
                    
                    # Apply noise reduction (basic)
                    audio = self._reduce_noise(audio, sr)
                    
                    # Convert to target format
                    with tempfile.NamedTemporaryFile(suffix=f".{target_format}") as temp_output:
                        sf.write(temp_output.name, audio, sr)
                        temp_output.seek(0)
                        return temp_output.read()
                        
                except Exception as exc:
                    logger.error("librosa processing failed", error=str(exc))
                    # Fall back to returning original data
                    return audio_data
        
        return await run_in_executor(_process)
    
    async def _preprocess_with_pydub(
        self,
        audio_data: bytes,
        target_format: str,
        normalize: bool,
        target_sample_rate: Optional[int],
    ) -> bytes:
        """Preprocess audio using pydub (good compatibility)."""
        
        def _process():
            from pydub import AudioSegment
            
            try:
                # Load audio
                audio = AudioSegment.from_file(io.BytesIO(audio_data))
                
                # Convert to mono
                if audio.channels > 1:
                    audio = audio.set_channels(1)
                
                # Resample if needed
                if target_sample_rate and audio.frame_rate != target_sample_rate:
                    audio = audio.set_frame_rate(target_sample_rate or self.target_sample_rate)
                
                # Normalize volume if requested
                if normalize:
                    audio = audio.normalize()
                
                # Apply basic noise gate (remove very quiet parts)
                audio = audio.strip_silence(silence_thresh=-40, chunk_len=300)
                
                # Export to target format
                output_buffer = io.BytesIO()
                audio.export(output_buffer, format=target_format)
                return output_buffer.getvalue()
                
            except Exception as exc:
                logger.error("pydub processing failed", error=str(exc))
                return audio_data
        
        return await run_in_executor(_process)
    
    async def _preprocess_with_soundfile(
        self,
        audio_data: bytes,
        target_format: str,
        target_sample_rate: Optional[int],
    ) -> bytes:
        """Preprocess audio using soundfile (basic)."""
        
        def _process():
            import soundfile as sf
            
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav") as temp_input:
                    temp_input.write(audio_data)
                    temp_input.flush()
                    
                    # Load audio
                    audio, sr = sf.read(temp_input.name)
                    
                    # Convert to mono if stereo
                    if len(audio.shape) > 1:
                        audio = np.mean(audio, axis=1)
                    
                    # Resample if needed (basic resampling)
                    if target_sample_rate and sr != target_sample_rate:
                        # Simple resampling (not ideal but works)
                        ratio = target_sample_rate / sr
                        new_length = int(len(audio) * ratio)
                        audio = np.interp(
                            np.linspace(0, len(audio), new_length),
                            np.arange(len(audio)),
                            audio
                        )
                        sr = target_sample_rate
                    
                    # Write to output format
                    with tempfile.NamedTemporaryFile(suffix=f".{target_format}") as temp_output:
                        sf.write(temp_output.name, audio, sr)
                        temp_output.seek(0)
                        return temp_output.read()
                        
            except Exception as exc:
                logger.error("soundfile processing failed", error=str(exc))
                return audio_data
        
        return await run_in_executor(_process)
    
    async def _basic_preprocessing(self, audio_data: bytes, target_format: str) -> bytes:
        """Basic preprocessing without external libraries."""
        
        def _process():
            # Very basic processing - mostly just pass through
            # In a real implementation, you might want to at least validate the audio format
            
            # For now, just return the original data
            # This assumes the input is already in a compatible format
            return audio_data
        
        return await run_in_executor(_process)
    
    def _apply_voice_activity_detection(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Apply basic voice activity detection."""
        if not self.librosa_available:
            return audio
        
        import librosa
        
        try:
            # Calculate spectral centroid to detect voice activity
            spectral_centroids = librosa.feature.spectral_centroid(y=audio, sr=sample_rate)[0]
            
            # Calculate frame-wise energy
            frame_length = 2048
            hop_length = 512
            frames = librosa.util.frame(audio, frame_length=frame_length, hop_length=hop_length)
            energy = np.sum(frames ** 2, axis=0)
            
            # Normalize energy
            energy = energy / np.max(energy) if np.max(energy) > 0 else energy
            
            # Create voice activity mask based on energy and spectral centroid
            energy_threshold = 0.01
            spectral_threshold = np.percentile(spectral_centroids, 25)
            
            # Interpolate to match audio length
            voice_mask = np.interp(
                np.arange(len(audio)),
                np.arange(0, len(audio), hop_length),
                (energy > energy_threshold) & (spectral_centroids > spectral_threshold)
            )
            
            # Apply smoothing to avoid abrupt cuts
            from scipy import ndimage
            voice_mask = ndimage.binary_closing(voice_mask, structure=np.ones(int(sample_rate * 0.1)))
            
            return audio * voice_mask
            
        except Exception as exc:
            logger.warning("VAD failed, returning original audio", error=str(exc))
            return audio
    
    def _normalize_audio(self, audio: np.ndarray, target_db: float = -20.0) -> np.ndarray:
        """Normalize audio to target dB level."""
        try:
            # Calculate RMS
            rms = np.sqrt(np.mean(audio ** 2))
            if rms == 0:
                return audio
            
            # Convert target dB to linear scale
            target_rms = 10 ** (target_db / 20.0)
            
            # Apply gain
            gain = target_rms / rms
            normalized = audio * gain
            
            # Prevent clipping
            if np.max(np.abs(normalized)) > 1.0:
                normalized = normalized / np.max(np.abs(normalized))
            
            return normalized
            
        except Exception as exc:
            logger.warning("Normalization failed", error=str(exc))
            return audio
    
    def _reduce_noise(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Apply basic noise reduction."""
        if not self.librosa_available:
            return audio
        
        try:
            import librosa
            from scipy.signal import medfilt
            
            # Apply median filter for impulse noise
            audio_filtered = medfilt(audio, kernel_size=3)
            
            # High-pass filter to remove low-frequency noise
            audio_filtered = librosa.effects.preemphasis(audio_filtered)
            
            return audio_filtered
            
        except Exception as exc:
            logger.warning("Noise reduction failed", error=str(exc))
            return audio
    
    async def extract_audio_features(self, audio_data: bytes) -> Dict[str, Any]:
        """Extract audio features for analysis."""
        if not self.librosa_available:
            return {}
        
        def _extract():
            import librosa
            
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav") as temp_file:
                    temp_file.write(audio_data)
                    temp_file.flush()
                    
                    # Load audio
                    audio, sr = librosa.load(temp_file.name, sr=self.target_sample_rate)
                    
                    # Extract features
                    features = {}
                    
                    # Duration
                    features["duration"] = len(audio) / sr
                    
                    # RMS energy
                    rms = librosa.feature.rms(y=audio)[0]
                    features["rms_mean"] = float(np.mean(rms))
                    features["rms_std"] = float(np.std(rms))
                    
                    # Zero crossing rate
                    zcr = librosa.feature.zero_crossing_rate(audio)[0]
                    features["zcr_mean"] = float(np.mean(zcr))
                    
                    # Spectral features
                    spectral_centroids = librosa.feature.spectral_centroid(y=audio, sr=sr)[0]
                    features["spectral_centroid_mean"] = float(np.mean(spectral_centroids))
                    
                    spectral_rolloff = librosa.feature.spectral_rolloff(y=audio, sr=sr)[0]
                    features["spectral_rolloff_mean"] = float(np.mean(spectral_rolloff))
                    
                    # MFCCs
                    mfccs = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13)
                    features["mfcc_mean"] = [float(np.mean(mfcc)) for mfcc in mfccs]
                    
                    return features
                    
            except Exception as exc:
                logger.error("Feature extraction failed", error=str(exc))
                return {}
        
        return await run_in_executor(_extract)
    
    async def detect_silence_periods(
        self,
        audio_data: bytes,
        silence_threshold: float = 0.01,
        min_silence_duration: float = 0.5,
    ) -> list:
        """Detect silence periods in audio."""
        if not self.librosa_available:
            return []
        
        def _detect():
            import librosa
            
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav") as temp_file:
                    temp_file.write(audio_data)
                    temp_file.flush()
                    
                    # Load audio
                    audio, sr = librosa.load(temp_file.name, sr=self.target_sample_rate)
                    
                    # Calculate frame-wise RMS
                    frame_length = int(sr * 0.025)  # 25ms frames
                    hop_length = int(frame_length / 2)
                    
                    frames = librosa.util.frame(
                        audio, 
                        frame_length=frame_length, 
                        hop_length=hop_length,
                        axis=0
                    )
                    rms = np.sqrt(np.mean(frames ** 2, axis=0))
                    
                    # Find silence periods
                    is_silent = rms < silence_threshold
                    silence_periods = []
                    
                    start_idx = None
                    for i, silent in enumerate(is_silent):
                        if silent and start_idx is None:
                            start_idx = i
                        elif not silent and start_idx is not None:
                            # End of silence period
                            duration = (i - start_idx) * hop_length / sr
                            if duration >= min_silence_duration:
                                start_time = start_idx * hop_length / sr
                                end_time = i * hop_length / sr
                                silence_periods.append((start_time, end_time))
                            start_idx = None
                    
                    return silence_periods
                    
            except Exception as exc:
                logger.error("Silence detection failed", error=str(exc))
                return []
        
        return await run_in_executor(_detect)
    
    async def get_audio_quality_metrics(self, audio_data: bytes) -> Dict[str, Any]:
        """Get audio quality metrics for monitoring."""
        try:
            if not self.librosa_available:
                return {"error": "librosa not available for quality metrics"}
            
            def _get_metrics():
                import librosa
                
                with tempfile.NamedTemporaryFile(suffix=".wav") as temp_file:
                    temp_file.write(audio_data)
                    temp_file.flush()
                    
                    # Load audio
                    audio, sr = librosa.load(temp_file.name, sr=None)
                    
                    # Calculate quality metrics
                    metrics = {}
                    
                    # Signal-to-noise ratio estimate
                    energy = np.mean(audio ** 2)
                    noise_floor = np.percentile(np.abs(audio), 10)
                    snr_estimate = 10 * np.log10(energy / (noise_floor ** 2 + 1e-10))
                    metrics["snr_estimate_db"] = float(snr_estimate)
                    
                    # Dynamic range
                    dynamic_range = 20 * np.log10(np.max(np.abs(audio)) / (np.mean(np.abs(audio)) + 1e-10))
                    metrics["dynamic_range_db"] = float(dynamic_range)
                    
                    # Zero crossing rate (indicator of signal clarity)
                    zcr = librosa.feature.zero_crossing_rate(audio)[0]
                    metrics["avg_zero_crossing_rate"] = float(np.mean(zcr))
                    
                    # Spectral centroid (brightness indicator)
                    spectral_centroid = librosa.feature.spectral_centroid(y=audio, sr=sr)[0]
                    metrics["avg_spectral_centroid"] = float(np.mean(spectral_centroid))
                    
                    # RMS energy levels
                    rms = librosa.feature.rms(y=audio)[0]
                    metrics["avg_rms"] = float(np.mean(rms))
                    metrics["rms_std"] = float(np.std(rms))
                    
                    # Clipping detection
                    max_val = np.max(np.abs(audio))
                    clipping_ratio = np.sum(np.abs(audio) > 0.95 * max_val) / len(audio)
                    metrics["clipping_ratio"] = float(clipping_ratio)
                    
                    return metrics
            
            return await run_in_executor(_get_metrics)
            
        except Exception as exc:
            logger.error(f"Quality metrics calculation failed: {exc}")
            return {"error": str(exc)}

    async def validate_audio_file(self, audio_data: bytes) -> Dict[str, Any]:
        """Validate audio file format and properties."""
        try:
            # Basic validation
            if len(audio_data) == 0:
                return {
                    "is_valid": False,
                    "errors": ["Empty audio data"],
                    "file_size": 0,
                }
            
            # Get basic audio info
            audio_info = get_audio_info(audio_data)
            
            validation_result = {
                "is_valid": True,
                "errors": [],
                "warnings": [],
                "file_size": len(audio_data),
                "detected_format": audio_info.get("format", "unknown"),
                "properties": {},
            }
            
            # Check file size limits
            max_size = 50 * 1024 * 1024  # 50MB limit
            if len(audio_data) > max_size:
                validation_result["is_valid"] = False
                validation_result["errors"].append(f"File too large: {len(audio_data)} bytes (max: {max_size})")
            
            # Try to get detailed properties if librosa is available
            if self.librosa_available:
                try:
                    def _get_properties():
                        import librosa
                        import tempfile
                        
                        with tempfile.NamedTemporaryFile(suffix=".wav") as temp_file:
                            temp_file.write(audio_data)
                            temp_file.flush()
                            
                            try:
                                # Load with librosa to get properties
                                audio, sr = librosa.load(temp_file.name, sr=None)
                                
                                return {
                                    "duration": len(audio) / sr if sr > 0 else 0,
                                    "sample_rate": sr,
                                    "channels": 1 if len(audio.shape) == 1 else audio.shape[1],
                                    "samples": len(audio),
                                    "bit_depth": "32-bit float (librosa)",
                                    "is_mono": len(audio.shape) == 1,
                                }
                                
                            except Exception as e:
                                logger.warning(f"Could not analyze audio with librosa: {e}")
                                return {"error": str(e)}
                    
                    properties = await run_in_executor(_get_properties)
                    if "error" not in properties:
                        validation_result["properties"] = properties
                        
                        # Validation checks
                        duration = properties.get("duration", 0)
                        if duration > 600:  # 10 minutes
                            validation_result["warnings"].append(f"Very long audio: {duration:.1f}s")
                        elif duration < 0.1:  # 100ms
                            validation_result["warnings"].append(f"Very short audio: {duration:.1f}s")
                        
                        sample_rate = properties.get("sample_rate", 0)
                        if sample_rate < 8000:
                            validation_result["warnings"].append(f"Low sample rate: {sample_rate}Hz")
                        elif sample_rate > 48000:
                            validation_result["warnings"].append(f"High sample rate: {sample_rate}Hz")
                    
                except Exception as e:
                    validation_result["warnings"].append(f"Could not analyze audio properties: {e}")
            
            # Check if format is supported
            supported_formats = ["wav", "mp3", "m4a", "flac", "ogg"]
            detected_format = validation_result["detected_format"]
            if detected_format != "unknown" and detected_format not in supported_formats:
                validation_result["warnings"].append(f"Format '{detected_format}' may not be fully supported")
            
            return validation_result
            
        except Exception as exc:
            logger.error("Audio validation failed", error=str(exc), exc_info=True)
            return {
                "is_valid": False,
                "errors": [f"Validation error: {str(exc)}"],
                "file_size": len(audio_data) if audio_data else 0,
            }

    async def convert_audio_format(
        self,
        audio_data: bytes,
        source_format: str = "auto",
        target_format: str = "wav",
        target_sample_rate: Optional[int] = None,
        target_channels: int = 1,
    ) -> bytes:
        """Convert audio from one format to another."""
        if not self.is_initialized:
            raise AudioProcessingError("Audio processor not initialized", "initialization")
        
        try:
            logger.debug("Converting audio format", 
                        source=source_format, 
                        target=target_format,
                        target_sr=target_sample_rate)
            
            # If formats are the same and no other changes needed, return as-is
            if (source_format == target_format and 
                target_sample_rate is None and 
                target_channels == 1):
                return audio_data
            
            # Use the best available library for conversion
            if self.librosa_available and self.soundfile_available:
                return await self._convert_with_librosa_soundfile(
                    audio_data, target_format, target_sample_rate, target_channels
                )
            elif self.pydub_available:
                return await self._convert_with_pydub(
                    audio_data, source_format, target_format, target_sample_rate, target_channels
                )
            elif self.soundfile_available:
                return await self._convert_with_soundfile_only(
                    audio_data, target_format, target_sample_rate, target_channels
                )
            else:
                # Basic conversion - just return the data (limited functionality)
                logger.warning("No audio conversion libraries available, returning original data")
                return audio_data
                
        except Exception as exc:
            logger.error("Audio format conversion failed", error=str(exc), exc_info=True)
            raise AudioProcessingError(f"Format conversion failed: {str(exc)}", "conversion")

    async def _convert_with_librosa_soundfile(
        self,
        audio_data: bytes,
        target_format: str,
        target_sample_rate: Optional[int],
        target_channels: int,
    ) -> bytes:
        """Convert audio using librosa + soundfile (best quality)."""
        
        def _convert():
            import librosa
            import soundfile as sf
            import tempfile
            
            with tempfile.NamedTemporaryFile(suffix=".wav") as temp_input:
                temp_input.write(audio_data)
                temp_input.flush()
                
                # Load with librosa
                audio, sr = librosa.load(
                    temp_input.name,
                    sr=target_sample_rate,
                    mono=(target_channels == 1),
                )
                
                # Ensure proper shape for channels
                if target_channels == 1 and len(audio.shape) > 1:
                    audio = np.mean(audio, axis=1)
                elif target_channels == 2 and len(audio.shape) == 1:
                    audio = np.stack([audio, audio], axis=1)
                
                # Write to target format
                with tempfile.NamedTemporaryFile(suffix=f".{target_format}") as temp_output:
                    sf.write(
                        temp_output.name, 
                        audio, 
                        target_sample_rate or sr,
                        format=target_format.upper()
                    )
                    temp_output.seek(0)
                    return temp_output.read()
        
        return await run_in_executor(_convert)

    async def _convert_with_pydub(
        self,
        audio_data: bytes,
        source_format: str,
        target_format: str,
        target_sample_rate: Optional[int],
        target_channels: int,
    ) -> bytes:
        """Convert audio using pydub."""
        
        def _convert():
            from pydub import AudioSegment
            import io
            
            # Load audio
            if source_format == "auto":
                audio = AudioSegment.from_file(io.BytesIO(audio_data))
            else:
                audio = AudioSegment.from_file(io.BytesIO(audio_data), format=source_format)
            
            # Apply transformations
            if target_channels == 1 and audio.channels > 1:
                audio = audio.set_channels(1)
            elif target_channels == 2 and audio.channels == 1:
                audio = audio.set_channels(2)
            
            if target_sample_rate and audio.frame_rate != target_sample_rate:
                audio = audio.set_frame_rate(target_sample_rate)
            
            # Export to target format
            output_buffer = io.BytesIO()
            audio.export(output_buffer, format=target_format)
            return output_buffer.getvalue()
        
        return await run_in_executor(_convert)

    async def _convert_with_soundfile_only(
        self,
        audio_data: bytes,
        target_format: str,
        target_sample_rate: Optional[int],
        target_channels: int,
    ) -> bytes:
        """Convert audio using soundfile only (limited functionality)."""
        
        def _convert():
            import soundfile as sf
            import tempfile
            
            with tempfile.NamedTemporaryFile(suffix=".wav") as temp_input:
                temp_input.write(audio_data)
                temp_input.flush()
                
                # Load audio
                audio, sr = sf.read(temp_input.name)
                
                # Handle channels
                if target_channels == 1 and len(audio.shape) > 1:
                    audio = np.mean(audio, axis=1)
                elif target_channels == 2 and len(audio.shape) == 1:
                    audio = np.stack([audio, audio], axis=1)
                
                # Simple resampling if needed (not ideal but functional)
                if target_sample_rate and sr != target_sample_rate:
                    ratio = target_sample_rate / sr
                    new_length = int(len(audio) * ratio)
                    if len(audio.shape) == 1:
                        audio = np.interp(
                            np.linspace(0, len(audio), new_length),
                            np.arange(len(audio)),
                            audio
                        )
                    else:
                        # Handle multi-channel
                        new_audio = np.zeros((new_length, audio.shape[1]))
                        for ch in range(audio.shape[1]):
                            new_audio[:, ch] = np.interp(
                                np.linspace(0, len(audio), new_length),
                                np.arange(len(audio)),
                                audio[:, ch]
                            )
                        audio = new_audio
                    sr = target_sample_rate
                
                # Write to target format
                with tempfile.NamedTemporaryFile(suffix=f".{target_format}") as temp_output:
                    sf.write(temp_output.name, audio, sr, format=target_format.upper())
                    temp_output.seek(0)
                    return temp_output.read()
        
        return await run_in_executor(_convert)

    async def optimize_for_transcription(self, audio_data: bytes) -> bytes:
        """Optimize audio specifically for speech transcription."""
        try:
            logger.debug("Optimizing audio for transcription", size=len(audio_data))
            
            # Use preprocessing with transcription-specific settings
            optimized_audio = await self.preprocess_audio(
                audio_data,
                target_format="wav",
                apply_vad=True,  # Remove silence for better transcription
                normalize=True,  # Normalize for consistent levels
                target_sample_rate=16000,  # Whisper's preferred sample rate
            )
            
            # Additional transcription-specific processing if librosa is available
            if self.librosa_available:
                optimized_audio = await self._apply_transcription_optimizations(optimized_audio)
            
            return optimized_audio
            
        except Exception as exc:
            logger.error("Audio transcription optimization failed", error=str(exc))
            # Return original data if optimization fails
            return audio_data

    async def _apply_transcription_optimizations(self, audio_data: bytes) -> bytes:
        """Apply additional optimizations specific to transcription."""
        
        def _optimize():
            import librosa
            import soundfile as sf
            import tempfile
            from scipy.signal import wiener
            
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav") as temp_input:
                    temp_input.write(audio_data)
                    temp_input.flush()
                    
                    # Load audio
                    audio, sr = librosa.load(temp_input.name, sr=16000, mono=True)
                    
                    # Apply transcription-specific optimizations
                    
                    # 1. High-pass filter to remove low-frequency noise
                    audio = librosa.effects.preemphasis(audio, coef=0.97)
                    
                    # 2. Spectral gating for noise reduction
                    # Estimate noise floor from quietest parts
                    audio_sorted = np.sort(np.abs(audio))
                    noise_floor = np.mean(audio_sorted[:len(audio_sorted)//10])
                    
                    # Apply spectral gating
                    if noise_floor > 0:
                        # Simple noise gate
                        gate_threshold = noise_floor * 3
                        audio = np.where(np.abs(audio) > gate_threshold, audio, audio * 0.1)
                    
                    # 3. Dynamic range compression for consistent levels
                    # Simple compressor
                    threshold = 0.5
                    ratio = 4.0
                    over_threshold = np.abs(audio) > threshold
                    audio[over_threshold] = np.sign(audio[over_threshold]) * (
                        threshold + (np.abs(audio[over_threshold]) - threshold) / ratio
                    )
                    
                    # 4. Apply Wiener filter for additional noise reduction
                    try:
                        # Only apply if audio has sufficient length
                        if len(audio) > 1024:
                            audio = wiener(audio, noise=noise_floor**2)
                    except Exception as e:
                        logger.debug(f"Wiener filter failed: {e}")
                    
                    # 5. Ensure proper amplitude range
                    max_amplitude = np.max(np.abs(audio))
                    if max_amplitude > 0:
                        # Normalize to -3dB to prevent clipping while maintaining headroom
                        target_peak = 0.707  # -3dB
                        audio = audio * (target_peak / max_amplitude)
                    
                    # 6. Apply final high-pass to remove any DC offset
                    from scipy.signal import butter, filtfilt
                    
                    # High-pass filter at 80Hz to remove rumble
                    nyquist = sr / 2
                    low_cutoff = 80 / nyquist
                    if low_cutoff < 1.0:
                        b, a = butter(2, low_cutoff, btype='high')
                        audio = filtfilt(b, a, audio)
                    
                    # Write optimized audio
                    with tempfile.NamedTemporaryFile(suffix=".wav") as temp_output:
                        sf.write(temp_output.name, audio, sr)
                        temp_output.seek(0)
                        return temp_output.read()
                        
            except Exception as exc:
                logger.error("Transcription optimization failed", error=str(exc))
                # Return original audio if optimization fails
                return audio_data
        
        return await run_in_executor(_optimize)