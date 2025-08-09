"""Tests for the audio processor module."""

import pytest
from unittest.mock import patch, MagicMock
import numpy as np
import tempfile
import os

from stt_service.audio_processor import AudioProcessor
from shared.exceptions import AudioProcessingError


class TestAudioProcessor:
    """Test cases for AudioProcessor class."""

    @pytest.mark.unit
    def test_initialization(self):
        """Test audio processor initialization."""
        processor = AudioProcessor(target_sample_rate=16000)
        assert processor.target_sample_rate == 16000
        assert processor.is_initialized is True

    @pytest.mark.unit
    async def test_health_check(self):
        """Test health check functionality."""
        processor = AudioProcessor()
        result = await processor.health_check()
        assert result is True

        # Test with uninitialized processor
        processor.is_initialized = False
        result = await processor.health_check()
        assert result is False

    @pytest.mark.unit 
    async def test_validate_audio_file_empty_data(self):
        """Test validation with empty audio data."""
        processor = AudioProcessor()
        result = await processor.validate_audio_file(b"")
        
        assert result["is_valid"] is False
        assert "Empty audio data" in result["errors"]
        assert result["file_size"] == 0

    @pytest.mark.unit
    async def test_validate_audio_file_valid_wav(self, sample_audio_data):
        """Test validation with valid WAV audio data."""
        processor = AudioProcessor()
        result = await processor.validate_audio_file(sample_audio_data)
        
        assert result["is_valid"] is True
        assert result["errors"] == []
        assert result["file_size"] == len(sample_audio_data)
        assert result["detected_format"] == "wav"

    @pytest.mark.unit
    async def test_validate_audio_file_large_file(self, large_audio_data):
        """Test validation with file exceeding size limit."""
        processor = AudioProcessor()
        result = await processor.validate_audio_file(large_audio_data)
        
        # Should fail due to size limit (50MB default)
        assert result["is_valid"] is False
        assert any("too large" in error for error in result["errors"])

    @pytest.mark.unit
    async def test_convert_audio_format_same_format(self, sample_audio_data):
        """Test audio conversion with same source and target format."""
        processor = AudioProcessor()
        
        result = await processor.convert_audio_format(
            sample_audio_data,
            source_format="wav",
            target_format="wav",
            target_sample_rate=None
        )
        
        # Should return original data when no conversion needed
        assert result == sample_audio_data

    @pytest.mark.unit
    async def test_convert_audio_format_uninitialized(self, sample_audio_data):
        """Test audio conversion with uninitialized processor."""
        processor = AudioProcessor()
        processor.is_initialized = False
        
        with pytest.raises(AudioProcessingError, match="not initialized"):
            await processor.convert_audio_format(sample_audio_data)

    @pytest.mark.integration
    async def test_preprocess_audio_basic(self, sample_audio_data):
        """Test basic audio preprocessing."""
        processor = AudioProcessor()
        
        result = await processor.preprocess_audio(
            sample_audio_data,
            target_format="wav",
            apply_vad=False,
            normalize=False
        )
        
        assert isinstance(result, bytes)
        assert len(result) > 0

    @pytest.mark.integration
    async def test_preprocess_audio_with_librosa(self, sample_audio_data):
        """Test audio preprocessing with librosa available."""
        processor = AudioProcessor()
        processor.librosa_available = True
        
        with patch('librosa.load') as mock_load:
            mock_load.return_value = (np.random.random(16000), 16000)
            
            with patch('soundfile.write') as mock_write:
                mock_write.return_value = None
                
                with patch('tempfile.NamedTemporaryFile') as mock_temp:
                    mock_temp.return_value.__enter__.return_value.name = "/tmp/test.wav"
                    mock_temp.return_value.__enter__.return_value.read.return_value = sample_audio_data
                    
                    result = await processor.preprocess_audio(
                        sample_audio_data,
                        apply_vad=True,
                        normalize=True
                    )
                    
                    assert isinstance(result, bytes)

    @pytest.mark.integration  
    async def test_preprocess_audio_with_pydub(self, sample_audio_data):
        """Test audio preprocessing with pydub available."""
        processor = AudioProcessor()
        processor.librosa_available = False
        processor.pydub_available = True
        
        with patch('pydub.AudioSegment.from_file') as mock_from_file:
            mock_segment = MagicMock()
            mock_segment.channels = 1
            mock_segment.frame_rate = 16000
            mock_segment.set_channels.return_value = mock_segment
            mock_segment.set_frame_rate.return_value = mock_segment
            mock_segment.normalize.return_value = mock_segment
            mock_segment.strip_silence.return_value = mock_segment
            mock_segment.export.return_value = None
            mock_from_file.return_value = mock_segment
            
            with patch('io.BytesIO') as mock_bytesio:
                mock_bytesio.return_value.getvalue.return_value = sample_audio_data
                
                result = await processor.preprocess_audio(
                    sample_audio_data,
                    normalize=True
                )
                
                assert isinstance(result, bytes)

    @pytest.mark.unit
    async def test_optimize_for_transcription(self, sample_audio_data):
        """Test audio optimization for transcription."""
        processor = AudioProcessor()
        
        result = await processor.optimize_for_transcription(sample_audio_data)
        
        assert isinstance(result, bytes)
        assert len(result) > 0

    @pytest.mark.unit
    async def test_optimize_for_transcription_error_fallback(self, sample_audio_data):
        """Test transcription optimization error fallback."""
        processor = AudioProcessor()
        
        with patch.object(processor, 'preprocess_audio', side_effect=Exception("Test error")):
            result = await processor.optimize_for_transcription(sample_audio_data)
            
            # Should return original data on error
            assert result == sample_audio_data

    @pytest.mark.integration
    async def test_extract_audio_features_no_librosa(self, sample_audio_data):
        """Test audio feature extraction without librosa."""
        processor = AudioProcessor()
        processor.librosa_available = False
        
        result = await processor.extract_audio_features(sample_audio_data)
        
        assert result == {}

    @pytest.mark.integration
    async def test_detect_silence_periods_no_librosa(self, sample_audio_data):
        """Test silence detection without librosa."""
        processor = AudioProcessor()
        processor.librosa_available = False
        
        result = await processor.detect_silence_periods(sample_audio_data)
        
        assert result == []

    @pytest.mark.integration
    async def test_get_audio_quality_metrics_no_librosa(self, sample_audio_data):
        """Test quality metrics without librosa."""
        processor = AudioProcessor()
        processor.librosa_available = False
        
        result = await processor.get_audio_quality_metrics(sample_audio_data)
        
        assert "error" in result
        assert "librosa not available" in result["error"]

    @pytest.mark.unit
    def test_normalize_audio(self):
        """Test audio normalization utility function."""
        processor = AudioProcessor()
        
        # Test with normal audio
        audio = np.array([0.1, 0.2, 0.3, 0.4])
        result = processor._normalize_audio(audio)
        
        assert isinstance(result, np.ndarray)
        assert len(result) == len(audio)
        
        # Test with silent audio
        silent_audio = np.zeros(1000)
        result = processor._normalize_audio(silent_audio)
        
        assert np.array_equal(result, silent_audio)

    @pytest.mark.unit
    def test_reduce_noise_no_librosa(self):
        """Test noise reduction without librosa."""
        processor = AudioProcessor()
        processor.librosa_available = False
        
        audio = np.random.random(1000)
        result = processor._reduce_noise(audio, 16000)
        
        # Should return original audio if librosa not available
        assert np.array_equal(result, audio)

    @pytest.mark.integration
    async def test_convert_with_pydub_format_conversion(self, sample_audio_data):
        """Test format conversion using pydub."""
        processor = AudioProcessor()
        
        with patch('pydub.AudioSegment.from_file') as mock_from_file:
            mock_segment = MagicMock()
            mock_segment.channels = 2  # stereo input
            mock_segment.frame_rate = 44100
            mock_segment.set_channels.return_value = mock_segment
            mock_segment.set_frame_rate.return_value = mock_segment
            mock_segment.export.return_value = None
            mock_from_file.return_value = mock_segment
            
            with patch('io.BytesIO') as mock_bytesio:
                mock_bytesio.return_value.getvalue.return_value = b"converted_audio"
                
                result = await processor._convert_with_pydub(
                    sample_audio_data,
                    source_format="wav",
                    target_format="mp3", 
                    target_sample_rate=16000,
                    target_channels=1
                )
                
                assert result == b"converted_audio"
                mock_segment.set_channels.assert_called_once_with(1)
                mock_segment.set_frame_rate.assert_called_once_with(16000)

    @pytest.mark.unit
    def test_apply_voice_activity_detection_no_librosa(self):
        """Test VAD without librosa available."""
        processor = AudioProcessor()
        processor.librosa_available = False
        
        audio = np.random.random(1000)
        result = processor._apply_voice_activity_detection(audio, 16000)
        
        # Should return original audio
        assert np.array_equal(result, audio)

    @pytest.mark.integration
    async def test_basic_preprocessing_fallback(self, sample_audio_data):
        """Test basic preprocessing fallback when no libraries available."""
        processor = AudioProcessor()
        processor.librosa_available = False
        processor.pydub_available = False
        processor.soundfile_available = False
        
        result = await processor.preprocess_audio(sample_audio_data)
        
        # Should return original data with basic preprocessing
        assert result == sample_audio_data