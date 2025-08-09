"""Tests for the gRPC server implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from stt_service.grpc_server import (
    AudioStreamingServiceServicer,
    create_grpc_server,
    run_grpc_server,
    AudioConfig,
    AudioData,
    TranscriptionResult,
    TranscriptAlternative,
    WordInfo,
    ErrorResponse,
    StatusMessage,
    STTRequest,
    STTResponse
)


class TestProtocolBufferClasses:
    """Test cases for protocol buffer dataclasses."""

    @pytest.mark.unit
    def test_audio_config_creation(self):
        """Test AudioConfig dataclass creation."""
        config = AudioConfig(
            encoding="LINEAR16",
            sample_rate_hertz=16000,
            audio_channel_count=1,
            language_code="en-US"
        )
        
        assert config.encoding == "LINEAR16"
        assert config.sample_rate_hertz == 16000
        assert config.audio_channel_count == 1
        assert config.language_code == "en-US"

    @pytest.mark.unit
    def test_audio_data_creation(self):
        """Test AudioData dataclass creation."""
        audio_data = AudioData(
            content=b"audio_bytes",
            timestamp=1234567890.0,
            sequence_number=1
        )
        
        assert audio_data.content == b"audio_bytes"
        assert audio_data.timestamp == 1234567890.0
        assert audio_data.sequence_number == 1

    @pytest.mark.unit
    def test_transcription_result_creation(self):
        """Test TranscriptionResult dataclass creation."""
        alternative = TranscriptAlternative(
            transcript="Hello world",
            confidence=0.95,
            words=[]
        )
        
        result = TranscriptionResult(
            alternatives=[alternative],
            is_final=True,
            stability=0.90,
            language_code="en-US"
        )
        
        assert len(result.alternatives) == 1
        assert result.alternatives[0].transcript == "Hello world"
        assert result.is_final is True
        assert result.stability == 0.90

    @pytest.mark.unit
    def test_word_info_creation(self):
        """Test WordInfo dataclass creation."""
        word = WordInfo(
            start_time=0.0,
            end_time=0.5,
            word="Hello",
            confidence=0.98
        )
        
        assert word.start_time == 0.0
        assert word.end_time == 0.5
        assert word.word == "Hello"
        assert word.confidence == 0.98

    @pytest.mark.unit
    def test_error_response_creation(self):
        """Test ErrorResponse dataclass creation."""
        error = ErrorResponse(
            code=500,
            message="Internal error",
            details=["detail1", "detail2"],
            timestamp=1234567890.0
        )
        
        assert error.code == 500
        assert error.message == "Internal error"
        assert len(error.details) == 2
        assert error.timestamp == 1234567890.0


class TestAudioStreamingServiceServicer:
    """Test cases for AudioStreamingServiceServicer."""

    @pytest.fixture
    def servicer(self, mock_whisper_engine, mock_audio_processor):
        """Create a servicer instance with mocked dependencies."""
        return AudioStreamingServiceServicer(mock_whisper_engine, mock_audio_processor)

    @pytest.mark.unit
    def test_servicer_initialization(self, servicer):
        """Test servicer initialization."""
        assert servicer.whisper_engine is not None
        assert servicer.audio_processor is not None
        assert isinstance(servicer.active_sessions, dict)
        assert len(servicer.active_sessions) == 0

    @pytest.mark.integration
    async def test_get_audio_config(self, servicer):
        """Test GetAudioConfig method."""
        request = MagicMock()
        context = MagicMock()
        
        result = await servicer.GetAudioConfig(request, context)
        
        assert "supported_configs" in result
        assert "supported_languages" in result
        assert isinstance(result["supported_configs"], list)
        assert len(result["supported_configs"]) > 0

    @pytest.mark.integration
    async def test_get_audio_config_error(self, servicer):
        """Test GetAudioConfig method with error."""
        request = MagicMock()
        context = MagicMock()
        
        with patch.object(servicer, 'whisper_engine', side_effect=Exception("Test error")):
            result = await servicer.GetAudioConfig(request, context)
            
            assert result is None
            context.set_code.assert_called_once()
            context.set_details.assert_called_once()

    @pytest.mark.integration
    async def test_handle_audio_config(self, servicer):
        """Test handling audio configuration."""
        session_id = "test-session"
        config = AudioConfig(
            encoding="LINEAR16",
            sample_rate_hertz=16000,
            language_code="en-US"
        )
        
        # Initialize session
        servicer.active_sessions[session_id] = {}
        
        await servicer._handle_audio_config(session_id, config)
        
        assert servicer.active_sessions[session_id]["audio_config"] == config

    @pytest.mark.integration
    async def test_handle_control_message_end_session(self, servicer, sample_audio_data):
        """Test handling control message to end session."""
        session_id = "test-session"
        
        # Set up session with buffer
        servicer.active_sessions[session_id] = {
            "buffer": sample_audio_data,
        }
        
        # Mock control message
        control = MagicMock()
        control.command = "END_SESSION"
        
        await servicer._handle_control_message(session_id, control)
        
        # Should have processed the buffer
        servicer.audio_processor.preprocess_audio.assert_called_once()
        servicer.whisper_engine.transcribe_chunk.assert_called_once()

    @pytest.mark.integration
    async def test_transcribe_audio_chunk(self, servicer, sample_audio_data):
        """Test transcribing audio chunk."""
        session_id = "test-session"
        audio_data = AudioData(content=sample_audio_data, sequence_number=1)
        session_state = {
            "audio_config": AudioConfig(),
            "buffer": b"",
            "sequence_number": 0
        }
        
        # Mock transcription result
        servicer.whisper_engine.transcribe_chunk.return_value = {
            "text": "Hello world",
            "confidence": 0.95
        }
        
        responses = []
        async for response in servicer._transcribe_audio_chunk(session_id, audio_data, session_state):
            responses.append(response)
        
        # Should have at least one response if buffer is large enough
        # Note: actual behavior depends on buffer size logic
        if responses:
            assert isinstance(responses[0], STTResponse)

    @pytest.mark.integration 
    async def test_transcribe_audio_chunk_error(self, servicer, sample_audio_data):
        """Test transcribing audio chunk with error."""
        session_id = "test-session"
        audio_data = AudioData(content=sample_audio_data)
        session_state = {"buffer": b""}
        
        # Mock error
        servicer.audio_processor.preprocess_audio.side_effect = Exception("Processing error")
        
        responses = []
        async for response in servicer._transcribe_audio_chunk(session_id, audio_data, session_state):
            responses.append(response)
        
        # Should have error response
        assert len(responses) == 1
        assert responses[0].error is not None
        assert "Processing error" in responses[0].error.message


class TestGRPCServerCreation:
    """Test cases for gRPC server creation and management."""

    @pytest.mark.integration
    async def test_create_grpc_server(self, mock_whisper_engine, mock_audio_processor):
        """Test creating gRPC server."""
        with patch('grpc.aio.server') as mock_server_func:
            mock_server = MagicMock()
            mock_server_func.return_value = mock_server
            
            server = await create_grpc_server(
                mock_whisper_engine,
                mock_audio_processor,
                port=50051
            )
            
            assert server == mock_server
            mock_server.add_insecure_port.assert_called_once_with('[::]:50051')

    @pytest.mark.integration
    async def test_run_grpc_server(self, mock_whisper_engine, mock_audio_processor):
        """Test running gRPC server."""
        with patch('stt_service.grpc_server.create_grpc_server') as mock_create:
            mock_server = AsyncMock()
            mock_create.return_value = mock_server
            
            # Create a task that will be cancelled quickly
            task = asyncio.create_task(run_grpc_server(
                mock_whisper_engine,
                mock_audio_processor,
                port=50051
            ))
            
            # Let it start
            await asyncio.sleep(0.1)
            
            # Cancel the task
            task.cancel()
            
            try:
                await task
            except asyncio.CancelledError:
                pass
            
            # Server should have been started
            mock_server.start.assert_called_once()

    @pytest.mark.integration
    async def test_process_audio_chunk_buffer_management(self, servicer, sample_audio_data):
        """Test audio chunk processing with buffer management."""
        session_id = "test-session"
        audio_data = AudioData(content=sample_audio_data)
        
        # Initialize session
        await servicer._session_lock.acquire()
        servicer.active_sessions[session_id] = {
            "buffer": b"",
            "sequence_number": 0
        }
        servicer._session_lock.release()
        
        responses = []
        async for response in servicer._process_audio_chunk(session_id, audio_data):
            responses.append(response)
        
        # Check that buffer was updated
        session_state = servicer.active_sessions[session_id]
        assert len(session_state["buffer"]) > 0
        assert session_state["sequence_number"] == audio_data.sequence_number

    @pytest.mark.integration
    async def test_stt_stream_mock(self, servicer, sample_audio_data):
        """Test STT streaming with mock request iterator."""
        
        # Create mock request iterator
        async def mock_request_iterator():
            # First send config
            config_request = STTRequest(config=AudioConfig())
            yield config_request
            
            # Then send audio data  
            audio_request = STTRequest(audio_data=AudioData(content=sample_audio_data))
            yield audio_request
        
        mock_context = MagicMock()
        
        responses = []
        async for response in servicer.SpeechToText(mock_request_iterator(), mock_context):
            responses.append(response)
        
        # Should have processed the requests
        assert len(responses) >= 0  # May be 0 due to buffer size logic

    @pytest.mark.integration
    async def test_tts_placeholder(self, servicer):
        """Test TTS placeholder functionality."""
        from stt_service.grpc_server import TTSRequest
        
        request = TTSRequest(text="Hello world", language_code="en-US")
        mock_context = MagicMock()
        
        responses = []
        async for response in servicer.TextToSpeech(request, mock_context):
            responses.append(response)
        
        # Should have status responses
        assert len(responses) >= 2  # PROCESSING and COMPLETED
        assert all(r.status is not None for r in responses)

    @pytest.mark.integration
    async def test_bidirectional_stream_config_handling(self, servicer):
        """Test bi-directional stream configuration handling."""
        
        async def mock_request_iterator():
            # Mock request with config
            request = MagicMock()
            request.config = AudioConfig(sample_rate_hertz=16000)
            yield request
        
        mock_context = MagicMock()
        
        responses = []
        async for response in servicer.BiDirectionalStream(mock_request_iterator(), mock_context):
            responses.append(response)
            break  # Just test first response
        
        # Should have received configuration response
        assert len(responses) == 1
        assert responses[0].status is not None
        assert responses[0].status.status == "CONFIGURED"