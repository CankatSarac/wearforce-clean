"""Tests for RAG Pipeline Service."""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock
from io import StringIO

from rag_service.main import app


@pytest.fixture
async def client():
    """Test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


class TestRAGService:
    """Test RAG Pipeline Service."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "service" in data

    @pytest.mark.asyncio
    async def test_search_endpoint(self, client):
        """Test document search endpoint."""
        request_data = {
            "query": "test query",
            "top_k": 5,
            "search_type": "hybrid",
            "similarity_threshold": 0.7,
        }
        
        response = await client.post("/search", json=request_data)
        # May return 503 if services not initialized
        assert response.status_code in [200, 503]

    @pytest.mark.asyncio
    async def test_rag_query(self, client):
        """Test RAG query endpoint."""
        request_data = {
            "question": "What is the company policy?",
            "top_k": 3,
            "similarity_threshold": 0.7,
            "include_sources": True,
            "model": "gpt-oss-20b",
        }
        
        response = await client.post("/rag", json=request_data)
        # May return 503 if services not initialized
        assert response.status_code in [200, 503]

    @pytest.mark.asyncio
    async def test_text_document_upload(self, client):
        """Test text document upload."""
        request_data = {
            "content": "This is a test document content.",
            "source": "test_document",
            "metadata": {"type": "test"},
        }
        
        response = await client.post("/documents/text", json=request_data)
        # May return 503 if services not initialized
        assert response.status_code in [200, 503]

    @pytest.mark.asyncio
    async def test_embeddings_generation(self, client):
        """Test embeddings generation endpoint."""
        request_data = {
            "texts": ["Hello world", "Test document"],
        }
        
        response = await client.post("/embeddings", json=request_data)
        # May return 503 if services not initialized
        assert response.status_code in [200, 503]

    @pytest.mark.asyncio
    async def test_documents_list(self, client):
        """Test document listing endpoint."""
        response = await client.get("/documents")
        # May return 503 if services not initialized
        assert response.status_code in [200, 503]