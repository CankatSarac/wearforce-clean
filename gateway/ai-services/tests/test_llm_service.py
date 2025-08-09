"""Tests for LLM Inference Service."""

import asyncio
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock

from llm_service.main import app
from shared.models import ChatRequest, ChatMessage, MessageRole


@pytest.fixture
def mock_engine_manager():
    """Mock LLM engine manager."""
    manager = AsyncMock()
    manager.list_models.return_value = ["gpt-oss-20b", "gpt-oss-120b"]
    manager.generate.return_value = {
        "text": "This is a test response",
        "finish_reason": "stop",
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "generation_time": 0.5,
    }
    return manager


@pytest.fixture
async def client():
    """Test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


class TestLLMService:
    """Test LLM Inference Service."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "service" in data

    @pytest.mark.asyncio
    async def test_list_models(self, client, mock_engine_manager):
        """Test list models endpoint."""
        # Mock the global engine manager
        from llm_service import main
        main.engine_manager = mock_engine_manager
        
        response = await client.get("/models")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert isinstance(data["models"], list)

    @pytest.mark.asyncio
    async def test_chat_completion(self, client, mock_engine_manager):
        """Test chat completion endpoint."""
        from llm_service import main
        main.engine_manager = mock_engine_manager
        
        request_data = {
            "model": "gpt-oss-20b",
            "messages": [
                {"role": "user", "content": "Hello, how are you?"}
            ],
            "temperature": 0.7,
            "max_tokens": 100,
        }
        
        response = await client.post("/v1/chat/completions", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert "choices" in data
        assert "usage" in data
        assert len(data["choices"]) > 0

    @pytest.mark.asyncio
    async def test_chat_completion_validation(self, client):
        """Test chat completion input validation."""
        # Empty messages
        request_data = {
            "model": "gpt-oss-20b",
            "messages": [],
        }
        
        response = await client.post("/v1/chat/completions", json=request_data)
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_completions_endpoint(self, client, mock_engine_manager):
        """Test text completions endpoint."""
        from llm_service import main
        main.engine_manager = mock_engine_manager
        
        request_data = {
            "model": "gpt-oss-20b",
            "prompt": "Complete this sentence:",
            "max_tokens": 50,
            "temperature": 0.7,
        }
        
        response = await client.post("/v1/completions", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0

    @pytest.mark.asyncio
    async def test_batch_endpoint(self, client):
        """Test batch processing endpoint."""
        requests = [
            {"prompt": "Hello", "model": "gpt-oss-20b"},
            {"prompt": "World", "model": "gpt-oss-20b"},
        ]
        
        response = await client.post("/batch", json=requests)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "status" in data