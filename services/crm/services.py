import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from ..shared.events import BaseEvent, EventType, get_event_publisher
from ..shared.exceptions import NotFoundException, ValidationException
from ..shared.middleware import get_current_user_id
from .models import (
    Account, AccountCreate, AccountUpdate, AccountRead,
    Contact, ContactCreate, ContactUpdate, ContactRead,
    Deal, DealCreate, DealUpdate, DealRead, DealStage,
    Activity, ActivityCreate, ActivityUpdate, ActivityRead,
)
from .repositories import AccountRepository, ContactRepository, DealRepository, ActivityRepository


class CRMService:
    """Main CRM service with business logic."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.account_repo = AccountRepository(session)
        self.contact_repo = ContactRepository(session)
        self.deal_repo = DealRepository(session)
        self.activity_repo = ActivityRepository(session)
        self.event_publisher = get_event_publisher()
    
    async def _publish_event(self, event_type: EventType, data: Dict[str, Any], entity_id: int = None):
        """Publish an event."""
        event = BaseEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            service="crm-service",
            timestamp=datetime.utcnow(),
            data=data,
            user_id=get_current_user_id(),
            metadata={"entity_id": entity_id} if entity_id else None
        )
        await self.event_publisher.publish(event)


class AccountService(CRMService):
    """Account management service."""
    
    async def create_account(self, account_data: AccountCreate) -> AccountRead:
        """Create a new account."""
        # Check if account with same name already exists
        existing = await self.account_repo.get_by_name(account_data.name)
        if existing:
            raise ValidationException(f"Account with name '{account_data.name}' already exists")
        
        account = await self.account_repo.create_account(account_data, get_current_user_id())
        
        # Publish event
        await self._publish_event(
            EventType.ACCOUNT_CREATED,
            {"account": account.model_dump()},
            account.id
        )
        
        return AccountRead.model_validate(account)
    
    async def get_account(self, account_id: int) -> AccountRead:
        """Get account by ID."""
        account = await self.account_repo.get(account_id)
        if not account:
            raise NotFoundException(f"Account with ID {account_id} not found")
        
        return AccountRead.model_validate(account)
    
    async def update_account(self, account_id: int, account_data: AccountUpdate) -> AccountRead:
        """Update an account."""
        # Check if new name conflicts with existing account
        if account_data.name:
            existing = await self.account_repo.get_by_name(account_data.name)
            if existing and existing.id != account_id:
                raise ValidationException(f"Account with name '{account_data.name}' already exists")
        
        account = await self.account_repo.update_account(account_id, account_data, get_current_user_id())
        if not account:
            raise NotFoundException(f"Account with ID {account_id} not found")
        
        # Publish event
        await self._publish_event(
            EventType.ACCOUNT_UPDATED,
            {"account": account.model_dump()},
            account.id
        )
        
        return AccountRead.model_validate(account)
    
    async def delete_account(self, account_id: int) -> bool:
        """Delete an account (soft delete)."""
        success = await self.account_repo.delete(account_id)
        if not success:
            raise NotFoundException(f"Account with ID {account_id} not found")
        
        # Publish event
        await self._publish_event(
            EventType.ACCOUNT_DELETED,
            {"account_id": account_id},
            account_id
        )
        
        return True
    
    async def search_accounts(
        self,
        search: Optional[str] = None,
        account_type: Optional[str] = None,
        status: Optional[str] = None,
        industry: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[AccountRead], int]:
        """Search accounts with filters."""
        accounts, total = await self.account_repo.search_accounts(
            search, account_type, status, industry, skip, limit
        )
        
        account_reads = [AccountRead.model_validate(account) for account in accounts]
        return account_reads, total
    
    async def get_account_hierarchy(self, account_id: int) -> Dict[str, Any]:
        """Get account with its parent and children."""
        account = await self.account_repo.get(account_id)
        if not account:
            raise NotFoundException(f"Account with ID {account_id} not found")
        
        # Get parent account
        parent = None
        if account.parent_account_id:
            parent = await self.account_repo.get(account.parent_account_id)
        
        # Get child accounts
        children = await self.account_repo.get_child_accounts(account_id)
        
        return {
            "account": AccountRead.model_validate(account),
            "parent": AccountRead.model_validate(parent) if parent else None,
            "children": [AccountRead.model_validate(child) for child in children]
        }


class ContactService(CRMService):
    """Contact management service."""
    
    async def create_contact(self, contact_data: ContactCreate) -> ContactRead:
        """Create a new contact."""
        # Check if contact with same email already exists
        if contact_data.email:
            existing = await self.contact_repo.get_by_email(contact_data.email)
            if existing:
                raise ValidationException(f"Contact with email '{contact_data.email}' already exists")
        
        contact = await self.contact_repo.create_contact(contact_data, get_current_user_id())
        
        # Publish event
        await self._publish_event(
            EventType.CONTACT_CREATED,
            {"contact": contact.model_dump()},
            contact.id
        )
        
        return ContactRead.model_validate(contact)
    
    async def get_contact(self, contact_id: int) -> ContactRead:
        """Get contact by ID."""
        contact = await self.contact_repo.get(contact_id)
        if not contact:
            raise NotFoundException(f"Contact with ID {contact_id} not found")
        
        return ContactRead.model_validate(contact)
    
    async def update_contact(self, contact_id: int, contact_data: ContactUpdate) -> ContactRead:
        """Update a contact."""
        # Check if new email conflicts with existing contact
        if contact_data.email:
            existing = await self.contact_repo.get_by_email(contact_data.email)
            if existing and existing.id != contact_id:
                raise ValidationException(f"Contact with email '{contact_data.email}' already exists")
        
        contact = await self.contact_repo.update_contact(contact_id, contact_data, get_current_user_id())
        if not contact:
            raise NotFoundException(f"Contact with ID {contact_id} not found")
        
        # Publish event
        await self._publish_event(
            EventType.CONTACT_UPDATED,
            {"contact": contact.model_dump()},
            contact.id
        )
        
        return ContactRead.model_validate(contact)
    
    async def delete_contact(self, contact_id: int) -> bool:
        """Delete a contact (soft delete)."""
        success = await self.contact_repo.delete(contact_id)
        if not success:
            raise NotFoundException(f"Contact with ID {contact_id} not found")
        
        # Publish event
        await self._publish_event(
            EventType.CONTACT_DELETED,
            {"contact_id": contact_id},
            contact_id
        )
        
        return True
    
    async def search_contacts(
        self,
        search: Optional[str] = None,
        account_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[ContactRead], int]:
        """Search contacts with filters."""
        contacts, total = await self.contact_repo.search_contacts(search, account_id, skip, limit)
        
        contact_reads = [ContactRead.model_validate(contact) for contact in contacts]
        return contact_reads, total


class DealService(CRMService):
    """Deal management service."""
    
    async def create_deal(self, deal_data: DealCreate) -> DealRead:
        """Create a new deal."""
        deal = await self.deal_repo.create_deal(deal_data, get_current_user_id())
        
        # Publish event
        await self._publish_event(
            EventType.DEAL_CREATED,
            {"deal": deal.model_dump()},
            deal.id
        )
        
        return DealRead.model_validate(deal)
    
    async def get_deal(self, deal_id: int) -> DealRead:
        """Get deal by ID."""
        deal = await self.deal_repo.get(deal_id)
        if not deal:
            raise NotFoundException(f"Deal with ID {deal_id} not found")
        
        return DealRead.model_validate(deal)
    
    async def update_deal(self, deal_id: int, deal_data: DealUpdate) -> DealRead:
        """Update a deal."""
        # Get current deal to check for stage changes
        current_deal = await self.deal_repo.get(deal_id)
        if not current_deal:
            raise NotFoundException(f"Deal with ID {deal_id} not found")
        
        deal = await self.deal_repo.update_deal(deal_id, deal_data, get_current_user_id())
        
        # Publish events
        await self._publish_event(
            EventType.DEAL_UPDATED,
            {"deal": deal.model_dump()},
            deal.id
        )
        
        # Check if stage changed
        if deal_data.stage and current_deal.stage != deal_data.stage:
            await self._publish_event(
                EventType.DEAL_STATUS_CHANGED,
                {
                    "deal_id": deal.id,
                    "previous_stage": current_deal.stage.value,
                    "new_stage": deal.stage.value
                },
                deal.id
            )
        
        return DealRead.model_validate(deal)
    
    async def delete_deal(self, deal_id: int) -> bool:
        """Delete a deal (soft delete)."""
        success = await self.deal_repo.delete(deal_id)
        if not success:
            raise NotFoundException(f"Deal with ID {deal_id} not found")
        
        # Publish event
        await self._publish_event(
            EventType.DEAL_DELETED,
            {"deal_id": deal_id},
            deal_id
        )
        
        return True
    
    async def search_deals(
        self,
        search: Optional[str] = None,
        stage: Optional[str] = None,
        account_id: Optional[int] = None,
        contact_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[DealRead], int]:
        """Search deals with filters."""
        deals, total = await self.deal_repo.search_deals(
            search, stage, account_id, contact_id, None, None, skip, limit
        )
        
        deal_reads = [DealRead.model_validate(deal) for deal in deals]
        return deal_reads, total
    
    async def get_pipeline_summary(self) -> Dict[str, Any]:
        """Get sales pipeline summary."""
        return await self.deal_repo.get_pipeline_summary()
    
    async def calculate_lead_score(self, deal_id: int) -> int:
        """Calculate lead score for a deal."""
        deal = await self.deal_repo.get(deal_id)
        if not deal:
            raise NotFoundException(f"Deal with ID {deal_id} not found")
        
        score = 0
        
        # Score based on deal amount
        if deal.amount:
            if deal.amount >= 100000:
                score += 30
            elif deal.amount >= 50000:
                score += 20
            elif deal.amount >= 10000:
                score += 10
        
        # Score based on probability
        if deal.probability:
            score += min(deal.probability // 10, 25)  # Max 25 points
        
        # Score based on stage
        stage_scores = {
            DealStage.LEAD: 5,
            DealStage.QUALIFIED: 15,
            DealStage.PROPOSAL: 25,
            DealStage.NEGOTIATION: 35,
            DealStage.CLOSED_WON: 100,
            DealStage.CLOSED_LOST: 0
        }
        score += stage_scores.get(deal.stage, 0)
        
        # Score based on account size (if available)
        if deal.account and deal.account.employees:
            if deal.account.employees >= 1000:
                score += 20
            elif deal.account.employees >= 100:
                score += 15
            elif deal.account.employees >= 50:
                score += 10
        
        # Update the deal with calculated score
        await self.deal_repo.update(deal_id, {"lead_score": min(score, 100)})
        
        return min(score, 100)


class ActivityService(CRMService):
    """Activity management service."""
    
    async def create_activity(self, activity_data: ActivityCreate) -> ActivityRead:
        """Create a new activity."""
        activity = await self.activity_repo.create_activity(activity_data, get_current_user_id())
        
        # Publish event
        await self._publish_event(
            EventType.ACTIVITY_CREATED,
            {"activity": activity.model_dump()},
            activity.id
        )
        
        return ActivityRead.model_validate(activity)
    
    async def get_activity(self, activity_id: int) -> ActivityRead:
        """Get activity by ID."""
        activity = await self.activity_repo.get(activity_id)
        if not activity:
            raise NotFoundException(f"Activity with ID {activity_id} not found")
        
        return ActivityRead.model_validate(activity)
    
    async def update_activity(self, activity_id: int, activity_data: ActivityUpdate) -> ActivityRead:
        """Update an activity."""
        activity = await self.activity_repo.update_activity(activity_id, activity_data, get_current_user_id())
        if not activity:
            raise NotFoundException(f"Activity with ID {activity_id} not found")
        
        # Publish event
        await self._publish_event(
            EventType.ACTIVITY_UPDATED,
            {"activity": activity.model_dump()},
            activity.id
        )
        
        return ActivityRead.model_validate(activity)
    
    async def delete_activity(self, activity_id: int) -> bool:
        """Delete an activity (soft delete)."""
        success = await self.activity_repo.delete(activity_id)
        if not success:
            raise NotFoundException(f"Activity with ID {activity_id} not found")
        
        # Publish event
        await self._publish_event(
            EventType.ACTIVITY_DELETED,
            {"activity_id": activity_id},
            activity_id
        )
        
        return True
    
    async def search_activities(
        self,
        search: Optional[str] = None,
        activity_type: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[ActivityRead], int]:
        """Search activities with filters."""
        activities, total = await self.activity_repo.search_activities(
            search, activity_type, status, None, None, None, skip, limit
        )
        
        activity_reads = [ActivityRead.model_validate(activity) for activity in activities]
        return activity_reads, total
    
    async def get_upcoming_activities(self, days: int = 7) -> List[ActivityRead]:
        """Get upcoming activities."""
        activities = await self.activity_repo.get_upcoming_activities(get_current_user_id(), days)
        return [ActivityRead.model_validate(activity) for activity in activities]