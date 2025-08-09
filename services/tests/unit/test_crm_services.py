"""
Unit tests for CRM services.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from decimal import Decimal
from datetime import date

from crm.services import AccountService, ContactService, DealService, ActivityService
from crm.models import AccountCreate, ContactCreate, DealCreate, ActivityCreate
from shared.exceptions import NotFoundException, AlreadyExistsException


class TestAccountService:
    """Test AccountService."""

    @pytest.fixture
    async def account_service(self, db_session):
        """Create AccountService instance."""
        return AccountService(db_session)

    @pytest.mark.asyncio
    async def test_create_account_success(self, account_service, account_factory):
        """Test successful account creation."""
        account_data = AccountCreate(
            name="Test Company",
            account_type="customer",
            industry="Technology",
            email="test@testcompany.com"
        )
        
        # Mock repository method
        account_service.account_repo.create_account = AsyncMock(return_value=account_factory())
        account_service.account_repo.get_by_name = AsyncMock(return_value=None)
        
        result = await account_service.create_account(account_data)
        
        assert result is not None
        account_service.account_repo.create_account.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_account_duplicate_name(self, account_service, account_factory):
        """Test creating account with duplicate name."""
        account_data = AccountCreate(
            name="Test Company",
            account_type="customer"
        )
        
        # Mock existing account
        account_service.account_repo.get_by_name = AsyncMock(return_value=account_factory())
        
        with pytest.raises(AlreadyExistsException):
            await account_service.create_account(account_data)

    @pytest.mark.asyncio
    async def test_get_account_not_found(self, account_service):
        """Test getting non-existent account."""
        account_service.account_repo.get = AsyncMock(return_value=None)
        
        with pytest.raises(NotFoundException):
            await account_service.get_account(999)

    @pytest.mark.asyncio
    async def test_update_account_success(self, account_service, account_factory):
        """Test successful account update."""
        account = account_factory()
        account_data = AccountCreate(name="Updated Company")
        
        account_service.account_repo.update_account = AsyncMock(return_value=account)
        
        result = await account_service.update_account(1, account_data)
        
        assert result is not None
        account_service.account_repo.update_account.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_account_success(self, account_service):
        """Test successful account deletion."""
        account_service.account_repo.delete = AsyncMock(return_value=True)
        
        result = await account_service.delete_account(1)
        
        assert result is True
        account_service.account_repo.delete.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_search_accounts(self, account_service, account_factory):
        """Test account search functionality."""
        accounts = [account_factory() for _ in range(3)]
        
        account_service.account_repo.search_accounts = AsyncMock(return_value=(accounts, 3))
        
        results, total = await account_service.search_accounts(
            search="tech", industry="Technology", skip=0, limit=10
        )
        
        assert len(results) == 3
        assert total == 3
        account_service.account_repo.search_accounts.assert_called_once_with(
            "tech", None, "Technology", None, None, None, 0, 10
        )


class TestContactService:
    """Test ContactService."""

    @pytest.fixture
    async def contact_service(self, db_session):
        """Create ContactService instance."""
        return ContactService(db_session)

    @pytest.mark.asyncio
    async def test_create_contact_success(self, contact_service, contact_factory):
        """Test successful contact creation."""
        contact_data = ContactCreate(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            account_id=1
        )
        
        contact_service.contact_repo.create_contact = AsyncMock(return_value=contact_factory())
        contact_service.contact_repo.get_by_email = AsyncMock(return_value=None)
        
        result = await contact_service.create_contact(contact_data)
        
        assert result is not None
        contact_service.contact_repo.create_contact.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_contact_duplicate_email(self, contact_service, contact_factory):
        """Test creating contact with duplicate email."""
        contact_data = ContactCreate(
            first_name="John",
            last_name="Doe",
            email="john@example.com"
        )
        
        contact_service.contact_repo.get_by_email = AsyncMock(return_value=contact_factory())
        
        with pytest.raises(AlreadyExistsException):
            await contact_service.create_contact(contact_data)

    @pytest.mark.asyncio
    async def test_update_lead_score(self, contact_service, contact_factory):
        """Test updating contact lead score."""
        contact = contact_factory()
        contact.lead_score = 50
        
        contact_service.contact_repo.get = AsyncMock(return_value=contact)
        contact_service.contact_repo.update_contact = AsyncMock(return_value=contact)
        
        result = await contact_service.update_lead_score(1, 85)
        
        assert result is not None
        contact_service.contact_repo.update_contact.assert_called_once()


class TestDealService:
    """Test DealService."""

    @pytest.fixture
    async def deal_service(self, db_session):
        """Create DealService instance."""
        return DealService(db_session)

    @pytest.mark.asyncio
    async def test_create_deal_success(self, deal_service, deal_factory):
        """Test successful deal creation."""
        deal_data = DealCreate(
            title="Big Deal",
            amount=Decimal("50000.00"),
            stage="qualification",
            account_id=1
        )
        
        deal_service.deal_repo.create_deal = AsyncMock(return_value=deal_factory())
        
        result = await deal_service.create_deal(deal_data)
        
        assert result is not None
        deal_service.deal_repo.create_deal.assert_called_once()

    @pytest.mark.asyncio
    async def test_move_deal_stage(self, deal_service, deal_factory):
        """Test moving deal to different stage."""
        deal = deal_factory()
        deal.stage = "qualification"
        
        deal_service.deal_repo.get = AsyncMock(return_value=deal)
        deal_service.deal_repo.update_deal = AsyncMock(return_value=deal)
        
        result = await deal_service.move_deal_stage(1, "proposal")
        
        assert result is not None
        deal_service.deal_repo.update_deal.assert_called_once()

    @pytest.mark.asyncio
    async def test_calculate_deal_probability(self, deal_service):
        """Test deal probability calculation."""
        # Test various scenarios
        assert deal_service._calculate_deal_probability("qualification") == 25
        assert deal_service._calculate_deal_probability("proposal") == 50
        assert deal_service._calculate_deal_probability("negotiation") == 75
        assert deal_service._calculate_deal_probability("closed_won") == 100
        assert deal_service._calculate_deal_probability("closed_lost") == 0


class TestActivityService:
    """Test ActivityService."""

    @pytest.fixture
    async def activity_service(self, db_session):
        """Create ActivityService instance."""
        return ActivityService(db_session)

    @pytest.mark.asyncio
    async def test_create_activity_success(self, activity_service, activity_factory):
        """Test successful activity creation."""
        activity_data = ActivityCreate(
            activity_type="call",
            subject="Discovery Call",
            account_id=1,
            contact_id=1
        )
        
        activity_service.activity_repo.create_activity = AsyncMock(return_value=activity_factory())
        
        result = await activity_service.create_activity(activity_data)
        
        assert result is not None
        activity_service.activity_repo.create_activity.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_activity(self, activity_service, activity_factory):
        """Test marking activity as completed."""
        activity = activity_factory()
        activity.completed = False
        
        activity_service.activity_repo.get = AsyncMock(return_value=activity)
        activity_service.activity_repo.update_activity = AsyncMock(return_value=activity)
        
        result = await activity_service.complete_activity(1)
        
        assert result is not None
        activity_service.activity_repo.update_activity.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_overdue_activities(self, activity_service, activity_factory):
        """Test getting overdue activities."""
        activities = [activity_factory() for _ in range(2)]
        
        activity_service.activity_repo.get_overdue_activities = AsyncMock(return_value=activities)
        
        result = await activity_service.get_overdue_activities()
        
        assert len(result) == 2
        activity_service.activity_repo.get_overdue_activities.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_upcoming_activities(self, activity_service, activity_factory):
        """Test getting upcoming activities."""
        activities = [activity_factory() for _ in range(3)]
        
        activity_service.activity_repo.get_upcoming_activities = AsyncMock(return_value=activities)
        
        result = await activity_service.get_upcoming_activities(days_ahead=7)
        
        assert len(result) == 3
        activity_service.activity_repo.get_upcoming_activities.assert_called_once_with(7)