from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import json

from sqlmodel import SQLModel, Field, Relationship
from pydantic import EmailStr, validator

from ..shared.database import TimestampMixin, SoftDeleteMixin, AuditMixin


class NotificationType(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"
    OPENED = "opened"
    CLICKED = "clicked"


class NotificationPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TemplateType(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"


class WebhookStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"
    SUSPENDED = "suspended"


# Database Models
class NotificationTemplate(SQLModel, TimestampMixin, SoftDeleteMixin, AuditMixin, table=True):
    __tablename__ = "notification_templates"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(nullable=False, index=True)
    template_type: TemplateType = Field(nullable=False)
    
    # Template content
    subject: Optional[str] = Field(default=None)  # For email templates
    content: str = Field(nullable=False)  # Template content with placeholders
    html_content: Optional[str] = Field(default=None)  # HTML content for emails
    
    # Template metadata
    description: Optional[str] = Field(default=None)
    language: str = Field(default="en", nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    
    # Variables that can be used in this template
    variables: Optional[str] = Field(default=None)  # JSON string of variable names and descriptions
    
    # Relationships
    notifications: List["Notification"] = Relationship(back_populates="template")
    
    def get_variables(self) -> Dict[str, str]:
        """Get template variables as a dictionary."""
        if self.variables:
            try:
                return json.loads(self.variables)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_variables(self, variables: Dict[str, str]):
        """Set template variables from a dictionary."""
        self.variables = json.dumps(variables)


class Notification(SQLModel, TimestampMixin, table=True):
    __tablename__ = "notifications"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    notification_type: NotificationType = Field(nullable=False)
    status: NotificationStatus = Field(default=NotificationStatus.PENDING, nullable=False)
    priority: NotificationPriority = Field(default=NotificationPriority.NORMAL, nullable=False)
    
    # Recipient information
    recipient_id: Optional[str] = Field(default=None)  # User/contact ID
    recipient_email: Optional[EmailStr] = Field(default=None)
    recipient_phone: Optional[str] = Field(default=None)
    recipient_device_token: Optional[str] = Field(default=None)  # For push notifications
    
    # Content
    subject: Optional[str] = Field(default=None)
    content: str = Field(nullable=False)
    html_content: Optional[str] = Field(default=None)
    
    # Template information
    template_id: Optional[int] = Field(default=None, foreign_key="notification_templates.id")
    template_variables: Optional[str] = Field(default=None)  # JSON string of variables used
    
    # Scheduling
    scheduled_at: Optional[datetime] = Field(default=None)
    sent_at: Optional[datetime] = Field(default=None)
    delivered_at: Optional[datetime] = Field(default=None)
    opened_at: Optional[datetime] = Field(default=None)
    clicked_at: Optional[datetime] = Field(default=None)
    
    # Tracking and metadata
    external_id: Optional[str] = Field(default=None)  # ID from external service (SendGrid, Twilio, etc.)
    error_message: Optional[str] = Field(default=None)
    retry_count: int = Field(default=0, nullable=False)
    max_retries: int = Field(default=3, nullable=False)
    
    # Context information
    source_service: Optional[str] = Field(default=None)  # Which service triggered this notification
    source_event: Optional[str] = Field(default=None)  # What event triggered this notification
    correlation_id: Optional[str] = Field(default=None)  # For tracking related notifications
    
    # Additional metadata
    metadata: Optional[str] = Field(default=None)  # JSON string for additional data
    
    # Relationships
    template: Optional[NotificationTemplate] = Relationship(back_populates="notifications")
    
    def get_template_variables(self) -> Dict[str, Any]:
        """Get template variables as a dictionary."""
        if self.template_variables:
            try:
                return json.loads(self.template_variables)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_template_variables(self, variables: Dict[str, Any]):
        """Set template variables from a dictionary."""
        self.template_variables = json.dumps(variables)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as a dictionary."""
        if self.metadata:
            try:
                return json.loads(self.metadata)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata: Dict[str, Any]):
        """Set metadata from a dictionary."""
        self.metadata = json.dumps(metadata)


class NotificationPreference(SQLModel, TimestampMixin, table=True):
    __tablename__ = "notification_preferences"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(nullable=False, index=True)
    
    # Notification type preferences
    email_enabled: bool = Field(default=True, nullable=False)
    sms_enabled: bool = Field(default=True, nullable=False)
    push_enabled: bool = Field(default=True, nullable=False)
    in_app_enabled: bool = Field(default=True, nullable=False)
    
    # Contact information
    email: Optional[EmailStr] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    device_tokens: Optional[str] = Field(default=None)  # JSON array of device tokens
    
    # Event-specific preferences
    preferences: Optional[str] = Field(default=None)  # JSON object with event-specific settings
    
    # Timezone for scheduling
    timezone: str = Field(default="UTC", nullable=False)
    
    def get_device_tokens(self) -> List[str]:
        """Get device tokens as a list."""
        if self.device_tokens:
            try:
                return json.loads(self.device_tokens)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_device_tokens(self, tokens: List[str]):
        """Set device tokens from a list."""
        self.device_tokens = json.dumps(tokens)
    
    def get_preferences(self) -> Dict[str, Any]:
        """Get preferences as a dictionary."""
        if self.preferences:
            try:
                return json.loads(self.preferences)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_preferences(self, preferences: Dict[str, Any]):
        """Set preferences from a dictionary."""
        self.preferences = json.dumps(preferences)


class Webhook(SQLModel, TimestampMixin, SoftDeleteMixin, AuditMixin, table=True):
    __tablename__ = "webhooks"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(nullable=False, index=True)
    url: str = Field(nullable=False)
    status: WebhookStatus = Field(default=WebhookStatus.ACTIVE, nullable=False)
    
    # Webhook configuration
    secret: Optional[str] = Field(default=None)  # For webhook signature verification
    events: str = Field(nullable=False)  # JSON array of events to listen for
    http_method: str = Field(default="POST", nullable=False)
    timeout_seconds: int = Field(default=30, nullable=False)
    
    # Headers to send with webhook
    headers: Optional[str] = Field(default=None)  # JSON object
    
    # Retry configuration
    max_retries: int = Field(default=3, nullable=False)
    retry_delay_seconds: int = Field(default=60, nullable=False)
    
    # Status tracking
    last_triggered_at: Optional[datetime] = Field(default=None)
    last_success_at: Optional[datetime] = Field(default=None)
    last_failure_at: Optional[datetime] = Field(default=None)
    failure_count: int = Field(default=0, nullable=False)
    
    # Description and metadata
    description: Optional[str] = Field(default=None)
    
    def get_events(self) -> List[str]:
        """Get events as a list."""
        try:
            return json.loads(self.events)
        except json.JSONDecodeError:
            return []
    
    def set_events(self, events: List[str]):
        """Set events from a list."""
        self.events = json.dumps(events)
    
    def get_headers(self) -> Dict[str, str]:
        """Get headers as a dictionary."""
        if self.headers:
            try:
                return json.loads(self.headers)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_headers(self, headers: Dict[str, str]):
        """Set headers from a dictionary."""
        self.headers = json.dumps(headers)


class WebhookDelivery(SQLModel, TimestampMixin, table=True):
    __tablename__ = "webhook_deliveries"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    webhook_id: int = Field(foreign_key="webhooks.id", nullable=False)
    
    # Event information
    event_type: str = Field(nullable=False)
    event_id: str = Field(nullable=False, index=True)
    
    # Delivery details
    request_url: str = Field(nullable=False)
    request_method: str = Field(nullable=False)
    request_headers: Optional[str] = Field(default=None)  # JSON object
    request_body: Optional[str] = Field(default=None)
    
    # Response details
    response_status: Optional[int] = Field(default=None)
    response_headers: Optional[str] = Field(default=None)  # JSON object
    response_body: Optional[str] = Field(default=None)
    
    # Timing
    sent_at: Optional[datetime] = Field(default=None)
    received_at: Optional[datetime] = Field(default=None)
    duration_ms: Optional[int] = Field(default=None)
    
    # Status and error tracking
    is_success: bool = Field(default=False, nullable=False)
    error_message: Optional[str] = Field(default=None)
    retry_count: int = Field(default=0, nullable=False)


# API Models
class NotificationTemplateCreate(SQLModel):
    name: str
    template_type: TemplateType
    subject: Optional[str] = None
    content: str
    html_content: Optional[str] = None
    description: Optional[str] = None
    language: str = "en"
    variables: Optional[Dict[str, str]] = None


class NotificationTemplateUpdate(SQLModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    content: Optional[str] = None
    html_content: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    variables: Optional[Dict[str, str]] = None


class NotificationTemplateRead(SQLModel):
    id: int
    name: str
    template_type: TemplateType
    subject: Optional[str]
    description: Optional[str]
    language: str
    is_active: bool
    variables: Optional[Dict[str, str]]
    created_at: datetime
    updated_at: datetime


class NotificationCreate(SQLModel):
    notification_type: NotificationType
    recipient_id: Optional[str] = None
    recipient_email: Optional[EmailStr] = None
    recipient_phone: Optional[str] = None
    subject: Optional[str] = None
    content: str
    html_content: Optional[str] = None
    template_id: Optional[int] = None
    template_variables: Optional[Dict[str, Any]] = None
    priority: NotificationPriority = NotificationPriority.NORMAL
    scheduled_at: Optional[datetime] = None
    source_service: Optional[str] = None
    source_event: Optional[str] = None


class NotificationUpdate(SQLModel):
    status: Optional[NotificationStatus] = None
    error_message: Optional[str] = None
    external_id: Optional[str] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None


class NotificationRead(SQLModel):
    id: int
    notification_type: NotificationType
    status: NotificationStatus
    priority: NotificationPriority
    recipient_email: Optional[EmailStr]
    recipient_phone: Optional[str]
    subject: Optional[str]
    scheduled_at: Optional[datetime]
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    retry_count: int
    source_service: Optional[str]
    source_event: Optional[str]
    created_at: datetime


class NotificationPreferenceCreate(SQLModel):
    user_id: str
    email_enabled: bool = True
    sms_enabled: bool = True
    push_enabled: bool = True
    in_app_enabled: bool = True
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    device_tokens: Optional[List[str]] = None
    timezone: str = "UTC"


class NotificationPreferenceUpdate(SQLModel):
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    in_app_enabled: Optional[bool] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    device_tokens: Optional[List[str]] = None
    timezone: Optional[str] = None


class NotificationPreferenceRead(SQLModel):
    id: int
    user_id: str
    email_enabled: bool
    sms_enabled: bool
    push_enabled: bool
    in_app_enabled: bool
    email: Optional[EmailStr]
    phone: Optional[str]
    device_tokens: Optional[List[str]]
    timezone: str
    created_at: datetime
    updated_at: datetime


class WebhookCreate(SQLModel):
    name: str
    url: str
    events: List[str]
    secret: Optional[str] = None
    http_method: str = "POST"
    timeout_seconds: int = 30
    headers: Optional[Dict[str, str]] = None
    max_retries: int = 3
    description: Optional[str] = None


class WebhookUpdate(SQLModel):
    name: Optional[str] = None
    url: Optional[str] = None
    events: Optional[List[str]] = None
    status: Optional[WebhookStatus] = None
    secret: Optional[str] = None
    timeout_seconds: Optional[int] = None
    headers: Optional[Dict[str, str]] = None
    max_retries: Optional[int] = None
    description: Optional[str] = None


class WebhookRead(SQLModel):
    id: int
    name: str
    url: str
    status: WebhookStatus
    events: List[str]
    timeout_seconds: int
    max_retries: int
    last_triggered_at: Optional[datetime]
    last_success_at: Optional[datetime]
    failure_count: int
    description: Optional[str]
    created_at: datetime


# Message queue models for background processing
class NotificationJob(SQLModel):
    notification_id: int
    retry_count: int = 0
    scheduled_at: Optional[datetime] = None


class WebhookJob(SQLModel):
    webhook_id: int
    event_type: str
    event_data: Dict[str, Any]
    retry_count: int = 0