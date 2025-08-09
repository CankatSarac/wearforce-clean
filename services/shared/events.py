import json
import asyncio
from datetime import datetime
from typing import Any, Dict, Optional, Callable, List
from dataclasses import dataclass, asdict
from enum import Enum

import nats
from nats.jetstream import JetStreamContext
import structlog

logger = structlog.get_logger()


class EventType(str, Enum):
    # CRM Events
    ACCOUNT_CREATED = "account.created"
    ACCOUNT_UPDATED = "account.updated"
    ACCOUNT_DELETED = "account.deleted"
    
    CONTACT_CREATED = "contact.created"
    CONTACT_UPDATED = "contact.updated"
    CONTACT_DELETED = "contact.deleted"
    
    DEAL_CREATED = "deal.created"
    DEAL_UPDATED = "deal.updated"
    DEAL_DELETED = "deal.deleted"
    DEAL_STATUS_CHANGED = "deal.status_changed"
    
    ACTIVITY_CREATED = "activity.created"
    ACTIVITY_UPDATED = "activity.updated"
    ACTIVITY_DELETED = "activity.deleted"
    
    # ERP Events
    PRODUCT_CREATED = "product.created"
    PRODUCT_UPDATED = "product.updated"
    PRODUCT_DELETED = "product.deleted"
    
    INVENTORY_UPDATED = "inventory.updated"
    STOCK_LOW = "stock.low"
    STOCK_OUT = "stock.out"
    
    ORDER_CREATED = "order.created"
    ORDER_UPDATED = "order.updated"
    ORDER_CANCELLED = "order.cancelled"
    ORDER_SHIPPED = "order.shipped"
    ORDER_DELIVERED = "order.delivered"
    
    PURCHASE_ORDER_CREATED = "purchase_order.created"
    PURCHASE_ORDER_UPDATED = "purchase_order.updated"
    
    # Notification Events
    EMAIL_SENT = "email.sent"
    SMS_SENT = "sms.sent"
    PUSH_SENT = "push.sent"
    NOTIFICATION_FAILED = "notification.failed"


@dataclass
class BaseEvent:
    """Base event structure."""
    event_id: str
    event_type: EventType
    service: str
    timestamp: datetime
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        result['event_type'] = self.event_type.value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseEvent':
        """Create event from dictionary."""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        data['event_type'] = EventType(data['event_type'])
        return cls(**data)


class EventPublisher:
    """NATS JetStream event publisher."""
    
    def __init__(self, nats_servers: List[str]):
        self.nats_servers = nats_servers
        self.nc: Optional[nats.NATS] = None
        self.js: Optional[JetStreamContext] = None
    
    async def connect(self):
        """Connect to NATS."""
        self.nc = await nats.connect(servers=self.nats_servers)
        self.js = self.nc.jetstream()
        
        # Create streams if they don't exist
        await self._create_streams()
        
        logger.info("Connected to NATS JetStream", servers=self.nats_servers)
    
    async def disconnect(self):
        """Disconnect from NATS."""
        if self.nc:
            await self.nc.close()
            logger.info("Disconnected from NATS")
    
    async def _create_streams(self):
        """Create JetStream streams for different event types."""
        streams = [
            {
                "name": "CRM_EVENTS",
                "subjects": ["crm.>"],
                "retention": "limits",
                "max_age": 7 * 24 * 60 * 60 * 1000000000,  # 7 days in nanoseconds
            },
            {
                "name": "ERP_EVENTS", 
                "subjects": ["erp.>"],
                "retention": "limits",
                "max_age": 7 * 24 * 60 * 60 * 1000000000,  # 7 days in nanoseconds
            },
            {
                "name": "NOTIFICATION_EVENTS",
                "subjects": ["notification.>"],
                "retention": "limits", 
                "max_age": 3 * 24 * 60 * 60 * 1000000000,  # 3 days in nanoseconds
            }
        ]
        
        for stream_config in streams:
            try:
                await self.js.add_stream(**stream_config)
                logger.info("Created stream", name=stream_config["name"])
            except Exception as e:
                if "stream name already in use" not in str(e):
                    logger.error("Failed to create stream", name=stream_config["name"], error=str(e))
    
    async def publish(self, event: BaseEvent) -> bool:
        """Publish an event to NATS JetStream."""
        if not self.js:
            logger.error("Not connected to NATS JetStream")
            return False
        
        try:
            subject = self._get_subject(event.service, event.event_type)
            message = json.dumps(event.to_dict())
            
            await self.js.publish(subject, message.encode())
            
            logger.info(
                "Published event",
                event_id=event.event_id,
                event_type=event.event_type,
                subject=subject
            )
            return True
            
        except Exception as e:
            logger.error(
                "Failed to publish event",
                event_id=event.event_id,
                event_type=event.event_type,
                error=str(e)
            )
            return False
    
    def _get_subject(self, service: str, event_type: EventType) -> str:
        """Get NATS subject for event."""
        return f"{service.replace('-', '_')}.{event_type.value.replace('.', '_')}"


class EventSubscriber:
    """NATS JetStream event subscriber."""
    
    def __init__(self, nats_servers: List[str], consumer_name: str):
        self.nats_servers = nats_servers
        self.consumer_name = consumer_name
        self.nc: Optional[nats.NATS] = None
        self.js: Optional[JetStreamContext] = None
        self.handlers: Dict[str, List[Callable]] = {}
    
    async def connect(self):
        """Connect to NATS."""
        self.nc = await nats.connect(servers=self.nats_servers)
        self.js = self.nc.jetstream()
        logger.info("Connected to NATS JetStream for subscription", consumer=self.consumer_name)
    
    async def disconnect(self):
        """Disconnect from NATS."""
        if self.nc:
            await self.nc.close()
            logger.info("Disconnected from NATS", consumer=self.consumer_name)
    
    def subscribe(self, event_pattern: str, handler: Callable[[BaseEvent], None]):
        """Subscribe to events matching a pattern."""
        if event_pattern not in self.handlers:
            self.handlers[event_pattern] = []
        self.handlers[event_pattern].append(handler)
    
    async def start_consuming(self):
        """Start consuming events."""
        if not self.js:
            raise RuntimeError("Not connected to NATS")
        
        for pattern in self.handlers.keys():
            asyncio.create_task(self._consume_pattern(pattern))
    
    async def _consume_pattern(self, pattern: str):
        """Consume events for a specific pattern."""
        try:
            consumer = await self.js.subscribe(
                subject=pattern,
                durable=self.consumer_name,
                manual_ack=True
            )
            
            logger.info("Started consuming events", pattern=pattern, consumer=self.consumer_name)
            
            async for msg in consumer.messages:
                try:
                    event_data = json.loads(msg.data.decode())
                    event = BaseEvent.from_dict(event_data)
                    
                    # Call all handlers for this pattern
                    for handler in self.handlers[pattern]:
                        try:
                            await handler(event) if asyncio.iscoroutinefunction(handler) else handler(event)
                        except Exception as e:
                            logger.error(
                                "Handler failed",
                                pattern=pattern,
                                event_id=event.event_id,
                                error=str(e)
                            )
                    
                    await msg.ack()
                    
                except Exception as e:
                    logger.error("Failed to process message", pattern=pattern, error=str(e))
                    await msg.nak()
                    
        except Exception as e:
            logger.error("Failed to consume events", pattern=pattern, error=str(e))


# Global event publisher
event_publisher: Optional[EventPublisher] = None


def init_events(nats_servers: List[str]) -> EventPublisher:
    """Initialize the event publisher."""
    global event_publisher
    event_publisher = EventPublisher(nats_servers)
    return event_publisher


def get_event_publisher() -> EventPublisher:
    """Get the global event publisher instance."""
    if event_publisher is None:
        raise RuntimeError("Events not initialized. Call init_events() first.")
    return event_publisher