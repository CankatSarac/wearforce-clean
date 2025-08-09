from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from ..shared.database import get_database
from ..shared.auth import get_role_based_auth, Permissions
from ..shared.utils import PaginatedResponse, paginate_query_params
from ..shared.exceptions import WearForceException, exception_handler
from ..shared.config import get_notification_settings
from .models import (
    NotificationTemplateCreate, NotificationTemplateUpdate, NotificationTemplateRead,
    NotificationCreate, NotificationUpdate, NotificationRead,
    NotificationPreferenceCreate, NotificationPreferenceUpdate, NotificationPreferenceRead,
    WebhookCreate, WebhookUpdate, WebhookRead
)
from .services import (
    NotificationTemplateService, NotificationManagerService, NotificationPreferenceService, WebhookService
)
from .providers import NotificationProviderFactory

# Initialize router
router = APIRouter(prefix="/api/v1", tags=["Notifications"])

# Dependencies
async def get_session() -> AsyncSession:
    db = get_database()
    async with db.session() as session:
        yield session

auth = get_role_based_auth()
require_notification_read = auth.require_permission(Permissions.NOTIFICATION_READ)
require_notification_write = auth.require_permission(Permissions.NOTIFICATION_WRITE)
require_notification_admin = auth.require_permission(Permissions.NOTIFICATION_ADMIN)

# Provider factory
notification_settings = get_notification_settings()
provider_factory = NotificationProviderFactory(notification_settings, use_dummy=notification_settings.use_dummy_providers)


# Template endpoints
@router.post("/templates", response_model=NotificationTemplateRead, dependencies=[Depends(require_notification_admin)])
async def create_notification_template(
    template_data: NotificationTemplateCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new notification template."""
    try:
        service = NotificationTemplateService(session)
        return await service.create_template(template_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/templates/{template_id}", response_model=NotificationTemplateRead, dependencies=[Depends(require_notification_read)])
async def get_notification_template(
    template_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get notification template by ID."""
    try:
        service = NotificationTemplateService(session)
        return await service.get_template(template_id)
    except WearForceException as e:
        raise exception_handler(e)


@router.put("/templates/{template_id}", response_model=NotificationTemplateRead, dependencies=[Depends(require_notification_admin)])
async def update_notification_template(
    template_id: int,
    template_data: NotificationTemplateUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Update a notification template."""
    try:
        service = NotificationTemplateService(session)
        return await service.update_template(template_id, template_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.delete("/templates/{template_id}", dependencies=[Depends(require_notification_admin)])
async def delete_notification_template(
    template_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Delete a notification template."""
    try:
        service = NotificationTemplateService(session)
        await service.delete_template(template_id)
        return {"message": "Template deleted successfully"}
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/templates", response_model=PaginatedResponse, dependencies=[Depends(require_notification_read)])
async def search_notification_templates(
    search: Optional[str] = Query(None, description="Search term for name, description, or content"),
    template_type: Optional[str] = Query(None, description="Template type filter"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    session: AsyncSession = Depends(get_session)
):
    """Search notification templates with filters and pagination."""
    try:
        skip, limit = paginate_query_params(skip, limit)
        service = NotificationTemplateService(session)
        templates, total = await service.search_templates(search, template_type, is_active, skip, limit)
        return PaginatedResponse.create(templates, total, skip, limit)
    except WearForceException as e:
        raise exception_handler(e)


@router.post("/templates/{template_id}/render", dependencies=[Depends(require_notification_read)])
async def render_notification_template(
    template_id: int,
    variables: Dict[str, Any],
    session: AsyncSession = Depends(get_session)
):
    """Render a notification template with variables."""
    try:
        service = NotificationTemplateService(session)
        return await service.render_template(template_id, variables)
    except WearForceException as e:
        raise exception_handler(e)


# Notification endpoints
@router.post("/notifications", response_model=NotificationRead, dependencies=[Depends(require_notification_write)])
async def create_notification(
    notification_data: NotificationCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session)
):
    """Create a new notification."""
    try:
        service = NotificationManagerService(session, provider_factory)
        notification = await service.create_notification(notification_data)
        
        # Schedule sending in background if not scheduled for later
        if not notification_data.scheduled_at or notification_data.scheduled_at <= datetime.utcnow():
            background_tasks.add_task(service.send_notification, notification.id)
        
        return notification
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/notifications/{notification_id}", response_model=NotificationRead, dependencies=[Depends(require_notification_read)])
async def get_notification(
    notification_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get notification by ID."""
    try:
        service = NotificationManagerService(session, provider_factory)
        return await service.get_notification(notification_id)
    except WearForceException as e:
        raise exception_handler(e)


@router.put("/notifications/{notification_id}/status", response_model=NotificationRead, dependencies=[Depends(require_notification_write)])
async def update_notification_status(
    notification_id: int,
    status: str = Query(..., description="New notification status"),
    external_id: Optional[str] = Query(None, description="External ID from provider"),
    error_message: Optional[str] = Query(None, description="Error message if failed"),
    session: AsyncSession = Depends(get_session)
):
    """Update notification status."""
    try:
        service = NotificationManagerService(session, provider_factory)
        return await service.update_notification_status(notification_id, status, external_id, error_message)
    except WearForceException as e:
        raise exception_handler(e)


@router.post("/notifications/{notification_id}/send", response_model=NotificationRead, dependencies=[Depends(require_notification_write)])
async def send_notification(
    notification_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Manually send a notification."""
    try:
        service = NotificationManagerService(session, provider_factory)
        success = await service.send_notification(notification_id)
        if success:
            return await service.get_notification(notification_id)
        else:
            raise HTTPException(status_code=400, detail="Failed to send notification")
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/notifications", response_model=PaginatedResponse, dependencies=[Depends(require_notification_read)])
async def search_notifications(
    search: Optional[str] = Query(None, description="Search term for subject, content, or recipient"),
    notification_type: Optional[str] = Query(None, description="Notification type filter"),
    status: Optional[str] = Query(None, description="Status filter"),
    recipient: Optional[str] = Query(None, description="Recipient filter"),
    source_service: Optional[str] = Query(None, description="Source service filter"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    session: AsyncSession = Depends(get_session)
):
    """Search notifications with filters and pagination."""
    try:
        skip, limit = paginate_query_params(skip, limit)
        service = NotificationManagerService(session, provider_factory)
        notifications, total = await service.search_notifications(
            search, notification_type, status, recipient, source_service, skip, limit
        )
        return PaginatedResponse.create(notifications, total, skip, limit)
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/notifications/stats", dependencies=[Depends(require_notification_read)])
async def get_notification_stats(
    session: AsyncSession = Depends(get_session)
):
    """Get notification statistics."""
    try:
        service = NotificationManagerService(session, provider_factory)
        return await service.get_notification_stats()
    except WearForceException as e:
        raise exception_handler(e)


@router.post("/notifications/process-pending", dependencies=[Depends(require_notification_admin)])
async def process_pending_notifications(
    batch_size: int = Query(100, ge=1, le=1000, description="Batch size for processing"),
    session: AsyncSession = Depends(get_session)
):
    """Process pending notifications."""
    try:
        service = NotificationManagerService(session, provider_factory)
        processed_count = await service.process_pending_notifications(batch_size)
        return {"message": f"Processed {processed_count} notifications"}
    except WearForceException as e:
        raise exception_handler(e)


@router.post("/notifications/retry-failed", dependencies=[Depends(require_notification_admin)])
async def retry_failed_notifications(
    batch_size: int = Query(50, ge=1, le=1000, description="Batch size for retry"),
    session: AsyncSession = Depends(get_session)
):
    """Retry failed notifications."""
    try:
        service = NotificationManagerService(session, provider_factory)
        retried_count = await service.retry_failed_notifications(batch_size)
        return {"message": f"Retried {retried_count} notifications"}
    except WearForceException as e:
        raise exception_handler(e)


# Notification preference endpoints
@router.post("/preferences", response_model=NotificationPreferenceRead, dependencies=[Depends(require_notification_write)])
async def create_notification_preference(
    preference_data: NotificationPreferenceCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create notification preferences for a user."""
    try:
        service = NotificationPreferenceService(session)
        return await service.create_preference(preference_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/preferences/{preference_id}", response_model=NotificationPreferenceRead, dependencies=[Depends(require_notification_read)])
async def get_notification_preference(
    preference_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get notification preferences by ID."""
    try:
        service = NotificationPreferenceService(session)
        return await service.get_preference(preference_id)
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/preferences/user/{user_id}", response_model=NotificationPreferenceRead, dependencies=[Depends(require_notification_read)])
async def get_notification_preference_by_user(
    user_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Get notification preferences by user ID."""
    try:
        service = NotificationPreferenceService(session)
        return await service.get_preference_by_user(user_id)
    except WearForceException as e:
        raise exception_handler(e)


@router.put("/preferences/{preference_id}", response_model=NotificationPreferenceRead, dependencies=[Depends(require_notification_write)])
async def update_notification_preference(
    preference_id: int,
    preference_data: NotificationPreferenceUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Update notification preferences."""
    try:
        service = NotificationPreferenceService(session)
        return await service.update_preference(preference_id, preference_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.delete("/preferences/{preference_id}", dependencies=[Depends(require_notification_write)])
async def delete_notification_preference(
    preference_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Delete notification preferences."""
    try:
        service = NotificationPreferenceService(session)
        await service.delete_preference(preference_id)
        return {"message": "Preferences deleted successfully"}
    except WearForceException as e:
        raise exception_handler(e)


# Webhook endpoints
@router.post("/webhooks", response_model=WebhookRead, dependencies=[Depends(require_notification_admin)])
async def create_webhook(
    webhook_data: WebhookCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new webhook."""
    try:
        service = WebhookService(session, provider_factory)
        return await service.create_webhook(webhook_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/webhooks/{webhook_id}", response_model=WebhookRead, dependencies=[Depends(require_notification_read)])
async def get_webhook(
    webhook_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get webhook by ID."""
    try:
        service = WebhookService(session, provider_factory)
        return await service.get_webhook(webhook_id)
    except WearForceException as e:
        raise exception_handler(e)


@router.put("/webhooks/{webhook_id}", response_model=WebhookRead, dependencies=[Depends(require_notification_admin)])
async def update_webhook(
    webhook_id: int,
    webhook_data: WebhookUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Update a webhook."""
    try:
        service = WebhookService(session, provider_factory)
        return await service.update_webhook(webhook_id, webhook_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.delete("/webhooks/{webhook_id}", dependencies=[Depends(require_notification_admin)])
async def delete_webhook(
    webhook_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Delete a webhook."""
    try:
        service = WebhookService(session, provider_factory)
        await service.delete_webhook(webhook_id)
        return {"message": "Webhook deleted successfully"}
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/webhooks", response_model=PaginatedResponse, dependencies=[Depends(require_notification_read)])
async def search_webhooks(
    search: Optional[str] = Query(None, description="Search term for name, URL, or description"),
    status: Optional[str] = Query(None, description="Status filter"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    session: AsyncSession = Depends(get_session)
):
    """Search webhooks with filters and pagination."""
    try:
        skip, limit = paginate_query_params(skip, limit)
        service = WebhookService(session, provider_factory)
        webhooks, total = await service.search_webhooks(search, status, skip, limit)
        return PaginatedResponse.create(webhooks, total, skip, limit)
    except WearForceException as e:
        raise exception_handler(e)


@router.post("/webhooks/trigger", dependencies=[Depends(require_notification_admin)])
async def trigger_webhooks(
    event_type: str = Query(..., description="Event type to trigger"),
    event_data: Dict[str, Any] = Query(..., description="Event data"),
    event_id: str = Query(..., description="Event ID"),
    session: AsyncSession = Depends(get_session)
):
    """Manually trigger webhooks for an event."""
    try:
        service = WebhookService(session, provider_factory)
        triggered_count = await service.trigger_webhook(event_type, event_data, event_id)
        return {"message": f"Triggered {triggered_count} webhooks"}
    except WearForceException as e:
        raise exception_handler(e)


# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "notification-service"}


# Utility endpoints for development/testing
@router.post("/test/email", dependencies=[Depends(require_notification_admin)])
async def test_email_notification(
    recipient_email: str = Query(..., description="Recipient email address"),
    subject: str = Query("Test Email", description="Email subject"),
    content: str = Query("This is a test email notification.", description="Email content"),
    session: AsyncSession = Depends(get_session)
):
    """Send a test email notification."""
    try:
        notification_data = NotificationCreate(
            notification_type="email",
            recipient_email=recipient_email,
            subject=subject,
            content=content,
            source_service="notification-service",
            source_event="test"
        )
        
        service = NotificationManagerService(session, provider_factory)
        notification = await service.create_notification(notification_data)
        
        success = await service.send_notification(notification.id)
        if success:
            return {"message": "Test email sent successfully", "notification_id": notification.id}
        else:
            return {"message": "Failed to send test email", "notification_id": notification.id}
            
    except WearForceException as e:
        raise exception_handler(e)


@router.post("/test/sms", dependencies=[Depends(require_notification_admin)])
async def test_sms_notification(
    recipient_phone: str = Query(..., description="Recipient phone number"),
    content: str = Query("This is a test SMS notification.", description="SMS content"),
    session: AsyncSession = Depends(get_session)
):
    """Send a test SMS notification."""
    try:
        notification_data = NotificationCreate(
            notification_type="sms",
            recipient_phone=recipient_phone,
            content=content,
            source_service="notification-service",
            source_event="test"
        )
        
        service = NotificationManagerService(session, provider_factory)
        notification = await service.create_notification(notification_data)
        
        success = await service.send_notification(notification.id)
        if success:
            return {"message": "Test SMS sent successfully", "notification_id": notification.id}
        else:
            return {"message": "Failed to send test SMS", "notification_id": notification.id}
            
    except WearForceException as e:
        raise exception_handler(e)