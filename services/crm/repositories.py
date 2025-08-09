from typing import Optional, List, Dict, Any
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func, and_, or_

from ..shared.database import BaseRepository
from ..shared.exceptions import NotFoundException, ValidationException
from .models import (
    Account, AccountCreate, AccountUpdate,
    Contact, ContactCreate, ContactUpdate,
    Deal, DealCreate, DealUpdate, DealStage,
    Activity, ActivityCreate, ActivityUpdate, ActivityStatus
)


class AccountRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Account)
    
    async def create_account(self, account_data: AccountCreate, created_by: str = None) -> Account:
        """Create a new account."""
        data = account_data.model_dump(exclude_unset=True)
        if created_by:
            data['created_by'] = created_by
        return await self.create(data)
    
    async def update_account(self, account_id: int, account_data: AccountUpdate, updated_by: str = None) -> Optional[Account]:
        """Update an account."""
        data = account_data.model_dump(exclude_unset=True)
        if updated_by:
            data['updated_by'] = updated_by
        return await self.update(account_id, data)
    
    async def get_by_name(self, name: str) -> Optional[Account]:
        """Get account by name."""
        statement = select(Account).where(
            and_(Account.name == name, Account.is_deleted == False)
        )
        result = await self.session.exec(statement)
        return result.first()
    
    async def search_accounts(
        self, 
        search: Optional[str] = None,
        account_type: Optional[str] = None,
        status: Optional[str] = None,
        industry: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[Account], int]:
        """Search accounts with filters."""
        statement = select(Account).where(Account.is_deleted == False)
        
        if search:
            search_term = f"%{search}%"
            statement = statement.where(
                or_(
                    Account.name.ilike(search_term),
                    Account.website.ilike(search_term),
                    Account.description.ilike(search_term)
                )
            )
        
        if account_type:
            statement = statement.where(Account.account_type == account_type)
        
        if status:
            statement = statement.where(Account.status == status)
            
        if industry:
            statement = statement.where(Account.industry == industry)
        
        # Get total count
        count_statement = select(func.count()).select_from(statement.subquery())
        count_result = await self.session.exec(count_statement)
        total = count_result.first()
        
        # Get paginated results
        statement = statement.offset(skip).limit(limit).order_by(Account.name)
        result = await self.session.exec(statement)
        accounts = result.all()
        
        return accounts, total
    
    async def get_child_accounts(self, parent_id: int) -> List[Account]:
        """Get child accounts for a parent account."""
        statement = select(Account).where(
            and_(
                Account.parent_account_id == parent_id,
                Account.is_deleted == False
            )
        ).order_by(Account.name)
        result = await self.session.exec(statement)
        return result.all()


class ContactRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Contact)
    
    async def create_contact(self, contact_data: ContactCreate, created_by: str = None) -> Contact:
        """Create a new contact."""
        data = contact_data.model_dump(exclude_unset=True)
        if created_by:
            data['created_by'] = created_by
        
        # Validate account exists if provided
        if data.get('account_id'):
            account_repo = AccountRepository(self.session)
            account = await account_repo.get(data['account_id'])
            if not account:
                raise ValidationException(f"Account with ID {data['account_id']} not found")
        
        return await self.create(data)
    
    async def update_contact(self, contact_id: int, contact_data: ContactUpdate, updated_by: str = None) -> Optional[Contact]:
        """Update a contact."""
        data = contact_data.model_dump(exclude_unset=True)
        if updated_by:
            data['updated_by'] = updated_by
        
        # Update full_name if first_name or last_name changed
        contact = await self.get(contact_id)
        if contact:
            first_name = data.get('first_name', contact.first_name)
            last_name = data.get('last_name', contact.last_name)
            data['full_name'] = f"{first_name} {last_name}"
        
        return await self.update(contact_id, data)
    
    async def get_by_email(self, email: str) -> Optional[Contact]:
        """Get contact by email."""
        statement = select(Contact).where(
            and_(Contact.email == email, Contact.is_deleted == False)
        )
        result = await self.session.exec(statement)
        return result.first()
    
    async def search_contacts(
        self,
        search: Optional[str] = None,
        account_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[Contact], int]:
        """Search contacts with filters."""
        statement = select(Contact).where(Contact.is_deleted == False)
        
        if search:
            search_term = f"%{search}%"
            statement = statement.where(
                or_(
                    Contact.full_name.ilike(search_term),
                    Contact.email.ilike(search_term),
                    Contact.title.ilike(search_term),
                    Contact.department.ilike(search_term)
                )
            )
        
        if account_id:
            statement = statement.where(Contact.account_id == account_id)
        
        # Get total count
        count_statement = select(func.count()).select_from(statement.subquery())
        count_result = await self.session.exec(count_statement)
        total = count_result.first()
        
        # Get paginated results
        statement = statement.offset(skip).limit(limit).order_by(Contact.full_name)
        result = await self.session.exec(statement)
        contacts = result.all()
        
        return contacts, total


class DealRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Deal)
    
    async def create_deal(self, deal_data: DealCreate, created_by: str = None) -> Deal:
        """Create a new deal."""
        data = deal_data.model_dump(exclude_unset=True)
        if created_by:
            data['created_by'] = created_by
        
        # Calculate expected revenue
        if data.get('amount') and data.get('probability'):
            data['expected_revenue'] = data['amount'] * (data['probability'] / 100)
        
        return await self.create(data)
    
    async def update_deal(self, deal_id: int, deal_data: DealUpdate, updated_by: str = None) -> Optional[Deal]:
        """Update a deal."""
        data = deal_data.model_dump(exclude_unset=True)
        if updated_by:
            data['updated_by'] = updated_by
        
        # Recalculate expected revenue if amount or probability changed
        deal = await self.get(deal_id)
        if deal:
            amount = data.get('amount', deal.amount)
            probability = data.get('probability', deal.probability)
            if amount and probability:
                data['expected_revenue'] = amount * (probability / 100)
        
        return await self.update(deal_id, data)
    
    async def get_deals_by_stage(self, stage: DealStage) -> List[Deal]:
        """Get deals by stage."""
        statement = select(Deal).where(
            and_(Deal.stage == stage, Deal.is_deleted == False)
        ).order_by(Deal.close_date)
        result = await self.session.exec(statement)
        return result.all()
    
    async def search_deals(
        self,
        search: Optional[str] = None,
        stage: Optional[str] = None,
        account_id: Optional[int] = None,
        contact_id: Optional[int] = None,
        close_date_from: Optional[date] = None,
        close_date_to: Optional[date] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[Deal], int]:
        """Search deals with filters."""
        statement = select(Deal).where(Deal.is_deleted == False)
        
        if search:
            search_term = f"%{search}%"
            statement = statement.where(
                or_(
                    Deal.name.ilike(search_term),
                    Deal.description.ilike(search_term),
                    Deal.next_step.ilike(search_term)
                )
            )
        
        if stage:
            statement = statement.where(Deal.stage == stage)
        
        if account_id:
            statement = statement.where(Deal.account_id == account_id)
            
        if contact_id:
            statement = statement.where(Deal.contact_id == contact_id)
        
        if close_date_from:
            statement = statement.where(Deal.close_date >= close_date_from)
            
        if close_date_to:
            statement = statement.where(Deal.close_date <= close_date_to)
        
        # Get total count
        count_statement = select(func.count()).select_from(statement.subquery())
        count_result = await self.session.exec(count_statement)
        total = count_result.first()
        
        # Get paginated results
        statement = statement.offset(skip).limit(limit).order_by(Deal.close_date.desc())
        result = await self.session.exec(statement)
        deals = result.all()
        
        return deals, total
    
    async def get_pipeline_summary(self) -> Dict[str, Any]:
        """Get pipeline summary by stage."""
        statement = select(
            Deal.stage,
            func.count(Deal.id).label('count'),
            func.sum(Deal.amount).label('total_amount'),
            func.sum(Deal.expected_revenue).label('total_expected_revenue')
        ).where(Deal.is_deleted == False).group_by(Deal.stage)
        
        result = await self.session.exec(statement)
        rows = result.all()
        
        pipeline = {}
        total_deals = 0
        total_amount = 0
        total_expected_revenue = 0
        
        for row in rows:
            stage_data = {
                'count': row.count,
                'total_amount': float(row.total_amount) if row.total_amount else 0,
                'total_expected_revenue': float(row.total_expected_revenue) if row.total_expected_revenue else 0,
            }
            pipeline[row.stage.value] = stage_data
            total_deals += row.count
            total_amount += stage_data['total_amount']
            total_expected_revenue += stage_data['total_expected_revenue']
        
        return {
            'pipeline': pipeline,
            'totals': {
                'deals': total_deals,
                'amount': total_amount,
                'expected_revenue': total_expected_revenue
            }
        }


class ActivityRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Activity)
    
    async def create_activity(self, activity_data: ActivityCreate, created_by: str = None) -> Activity:
        """Create a new activity."""
        data = activity_data.model_dump(exclude_unset=True)
        if created_by:
            data['created_by'] = created_by
        return await self.create(data)
    
    async def update_activity(self, activity_id: int, activity_data: ActivityUpdate, updated_by: str = None) -> Optional[Activity]:
        """Update an activity."""
        data = activity_data.model_dump(exclude_unset=True)
        if updated_by:
            data['updated_by'] = updated_by
        return await self.update(activity_id, data)
    
    async def get_upcoming_activities(self, user_id: Optional[str] = None, days: int = 7) -> List[Activity]:
        """Get upcoming activities."""
        end_date = datetime.utcnow().replace(hour=23, minute=59, second=59)
        from datetime import timedelta
        end_date += timedelta(days=days)
        
        statement = select(Activity).where(
            and_(
                Activity.is_deleted == False,
                Activity.status.in_([ActivityStatus.PLANNED, ActivityStatus.IN_PROGRESS]),
                Activity.due_date <= end_date,
                Activity.due_date >= datetime.utcnow()
            )
        ).order_by(Activity.due_date)
        
        if user_id:
            statement = statement.where(Activity.created_by == user_id)
        
        result = await self.session.exec(statement)
        return result.all()
    
    async def search_activities(
        self,
        search: Optional[str] = None,
        activity_type: Optional[str] = None,
        status: Optional[str] = None,
        account_id: Optional[int] = None,
        contact_id: Optional[int] = None,
        deal_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[Activity], int]:
        """Search activities with filters."""
        statement = select(Activity).where(Activity.is_deleted == False)
        
        if search:
            search_term = f"%{search}%"
            statement = statement.where(
                or_(
                    Activity.subject.ilike(search_term),
                    Activity.description.ilike(search_term),
                    Activity.outcome.ilike(search_term)
                )
            )
        
        if activity_type:
            statement = statement.where(Activity.activity_type == activity_type)
        
        if status:
            statement = statement.where(Activity.status == status)
        
        if account_id:
            statement = statement.where(Activity.account_id == account_id)
        
        if contact_id:
            statement = statement.where(Activity.contact_id == contact_id)
            
        if deal_id:
            statement = statement.where(Activity.deal_id == deal_id)
        
        # Get total count
        count_statement = select(func.count()).select_from(statement.subquery())
        count_result = await self.session.exec(count_statement)
        total = count_result.first()
        
        # Get paginated results
        statement = statement.offset(skip).limit(limit).order_by(Activity.due_date.desc())
        result = await self.session.exec(statement)
        activities = result.all()
        
        return activities, total