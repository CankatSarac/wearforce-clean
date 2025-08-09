"""Pytest configuration and fixtures for STT service tests."""

import asyncio
import os
import tempfile
import wave
from pathlib import Path
from typing import AsyncGenerator, Dict, Generator
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from fastapi.testclient import TestClient

# Import service components
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from shared.config import STTServiceConfig
from stt_service.audio_processor import AudioProcessor
from stt_service.whisper_engine import WhisperEngine


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_config() -> STTServiceConfig:
    """Test configuration."""
    return STTServiceConfig(
        name="test-stt-service",
        port=8001,
        debug=True,
        whisper_model_size="tiny.en",
        max_audio_size=5 * 1024 * 1024,  # 5MB for testing
    )


@pytest.fixture
def sample_audio_data() -> bytes:
    """Generate sample WAV audio data for testing."""
    # Generate 1 second of 16kHz mono audio (sine wave at 440Hz)
    sample_rate = 16000
    duration = 1.0
    frequency = 440.0
    
    # Generate samples
    samples = np.sin(2 * np.pi * frequency * np.linspace(0, duration, int(sample_rate * duration)))
    samples = (samples * 32767).astype(np.int16)
    
    # Create WAV file in memory
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        with wave.open(tmp_file.name, 'wb') as wav_file:
            wav_file.setnchannels(1)  # mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(samples.tobytes())
        
        # Read the file back
        with open(tmp_file.name, 'rb') as f:
            audio_data = f.read()
        
        # Clean up
        os.unlink(tmp_file.name)
        
        return audio_data


@pytest.fixture
def invalid_audio_data() -> bytes:
    """Generate invalid audio data for testing."""
    return b"This is not audio data"


@pytest.fixture
def large_audio_data() -> bytes:
    """Generate large audio data for testing size limits."""
    # Create a large WAV file (>5MB)
    sample_rate = 16000
    duration = 60.0  # 60 seconds
    frequency = 440.0
    
    samples = np.sin(2 * np.pi * frequency * np.linspace(0, duration, int(sample_rate * duration)))
    samples = (samples * 32767).astype(np.int16)
    
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        with wave.open(tmp_file.name, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(samples.tobytes())
        
        with open(tmp_file.name, 'rb') as f:
            audio_data = f.read()
        
        os.unlink(tmp_file.name)
        return audio_data


@pytest.fixture
def mock_whisper_engine() -> AsyncMock:
    """Mock Whisper engine for testing."""
    engine = AsyncMock(spec=WhisperEngine)
    engine.is_initialized = True
    engine.backend = "mock"
    
    # Mock transcription results
    engine.transcribe.return_value = {
        "text": "Hello, this is a test transcription.",
        "language": "en",
        "confidence": 0.95,
        "duration": 1.0,
        "segments": [
            {
                "text": "Hello, this is a test transcription.",
                "start": 0.0,
                "end": 1.0,
                "confidence": 0.95,
            }
        ],
        "words": [
            {"word": "Hello", "start": 0.0, "end": 0.2, "confidence": 0.98},
            {"word": "this", "start": 0.2, "end": 0.4, "confidence": 0.96},
            {"word": "is", "start": 0.4, "end": 0.5, "confidence": 0.94},
            {"word": "a", "start": 0.5, "end": 0.6, "confidence": 0.92},
            {"word": "test", "start": 0.6, "end": 0.8, "confidence": 0.97},
            {"word": "transcription", "start": 0.8, "end": 1.0, "confidence": 0.99},
        ],
    }
    
    engine.transcribe_chunk.return_value = {
        "text": "Hello",
        "confidence": 0.95,
    }
    
    engine.health_check.return_value = True
    engine.cleanup = AsyncMock()
    
    return engine


@pytest.fixture
def mock_audio_processor() -> AsyncMock:
    """Mock Audio processor for testing."""
    processor = AsyncMock(spec=AudioProcessor)
    processor.is_initialized = True
    
    # Mock preprocessing results
    async def mock_preprocess(audio_data, **kwargs):
        return audio_data  # Return input data unchanged for simplicity
    
    processor.preprocess_audio.side_effect = mock_preprocess
    processor.validate_audio_file.return_value = {
        "is_valid": True,
        "errors": [],
        "warnings": [],
        "file_size": 1000,
        "detected_format": "wav",
        "properties": {
            "duration": 1.0,
            "sample_rate": 16000,
            "channels": 1,
        },
    }
    
    processor.convert_audio_format.side_effect = mock_preprocess
    processor.optimize_for_transcription.side_effect = mock_preprocess
    processor.get_audio_quality_metrics.return_value = {
        "snr_estimate_db": 20.0,
        "dynamic_range_db": 10.0,
        "avg_rms": 0.1,
        "clipping_ratio": 0.0,
    }
    
    processor.health_check.return_value = True
    
    return processor


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Mock Redis client for testing."""
    redis_mock = AsyncMock()
    redis_mock.ping.return_value = True
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.exists.return_value = False
    redis_mock.health_check.return_value = True
    redis_mock.initialize = AsyncMock()
    redis_mock.close = AsyncMock()
    return redis_mock


@pytest.fixture
def test_client(mock_whisper_engine, mock_audio_processor, mock_redis) -> Generator[TestClient, None, None]:
    """FastAPI test client with mocked dependencies."""
    # Mock the global dependencies
    import stt_service.main as main_module
    
    # Store original values
    original_whisper = main_module.whisper_engine
    original_processor = main_module.audio_processor
    original_redis = main_module.redis_client
    
    # Replace with mocks
    main_module.whisper_engine = mock_whisper_engine
    main_module.audio_processor = mock_audio_processor  
    main_module.redis_client = mock_redis
    
    # Import app after mocking dependencies
    from stt_service.main import app
    
    with TestClient(app) as client:
        yield client
    
    # Restore original values
    main_module.whisper_engine = original_whisper
    main_module.audio_processor = original_processor
    main_module.redis_client = original_redis


@pytest.fixture
def audio_formats() -> Dict[str, bytes]:
    """Sample audio data in different formats."""
    # This would ideally contain actual audio samples in different formats
    # For testing, we'll simulate different format headers
    return {
        "wav": b"RIFF\x00\x00\x00\x00WAVE",  # WAV header
        "mp3": b"\xff\xfb\x90\x00",  # MP3 header
        "flac": b"fLaC\x00\x00\x00\x22",  # FLAC header
        "ogg": b"OggS\x00\x02\x00\x00",  # OGG header
    }


@pytest.fixture
async def real_audio_processor() -> AsyncGenerator[AudioProcessor, None]:
    """Real audio processor instance for integration tests."""
    processor = AudioProcessor()
    yield processor


@pytest.fixture
def mock_grpc_server() -> MagicMock:
    """Mock gRPC server for testing."""
    server_mock = MagicMock()
    server_mock.start = AsyncMock()
    server_mock.stop = AsyncMock()
    server_mock.wait_for_termination = AsyncMock()
    return server_mock


# Test utilities
def create_test_wav_file(duration: float = 1.0, sample_rate: int = 16000, frequency: float = 440.0) -> bytes:
    """Create a test WAV file with specified parameters."""
    samples = np.sin(2 * np.pi * frequency * np.linspace(0, duration, int(sample_rate * duration)))
    samples = (samples * 32767).astype(np.int16)
    
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        with wave.open(tmp_file.name, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2) 
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(samples.tobytes())
        
        with open(tmp_file.name, 'rb') as f:
            audio_data = f.read()
        
        os.unlink(tmp_file.name)
        return audio_data


# Markers for different test categories
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.slow = pytest.mark.slow
pytest.mark.gpu = pytest.mark.gpu
pytest.mark.cpu = pytest.mark.cpu