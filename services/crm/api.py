from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..shared.database import get_database
from ..shared.auth import get_role_based_auth, Permissions
from ..shared.utils import PaginatedResponse, paginate_query_params
from ..shared.exceptions import WearForceException, exception_handler
from .models import (
    AccountCreate, AccountUpdate, AccountRead,
    ContactCreate, ContactUpdate, ContactRead,
    DealCreate, DealUpdate, DealRead,
    ActivityCreate, ActivityUpdate, ActivityRead,
)
from .services import AccountService, ContactService, DealService, ActivityService

# Initialize router
router = APIRouter(prefix="/api/v1", tags=["CRM"])

# Dependencies
async def get_session() -> AsyncSession:
    db = get_database()
    async with db.session() as session:
        yield session

auth = get_role_based_auth()
require_crm_read = auth.require_permission(Permissions.CRM_READ)
require_crm_write = auth.require_permission(Permissions.CRM_WRITE)
require_crm_delete = auth.require_permission(Permissions.CRM_DELETE)


# Account endpoints
@router.post("/accounts", response_model=AccountRead, dependencies=[Depends(require_crm_write)])
async def create_account(
    account_data: AccountCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new account."""
    try:
        service = AccountService(session)
        return await service.create_account(account_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/accounts/{account_id}", response_model=AccountRead, dependencies=[Depends(require_crm_read)])
async def get_account(
    account_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get account by ID."""
    try:
        service = AccountService(session)
        return await service.get_account(account_id)
    except WearForceException as e:
        raise exception_handler(e)


@router.put("/accounts/{account_id}", response_model=AccountRead, dependencies=[Depends(require_crm_write)])
async def update_account(
    account_id: int,
    account_data: AccountUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Update an account."""
    try:
        service = AccountService(session)
        return await service.update_account(account_id, account_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.delete("/accounts/{account_id}", dependencies=[Depends(require_crm_delete)])
async def delete_account(
    account_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Delete an account."""
    try:
        service = AccountService(session)
        await service.delete_account(account_id)
        return {"message": "Account deleted successfully"}
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/accounts", response_model=PaginatedResponse, dependencies=[Depends(require_crm_read)])
async def search_accounts(
    search: Optional[str] = Query(None, description="Search term for name, website, or description"),
    account_type: Optional[str] = Query(None, description="Account type filter"),
    status: Optional[str] = Query(None, description="Account status filter"),
    industry: Optional[str] = Query(None, description="Industry filter"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    session: AsyncSession = Depends(get_session)
):
    """Search accounts with filters and pagination."""
    try:
        skip, limit = paginate_query_params(skip, limit)
        service = AccountService(session)
        accounts, total = await service.search_accounts(search, account_type, status, industry, skip, limit)
        return PaginatedResponse.create(accounts, total, skip, limit)
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/accounts/{account_id}/hierarchy", dependencies=[Depends(require_crm_read)])
async def get_account_hierarchy(
    account_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get account with its parent and children."""
    try:
        service = AccountService(session)
        return await service.get_account_hierarchy(account_id)
    except WearForceException as e:
        raise exception_handler(e)


# Contact endpoints
@router.post("/contacts", response_model=ContactRead, dependencies=[Depends(require_crm_write)])
async def create_contact(
    contact_data: ContactCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new contact."""
    try:
        service = ContactService(session)
        return await service.create_contact(contact_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/contacts/{contact_id}", response_model=ContactRead, dependencies=[Depends(require_crm_read)])
async def get_contact(
    contact_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get contact by ID."""
    try:
        service = ContactService(session)
        return await service.get_contact(contact_id)
    except WearForceException as e:
        raise exception_handler(e)


@router.put("/contacts/{contact_id}", response_model=ContactRead, dependencies=[Depends(require_crm_write)])
async def update_contact(
    contact_id: int,
    contact_data: ContactUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Update a contact."""
    try:
        service = ContactService(session)
        return await service.update_contact(contact_id, contact_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.delete("/contacts/{contact_id}", dependencies=[Depends(require_crm_delete)])
async def delete_contact(
    contact_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Delete a contact."""
    try:
        service = ContactService(session)
        await service.delete_contact(contact_id)
        return {"message": "Contact deleted successfully"}
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/contacts", response_model=PaginatedResponse, dependencies=[Depends(require_crm_read)])
async def search_contacts(
    search: Optional[str] = Query(None, description="Search term for name, email, title, or department"),
    account_id: Optional[int] = Query(None, description="Filter by account ID"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    session: AsyncSession = Depends(get_session)
):
    """Search contacts with filters and pagination."""
    try:
        skip, limit = paginate_query_params(skip, limit)
        service = ContactService(session)
        contacts, total = await service.search_contacts(search, account_id, skip, limit)
        return PaginatedResponse.create(contacts, total, skip, limit)
    except WearForceException as e:
        raise exception_handler(e)


# Deal endpoints
@router.post("/deals", response_model=DealRead, dependencies=[Depends(require_crm_write)])
async def create_deal(
    deal_data: DealCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new deal."""
    try:
        service = DealService(session)
        return await service.create_deal(deal_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/deals/{deal_id}", response_model=DealRead, dependencies=[Depends(require_crm_read)])
async def get_deal(
    deal_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get deal by ID."""
    try:
        service = DealService(session)
        return await service.get_deal(deal_id)
    except WearForceException as e:
        raise exception_handler(e)


@router.put("/deals/{deal_id}", response_model=DealRead, dependencies=[Depends(require_crm_write)])
async def update_deal(
    deal_id: int,
    deal_data: DealUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Update a deal."""
    try:
        service = DealService(session)
        return await service.update_deal(deal_id, deal_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.delete("/deals/{deal_id}", dependencies=[Depends(require_crm_delete)])
async def delete_deal(
    deal_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Delete a deal."""
    try:
        service = DealService(session)
        await service.delete_deal(deal_id)
        return {"message": "Deal deleted successfully"}
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/deals", response_model=PaginatedResponse, dependencies=[Depends(require_crm_read)])
async def search_deals(
    search: Optional[str] = Query(None, description="Search term for name, description, or next step"),
    stage: Optional[str] = Query(None, description="Deal stage filter"),
    account_id: Optional[int] = Query(None, description="Filter by account ID"),
    contact_id: Optional[int] = Query(None, description="Filter by contact ID"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    session: AsyncSession = Depends(get_session)
):
    """Search deals with filters and pagination."""
    try:
        skip, limit = paginate_query_params(skip, limit)
        service = DealService(session)
        deals, total = await service.search_deals(search, stage, account_id, contact_id, skip, limit)
        return PaginatedResponse.create(deals, total, skip, limit)
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/deals/pipeline/summary", dependencies=[Depends(require_crm_read)])
async def get_pipeline_summary(
    session: AsyncSession = Depends(get_session)
):
    """Get sales pipeline summary."""
    try:
        service = DealService(session)
        return await service.get_pipeline_summary()
    except WearForceException as e:
        raise exception_handler(e)


@router.post("/deals/{deal_id}/calculate-score", dependencies=[Depends(require_crm_write)])
async def calculate_lead_score(
    deal_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Calculate lead score for a deal."""
    try:
        service = DealService(session)
        score = await service.calculate_lead_score(deal_id)
        return {"deal_id": deal_id, "lead_score": score}
    except WearForceException as e:
        raise exception_handler(e)


# Activity endpoints
@router.post("/activities", response_model=ActivityRead, dependencies=[Depends(require_crm_write)])
async def create_activity(
    activity_data: ActivityCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new activity."""
    try:
        service = ActivityService(session)
        return await service.create_activity(activity_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/activities/{activity_id}", response_model=ActivityRead, dependencies=[Depends(require_crm_read)])
async def get_activity(
    activity_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get activity by ID."""
    try:
        service = ActivityService(session)
        return await service.get_activity(activity_id)
    except WearForceException as e:
        raise exception_handler(e)


@router.put("/activities/{activity_id}", response_model=ActivityRead, dependencies=[Depends(require_crm_write)])
async def update_activity(
    activity_id: int,
    activity_data: ActivityUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Update an activity."""
    try:
        service = ActivityService(session)
        return await service.update_activity(activity_id, activity_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.delete("/activities/{activity_id}", dependencies=[Depends(require_crm_delete)])
async def delete_activity(
    activity_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Delete an activity."""
    try:
        service = ActivityService(session)
        await service.delete_activity(activity_id)
        return {"message": "Activity deleted successfully"}
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/activities", response_model=PaginatedResponse, dependencies=[Depends(require_crm_read)])
async def search_activities(
    search: Optional[str] = Query(None, description="Search term for subject, description, or outcome"),
    activity_type: Optional[str] = Query(None, description="Activity type filter"),
    status: Optional[str] = Query(None, description="Activity status filter"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    session: AsyncSession = Depends(get_session)
):
    """Search activities with filters and pagination."""
    try:
        skip, limit = paginate_query_params(skip, limit)
        service = ActivityService(session)
        activities, total = await service.search_activities(search, activity_type, status, skip, limit)
        return PaginatedResponse.create(activities, total, skip, limit)
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/activities/upcoming", response_model=List[ActivityRead], dependencies=[Depends(require_crm_read)])
async def get_upcoming_activities(
    days: int = Query(7, ge=1, le=30, description="Number of days to look ahead"),
    session: AsyncSession = Depends(get_session)
):
    """Get upcoming activities."""
    try:
        service = ActivityService(session)
        return await service.get_upcoming_activities(days)
    except WearForceException as e:
        raise exception_handler(e)


# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "crm-service"}