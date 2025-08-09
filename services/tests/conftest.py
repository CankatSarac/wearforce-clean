"""
Pytest configuration and shared fixtures.
"""

import asyncio
import pytest
import pytest_asyncio
from datetime import datetime, date
from decimal import Decimal
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from shared.database import Database
from shared.config import get_settings

# Import all models to ensure they're registered
from crm.models import *  # noqa
from erp.models import *  # noqa
from notification.models import *  # noqa


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_database() -> AsyncGenerator[Database, None]:
    """Create a test database instance."""
    # Use SQLite in-memory database for tests
    database_url = "sqlite+aiosqlite:///:memory:"
    
    # Create test engine with special configuration for SQLite
    engine = create_async_engine(
        database_url,
        poolclass=StaticPool,
        connect_args={
            "check_same_thread": False,
        },
        echo=False
    )
    
    database = Database()
    database.engine = engine
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(database.metadata.create_all)
    
    yield database
    
    # Cleanup
    await database.close()


@pytest.fixture
async def db_session(test_database: Database) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for testing."""
    async with test_database.session() as session:
        # Start a transaction
        await session.begin()
        
        yield session
        
        # Rollback the transaction to keep tests isolated
        await session.rollback()


@pytest.fixture
def mock_current_time():
    """Mock current time for testing."""
    return datetime(2024, 1, 15, 10, 30, 0)


@pytest.fixture
def mock_current_date():
    """Mock current date for testing."""
    return date(2024, 1, 15)


# Import test factories
from .factories.crm_factories import *  # noqa
from .factories.erp_factories import *  # noqa
from .factories.notification_factories import *  # noqa