"""Tests for the Whisper engine module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
import os

from stt_service.whisper_engine import WhisperEngine, WhisperModelManager
from shared.exceptions import ModelInferenceError


class TestWhisperEngine:
    """Test cases for WhisperEngine class."""

    @pytest.mark.unit
    def test_initialization(self):
        """Test Whisper engine initialization parameters."""
        engine = WhisperEngine(
            model_path="base.en",
            device="cpu",
            compute_type="float16",
            num_workers=4
        )
        
        assert engine.model_path == "base.en"
        assert engine.device == "cpu"
        assert engine.compute_type == "float16"
        assert engine.num_workers == 4
        assert engine.is_initialized is False
        assert engine.model is None

    @pytest.mark.unit
    async def test_health_check_uninitialized(self):
        """Test health check with uninitialized engine."""
        engine = WhisperEngine()
        result = await engine.health_check()
        assert result is False

    @pytest.mark.unit
    async def test_health_check_initialized(self):
        """Test health check with initialized engine."""
        engine = WhisperEngine()
        engine.is_initialized = True
        engine.model = MagicMock()
        
        result = await engine.health_check()
        assert result is True

    @pytest.mark.unit
    async def test_initialize_no_backends_available(self):
        """Test initialization when no Whisper backends are available."""
        engine = WhisperEngine()
        
        with patch.object(engine, '_init_whisper_cpp', side_effect=ImportError("No whispercpp")):
            with patch.object(engine, '_init_faster_whisper', side_effect=ImportError("No faster-whisper")):
                with patch.object(engine, '_init_openai_whisper', side_effect=ImportError("No openai-whisper")):
                    
                    with pytest.raises(ModelInferenceError, match="No Whisper backend available"):
                        await engine.initialize()

    @pytest.mark.unit
    async def test_initialize_whisper_cpp_success(self):
        """Test successful initialization with whisper.cpp."""
        engine = WhisperEngine()
        
        with patch.object(engine, '_init_whisper_cpp') as mock_init:
            mock_init.return_value = None
            engine.backend = "whisper-cpp"
            
            await engine.initialize()
            
            assert engine.is_initialized is True
            mock_init.assert_called_once()

    @pytest.mark.unit
    async def test_initialize_faster_whisper_fallback(self):
        """Test fallback to faster-whisper when whisper.cpp fails."""
        engine = WhisperEngine()
        
        with patch.object(engine, '_init_whisper_cpp', side_effect=ImportError("No whispercpp")):
            with patch.object(engine, '_init_faster_whisper') as mock_init:
                mock_init.return_value = None
                engine.backend = "faster-whisper"
                
                await engine.initialize()
                
                assert engine.is_initialized is True
                mock_init.assert_called_once()

    @pytest.mark.unit
    async def test_initialize_openai_whisper_fallback(self):
        """Test fallback to openai-whisper when others fail."""
        engine = WhisperEngine()
        
        with patch.object(engine, '_init_whisper_cpp', side_effect=ImportError()):
            with patch.object(engine, '_init_faster_whisper', side_effect=ImportError()):
                with patch.object(engine, '_init_openai_whisper') as mock_init:
                    mock_init.return_value = None
                    engine.backend = "openai-whisper"
                    
                    await engine.initialize()
                    
                    assert engine.is_initialized is True
                    mock_init.assert_called_once()

    @pytest.mark.unit
    async def test_transcribe_not_initialized(self, sample_audio_data):
        """Test transcription with uninitialized engine."""
        engine = WhisperEngine()
        
        with pytest.raises(ModelInferenceError, match="not initialized"):
            await engine.transcribe(sample_audio_data)

    @pytest.mark.unit 
    async def test_transcribe_chunk_not_initialized(self, sample_audio_data):
        """Test chunk transcription with uninitialized engine."""
        engine = WhisperEngine()
        
        with pytest.raises(ModelInferenceError, match="not initialized"):
            await engine.transcribe_chunk(sample_audio_data)

    @pytest.mark.unit
    async def test_transcribe_chunk_error_handling(self, sample_audio_data):
        """Test chunk transcription error handling."""
        engine = WhisperEngine()
        engine.is_initialized = True
        engine.backend = "faster-whisper"
        
        with patch.object(engine, '_transcribe_audio', side_effect=Exception("Test error")):
            result = await engine.transcribe_chunk(sample_audio_data)
            
            # Should return empty result on error instead of failing
            assert result == {"text": "", "confidence": 0.0}

    @pytest.mark.integration
    async def test_transcribe_faster_whisper_mock(self, sample_audio_data):
        """Test transcription with mocked faster-whisper."""
        engine = WhisperEngine()
        engine.is_initialized = True
        engine.backend = "faster-whisper"
        
        # Mock the transcription result
        expected_result = {
            "text": "Hello world",
            "language": "en", 
            "confidence": 0.95,
            "duration": 1.0,
            "segments": [],
            "words": []
        }
        
        with patch.object(engine, '_transcribe_audio', return_value=expected_result):
            result = await engine.transcribe(sample_audio_data)
            
            assert result == expected_result

    @pytest.mark.unit
    async def test_init_whisper_cpp_model_not_found(self):
        """Test whisper.cpp initialization when model file not found."""
        engine = WhisperEngine(model_path="nonexistent_model")
        
        with patch('whispercpp.Whisper') as mock_whisper_class:
            with patch('os.path.isfile', return_value=False):
                with pytest.raises(ModelInferenceError, match="not found"):
                    await engine._init_whisper_cpp()

    @pytest.mark.unit
    async def test_init_whisper_cpp_model_found(self):
        """Test whisper.cpp initialization with model file found."""
        engine = WhisperEngine(model_path="/app/models/ggml-base.en.bin")
        
        with patch('whispercpp.Whisper') as mock_whisper_class:
            with patch('os.path.isfile', return_value=True):
                mock_model = MagicMock()
                mock_whisper_class.return_value = mock_model
                
                await engine._init_whisper_cpp()
                
                assert engine.model == mock_model
                assert engine.backend == "whisper-cpp"

    @pytest.mark.unit
    async def test_init_faster_whisper(self):
        """Test faster-whisper initialization."""
        engine = WhisperEngine()
        
        with patch('faster_whisper.WhisperModel') as mock_whisper_class:
            mock_model = MagicMock()
            mock_whisper_class.return_value = mock_model
            
            await engine._init_faster_whisper()
            
            assert engine.model == mock_model
            assert engine.backend == "faster-whisper"
            mock_whisper_class.assert_called_once_with(
                engine.model_path,
                device=engine.device,
                compute_type=engine.compute_type,
                num_workers=engine.num_workers
            )

    @pytest.mark.unit
    async def test_init_openai_whisper(self):
        """Test openai-whisper initialization."""
        engine = WhisperEngine()
        
        with patch('whisper.load_model') as mock_load_model:
            with patch('shared.utils.run_in_executor') as mock_executor:
                mock_model = MagicMock()
                mock_executor.return_value = mock_model
                
                await engine._init_openai_whisper()
                
                assert engine.model == mock_model
                assert engine.backend == "openai-whisper"

    @pytest.mark.integration
    async def test_transcribe_faster_whisper_detailed(self, sample_audio_data):
        """Test detailed faster-whisper transcription with mocked components."""
        engine = WhisperEngine()
        engine.is_initialized = True
        engine.backend = "faster-whisper"
        
        # Create mock segments
        mock_segment = MagicMock()
        mock_segment.text = "Hello world"
        mock_segment.start = 0.0
        mock_segment.end = 1.0
        mock_segment.avg_logprob = -0.5
        
        mock_word = MagicMock()
        mock_word.word = "Hello"
        mock_word.start = 0.0
        mock_word.end = 0.5
        mock_word.probability = 0.95
        mock_segment.words = [mock_word]
        
        # Mock transcription info
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.99
        mock_info.duration = 1.0
        
        with patch.object(engine, '_transcribe_faster_whisper') as mock_transcribe:
            expected_result = {
                "text": "Hello world",
                "language": "en",
                "confidence": 0.99,
                "duration": 1.0,
                "segments": [{
                    "text": "Hello world",
                    "start": 0.0,
                    "end": 1.0,
                    "confidence": -0.5
                }],
                "words": [{
                    "word": "Hello",
                    "start": 0.0,
                    "end": 0.5,
                    "confidence": 0.95
                }]
            }
            mock_transcribe.return_value = expected_result
            
            result = await engine.transcribe(
                sample_audio_data,
                return_timestamps=True,
                return_word_level_timestamps=True
            )
            
            assert result == expected_result

    @pytest.mark.unit
    async def test_cleanup(self):
        """Test engine cleanup."""
        engine = WhisperEngine()
        engine.is_initialized = True
        engine.model = MagicMock()
        engine.model.cleanup = MagicMock()
        
        await engine.cleanup()
        
        assert engine.is_initialized is False
        engine.model.cleanup.assert_called_once()

    @pytest.mark.unit
    async def test_cleanup_with_free_method(self):
        """Test cleanup with whisper.cpp free method."""
        engine = WhisperEngine()
        engine.is_initialized = True
        engine.backend = "whisper-cpp"
        engine.model = MagicMock()
        engine.model.free = MagicMock()
        
        await engine.cleanup()
        
        assert engine.is_initialized is False
        engine.model.free.assert_called_once()


class TestWhisperModelManager:
    """Test cases for WhisperModelManager class."""

    @pytest.mark.unit
    def test_initialization(self):
        """Test model manager initialization."""
        manager = WhisperModelManager()
        assert isinstance(manager.models, dict)
        assert len(manager.models) == 0

    @pytest.mark.unit
    async def test_load_model(self):
        """Test loading a model."""
        manager = WhisperModelManager()
        
        with patch('stt_service.whisper_engine.WhisperEngine') as mock_engine_class:
            mock_engine = AsyncMock()
            mock_engine.initialize = AsyncMock()
            mock_engine_class.return_value = mock_engine
            
            result = await manager.load_model(
                "test_model",
                "base.en",
                device="cpu"
            )
            
            assert result == mock_engine
            assert "test_model" in manager.models
            assert manager.models["test_model"] == mock_engine
            mock_engine.initialize.assert_called_once()

    @pytest.mark.unit
    async def test_load_model_already_loaded(self):
        """Test loading an already loaded model."""
        manager = WhisperModelManager()
        existing_engine = MagicMock()
        manager.models["test_model"] = existing_engine
        
        result = await manager.load_model("test_model", "base.en")
        
        assert result == existing_engine

    @pytest.mark.unit
    def test_get_model(self):
        """Test getting a loaded model."""
        manager = WhisperModelManager()
        engine = MagicMock()
        manager.models["test_model"] = engine
        
        result = manager.get_model("test_model")
        assert result == engine
        
        result = manager.get_model("nonexistent")
        assert result is None

    @pytest.mark.unit
    async def test_unload_model(self):
        """Test unloading a model."""
        manager = WhisperModelManager()
        mock_engine = AsyncMock()
        manager.models["test_model"] = mock_engine
        
        await manager.unload_model("test_model")
        
        assert "test_model" not in manager.models
        mock_engine.cleanup.assert_called_once()

    @pytest.mark.unit
    async def test_unload_nonexistent_model(self):
        """Test unloading a model that doesn't exist."""
        manager = WhisperModelManager()
        
        # Should not raise an error
        await manager.unload_model("nonexistent")

    @pytest.mark.unit
    async def test_cleanup_all(self):
        """Test cleaning up all models."""
        manager = WhisperModelManager()
        
        mock_engine1 = AsyncMock()
        mock_engine2 = AsyncMock()
        manager.models["model1"] = mock_engine1
        manager.models["model2"] = mock_engine2
        
        await manager.cleanup_all()
        
        assert len(manager.models) == 0
        mock_engine1.cleanup.assert_called_once()
        mock_engine2.cleanup.assert_called_once()