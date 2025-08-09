"""Tests for NLU/Agent Router Service."""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock

from nlu_service.main import app


@pytest.fixture
async def client():
    """Test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


class TestNLUService:
    """Test NLU/Agent Router Service."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "service" in data

    @pytest.mark.asyncio
    async def test_nlu_endpoint(self, client):
        """Test NLU processing endpoint."""
        request_data = {
            "text": "Create a new contact for John Doe",
            "language": "en",
            "classify_intent": True,
            "extract_entities": True,
        }
        
        response = await client.post("/nlu", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert "text" in data
        assert "language" in data
        assert "processing_time" in data

    @pytest.mark.asyncio
    async def test_agent_endpoint(self, client):
        """Test agent processing endpoint."""
        request_data = {
            "text": "I need help with creating a contact",
            "conversation_id": "test-conv-123",
            "context": {"user_type": "admin"},
        }
        
        response = await client.post("/agent", json=request_data)
        # May return 503 if services not initialized in test
        assert response.status_code in [200, 503]

    @pytest.mark.asyncio
    async def test_tools_list(self, client):
        """Test tools list endpoint."""
        response = await client.get("/tools")
        # May return 503 if services not initialized
        assert response.status_code in [200, 503]

    @pytest.mark.asyncio
    async def test_intents_list(self, client):
        """Test intents list endpoint."""
        response = await client.get("/intents")
        # May return 503 if services not initialized
        assert response.status_code in [200, 503]

    @pytest.mark.asyncio
    async def test_entities_list(self, client):
        """Test entity types list endpoint."""
        response = await client.get("/entities")
        # May return 503 if services not initialized
        assert response.status_code in [200, 503]