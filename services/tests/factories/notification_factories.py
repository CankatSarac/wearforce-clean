"""
Test factories for Notification models.
"""

import factory
from datetime import datetime
from faker import Faker

from notification.models import (
    NotificationTemplate, Notification, NotificationPreference, Webhook, WebhookDelivery,
    TemplateType, NotificationType, NotificationStatus, NotificationPriority, WebhookStatus
)

fake = Faker()


class NotificationTemplateFactory(factory.Factory):
    """Factory for NotificationTemplate model."""
    
    class Meta:
        model = NotificationTemplate
    
    name = factory.LazyAttribute(lambda obj: fake.catch_phrase())
    template_type = factory.LazyAttribute(lambda obj: fake.random_element(elements=[e.value for e in TemplateType]))
    subject = factory.LazyAttribute(lambda obj: fake.sentence(nb_words=6) if obj.template_type == "email" else None)
    content = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=500))
    html_content = factory.LazyAttribute(lambda obj: f"<h1>{fake.sentence()}</h1><p>{fake.text(max_nb_chars=200)}</p>" if obj.template_type == "email" else None)
    description = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=100))
    language = "en"
    is_active = factory.LazyAttribute(lambda obj: fake.boolean(chance_of_getting_true=80))
    variables = factory.LazyAttribute(lambda obj: '{"name": "Recipient name", "company": "Company name"}')
    created_by = "test_user"
    created_at = factory.LazyAttribute(lambda obj: datetime.utcnow())
    updated_at = factory.LazyAttribute(lambda obj: datetime.utcnow())


class NotificationFactory(factory.Factory):
    """Factory for Notification model."""
    
    class Meta:
        model = Notification
    
    notification_type = factory.LazyAttribute(lambda obj: fake.random_element(elements=[e.value for e in NotificationType]))
    status = factory.LazyAttribute(lambda obj: fake.random_element(elements=[e.value for e in NotificationStatus]))
    priority = factory.LazyAttribute(lambda obj: fake.random_element(elements=[e.value for e in NotificationPriority]))
    recipient_id = factory.LazyAttribute(lambda obj: fake.uuid4())
    recipient_email = factory.LazyAttribute(lambda obj: fake.email() if obj.notification_type == "email" else None)
    recipient_phone = factory.LazyAttribute(lambda obj: fake.phone_number() if obj.notification_type == "sms" else None)
    recipient_device_token = factory.LazyAttribute(lambda obj: fake.uuid4() if obj.notification_type == "push" else None)
    subject = factory.LazyAttribute(lambda obj: fake.sentence(nb_words=6) if obj.notification_type == "email" else None)
    content = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=300))
    html_content = factory.LazyAttribute(lambda obj: f"<p>{fake.text(max_nb_chars=200)}</p>" if obj.notification_type == "email" else None)
    template_id = None  # Set explicitly in tests if needed
    template_variables = factory.LazyAttribute(lambda obj: '{"name": "John Doe"}' if fake.boolean() else None)
    scheduled_at = factory.LazyAttribute(lambda obj: fake.date_time_between(start_date='-1d', end_date='+1d') if fake.boolean(chance_of_getting_true=30) else None)
    sent_at = factory.LazyAttribute(lambda obj: fake.date_time_between(start_date='-1d', end_date='now') if obj.status in ["sent", "delivered"] else None)
    delivered_at = factory.LazyAttribute(lambda obj: fake.date_time_between(start_date=obj.sent_at, end_date='now') if obj.status == "delivered" and obj.sent_at else None)
    opened_at = factory.LazyAttribute(lambda obj: fake.date_time_between(start_date=obj.delivered_at, end_date='now') if obj.status == "opened" and obj.delivered_at else None)
    clicked_at = factory.LazyAttribute(lambda obj: fake.date_time_between(start_date=obj.opened_at, end_date='now') if obj.status == "clicked" and obj.opened_at else None)
    external_id = factory.LazyAttribute(lambda obj: fake.uuid4() if obj.status in ["sent", "delivered"] else None)
    error_message = factory.LazyAttribute(lambda obj: fake.sentence() if obj.status == "failed" else None)
    retry_count = factory.LazyAttribute(lambda obj: fake.random_int(min=0, max=3))
    max_retries = 3
    source_service = factory.LazyAttribute(lambda obj: fake.random_element(elements=["crm-service", "erp-service", "notification-service"]))
    source_event = factory.LazyAttribute(lambda obj: fake.random_element(elements=["user.created", "order.confirmed", "deal.updated", "stock.low"]))
    correlation_id = factory.LazyAttribute(lambda obj: fake.uuid4())
    metadata = factory.LazyAttribute(lambda obj: '{"campaign_id": "camp_123"}' if fake.boolean() else None)
    created_at = factory.LazyAttribute(lambda obj: datetime.utcnow())
    updated_at = factory.LazyAttribute(lambda obj: datetime.utcnow())


class NotificationPreferenceFactory(factory.Factory):
    """Factory for NotificationPreference model."""
    
    class Meta:
        model = NotificationPreference
    
    user_id = factory.LazyAttribute(lambda obj: fake.uuid4())
    email_enabled = factory.LazyAttribute(lambda obj: fake.boolean(chance_of_getting_true=80))
    sms_enabled = factory.LazyAttribute(lambda obj: fake.boolean(chance_of_getting_true=60))
    push_enabled = factory.LazyAttribute(lambda obj: fake.boolean(chance_of_getting_true=70))
    in_app_enabled = factory.LazyAttribute(lambda obj: fake.boolean(chance_of_getting_true=90))
    email = factory.LazyAttribute(lambda obj: fake.email() if obj.email_enabled else None)
    phone = factory.LazyAttribute(lambda obj: fake.phone_number() if obj.sms_enabled else None)
    device_tokens = factory.LazyAttribute(lambda obj: f'["{fake.uuid4()}", "{fake.uuid4()}"]' if obj.push_enabled else None)
    preferences = factory.LazyAttribute(lambda obj: '{"marketing": true, "alerts": true, "reminders": false}')
    timezone = factory.LazyAttribute(lambda obj: fake.timezone())
    created_at = factory.LazyAttribute(lambda obj: datetime.utcnow())
    updated_at = factory.LazyAttribute(lambda obj: datetime.utcnow())


class WebhookFactory(factory.Factory):
    """Factory for Webhook model."""
    
    class Meta:
        model = Webhook
    
    name = factory.LazyAttribute(lambda obj: f"{fake.company()} Webhook")
    url = factory.LazyAttribute(lambda obj: fake.url())
    status = factory.LazyAttribute(lambda obj: fake.random_element(elements=[e.value for e in WebhookStatus]))
    events = factory.LazyAttribute(lambda obj: '["order.created", "order.updated", "user.created"]')
    secret = factory.LazyAttribute(lambda obj: fake.password(length=32))
    http_method = "POST"
    timeout_seconds = factory.LazyAttribute(lambda obj: fake.random_int(min=10, max=60))
    headers = factory.LazyAttribute(lambda obj: '{"Content-Type": "application/json", "Authorization": "Bearer token123"}')
    max_retries = factory.LazyAttribute(lambda obj: fake.random_int(min=1, max=5))
    retry_delay_seconds = factory.LazyAttribute(lambda obj: fake.random_int(min=30, max=300))
    last_triggered_at = factory.LazyAttribute(lambda obj: fake.date_time_between(start_date='-7d', end_date='now') if fake.boolean() else None)
    last_success_at = factory.LazyAttribute(lambda obj: fake.date_time_between(start_date='-7d', end_date='now') if fake.boolean() else None)
    last_failure_at = factory.LazyAttribute(lambda obj: fake.date_time_between(start_date='-7d', end_date='now') if fake.boolean() else None)
    failure_count = factory.LazyAttribute(lambda obj: fake.random_int(min=0, max=10))
    description = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=200))
    created_by = "test_user"
    created_at = factory.LazyAttribute(lambda obj: datetime.utcnow())
    updated_at = factory.LazyAttribute(lambda obj: datetime.utcnow())


class WebhookDeliveryFactory(factory.Factory):
    """Factory for WebhookDelivery model."""
    
    class Meta:
        model = WebhookDelivery
    
    webhook_id = None  # Set explicitly in tests
    event_type = factory.LazyAttribute(lambda obj: fake.random_element(elements=["order.created", "user.updated", "deal.closed"]))
    event_id = factory.LazyAttribute(lambda obj: fake.uuid4())
    request_url = factory.LazyAttribute(lambda obj: fake.url())
    request_method = "POST"
    request_headers = factory.LazyAttribute(lambda obj: '{"Content-Type": "application/json"}')
    request_body = factory.LazyAttribute(lambda obj: f'{{"event_type": "{obj.event_type}", "data": {{"id": "{fake.uuid4()}"}}}}')
    response_status = factory.LazyAttribute(lambda obj: fake.random_element(elements=[200, 201, 400, 401, 500]))
    response_headers = factory.LazyAttribute(lambda obj: '{"Content-Type": "application/json", "Server": "nginx"}')
    response_body = factory.LazyAttribute(lambda obj: '{"success": true}' if obj.response_status < 400 else '{"error": "Bad request"}')
    sent_at = factory.LazyAttribute(lambda obj: fake.date_time_between(start_date='-1d', end_date='now'))
    received_at = factory.LazyAttribute(lambda obj: fake.date_time_between(start_date=obj.sent_at, end_date='now'))
    duration_ms = factory.LazyAttribute(lambda obj: fake.random_int(min=50, max=5000))
    is_success = factory.LazyAttribute(lambda obj: obj.response_status < 400)
    error_message = factory.LazyAttribute(lambda obj: fake.sentence() if not obj.is_success else None)
    retry_count = factory.LazyAttribute(lambda obj: fake.random_int(min=0, max=3))
    created_at = factory.LazyAttribute(lambda obj: datetime.utcnow())
    updated_at = factory.LazyAttribute(lambda obj: datetime.utcnow())


# Factories with relationships
class NotificationWithTemplateFactory(NotificationFactory):
    """Notification factory with template relationship."""
    
    template = factory.SubFactory(NotificationTemplateFactory)
    template_id = factory.LazyAttribute(lambda obj: obj.template.id)


class WebhookDeliveryWithWebhookFactory(WebhookDeliveryFactory):
    """WebhookDelivery factory with webhook relationship."""
    
    webhook = factory.SubFactory(WebhookFactory)
    webhook_id = factory.LazyAttribute(lambda obj: obj.webhook.id)
    request_url = factory.LazyAttribute(lambda obj: obj.webhook.url)


# Pytest fixtures
import pytest


@pytest.fixture
def notification_template_factory():
    """Notification template factory fixture."""
    return NotificationTemplateFactory


@pytest.fixture
def notification_factory():
    """Notification factory fixture."""
    return NotificationFactory


@pytest.fixture
def notification_preference_factory():
    """Notification preference factory fixture."""
    return NotificationPreferenceFactory


@pytest.fixture
def webhook_factory():
    """Webhook factory fixture."""
    return WebhookFactory


@pytest.fixture
def webhook_delivery_factory():
    """Webhook delivery factory fixture."""
    return WebhookDeliveryFactory


@pytest.fixture
async def sample_notification_template(db_session):
    """Create a sample notification template for testing."""
    template = NotificationTemplateFactory()
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)
    return template


@pytest.fixture
async def sample_notification(db_session):
    """Create a sample notification for testing."""
    notification = NotificationFactory()
    db_session.add(notification)
    await db_session.commit()
    await db_session.refresh(notification)
    return notification


@pytest.fixture
async def sample_notification_preference(db_session):
    """Create a sample notification preference for testing."""
    preference = NotificationPreferenceFactory()
    db_session.add(preference)
    await db_session.commit()
    await db_session.refresh(preference)
    return preference


@pytest.fixture
async def sample_webhook(db_session):
    """Create a sample webhook for testing."""
    webhook = WebhookFactory()
    db_session.add(webhook)
    await db_session.commit()
    await db_session.refresh(webhook)
    return webhook


@pytest.fixture
async def sample_webhook_delivery(db_session, sample_webhook):
    """Create a sample webhook delivery for testing."""
    delivery = WebhookDeliveryFactory(webhook_id=sample_webhook.id)
    db_session.add(delivery)
    await db_session.commit()
    await db_session.refresh(delivery)
    return delivery