import smtplib
import asyncio
import httpx
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict, Any, List
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

import structlog
from twilio.rest import Client as TwilioClient
from firebase_admin import messaging, credentials, initialize_app
import firebase_admin

from ..shared.config import NotificationSettings
from .models import Notification, NotificationStatus

logger = structlog.get_logger()


class NotificationProvider(ABC):
    """Abstract base class for notification providers."""
    
    @abstractmethod
    async def send(self, notification: Notification) -> bool:
        """Send a notification. Returns True if successful."""
        pass


class EmailProvider(NotificationProvider):
    """SMTP email provider."""
    
    def __init__(self, settings: NotificationSettings):
        self.settings = settings
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        self.smtp_use_tls = settings.smtp_use_tls
    
    async def send(self, notification: Notification) -> bool:
        """Send email notification."""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.smtp_username
            msg['To'] = notification.recipient_email
            msg['Subject'] = notification.subject or "Notification"
            
            # Add text content
            if notification.content:
                text_part = MIMEText(notification.content, 'plain')
                msg.attach(text_part)
            
            # Add HTML content if available
            if notification.html_content:
                html_part = MIMEText(notification.html_content, 'html')
                msg.attach(html_part)
            
            # Send email in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None, 
                self._send_smtp_email, 
                msg.as_string(),
                notification.recipient_email
            )
            
            if success:
                logger.info(
                    "Email sent successfully",
                    notification_id=notification.id,
                    recipient=notification.recipient_email
                )
            else:
                logger.error(
                    "Failed to send email",
                    notification_id=notification.id,
                    recipient=notification.recipient_email
                )
            
            return success
            
        except Exception as e:
            logger.error(
                "Email sending error",
                notification_id=notification.id,
                recipient=notification.recipient_email,
                error=str(e)
            )
            return False
    
    def _send_smtp_email(self, message: str, recipient: str) -> bool:
        """Send email using SMTP (blocking operation)."""
        try:
            # Create SMTP connection
            if self.smtp_use_tls:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
            
            # Login if credentials are provided
            if self.smtp_username and self.smtp_password:
                server.login(self.smtp_username, self.smtp_password)
            
            # Send email
            server.sendmail(self.smtp_username, recipient, message)
            server.quit()
            
            return True
            
        except Exception as e:
            logger.error("SMTP error", error=str(e))
            return False


class SMSProvider(NotificationProvider):
    """Twilio SMS provider."""
    
    def __init__(self, settings: NotificationSettings):
        self.settings = settings
        if settings.twilio_account_sid and settings.twilio_auth_token:
            self.client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
            self.from_number = settings.twilio_from_number
        else:
            self.client = None
            logger.warning("Twilio credentials not configured, SMS sending disabled")
    
    async def send(self, notification: Notification) -> bool:
        """Send SMS notification."""
        if not self.client:
            logger.error("Twilio client not configured", notification_id=notification.id)
            return False
        
        try:
            # Send SMS in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(
                None,
                self._send_twilio_sms,
                notification.recipient_phone,
                notification.content
            )
            
            if message:
                logger.info(
                    "SMS sent successfully",
                    notification_id=notification.id,
                    recipient=notification.recipient_phone,
                    twilio_sid=message.sid
                )
                return True
            else:
                logger.error(
                    "Failed to send SMS",
                    notification_id=notification.id,
                    recipient=notification.recipient_phone
                )
                return False
                
        except Exception as e:
            logger.error(
                "SMS sending error",
                notification_id=notification.id,
                recipient=notification.recipient_phone,
                error=str(e)
            )
            return False
    
    def _send_twilio_sms(self, to_number: str, content: str):
        """Send SMS using Twilio (blocking operation)."""
        try:
            message = self.client.messages.create(
                body=content,
                from_=self.from_number,
                to=to_number
            )
            return message
        except Exception as e:
            logger.error("Twilio SMS error", error=str(e))
            return None


class PushNotificationProvider(NotificationProvider):
    """Firebase Cloud Messaging push notification provider."""
    
    def __init__(self, settings: NotificationSettings):
        self.settings = settings
        self.initialized = False
        
        if settings.firebase_service_account_path:
            try:
                # Initialize Firebase Admin SDK
                if not firebase_admin._apps:
                    cred = credentials.Certificate(settings.firebase_service_account_path)
                    initialize_app(cred)
                
                self.initialized = True
                logger.info("Firebase Admin SDK initialized for push notifications")
                
            except Exception as e:
                logger.error("Failed to initialize Firebase Admin SDK", error=str(e))
        else:
            logger.warning("Firebase service account not configured, push notifications disabled")
    
    async def send(self, notification: Notification) -> bool:
        """Send push notification."""
        if not self.initialized:
            logger.error("Firebase not initialized", notification_id=notification.id)
            return False
        
        if not notification.recipient_device_token:
            logger.error("No device token provided", notification_id=notification.id)
            return False
        
        try:
            # Create FCM message
            message = messaging.Message(
                notification=messaging.Notification(
                    title=notification.subject or "Notification",
                    body=notification.content
                ),
                token=notification.recipient_device_token,
                data=notification.get_metadata()  # Additional data
            )
            
            # Send push notification in thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                messaging.send,
                message
            )
            
            if response:
                logger.info(
                    "Push notification sent successfully",
                    notification_id=notification.id,
                    fcm_response=response
                )
                return True
            else:
                logger.error(
                    "Failed to send push notification",
                    notification_id=notification.id
                )
                return False
                
        except Exception as e:
            logger.error(
                "Push notification error",
                notification_id=notification.id,
                error=str(e)
            )
            return False


class WebhookProvider(NotificationProvider):
    """HTTP webhook provider."""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def send_webhook(self, webhook_url: str, event_data: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> bool:
        """Send webhook notification."""
        try:
            response = await self.client.post(
                webhook_url,
                json=event_data,
                headers=headers or {}
            )
            
            success = 200 <= response.status_code < 300
            
            if success:
                logger.info("Webhook sent successfully", url=webhook_url, status=response.status_code)
            else:
                logger.error(
                    "Webhook failed",
                    url=webhook_url,
                    status=response.status_code,
                    response=response.text
                )
            
            return success
            
        except Exception as e:
            logger.error("Webhook error", url=webhook_url, error=str(e))
            return False
    
    async def send(self, notification: Notification) -> bool:
        """Send notification as webhook (not typically used directly)."""
        # This would require webhook URL to be stored in notification metadata
        metadata = notification.get_metadata()
        webhook_url = metadata.get('webhook_url')
        
        if not webhook_url:
            logger.error("No webhook URL in notification metadata", notification_id=notification.id)
            return False
        
        webhook_data = {
            "id": notification.id,
            "type": notification.notification_type,
            "content": notification.content,
            "recipient": notification.recipient_email or notification.recipient_phone,
            "created_at": notification.created_at.isoformat() if notification.created_at else None
        }
        
        return await self.send_webhook(webhook_url, webhook_data)
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class NotificationProviderFactory:
    """Factory for creating notification providers."""
    
    def __init__(self, settings: NotificationSettings):
        self.settings = settings
        self._providers = {}
    
    def get_email_provider(self) -> EmailProvider:
        """Get email provider instance."""
        if 'email' not in self._providers:
            self._providers['email'] = EmailProvider(self.settings)
        return self._providers['email']
    
    def get_sms_provider(self) -> SMSProvider:
        """Get SMS provider instance."""
        if 'sms' not in self._providers:
            self._providers['sms'] = SMSProvider(self.settings)
        return self._providers['sms']
    
    def get_push_provider(self) -> PushNotificationProvider:
        """Get push notification provider instance."""
        if 'push' not in self._providers:
            self._providers['push'] = PushNotificationProvider(self.settings)
        return self._providers['push']
    
    def get_webhook_provider(self) -> WebhookProvider:
        """Get webhook provider instance."""
        if 'webhook' not in self._providers:
            self._providers['webhook'] = WebhookProvider()
        return self._providers['webhook']
    
    async def close_all(self):
        """Close all providers."""
        for provider in self._providers.values():
            if hasattr(provider, 'close'):
                await provider.close()


# Template rendering utility
class TemplateRenderer:
    """Simple template renderer for notifications."""
    
    @staticmethod
    def render(template: str, variables: Dict[str, Any]) -> str:
        """Render template with variables using simple string substitution."""
        try:
            # Simple variable substitution using format()
            return template.format(**variables)
        except KeyError as e:
            logger.warning(f"Missing template variable: {e}")
            return template
        except Exception as e:
            logger.error(f"Template rendering error: {e}")
            return template
    
    @staticmethod
    def extract_variables(template: str) -> List[str]:
        """Extract variable names from a template string."""
        import re
        # Find all {variable_name} patterns
        pattern = r'\{([^}]+)\}'
        return list(set(re.findall(pattern, template)))