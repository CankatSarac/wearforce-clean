"""Shared test configuration and fixtures."""

import asyncio
import pytest
import os
from typing import AsyncGenerator

# Set test environment variables
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "true"
os.environ["DB_HOST"] = "localhost"
os.environ["REDIS_HOST"] = "localhost"
os.environ["QDRANT_HOST"] = "localhost"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def mock_redis():
    """Mock Redis client."""
    from unittest.mock import AsyncMock
    redis = AsyncMock()
    redis.get.return_value = None
    redis.set.return_value = True
    redis.delete.return_value = 1
    redis.ping.return_value = True
    redis.health_check.return_value = True
    return redis


@pytest.fixture
async def mock_vector_db():
    """Mock vector database."""
    from unittest.mock import AsyncMock
    db = AsyncMock()
    db.search.return_value = []
    db.upsert_vectors.return_value = None
    db.health_check.return_value = True
    return db