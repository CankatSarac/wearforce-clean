from datetime import datetime, date
from typing import Optional, List
from enum import Enum
from decimal import Decimal

from sqlmodel import SQLModel, Field, Relationship
from pydantic import EmailStr

from ..shared.database import TimestampMixin, SoftDeleteMixin, AuditMixin


class AccountType(str, Enum):
    PROSPECT = "prospect"
    CUSTOMER = "customer"
    PARTNER = "partner"
    VENDOR = "vendor"


class AccountStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class Industry(str, Enum):
    TECHNOLOGY = "technology"
    HEALTHCARE = "healthcare"
    FINANCE = "finance"
    RETAIL = "retail"
    MANUFACTURING = "manufacturing"
    EDUCATION = "education"
    REAL_ESTATE = "real_estate"
    OTHER = "other"


class DealStage(str, Enum):
    LEAD = "lead"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class DealPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActivityType(str, Enum):
    CALL = "call"
    EMAIL = "email"
    MEETING = "meeting"
    TASK = "task"
    NOTE = "note"


class ActivityStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# Database Models
class Account(SQLModel, TimestampMixin, SoftDeleteMixin, AuditMixin, table=True):
    __tablename__ = "accounts"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, nullable=False)
    account_type: AccountType = Field(default=AccountType.PROSPECT)
    status: AccountStatus = Field(default=AccountStatus.ACTIVE)
    industry: Optional[Industry] = Field(default=None)
    
    # Contact information
    website: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    fax: Optional[str] = Field(default=None)
    
    # Address
    billing_street: Optional[str] = Field(default=None)
    billing_city: Optional[str] = Field(default=None)
    billing_state: Optional[str] = Field(default=None)
    billing_postal_code: Optional[str] = Field(default=None)
    billing_country: Optional[str] = Field(default=None)
    
    shipping_street: Optional[str] = Field(default=None)
    shipping_city: Optional[str] = Field(default=None)
    shipping_state: Optional[str] = Field(default=None)
    shipping_postal_code: Optional[str] = Field(default=None)
    shipping_country: Optional[str] = Field(default=None)
    
    # Business details
    annual_revenue: Optional[Decimal] = Field(default=None, decimal_places=2)
    employees: Optional[int] = Field(default=None)
    description: Optional[str] = Field(default=None)
    
    # Parent account relationship
    parent_account_id: Optional[int] = Field(default=None, foreign_key="accounts.id")
    parent_account: Optional["Account"] = Relationship(back_populates="child_accounts")
    child_accounts: List["Account"] = Relationship(back_populates="parent_account")
    
    # Relationships
    contacts: List["Contact"] = Relationship(back_populates="account")
    deals: List["Deal"] = Relationship(back_populates="account")
    activities: List["Activity"] = Relationship(back_populates="account")


class Contact(SQLModel, TimestampMixin, SoftDeleteMixin, AuditMixin, table=True):
    __tablename__ = "contacts"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    first_name: str = Field(nullable=False)
    last_name: str = Field(nullable=False)
    full_name: str = Field(nullable=False, index=True)
    
    # Contact information
    email: Optional[EmailStr] = Field(default=None, index=True)
    phone: Optional[str] = Field(default=None)
    mobile: Optional[str] = Field(default=None)
    fax: Optional[str] = Field(default=None)
    
    # Job information
    title: Optional[str] = Field(default=None)
    department: Optional[str] = Field(default=None)
    
    # Address
    mailing_street: Optional[str] = Field(default=None)
    mailing_city: Optional[str] = Field(default=None)
    mailing_state: Optional[str] = Field(default=None)
    mailing_postal_code: Optional[str] = Field(default=None)
    mailing_country: Optional[str] = Field(default=None)
    
    # Personal information
    birthdate: Optional[date] = Field(default=None)
    lead_source: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    
    # Account relationship
    account_id: Optional[int] = Field(default=None, foreign_key="accounts.id")
    account: Optional[Account] = Relationship(back_populates="contacts")
    
    # Relationships
    deals: List["Deal"] = Relationship(back_populates="contact")
    activities: List["Activity"] = Relationship(back_populates="contact")
    
    def __init__(self, **data):
        if 'first_name' in data and 'last_name' in data:
            data['full_name'] = f"{data['first_name']} {data['last_name']}"
        super().__init__(**data)


class Deal(SQLModel, TimestampMixin, SoftDeleteMixin, AuditMixin, table=True):
    __tablename__ = "deals"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(nullable=False, index=True)
    stage: DealStage = Field(default=DealStage.LEAD)
    priority: DealPriority = Field(default=DealPriority.MEDIUM)
    
    # Financial information
    amount: Optional[Decimal] = Field(default=None, decimal_places=2)
    probability: Optional[int] = Field(default=None, ge=0, le=100)
    expected_revenue: Optional[Decimal] = Field(default=None, decimal_places=2)
    
    # Dates
    close_date: Optional[date] = Field(default=None)
    next_step: Optional[str] = Field(default=None)
    
    # Lead scoring
    lead_score: Optional[int] = Field(default=0, ge=0, le=100)
    
    # Additional information
    description: Optional[str] = Field(default=None)
    competitor: Optional[str] = Field(default=None)
    loss_reason: Optional[str] = Field(default=None)
    
    # Relationships
    account_id: Optional[int] = Field(default=None, foreign_key="accounts.id")
    account: Optional[Account] = Relationship(back_populates="deals")
    
    contact_id: Optional[int] = Field(default=None, foreign_key="contacts.id")
    contact: Optional[Contact] = Relationship(back_populates="deals")
    
    activities: List["Activity"] = Relationship(back_populates="deal")


class Activity(SQLModel, TimestampMixin, SoftDeleteMixin, AuditMixin, table=True):
    __tablename__ = "activities"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    subject: str = Field(nullable=False)
    activity_type: ActivityType = Field(nullable=False)
    status: ActivityStatus = Field(default=ActivityStatus.PLANNED)
    
    # Scheduling
    start_date: Optional[datetime] = Field(default=None)
    end_date: Optional[datetime] = Field(default=None)
    due_date: Optional[datetime] = Field(default=None)
    
    # Content
    description: Optional[str] = Field(default=None)
    outcome: Optional[str] = Field(default=None)
    
    # Priority and visibility
    priority: DealPriority = Field(default=DealPriority.MEDIUM)
    is_private: bool = Field(default=False)
    
    # Relationships
    account_id: Optional[int] = Field(default=None, foreign_key="accounts.id")
    account: Optional[Account] = Relationship(back_populates="activities")
    
    contact_id: Optional[int] = Field(default=None, foreign_key="contacts.id")
    contact: Optional[Contact] = Relationship(back_populates="activities")
    
    deal_id: Optional[int] = Field(default=None, foreign_key="deals.id")
    deal: Optional[Deal] = Relationship(back_populates="activities")


# API Models
class AccountCreate(SQLModel):
    name: str
    account_type: AccountType = AccountType.PROSPECT
    status: AccountStatus = AccountStatus.ACTIVE
    industry: Optional[Industry] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    billing_street: Optional[str] = None
    billing_city: Optional[str] = None
    billing_state: Optional[str] = None
    billing_postal_code: Optional[str] = None
    billing_country: Optional[str] = None
    annual_revenue: Optional[Decimal] = None
    employees: Optional[int] = None
    description: Optional[str] = None
    parent_account_id: Optional[int] = None


class AccountUpdate(SQLModel):
    name: Optional[str] = None
    account_type: Optional[AccountType] = None
    status: Optional[AccountStatus] = None
    industry: Optional[Industry] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    billing_street: Optional[str] = None
    billing_city: Optional[str] = None
    billing_state: Optional[str] = None
    billing_postal_code: Optional[str] = None
    billing_country: Optional[str] = None
    annual_revenue: Optional[Decimal] = None
    employees: Optional[int] = None
    description: Optional[str] = None
    parent_account_id: Optional[int] = None


class AccountRead(SQLModel):
    id: int
    name: str
    account_type: AccountType
    status: AccountStatus
    industry: Optional[Industry]
    website: Optional[str]
    phone: Optional[str]
    annual_revenue: Optional[Decimal]
    employees: Optional[int]
    created_at: datetime
    updated_at: datetime


class ContactCreate(SQLModel):
    first_name: str
    last_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    account_id: Optional[int] = None


class ContactUpdate(SQLModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    account_id: Optional[int] = None


class ContactRead(SQLModel):
    id: int
    full_name: str
    email: Optional[EmailStr]
    phone: Optional[str]
    title: Optional[str]
    department: Optional[str]
    created_at: datetime
    updated_at: datetime


class DealCreate(SQLModel):
    name: str
    stage: DealStage = DealStage.LEAD
    priority: DealPriority = DealPriority.MEDIUM
    amount: Optional[Decimal] = None
    probability: Optional[int] = None
    close_date: Optional[date] = None
    account_id: Optional[int] = None
    contact_id: Optional[int] = None


class DealUpdate(SQLModel):
    name: Optional[str] = None
    stage: Optional[DealStage] = None
    priority: Optional[DealPriority] = None
    amount: Optional[Decimal] = None
    probability: Optional[int] = None
    close_date: Optional[date] = None
    account_id: Optional[int] = None
    contact_id: Optional[int] = None


class DealRead(SQLModel):
    id: int
    name: str
    stage: DealStage
    priority: DealPriority
    amount: Optional[Decimal]
    probability: Optional[int]
    close_date: Optional[date]
    lead_score: int
    created_at: datetime
    updated_at: datetime


class ActivityCreate(SQLModel):
    subject: str
    activity_type: ActivityType
    status: ActivityStatus = ActivityStatus.PLANNED
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    description: Optional[str] = None
    priority: DealPriority = DealPriority.MEDIUM
    account_id: Optional[int] = None
    contact_id: Optional[int] = None
    deal_id: Optional[int] = None


class ActivityUpdate(SQLModel):
    subject: Optional[str] = None
    status: Optional[ActivityStatus] = None
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    description: Optional[str] = None
    outcome: Optional[str] = None
    priority: Optional[DealPriority] = None


class ActivityRead(SQLModel):
    id: int
    subject: str
    activity_type: ActivityType
    status: ActivityStatus
    start_date: Optional[datetime]
    due_date: Optional[datetime]
    priority: DealPriority
    created_at: datetime
    updated_at: datetime