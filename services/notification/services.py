import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from ..shared.events import BaseEvent, EventType, get_event_publisher
from ..shared.exceptions import NotFoundException, ValidationException, AlreadyExistsException
from ..shared.middleware import get_current_user_id
from ..shared.utils import utc_now
from .models import (
    NotificationTemplate, NotificationTemplateCreate, NotificationTemplateUpdate, NotificationTemplateRead,
    Notification, NotificationCreate, NotificationUpdate, NotificationRead, NotificationStatus, NotificationType,
    NotificationPreference, NotificationPreferenceCreate, NotificationPreferenceUpdate, NotificationPreferenceRead,
    Webhook, WebhookCreate, WebhookUpdate, WebhookRead,
    WebhookDelivery
)
from .repositories import (
    NotificationTemplateRepository, NotificationRepository, NotificationPreferenceRepository,
    WebhookRepository, WebhookDeliveryRepository
)
from .providers import NotificationProviderFactory, TemplateRenderer


class NotificationService:
    """Main notification service with business logic."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.template_repo = NotificationTemplateRepository(session)
        self.notification_repo = NotificationRepository(session)
        self.preference_repo = NotificationPreferenceRepository(session)
        self.webhook_repo = WebhookRepository(session)
        self.webhook_delivery_repo = WebhookDeliveryRepository(session)
        self.event_publisher = get_event_publisher()
    
    async def _publish_event(self, event_type: EventType, data: Dict[str, Any], entity_id: int = None):
        """Publish an event."""
        event = BaseEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            service="notification-service",
            timestamp=utc_now(),
            data=data,
            user_id=get_current_user_id(),
            metadata={"entity_id": entity_id} if entity_id else None
        )
        await self.event_publisher.publish(event)


class NotificationTemplateService(NotificationService):
    """Notification template management service."""
    
    async def create_template(self, template_data: NotificationTemplateCreate) -> NotificationTemplateRead:
        """Create a new notification template."""
        # Check if template with same name and type already exists
        existing = await self.template_repo.get_by_name_and_type(
            template_data.name, template_data.template_type
        )
        if existing:
            raise AlreadyExistsException(
                f"Template '{template_data.name}' of type '{template_data.template_type}' already exists"
            )
        
        template = await self.template_repo.create_template(template_data, get_current_user_id())
        
        return NotificationTemplateRead.model_validate(template)
    
    async def get_template(self, template_id: int) -> NotificationTemplateRead:
        """Get template by ID."""
        template = await self.template_repo.get(template_id)
        if not template:
            raise NotFoundException(f"Template with ID {template_id} not found")
        
        # Convert variables JSON back to dict for response
        template_dict = template.model_dump()
        template_dict['variables'] = template.get_variables()
        
        return NotificationTemplateRead(**template_dict)
    
    async def update_template(self, template_id: int, template_data: NotificationTemplateUpdate) -> NotificationTemplateRead:
        """Update a notification template."""
        template = await self.template_repo.update_template(template_id, template_data, get_current_user_id())
        if not template:
            raise NotFoundException(f"Template with ID {template_id} not found")
        
        # Convert variables JSON back to dict for response
        template_dict = template.model_dump()
        template_dict['variables'] = template.get_variables()
        
        return NotificationTemplateRead(**template_dict)
    
    async def delete_template(self, template_id: int) -> bool:
        """Delete a template (soft delete)."""
        success = await self.template_repo.delete(template_id)
        if not success:
            raise NotFoundException(f"Template with ID {template_id} not found")
        
        return True
    
    async def search_templates(
        self,
        search: Optional[str] = None,
        template_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[NotificationTemplateRead], int]:
        """Search notification templates with filters."""
        templates, total = await self.template_repo.search_templates(
            search, template_type, is_active, skip, limit
        )
        
        template_reads = []
        for template in templates:
            template_dict = template.model_dump()
            template_dict['variables'] = template.get_variables()
            template_reads.append(NotificationTemplateRead(**template_dict))
        
        return template_reads, total
    
    async def render_template(self, template_id: int, variables: Dict[str, Any]) -> Dict[str, str]:
        """Render a template with variables."""
        template = await self.template_repo.get(template_id)
        if not template:
            raise NotFoundException(f"Template with ID {template_id} not found")
        
        if not template.is_active:
            raise ValidationException(f"Template {template_id} is inactive")
        
        # Render content
        rendered_content = TemplateRenderer.render(template.content, variables)
        rendered_subject = TemplateRenderer.render(template.subject or "", variables)
        rendered_html = None
        
        if template.html_content:
            rendered_html = TemplateRenderer.render(template.html_content, variables)
        
        return {
            "subject": rendered_subject,
            "content": rendered_content,
            "html_content": rendered_html
        }


class NotificationManagerService(NotificationService):
    """Notification management and sending service."""
    
    def __init__(self, session: AsyncSession, provider_factory: NotificationProviderFactory):
        super().__init__(session)
        self.provider_factory = provider_factory
    
    async def create_notification(self, notification_data: NotificationCreate) -> NotificationRead:
        """Create a new notification."""
        # Validate template if provided
        if notification_data.template_id:
            template = await self.template_repo.get(notification_data.template_id)
            if not template:
                raise ValidationException(f"Template with ID {notification_data.template_id} not found")
            
            if not template.is_active:
                raise ValidationException(f"Template {notification_data.template_id} is inactive")
            
            # If using template, render content
            if notification_data.template_variables:
                rendered = await NotificationTemplateService(self.session).render_template(
                    notification_data.template_id,
                    notification_data.template_variables
                )
                # Override content with rendered template
                notification_data.subject = rendered["subject"]
                notification_data.content = rendered["content"]
                if rendered["html_content"]:
                    notification_data.html_content = rendered["html_content"]
        
        # Validate recipient based on notification type
        self._validate_recipient(notification_data)
        
        notification = await self.notification_repo.create_notification(notification_data)
        
        return NotificationRead.model_validate(notification)
    
    def _validate_recipient(self, notification_data: NotificationCreate):
        """Validate recipient information based on notification type."""
        if notification_data.notification_type == NotificationType.EMAIL:
            if not notification_data.recipient_email:
                raise ValidationException("Email address is required for email notifications")
        elif notification_data.notification_type == NotificationType.SMS:
            if not notification_data.recipient_phone:
                raise ValidationException("Phone number is required for SMS notifications")
        elif notification_data.notification_type == NotificationType.PUSH:
            if not (notification_data.recipient_id or hasattr(notification_data, 'recipient_device_token')):
                raise ValidationException("User ID or device token is required for push notifications")
    
    async def get_notification(self, notification_id: int) -> NotificationRead:
        """Get notification by ID."""
        notification = await self.notification_repo.get(notification_id)
        if not notification:
            raise NotFoundException(f"Notification with ID {notification_id} not found")
        
        return NotificationRead.model_validate(notification)
    
    async def update_notification_status(
        self,
        notification_id: int,
        status: NotificationStatus,
        external_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> NotificationRead:
        """Update notification status."""
        update_data = NotificationUpdate(
            status=status,
            external_id=external_id,
            error_message=error_message
        )
        
        # Set timestamp based on status
        if status == NotificationStatus.SENT:
            update_data.sent_at = utc_now()
        elif status == NotificationStatus.DELIVERED:
            update_data.delivered_at = utc_now()
        
        notification = await self.notification_repo.update_notification(notification_id, update_data)
        if not notification:
            raise NotFoundException(f"Notification with ID {notification_id} not found")
        
        return NotificationRead.model_validate(notification)
    
    async def send_notification(self, notification_id: int) -> bool:
        """Send a single notification."""
        notification = await self.notification_repo.get(notification_id)
        if not notification:
            raise NotFoundException(f"Notification with ID {notification_id} not found")
        
        if notification.status != NotificationStatus.PENDING:
            raise ValidationException(f"Notification {notification_id} is not in pending status")
        
        return await self._send_notification(notification)
    
    async def _send_notification(self, notification: Notification) -> bool:
        """Send notification using appropriate provider."""
        try:
            provider = None
            recipient = None
            
            if notification.notification_type == NotificationType.EMAIL:
                provider = self.provider_factory.get_email_provider()
                recipient = notification.recipient_email
            elif notification.notification_type == NotificationType.SMS:
                provider = self.provider_factory.get_sms_provider()
                recipient = notification.recipient_phone
            elif notification.notification_type == NotificationType.PUSH:
                provider = self.provider_factory.get_push_provider()
                recipient = notification.recipient_device_token
            
            if not provider or not recipient:
                await self._update_notification_failed(notification, "Invalid notification type or missing recipient")
                return False
            
            # Send notification
            result = await provider.send(
                recipient=recipient,
                subject=notification.subject,
                content=notification.content,
                html_content=notification.html_content,
                metadata=notification.get_metadata()
            )
            
            if result["success"]:
                await self.notification_repo.update_notification(
                    notification.id,
                    NotificationUpdate(
                        status=NotificationStatus.SENT,
                        sent_at=utc_now(),
                        external_id=result.get("external_id")
                    )
                )
                
                # Publish success event
                await self._publish_event(
                    EventType.EMAIL_SENT if notification.notification_type == NotificationType.EMAIL 
                    else EventType.SMS_SENT if notification.notification_type == NotificationType.SMS 
                    else EventType.PUSH_SENT,
                    {
                        "notification_id": notification.id,
                        "notification_type": notification.notification_type.value,
                        "recipient": recipient,
                        "external_id": result.get("external_id")
                    },
                    notification.id
                )
                
                return True
            else:
                await self._update_notification_failed(notification, result.get("error", "Unknown error"))
                return False
                
        except Exception as e:
            await self._update_notification_failed(notification, str(e))
            return False
    
    async def _update_notification_failed(self, notification: Notification, error_message: str):
        """Update notification as failed and handle retry logic."""
        retry_count = notification.retry_count + 1
        status = NotificationStatus.FAILED
        
        await self.notification_repo.update_notification(
            notification.id,
            NotificationUpdate(
                status=status,
                error_message=error_message,
                retry_count=retry_count
            )
        )
        
        # Publish failure event
        await self._publish_event(
            EventType.NOTIFICATION_FAILED,
            {
                "notification_id": notification.id,
                "notification_type": notification.notification_type.value,
                "error": error_message,
                "retry_count": retry_count
            },
            notification.id
        )
    
    async def process_pending_notifications(self, batch_size: int = 100) -> int:
        """Process pending notifications."""
        pending_notifications = await self.notification_repo.get_pending_notifications(batch_size)
        processed_count = 0
        
        for notification in pending_notifications:
            try:
                success = await self._send_notification(notification)
                if success:
                    processed_count += 1
            except Exception as e:
                await self._update_notification_failed(notification, str(e))
        
        return processed_count
    
    async def retry_failed_notifications(self, batch_size: int = 50) -> int:
        """Retry failed notifications that can be retried."""
        failed_notifications = await self.notification_repo.get_failed_notifications_for_retry(batch_size)
        retried_count = 0
        
        for notification in failed_notifications:
            try:
                # Reset status to pending for retry
                await self.notification_repo.update_notification(
                    notification.id,
                    NotificationUpdate(status=NotificationStatus.PENDING)
                )
                
                success = await self._send_notification(notification)
                if success:
                    retried_count += 1
                    
            except Exception as e:
                await self._update_notification_failed(notification, str(e))
        
        return retried_count
    
    async def search_notifications(
        self,
        search: Optional[str] = None,
        notification_type: Optional[str] = None,
        status: Optional[str] = None,
        recipient: Optional[str] = None,
        source_service: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[NotificationRead], int]:
        """Search notifications with filters."""
        notifications, total = await self.notification_repo.search_notifications(
            search, notification_type, status, recipient, source_service, None, None, skip, limit
        )
        
        notification_reads = [NotificationRead.model_validate(notification) for notification in notifications]
        return notification_reads, total
    
    async def get_notification_stats(self) -> Dict[str, Any]:
        """Get notification statistics."""
        return await self.notification_repo.get_notification_stats()


class NotificationPreferenceService(NotificationService):
    """Notification preference management service."""
    
    async def create_preference(self, preference_data: NotificationPreferenceCreate) -> NotificationPreferenceRead:
        """Create notification preferences for a user."""
        # Check if preferences already exist for this user
        existing = await self.preference_repo.get_by_user_id(preference_data.user_id)
        if existing:
            raise AlreadyExistsException(f"Preferences already exist for user {preference_data.user_id}")
        
        preference = await self.preference_repo.create_preference(preference_data)
        
        # Convert device tokens back to list for response
        preference_dict = preference.model_dump()
        preference_dict['device_tokens'] = preference.get_device_tokens()
        
        return NotificationPreferenceRead(**preference_dict)
    
    async def get_preference(self, preference_id: int) -> NotificationPreferenceRead:
        """Get notification preferences by ID."""
        preference = await self.preference_repo.get(preference_id)
        if not preference:
            raise NotFoundException(f"Preferences with ID {preference_id} not found")
        
        # Convert device tokens back to list for response
        preference_dict = preference.model_dump()
        preference_dict['device_tokens'] = preference.get_device_tokens()
        
        return NotificationPreferenceRead(**preference_dict)
    
    async def get_preference_by_user(self, user_id: str) -> NotificationPreferenceRead:
        """Get notification preferences by user ID."""
        preference = await self.preference_repo.get_by_user_id(user_id)
        if not preference:
            raise NotFoundException(f"Preferences not found for user {user_id}")
        
        # Convert device tokens back to list for response
        preference_dict = preference.model_dump()
        preference_dict['device_tokens'] = preference.get_device_tokens()
        
        return NotificationPreferenceRead(**preference_dict)
    
    async def update_preference(self, preference_id: int, preference_data: NotificationPreferenceUpdate) -> NotificationPreferenceRead:
        """Update notification preferences."""
        preference = await self.preference_repo.update_preference(preference_id, preference_data)
        if not preference:
            raise NotFoundException(f"Preferences with ID {preference_id} not found")
        
        # Convert device tokens back to list for response
        preference_dict = preference.model_dump()
        preference_dict['device_tokens'] = preference.get_device_tokens()
        
        return NotificationPreferenceRead(**preference_dict)
    
    async def delete_preference(self, preference_id: int) -> bool:
        """Delete notification preferences."""
        success = await self.preference_repo.delete(preference_id)
        if not success:
            raise NotFoundException(f"Preferences with ID {preference_id} not found")
        
        return True


class WebhookService(NotificationService):
    """Webhook management service."""
    
    def __init__(self, session: AsyncSession, provider_factory: NotificationProviderFactory):
        super().__init__(session)
        self.provider_factory = provider_factory
    
    async def create_webhook(self, webhook_data: WebhookCreate) -> WebhookRead:
        """Create a new webhook."""
        webhook = await self.webhook_repo.create_webhook(webhook_data, get_current_user_id())
        
        # Convert events back to list for response
        webhook_dict = webhook.model_dump()
        webhook_dict['events'] = webhook.get_events()
        
        return WebhookRead(**webhook_dict)
    
    async def get_webhook(self, webhook_id: int) -> WebhookRead:
        """Get webhook by ID."""
        webhook = await self.webhook_repo.get(webhook_id)
        if not webhook:
            raise NotFoundException(f"Webhook with ID {webhook_id} not found")
        
        # Convert events back to list for response
        webhook_dict = webhook.model_dump()
        webhook_dict['events'] = webhook.get_events()
        
        return WebhookRead(**webhook_dict)
    
    async def update_webhook(self, webhook_id: int, webhook_data: WebhookUpdate) -> WebhookRead:
        """Update a webhook."""
        webhook = await self.webhook_repo.update_webhook(webhook_id, webhook_data, get_current_user_id())
        if not webhook:
            raise NotFoundException(f"Webhook with ID {webhook_id} not found")
        
        # Convert events back to list for response
        webhook_dict = webhook.model_dump()
        webhook_dict['events'] = webhook.get_events()
        
        return WebhookRead(**webhook_dict)
    
    async def delete_webhook(self, webhook_id: int) -> bool:
        """Delete a webhook (soft delete)."""
        success = await self.webhook_repo.delete(webhook_id)
        if not success:
            raise NotFoundException(f"Webhook with ID {webhook_id} not found")
        
        return True
    
    async def search_webhooks(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[WebhookRead], int]:
        """Search webhooks with filters."""
        webhooks, total = await self.webhook_repo.search_webhooks(search, status, skip, limit)
        
        webhook_reads = []
        for webhook in webhooks:
            webhook_dict = webhook.model_dump()
            webhook_dict['events'] = webhook.get_events()
            webhook_reads.append(WebhookRead(**webhook_dict))
        
        return webhook_reads, total
    
    async def trigger_webhook(self, event_type: str, event_data: Dict[str, Any], event_id: str) -> int:
        """Trigger webhooks for a specific event."""
        webhooks = await self.webhook_repo.get_active_webhooks_for_event(event_type)
        triggered_count = 0
        
        webhook_provider = self.provider_factory.get_webhook_provider()
        
        for webhook in webhooks:
            try:
                # Create delivery record
                delivery = await self.webhook_delivery_repo.create_delivery_record(
                    webhook_id=webhook.id,
                    event_type=event_type,
                    event_id=event_id,
                    request_url=webhook.url,
                    request_method=webhook.http_method
                )
                
                # Send webhook
                result = await webhook_provider.send_webhook(
                    url=webhook.url,
                    event_type=event_type,
                    event_data=event_data,
                    secret=webhook.secret,
                    headers=webhook.get_headers(),
                    method=webhook.http_method,
                    timeout=webhook.timeout_seconds
                )
                
                # Update delivery record with response
                await self.webhook_delivery_repo.update_delivery_response(
                    delivery_id=delivery.id,
                    response_status=result.get("status_code", 0),
                    response_body=result.get("response_body"),
                    duration_ms=result.get("duration_ms"),
                    error_message=result.get("error")
                )
                
                # Update webhook status
                await self.webhook_repo.update_webhook_status(webhook.id, result["success"])
                
                if result["success"]:
                    triggered_count += 1
                    
            except Exception as e:
                # Update webhook as failed
                await self.webhook_repo.update_webhook_status(webhook.id, False)
        
        return triggered_count