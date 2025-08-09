"""
Test factories for CRM models.
"""

import factory
from datetime import datetime, date, timedelta
from decimal import Decimal
from faker import Faker

from crm.models import (
    Account, Contact, Deal, Activity,
    AccountType, DealStage, ActivityType
)

fake = Faker()


class AccountFactory(factory.Factory):
    """Factory for Account model."""
    
    class Meta:
        model = Account
    
    name = factory.LazyAttribute(lambda obj: fake.company())
    account_type = factory.LazyAttribute(lambda obj: fake.random_element(elements=[e.value for e in AccountType]))
    industry = factory.LazyAttribute(lambda obj: fake.random_element(elements=[
        "Technology", "Healthcare", "Finance", "Manufacturing", "Retail", "Education"
    ]))
    website = factory.LazyAttribute(lambda obj: fake.url())
    phone = factory.LazyAttribute(lambda obj: fake.phone_number())
    email = factory.LazyAttribute(lambda obj: fake.company_email())
    annual_revenue = factory.LazyAttribute(lambda obj: Decimal(str(fake.random_int(min=100000, max=50000000))))
    employee_count = factory.LazyAttribute(lambda obj: fake.random_int(min=10, max=10000))
    billing_address = factory.LazyAttribute(lambda obj: fake.address())
    shipping_address = factory.LazyAttribute(lambda obj: fake.address())
    description = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=200))
    created_by = "test_user"
    created_at = factory.LazyAttribute(lambda obj: datetime.utcnow())
    updated_at = factory.LazyAttribute(lambda obj: datetime.utcnow())


class ContactFactory(factory.Factory):
    """Factory for Contact model."""
    
    class Meta:
        model = Contact
    
    account_id = None  # Set explicitly in tests
    first_name = factory.LazyAttribute(lambda obj: fake.first_name())
    last_name = factory.LazyAttribute(lambda obj: fake.last_name())
    email = factory.LazyAttribute(lambda obj: fake.email())
    phone = factory.LazyAttribute(lambda obj: fake.phone_number())
    job_title = factory.LazyAttribute(lambda obj: fake.job())
    department = factory.LazyAttribute(lambda obj: fake.random_element(elements=[
        "Sales", "Marketing", "Engineering", "Operations", "Finance", "HR"
    ]))
    lead_score = factory.LazyAttribute(lambda obj: fake.random_int(min=0, max=100))
    source = factory.LazyAttribute(lambda obj: fake.random_element(elements=[
        "Website", "Referral", "Cold Call", "Email", "Social Media", "Trade Show"
    ]))
    status = factory.LazyAttribute(lambda obj: fake.random_element(elements=[
        "New", "Qualified", "Contacted", "Converted"
    ]))
    created_by = "test_user"
    created_at = factory.LazyAttribute(lambda obj: datetime.utcnow())
    updated_at = factory.LazyAttribute(lambda obj: datetime.utcnow())


class DealFactory(factory.Factory):
    """Factory for Deal model."""
    
    class Meta:
        model = Deal
    
    account_id = None  # Set explicitly in tests
    contact_id = None  # Set explicitly in tests
    title = factory.LazyAttribute(lambda obj: f"{fake.catch_phrase()} - {fake.bs()}")
    amount = factory.LazyAttribute(lambda obj: Decimal(str(fake.random_int(min=1000, max=1000000))))
    stage = factory.LazyAttribute(lambda obj: fake.random_element(elements=[e.value for e in DealStage]))
    probability = factory.LazyAttribute(lambda obj: fake.random_int(min=10, max=90))
    close_date = factory.LazyAttribute(lambda obj: fake.date_between(start_date='today', end_date='+365d'))
    description = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=300))
    source = factory.LazyAttribute(lambda obj: fake.random_element(elements=[
        "Inbound", "Outbound", "Referral", "Partner", "Marketing"
    ]))
    created_by = "test_user"
    created_at = factory.LazyAttribute(lambda obj: datetime.utcnow())
    updated_at = factory.LazyAttribute(lambda obj: datetime.utcnow())


class ActivityFactory(factory.Factory):
    """Factory for Activity model."""
    
    class Meta:
        model = Activity
    
    account_id = None  # Set explicitly in tests
    contact_id = None  # Set explicitly in tests
    deal_id = None  # Optional
    activity_type = factory.LazyAttribute(lambda obj: fake.random_element(elements=[e.value for e in ActivityType]))
    subject = factory.LazyAttribute(lambda obj: fake.sentence(nb_words=6))
    description = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=200))
    due_date = factory.LazyAttribute(lambda obj: fake.date_time_between(start_date='-30d', end_date='+30d'))
    completed = factory.LazyAttribute(lambda obj: fake.boolean(chance_of_getting_true=30))
    priority = factory.LazyAttribute(lambda obj: fake.random_element(elements=["Low", "Medium", "High", "Urgent"]))
    created_by = "test_user"
    created_at = factory.LazyAttribute(lambda obj: datetime.utcnow())
    updated_at = factory.LazyAttribute(lambda obj: datetime.utcnow())


# Factory with relationships
class ContactWithAccountFactory(ContactFactory):
    """Contact factory with account relationship."""
    
    account = factory.SubFactory(AccountFactory)
    account_id = factory.LazyAttribute(lambda obj: obj.account.id)


class DealWithRelationshipsFactory(DealFactory):
    """Deal factory with account and contact relationships."""
    
    account = factory.SubFactory(AccountFactory)
    contact = factory.SubFactory(ContactFactory)
    account_id = factory.LazyAttribute(lambda obj: obj.account.id)
    contact_id = factory.LazyAttribute(lambda obj: obj.contact.id)


class ActivityWithRelationshipsFactory(ActivityFactory):
    """Activity factory with relationships."""
    
    account = factory.SubFactory(AccountFactory)
    contact = factory.SubFactory(ContactFactory)
    deal = factory.SubFactory(DealFactory)
    account_id = factory.LazyAttribute(lambda obj: obj.account.id)
    contact_id = factory.LazyAttribute(lambda obj: obj.contact.id)
    deal_id = factory.LazyAttribute(lambda obj: obj.deal.id)


# Pytest fixtures
import pytest


@pytest.fixture
def account_factory():
    """Account factory fixture."""
    return AccountFactory


@pytest.fixture
def contact_factory():
    """Contact factory fixture."""
    return ContactFactory


@pytest.fixture
def deal_factory():
    """Deal factory fixture."""
    return DealFactory


@pytest.fixture
def activity_factory():
    """Activity factory fixture."""
    return ActivityFactory


@pytest.fixture
async def sample_account(db_session):
    """Create a sample account for testing."""
    account = AccountFactory()
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


@pytest.fixture
async def sample_contact(db_session, sample_account):
    """Create a sample contact for testing."""
    contact = ContactFactory(account_id=sample_account.id)
    db_session.add(contact)
    await db_session.commit()
    await db_session.refresh(contact)
    return contact


@pytest.fixture
async def sample_deal(db_session, sample_account, sample_contact):
    """Create a sample deal for testing."""
    deal = DealFactory(account_id=sample_account.id, contact_id=sample_contact.id)
    db_session.add(deal)
    await db_session.commit()
    await db_session.refresh(deal)
    return deal


@pytest.fixture
async def sample_activity(db_session, sample_account, sample_contact):
    """Create a sample activity for testing."""
    activity = ActivityFactory(account_id=sample_account.id, contact_id=sample_contact.id)
    db_session.add(activity)
    await db_session.commit()
    await db_session.refresh(activity)
    return activity