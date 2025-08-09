"""
Test utilities and helpers.
"""

import asyncio
import json
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest
from faker import Faker
from sqlalchemy.ext.asyncio import AsyncSession

fake = Faker()


class TestHelpers:
    """Collection of test helper methods."""
    
    @staticmethod
    def mock_datetime(year: int = 2024, month: int = 1, day: int = 15) -> datetime:
        """Create a mock datetime for consistent testing."""
        return datetime(year, month, day, 10, 30, 0)
    
    @staticmethod
    def mock_date(year: int = 2024, month: int = 1, day: int = 15) -> date:
        """Create a mock date for consistent testing."""
        return date(year, month, day)
    
    @staticmethod
    def create_mock_session() -> AsyncMock:
        """Create a mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        session.exec = AsyncMock()
        session.close = AsyncMock()
        return session
    
    @staticmethod
    def assert_decimal_equal(actual: Decimal, expected: Decimal, places: int = 2):
        """Assert decimal values are equal to specified decimal places."""
        assert round(actual, places) == round(expected, places)
    
    @staticmethod
    def assert_datetime_close(actual: datetime, expected: datetime, seconds: int = 5):
        """Assert datetimes are close within specified seconds."""
        diff = abs((actual - expected).total_seconds())
        assert diff <= seconds, f"Datetimes differ by {diff} seconds"
    
    @staticmethod
    def create_json_response(data: Any) -> str:
        """Create JSON response string with proper serialization."""
        def json_serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, date):
                return obj.isoformat()
            elif isinstance(obj, Decimal):
                return float(obj)
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        
        return json.dumps(data, default=json_serializer)


class AsyncMockMixin:
    """Mixin for creating async mocks."""
    
    @staticmethod
    def create_async_mock_response(data: Any, status_code: int = 200):
        """Create async mock response."""
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value=data)
        mock_response.status_code = status_code
        mock_response.text = TestHelpers.create_json_response(data)
        return mock_response


class DatabaseTestMixin:
    """Mixin for database testing utilities."""
    
    @staticmethod
    async def create_test_data(session: AsyncSession, factories: List[Any], count: int = 5):
        """Create test data using factories."""
        instances = []
        for factory in factories:
            for _ in range(count):
                instance = factory()
                session.add(instance)
                instances.append(instance)
        
        await session.commit()
        
        # Refresh instances
        for instance in instances:
            await session.refresh(instance)
        
        return instances
    
    @staticmethod
    async def cleanup_test_data(session: AsyncSession, instances: List[Any]):
        """Clean up test data."""
        for instance in instances:
            await session.delete(instance)
        await session.commit()


class FixtureHelpers:
    """Helpers for creating test fixtures."""
    
    @staticmethod
    def create_account_data(**overrides) -> Dict[str, Any]:
        """Create account test data."""
        data = {
            "name": fake.company(),
            "account_type": "customer",
            "industry": "Technology",
            "website": fake.url(),
            "phone": fake.phone_number(),
            "email": fake.company_email(),
            "annual_revenue": float(fake.pyfloat(left_digits=6, right_digits=2, positive=True)),
            "employee_count": fake.random_int(min=10, max=1000),
            "billing_address": fake.address(),
            "shipping_address": fake.address()
        }
        data.update(overrides)
        return data
    
    @staticmethod
    def create_contact_data(account_id: int = None, **overrides) -> Dict[str, Any]:
        """Create contact test data."""
        data = {
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "email": fake.email(),
            "phone": fake.phone_number(),
            "job_title": fake.job(),
            "department": fake.random_element(elements=["Sales", "Marketing", "Engineering"])
        }
        if account_id:
            data["account_id"] = account_id
        data.update(overrides)
        return data
    
    @staticmethod
    def create_deal_data(account_id: int = None, contact_id: int = None, **overrides) -> Dict[str, Any]:
        """Create deal test data."""
        data = {
            "title": fake.catch_phrase(),
            "amount": float(fake.pyfloat(left_digits=5, right_digits=2, positive=True)),
            "stage": "qualification",
            "probability": fake.random_int(min=10, max=90),
            "close_date": fake.date_between(start_date='today', end_date='+365d').isoformat(),
            "description": fake.text(max_nb_chars=200)
        }
        if account_id:
            data["account_id"] = account_id
        if contact_id:
            data["contact_id"] = contact_id
        data.update(overrides)
        return data
    
    @staticmethod
    def create_product_data(**overrides) -> Dict[str, Any]:
        """Create product test data."""
        data = {
            "name": fake.catch_phrase(),
            "sku": fake.bothify(text='PROD-####-??').upper(),
            "product_type": "simple",
            "status": "active",
            "cost_price": float(fake.pyfloat(left_digits=3, right_digits=2, positive=True)),
            "selling_price": float(fake.pyfloat(left_digits=3, right_digits=2, positive=True)),
            "track_inventory": True,
            "minimum_stock_level": fake.random_int(min=10, max=100),
            "category": fake.random_element(elements=["Apparel", "Electronics", "Books"]),
            "brand": fake.company(),
            "description": fake.text(max_nb_chars=200)
        }
        data.update(overrides)
        return data
    
    @staticmethod
    def create_warehouse_data(**overrides) -> Dict[str, Any]:
        """Create warehouse test data."""
        data = {
            "name": f"{fake.city()} Warehouse",
            "code": fake.bothify(text='WH-####').upper(),
            "city": fake.city(),
            "state": fake.state_abbr(),
            "country": fake.country_code(),
            "is_default": False
        }
        data.update(overrides)
        return data
    
    @staticmethod
    def create_notification_template_data(**overrides) -> Dict[str, Any]:
        """Create notification template test data."""
        data = {
            "name": fake.catch_phrase(),
            "template_type": "email",
            "subject": fake.sentence(nb_words=6),
            "content": fake.text(max_nb_chars=300),
            "description": fake.text(max_nb_chars=100),
            "language": "en",
            "variables": {"name": "Recipient name", "company": "Company name"}
        }
        data.update(overrides)
        return data


# Pytest plugins and custom markers
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "external: mark test as requiring external services")
    config.addinivalue_line("markers", "smoke: mark test as smoke test")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on file location."""
    for item in items:
        # Add unit marker to tests in unit/ directory
        if "unit/" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        
        # Add integration marker to tests in integration/ directory
        elif "integration/" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        
        # Mark slow tests
        if "slow" in item.name.lower():
            item.add_marker(pytest.mark.slow)


# Custom assertions
def assert_response_structure(response_data: Dict[str, Any], expected_keys: List[str]):
    """Assert that response has expected structure."""
    assert isinstance(response_data, dict), "Response should be a dictionary"
    
    for key in expected_keys:
        assert key in response_data, f"Response should contain key: {key}"


def assert_pagination_structure(response_data: Dict[str, Any]):
    """Assert that response has proper pagination structure."""
    expected_keys = ["items", "total", "page", "page_size", "has_next", "has_previous"]
    assert_response_structure(response_data, expected_keys)
    
    assert isinstance(response_data["items"], list), "Items should be a list"
    assert isinstance(response_data["total"], int), "Total should be an integer"
    assert response_data["total"] >= 0, "Total should be non-negative"


def assert_error_response(response_data: Dict[str, Any], expected_error_type: str = None):
    """Assert that response is a proper error response."""
    expected_keys = ["detail"]
    assert_response_structure(response_data, expected_keys)
    
    if expected_error_type:
        assert expected_error_type.lower() in response_data["detail"].lower()


# Performance testing utilities
class PerformanceTimer:
    """Context manager for performance testing."""
    
    def __init__(self, max_duration_seconds: float = 1.0):
        self.max_duration = max_duration_seconds
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = asyncio.get_event_loop().time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = asyncio.get_event_loop().time()
        duration = self.end_time - self.start_time
        assert duration <= self.max_duration, \
            f"Operation took {duration:.3f}s, expected <= {self.max_duration}s"
    
    @property
    def duration(self) -> float:
        """Get the measured duration."""
        if self.start_time is None or self.end_time is None:
            return 0.0
        return self.end_time - self.start_time


# Mock data generators
class MockDataGenerator:
    """Generate mock data for various testing scenarios."""
    
    @staticmethod
    def generate_account_list(count: int = 5) -> List[Dict[str, Any]]:
        """Generate list of account data."""
        return [FixtureHelpers.create_account_data() for _ in range(count)]
    
    @staticmethod
    def generate_contact_list(account_ids: List[int], count: int = 5) -> List[Dict[str, Any]]:
        """Generate list of contact data with account relationships."""
        contacts = []
        for i in range(count):
            account_id = fake.random_element(elements=account_ids)
            contacts.append(FixtureHelpers.create_contact_data(account_id=account_id))
        return contacts
    
    @staticmethod
    def generate_paginated_response(items: List[Any], page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """Generate paginated response structure."""
        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        
        return {
            "items": items[start:end],
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": end < total,
            "has_previous": page > 1
        }