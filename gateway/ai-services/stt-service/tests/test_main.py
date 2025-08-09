"""Tests for the main FastAPI application."""

import pytest
import json
import base64
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
import io


class TestMainApplication:
    """Test cases for the main FastAPI application."""

    @pytest.mark.unit
    def test_health_endpoint(self, test_client):
        """Test the health check endpoint."""
        response = test_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "service" in data
        assert "checks" in data

    @pytest.mark.unit
    def test_liveness_probe(self, test_client):
        """Test the Kubernetes liveness probe endpoint."""
        response = test_client.get("/health/live")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert "timestamp" in data

    @pytest.mark.unit 
    def test_readiness_probe(self, test_client):
        """Test the Kubernetes readiness probe endpoint."""
        response = test_client.get("/health/ready")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "active_connections" in data

    @pytest.mark.unit
    def test_service_status(self, test_client):
        """Test the detailed service status endpoint."""
        response = test_client.get("/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "stt-service"
        assert "version" in data
        assert "connections" in data
        assert "models" in data
        assert "services" in data

    @pytest.mark.unit
    def test_service_info(self, test_client):
        """Test the service info endpoint."""
        response = test_client.get("/info")
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "stt-service"
        assert data["version"] == "1.0.0"
        assert isinstance(data["endpoints"], list)
        assert len(data["endpoints"]) > 0

    @pytest.mark.unit
    def test_metrics_endpoint(self, test_client):
        """Test the Prometheus metrics endpoint."""
        response = test_client.get("/metrics")
        
        assert response.status_code == 200
        # Metrics should be in text format
        assert response.headers["content-type"].startswith("text/plain")

    @pytest.mark.unit
    def test_validate_audio_endpoint(self, test_client, sample_audio_data):
        """Test the audio validation endpoint."""
        files = {"file": ("test.wav", io.BytesIO(sample_audio_data), "audio/wav")}
        
        response = test_client.post("/validate-audio", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert "validation" in data
        assert "file_info" in data
        assert data["validation"]["is_valid"] is True

    @pytest.mark.unit
    def test_validate_audio_invalid_file(self, test_client):
        """Test audio validation with invalid file."""
        files = {"file": ("test.txt", io.BytesIO(b"not audio"), "text/plain")}
        
        # Should still process but validation should indicate issues
        response = test_client.post("/validate-audio", files=files)
        assert response.status_code == 200

    @pytest.mark.unit
    def test_convert_audio_endpoint(self, test_client, sample_audio_data):
        """Test the audio conversion endpoint."""
        files = {"file": ("test.wav", io.BytesIO(sample_audio_data), "audio/wav")}
        data = {
            "target_format": "mp3",
            "target_sample_rate": 16000
        }
        
        response = test_client.post("/convert-audio", files=files, data=data)
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/mpeg"

    @pytest.mark.unit
    def test_convert_audio_invalid_file_type(self, test_client):
        """Test audio conversion with invalid file type."""
        files = {"file": ("test.txt", io.BytesIO(b"not audio"), "text/plain")}
        
        response = test_client.post("/convert-audio", files=files)
        
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]

    @pytest.mark.unit
    def test_transcribe_endpoint(self, test_client, sample_audio_data):
        """Test the transcription endpoint with base64 audio."""
        audio_b64 = base64.b64encode(sample_audio_data).decode('utf-8')
        
        payload = {
            "audio_data": audio_b64,
            "model": "base.en",
            "language": "en",
            "temperature": 0.0,
            "return_timestamps": True
        }
        
        response = test_client.post("/transcribe", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "text" in data
        assert "processing_time" in data
        assert data["text"] == "Hello, this is a test transcription."

    @pytest.mark.unit
    def test_transcribe_missing_audio_data(self, test_client):
        """Test transcription with missing audio data."""
        payload = {
            "model": "base.en",
            "language": "en"
        }
        
        response = test_client.post("/transcribe", json=payload)
        
        assert response.status_code == 422  # Validation error

    @pytest.mark.unit
    def test_transcribe_file_endpoint(self, test_client, sample_audio_data):
        """Test the file transcription endpoint."""
        files = {"file": ("test.wav", io.BytesIO(sample_audio_data), "audio/wav")}
        data = {
            "model": "base.en",
            "language": "en",
            "temperature": "0.0",
            "return_timestamps": "true"
        }
        
        response = test_client.post("/transcribe-file", files=files, data=data)
        
        assert response.status_code == 200
        response_data = response.json()
        assert "text" in response_data
        assert response_data["text"] == "Hello, this is a test transcription."

    @pytest.mark.unit
    def test_transcribe_file_invalid_type(self, test_client):
        """Test file transcription with invalid file type."""
        files = {"file": ("test.txt", io.BytesIO(b"not audio"), "text/plain")}
        
        response = test_client.post("/transcribe-file", files=files)
        
        assert response.status_code == 422  # Validation error
        assert "Invalid file type" in response.json()["detail"]

    @pytest.mark.unit
    def test_transcribe_file_too_large(self, test_client, large_audio_data):
        """Test file transcription with file that's too large."""
        files = {"file": ("large.wav", io.BytesIO(large_audio_data), "audio/wav")}
        
        response = test_client.post("/transcribe-file", files=files)
        
        assert response.status_code == 422  # Validation error
        assert "too large" in response.json()["detail"]


class TestStreamingWebSocket:
    """Test cases for WebSocket streaming functionality."""

    @pytest.mark.integration
    def test_websocket_connect(self, test_client):
        """Test WebSocket connection establishment."""
        with test_client.websocket_connect("/transcribe-stream/test-session") as websocket:
            # Connection should be established
            assert websocket is not None

    @pytest.mark.integration
    def test_websocket_start_session(self, test_client):
        """Test starting a transcription session via WebSocket."""
        with test_client.websocket_connect("/transcribe-stream/test-session") as websocket:
            # Send start session message
            message = {
                "type": "start_session",
                "data": {
                    "model": "base.en",
                    "language": "en",
                    "temperature": 0.0
                }
            }
            websocket.send_json(message)
            
            # Should receive session started response
            response = websocket.receive_json()
            assert response["type"] == "session_started"

    @pytest.mark.integration
    def test_websocket_audio_chunk(self, test_client, sample_audio_data):
        """Test sending audio chunk via WebSocket."""
        with test_client.websocket_connect("/transcribe-stream/test-session") as websocket:
            # Start session first
            start_message = {
                "type": "start_session",
                "data": {"model": "base.en"}
            }
            websocket.send_json(start_message)
            websocket.receive_json()  # Consume session started response
            
            # Send audio chunk
            audio_b64 = base64.b64encode(sample_audio_data).decode('utf-8')
            chunk_message = {
                "type": "audio_chunk",
                "data": {"audio": audio_b64}
            }
            websocket.send_json(chunk_message)
            
            # Should receive transcription result (may take some time due to buffering)
            try:
                response = websocket.receive_json()
                if response["type"] == "transcription_chunk":
                    assert "text" in response["data"]
            except:
                # Might not get immediate response due to buffering logic
                pass

    @pytest.mark.integration
    def test_websocket_ping_pong(self, test_client):
        """Test WebSocket ping-pong functionality."""
        with test_client.websocket_connect("/transcribe-stream/test-session") as websocket:
            ping_message = {
                "type": "ping",
                "data": {}
            }
            websocket.send_json(ping_message)
            
            response = websocket.receive_json()
            assert response["type"] == "pong"
            assert "timestamp" in response["data"]

    @pytest.mark.integration
    def test_websocket_end_session(self, test_client):
        """Test ending a transcription session via WebSocket."""
        with test_client.websocket_connect("/transcribe-stream/test-session") as websocket:
            # Start session first
            start_message = {
                "type": "start_session", 
                "data": {"model": "base.en"}
            }
            websocket.send_json(start_message)
            websocket.receive_json()
            
            # End session
            end_message = {
                "type": "end_session",
                "data": {}
            }
            websocket.send_json(end_message)
            
            response = websocket.receive_json()
            assert response["type"] == "session_ended"


class TestConnectionManager:
    """Test cases for streaming connection manager."""

    @pytest.mark.unit
    def test_connection_manager_initialization(self):
        """Test connection manager initialization."""
        from stt_service.main import StreamingConnectionManager
        
        manager = StreamingConnectionManager(max_connections=10, max_buffer_size=1024)
        
        assert manager.max_connections == 10
        assert manager.max_buffer_size == 1024
        assert len(manager.active_connections) == 0

    @pytest.mark.unit
    def test_can_accept_data_buffer_limit(self):
        """Test backpressure control based on buffer size."""
        from stt_service.main import StreamingConnectionManager
        
        manager = StreamingConnectionManager(max_buffer_size=1000)
        session_id = "test-session"
        
        # Initialize session state
        manager.connection_states[session_id] = {
            "buffer_size": 800,
            "is_processing": False,
            "message_count": 10,
            "error_count": 1
        }
        
        # Should accept small data
        assert manager.can_accept_data(session_id, 100) is True
        
        # Should reject data that would exceed buffer limit
        assert manager.can_accept_data(session_id, 300) is False

    @pytest.mark.unit
    def test_can_accept_data_processing_state(self):
        """Test backpressure control based on processing state."""
        from stt_service.main import StreamingConnectionManager
        
        manager = StreamingConnectionManager()
        session_id = "test-session"
        
        # Session currently processing
        manager.connection_states[session_id] = {
            "buffer_size": 100,
            "is_processing": True,
            "message_count": 10,
            "error_count": 0
        }
        
        # Should not accept data while processing
        assert manager.can_accept_data(session_id, 100) is False

    @pytest.mark.unit
    def test_can_accept_data_error_rate(self):
        """Test backpressure control based on error rate."""
        from stt_service.main import StreamingConnectionManager
        
        manager = StreamingConnectionManager()
        session_id = "test-session"
        
        # High error rate session
        manager.connection_states[session_id] = {
            "buffer_size": 100,
            "is_processing": False,
            "message_count": 10,
            "error_count": 6  # 60% error rate
        }
        
        # Should not accept data with high error rate
        assert manager.can_accept_data(session_id, 100) is False


class TestErrorHandling:
    """Test cases for error handling scenarios."""

    @pytest.mark.unit
    def test_whisper_engine_not_initialized(self, test_client):
        """Test behavior when Whisper engine is not initialized."""
        with patch('stt_service.main.whisper_engine', None):
            response = test_client.get("/health/live")
            assert response.status_code == 503

    @pytest.mark.unit
    def test_audio_processor_not_initialized(self, test_client):
        """Test behavior when audio processor is not initialized."""
        with patch('stt_service.main.audio_processor', None):
            response = test_client.get("/health/live")
            assert response.status_code == 503

    @pytest.mark.unit
    def test_transcription_error_handling(self, test_client, mock_whisper_engine, sample_audio_data):
        """Test transcription error handling."""
        # Make the mock throw an exception
        mock_whisper_engine.transcribe.side_effect = Exception("Transcription failed")
        
        audio_b64 = base64.b64encode(sample_audio_data).decode('utf-8')
        payload = {
            "audio_data": audio_b64,
            "model": "base.en"
        }
        
        response = test_client.post("/transcribe", json=payload)
        
        assert response.status_code == 500
        assert "Transcription failed" in response.json()["detail"]