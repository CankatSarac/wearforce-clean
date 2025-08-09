from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func, and_, or_

from ..shared.database import BaseRepository
from ..shared.exceptions import NotFoundException, ValidationException
from .models import (
    NotificationTemplate, NotificationTemplateCreate, NotificationTemplateUpdate, TemplateType,
    Notification, NotificationCreate, NotificationUpdate, NotificationStatus, NotificationType,
    NotificationPreference, NotificationPreferenceCreate, NotificationPreferenceUpdate,
    Webhook, WebhookCreate, WebhookUpdate, WebhookStatus,
    WebhookDelivery
)


class NotificationTemplateRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, NotificationTemplate)
    
    async def create_template(self, template_data: NotificationTemplateCreate, created_by: str = None) -> NotificationTemplate:
        """Create a new notification template."""
        data = template_data.model_dump(exclude_unset=True)
        if created_by:
            data['created_by'] = created_by
        
        # Handle variables
        if 'variables' in data and data['variables']:
            template = NotificationTemplate(**{k: v for k, v in data.items() if k != 'variables'})
            template.set_variables(data['variables'])
        else:
            template = NotificationTemplate(**data)
        
        self.session.add(template)
        await self.session.flush()
        await self.session.refresh(template)
        return template
    
    async def update_template(self, template_id: int, template_data: NotificationTemplateUpdate, updated_by: str = None) -> Optional[NotificationTemplate]:
        """Update a notification template."""
        template = await self.get(template_id)
        if not template:
            return None
        
        data = template_data.model_dump(exclude_unset=True)
        if updated_by:
            data['updated_by'] = updated_by
        
        # Handle variables separately
        variables = data.pop('variables', None)
        if variables is not None:
            template.set_variables(variables)
        
        # Update other fields
        for key, value in data.items():
            if hasattr(template, key):
                setattr(template, key, value)
        
        if hasattr(template, 'updated_at'):
            template.updated_at = datetime.utcnow()
        
        await self.session.flush()
        await self.session.refresh(template)
        return template
    
    async def get_by_name_and_type(self, name: str, template_type: TemplateType) -> Optional[NotificationTemplate]:
        """Get template by name and type."""
        statement = select(NotificationTemplate).where(
            and_(
                NotificationTemplate.name == name,
                NotificationTemplate.template_type == template_type,
                NotificationTemplate.is_deleted == False,
                NotificationTemplate.is_active == True
            )
        )
        result = await self.session.exec(statement)
        return result.first()
    
    async def search_templates(
        self,
        search: Optional[str] = None,
        template_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[NotificationTemplate], int]:
        """Search notification templates with filters."""
        statement = select(NotificationTemplate).where(NotificationTemplate.is_deleted == False)
        
        if search:
            search_term = f"%{search}%"
            statement = statement.where(
                or_(
                    NotificationTemplate.name.ilike(search_term),
                    NotificationTemplate.description.ilike(search_term),
                    NotificationTemplate.content.ilike(search_term)
                )
            )
        
        if template_type:
            statement = statement.where(NotificationTemplate.template_type == template_type)
        
        if is_active is not None:
            statement = statement.where(NotificationTemplate.is_active == is_active)
        
        # Get total count
        count_statement = select(func.count()).select_from(statement.subquery())
        count_result = await self.session.exec(count_statement)
        total = count_result.first()
        
        # Get paginated results
        statement = statement.offset(skip).limit(limit).order_by(NotificationTemplate.name)
        result = await self.session.exec(statement)
        templates = result.all()
        
        return templates, total


class NotificationRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Notification)
    
    async def create_notification(self, notification_data: NotificationCreate) -> Notification:
        """Create a new notification."""
        data = notification_data.model_dump(exclude_unset=True)
        
        # Handle template variables
        template_variables = data.pop('template_variables', None)
        
        notification = Notification(**data)
        
        if template_variables:
            notification.set_template_variables(template_variables)
        
        self.session.add(notification)
        await self.session.flush()
        await self.session.refresh(notification)
        return notification
    
    async def update_notification(self, notification_id: int, notification_data: NotificationUpdate) -> Optional[Notification]:
        """Update a notification."""
        notification = await self.get(notification_id)
        if not notification:
            return None
        
        data = notification_data.model_dump(exclude_unset=True)
        
        for key, value in data.items():
            if hasattr(notification, key):
                setattr(notification, key, value)
        
        await self.session.flush()
        await self.session.refresh(notification)
        return notification
    
    async def get_pending_notifications(self, limit: int = 100) -> List[Notification]:
        """Get pending notifications ready to be sent."""
        statement = select(Notification).where(
            and_(
                Notification.status == NotificationStatus.PENDING,
                or_(
                    Notification.scheduled_at.is_(None),
                    Notification.scheduled_at <= datetime.utcnow()
                ),
                Notification.retry_count < Notification.max_retries
            )
        ).limit(limit).order_by(Notification.created_at)
        
        result = await self.session.exec(statement)
        return result.all()
    
    async def get_failed_notifications_for_retry(self, limit: int = 50) -> List[Notification]:
        """Get failed notifications that can be retried."""
        # Retry after exponential backoff: 5 minutes, 15 minutes, 45 minutes
        retry_delays = [5, 15, 45]  # minutes
        
        conditions = []
        for retry_count in range(len(retry_delays)):
            delay_minutes = retry_delays[retry_count] if retry_count < len(retry_delays) else retry_delays[-1]
            retry_time = datetime.utcnow() - timedelta(minutes=delay_minutes)
            
            conditions.append(
                and_(
                    Notification.retry_count == retry_count,
                    Notification.updated_at <= retry_time
                )
            )
        
        statement = select(Notification).where(
            and_(
                Notification.status == NotificationStatus.FAILED,
                Notification.retry_count < Notification.max_retries,
                or_(*conditions)
            )
        ).limit(limit).order_by(Notification.updated_at)
        
        result = await self.session.exec(statement)
        return result.all()
    
    async def search_notifications(
        self,
        search: Optional[str] = None,
        notification_type: Optional[str] = None,
        status: Optional[str] = None,
        recipient: Optional[str] = None,
        source_service: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[Notification], int]:
        """Search notifications with filters."""
        statement = select(Notification)
        
        conditions = []
        
        if search:
            search_term = f"%{search}%"
            conditions.append(
                or_(
                    Notification.subject.ilike(search_term),
                    Notification.content.ilike(search_term),
                    Notification.recipient_email.ilike(search_term),
                    Notification.recipient_phone.ilike(search_term)
                )
            )
        
        if notification_type:
            conditions.append(Notification.notification_type == notification_type)
        
        if status:
            conditions.append(Notification.status == status)
        
        if recipient:
            recipient_term = f"%{recipient}%"
            conditions.append(
                or_(
                    Notification.recipient_email.ilike(recipient_term),
                    Notification.recipient_phone.ilike(recipient_term),
                    Notification.recipient_id.ilike(recipient_term)
                )
            )
        
        if source_service:
            conditions.append(Notification.source_service == source_service)
        
        if date_from:
            conditions.append(Notification.created_at >= date_from)
        
        if date_to:
            conditions.append(Notification.created_at <= date_to)
        
        if conditions:
            statement = statement.where(and_(*conditions))
        
        # Get total count
        count_statement = select(func.count()).select_from(statement.subquery())
        count_result = await self.session.exec(count_statement)
        total = count_result.first()
        
        # Get paginated results
        statement = statement.offset(skip).limit(limit).order_by(Notification.created_at.desc())
        result = await self.session.exec(statement)
        notifications = result.all()
        
        return notifications, total
    
    async def get_notification_stats(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get notification statistics."""
        statement = select(
            Notification.status,
            Notification.notification_type,
            func.count(Notification.id).label('count')
        )
        
        if date_from:
            statement = statement.where(Notification.created_at >= date_from)
        
        if date_to:
            statement = statement.where(Notification.created_at <= date_to)
        
        statement = statement.group_by(Notification.status, Notification.notification_type)
        
        result = await self.session.exec(statement)
        rows = result.all()
        
        stats = {
            'by_status': {},
            'by_type': {},
            'total': 0
        }
        
        for row in rows:
            status = row.status.value
            notification_type = row.notification_type.value
            count = row.count
            
            if status not in stats['by_status']:
                stats['by_status'][status] = 0
            stats['by_status'][status] += count
            
            if notification_type not in stats['by_type']:
                stats['by_type'][notification_type] = 0
            stats['by_type'][notification_type] += count
            
            stats['total'] += count
        
        return stats


class NotificationPreferenceRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, NotificationPreference)
    
    async def create_preference(self, preference_data: NotificationPreferenceCreate) -> NotificationPreference:
        """Create a new notification preference."""
        data = preference_data.model_dump(exclude_unset=True)
        
        # Handle device tokens
        device_tokens = data.pop('device_tokens', None)
        
        preference = NotificationPreference(**data)
        
        if device_tokens:
            preference.set_device_tokens(device_tokens)
        
        self.session.add(preference)
        await self.session.flush()
        await self.session.refresh(preference)
        return preference
    
    async def update_preference(self, preference_id: int, preference_data: NotificationPreferenceUpdate) -> Optional[NotificationPreference]:
        """Update notification preferences."""
        preference = await self.get(preference_id)
        if not preference:
            return None
        
        data = preference_data.model_dump(exclude_unset=True)
        
        # Handle device tokens separately
        device_tokens = data.pop('device_tokens', None)
        if device_tokens is not None:
            preference.set_device_tokens(device_tokens)
        
        # Update other fields
        for key, value in data.items():
            if hasattr(preference, key):
                setattr(preference, key, value)
        
        if hasattr(preference, 'updated_at'):
            preference.updated_at = datetime.utcnow()
        
        await self.session.flush()
        await self.session.refresh(preference)
        return preference
    
    async def get_by_user_id(self, user_id: str) -> Optional[NotificationPreference]:
        """Get notification preferences by user ID."""
        statement = select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        result = await self.session.exec(statement)
        return result.first()
    
    async def get_users_with_notification_enabled(
        self, 
        notification_type: NotificationType,
        user_ids: Optional[List[str]] = None
    ) -> List[NotificationPreference]:
        """Get users who have a specific notification type enabled."""
        type_field_map = {
            NotificationType.EMAIL: NotificationPreference.email_enabled,
            NotificationType.SMS: NotificationPreference.sms_enabled,
            NotificationType.PUSH: NotificationPreference.push_enabled,
            NotificationType.IN_APP: NotificationPreference.in_app_enabled,
        }
        
        type_field = type_field_map.get(notification_type)
        if not type_field:
            return []
        
        statement = select(NotificationPreference).where(type_field == True)
        
        if user_ids:
            statement = statement.where(NotificationPreference.user_id.in_(user_ids))
        
        result = await self.session.exec(statement)
        return result.all()


class WebhookRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Webhook)
    
    async def create_webhook(self, webhook_data: WebhookCreate, created_by: str = None) -> Webhook:
        """Create a new webhook."""
        data = webhook_data.model_dump(exclude_unset=True)
        if created_by:
            data['created_by'] = created_by
        
        # Handle events and headers
        events = data.pop('events', None)
        headers = data.pop('headers', None)
        
        webhook = Webhook(**data)
        
        if events:
            webhook.set_events(events)
        
        if headers:
            webhook.set_headers(headers)
        
        self.session.add(webhook)
        await self.session.flush()
        await self.session.refresh(webhook)
        return webhook
    
    async def update_webhook(self, webhook_id: int, webhook_data: WebhookUpdate, updated_by: str = None) -> Optional[Webhook]:
        """Update a webhook."""
        webhook = await self.get(webhook_id)
        if not webhook:
            return None
        
        data = webhook_data.model_dump(exclude_unset=True)
        if updated_by:
            data['updated_by'] = updated_by
        
        # Handle events and headers separately
        events = data.pop('events', None)
        headers = data.pop('headers', None)
        
        if events is not None:
            webhook.set_events(events)
        
        if headers is not None:
            webhook.set_headers(headers)
        
        # Update other fields
        for key, value in data.items():
            if hasattr(webhook, key):
                setattr(webhook, key, value)
        
        if hasattr(webhook, 'updated_at'):
            webhook.updated_at = datetime.utcnow()
        
        await self.session.flush()
        await self.session.refresh(webhook)
        return webhook
    
    async def get_active_webhooks_for_event(self, event_type: str) -> List[Webhook]:
        """Get active webhooks that listen for a specific event."""
        statement = select(Webhook).where(
            and_(
                Webhook.status == WebhookStatus.ACTIVE,
                Webhook.is_deleted == False
            )
        )
        
        result = await self.session.exec(statement)
        webhooks = result.all()
        
        # Filter by event type (since events are stored as JSON)
        matching_webhooks = []
        for webhook in webhooks:
            webhook_events = webhook.get_events()
            if event_type in webhook_events or '*' in webhook_events:
                matching_webhooks.append(webhook)
        
        return matching_webhooks
    
    async def update_webhook_status(self, webhook_id: int, success: bool):
        """Update webhook status after delivery attempt."""
        webhook = await self.get(webhook_id)
        if not webhook:
            return
        
        webhook.last_triggered_at = datetime.utcnow()
        
        if success:
            webhook.last_success_at = datetime.utcnow()
            webhook.failure_count = 0
            if webhook.status == WebhookStatus.FAILED:
                webhook.status = WebhookStatus.ACTIVE
        else:
            webhook.last_failure_at = datetime.utcnow()
            webhook.failure_count += 1
            
            # Suspend webhook after too many failures
            if webhook.failure_count >= 10:
                webhook.status = WebhookStatus.SUSPENDED
            elif webhook.failure_count >= 5:
                webhook.status = WebhookStatus.FAILED
    
    async def search_webhooks(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[Webhook], int]:
        """Search webhooks with filters."""
        statement = select(Webhook).where(Webhook.is_deleted == False)
        
        if search:
            search_term = f"%{search}%"
            statement = statement.where(
                or_(
                    Webhook.name.ilike(search_term),
                    Webhook.url.ilike(search_term),
                    Webhook.description.ilike(search_term)
                )
            )
        
        if status:
            statement = statement.where(Webhook.status == status)
        
        # Get total count
        count_statement = select(func.count()).select_from(statement.subquery())
        count_result = await self.session.exec(count_statement)
        total = count_result.first()
        
        # Get paginated results
        statement = statement.offset(skip).limit(limit).order_by(Webhook.name)
        result = await self.session.exec(statement)
        webhooks = result.all()
        
        return webhooks, total


class WebhookDeliveryRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, WebhookDelivery)
    
    async def create_delivery_record(
        self,
        webhook_id: int,
        event_type: str,
        event_id: str,
        request_url: str,
        request_method: str = "POST",
        request_headers: Optional[Dict[str, str]] = None,
        request_body: Optional[str] = None
    ) -> WebhookDelivery:
        """Create a webhook delivery record."""
        delivery = WebhookDelivery(
            webhook_id=webhook_id,
            event_type=event_type,
            event_id=event_id,
            request_url=request_url,
            request_method=request_method,
            sent_at=datetime.utcnow()
        )
        
        if request_headers:
            delivery.request_headers = json.dumps(request_headers)
        
        if request_body:
            delivery.request_body = request_body
        
        self.session.add(delivery)
        await self.session.flush()
        await self.session.refresh(delivery)
        return delivery
    
    async def update_delivery_response(
        self,
        delivery_id: int,
        response_status: int,
        response_headers: Optional[Dict[str, str]] = None,
        response_body: Optional[str] = None,
        duration_ms: Optional[int] = None,
        error_message: Optional[str] = None
    ):
        """Update webhook delivery with response information."""
        delivery = await self.get(delivery_id)
        if not delivery:
            return
        
        delivery.response_status = response_status
        delivery.received_at = datetime.utcnow()
        delivery.is_success = 200 <= response_status < 300
        
        if response_headers:
            delivery.response_headers = json.dumps(response_headers)
        
        if response_body:
            delivery.response_body = response_body
        
        if duration_ms:
            delivery.duration_ms = duration_ms
        
        if error_message:
            delivery.error_message = error_message