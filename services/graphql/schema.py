import strawberry
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal

from .resolvers import CRMResolver, ERPResolver, NotificationResolver


# Common scalar types
@strawberry.scalar
class DateTime:
    serialize = lambda value: value.isoformat() if value else None
    parse_value = lambda value: datetime.fromisoformat(value) if value else None
    parse_literal = lambda ast: datetime.fromisoformat(ast.value) if ast.value else None


@strawberry.scalar
class DecimalType:
    serialize = lambda value: float(value) if value else None
    parse_value = lambda value: Decimal(str(value)) if value is not None else None
    parse_literal = lambda ast: Decimal(str(ast.value)) if ast.value else None


@strawberry.scalar
class JSONType:
    serialize = lambda value: value
    parse_value = lambda value: value
    parse_literal = lambda ast: ast.value


# CRM Types
@strawberry.type
class Account:
    id: int
    name: str
    account_type: str
    industry: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    annual_revenue: Optional[DecimalType] = None
    employee_count: Optional[int] = None
    created_at: DateTime
    updated_at: DateTime


@strawberry.type
class Contact:
    id: int
    account_id: Optional[int] = None
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    lead_score: Optional[int] = None
    created_at: DateTime
    updated_at: DateTime


@strawberry.type
class Deal:
    id: int
    account_id: Optional[int] = None
    contact_id: Optional[int] = None
    title: str
    amount: Optional[DecimalType] = None
    stage: str
    probability: Optional[int] = None
    close_date: Optional[DateTime] = None
    created_at: DateTime
    updated_at: DateTime


@strawberry.type
class Activity:
    id: int
    account_id: Optional[int] = None
    contact_id: Optional[int] = None
    deal_id: Optional[int] = None
    activity_type: str
    subject: str
    description: Optional[str] = None
    due_date: Optional[DateTime] = None
    completed: bool
    created_at: DateTime


# ERP Types
@strawberry.type
class Product:
    id: int
    name: str
    sku: str
    product_type: str
    status: str
    cost_price: Optional[DecimalType] = None
    selling_price: Optional[DecimalType] = None
    track_inventory: bool
    minimum_stock_level: Optional[int] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    created_at: DateTime
    updated_at: DateTime


@strawberry.type
class Warehouse:
    id: int
    name: str
    code: str
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    is_default: bool
    is_active: bool
    created_at: DateTime


@strawberry.type
class InventoryItem:
    id: int
    product_id: int
    warehouse_id: int
    quantity_on_hand: int
    quantity_reserved: int
    quantity_available: int
    stock_status: str
    reorder_point: Optional[int] = None
    created_at: DateTime
    updated_at: DateTime


@strawberry.type
class Supplier:
    id: int
    name: str
    code: str
    status: str
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    payment_terms: Optional[str] = None
    created_at: DateTime


@strawberry.type
class Order:
    id: int
    order_number: str
    order_type: str
    status: str
    order_date: DateTime
    customer_name: Optional[str] = None
    total_amount: DecimalType
    created_at: DateTime


# Notification Types
@strawberry.type
class NotificationTemplate:
    id: int
    name: str
    template_type: str
    subject: Optional[str] = None
    description: Optional[str] = None
    language: str
    is_active: bool
    variables: Optional[JSONType] = None
    created_at: DateTime
    updated_at: DateTime


@strawberry.type
class Notification:
    id: int
    notification_type: str
    status: str
    priority: str
    recipient_email: Optional[str] = None
    recipient_phone: Optional[str] = None
    subject: Optional[str] = None
    scheduled_at: Optional[DateTime] = None
    sent_at: Optional[DateTime] = None
    delivered_at: Optional[DateTime] = None
    retry_count: int
    source_service: Optional[str] = None
    source_event: Optional[str] = None
    created_at: DateTime


@strawberry.type
class NotificationPreference:
    id: int
    user_id: str
    email_enabled: bool
    sms_enabled: bool
    push_enabled: bool
    in_app_enabled: bool
    email: Optional[str] = None
    phone: Optional[str] = None
    device_tokens: Optional[List[str]] = None
    timezone: str
    created_at: DateTime
    updated_at: DateTime


@strawberry.type
class Webhook:
    id: int
    name: str
    url: str
    status: str
    events: List[str]
    timeout_seconds: int
    max_retries: int
    last_triggered_at: Optional[DateTime] = None
    last_success_at: Optional[DateTime] = None
    failure_count: int
    description: Optional[str] = None
    created_at: DateTime


# Pagination Types
@strawberry.type
class PageInfo:
    has_next_page: bool
    has_previous_page: bool
    start_cursor: Optional[str] = None
    end_cursor: Optional[str] = None
    total_count: int
    page: int
    page_size: int


@strawberry.type
class AccountConnection:
    nodes: List[Account]
    page_info: PageInfo


@strawberry.type
class ContactConnection:
    nodes: List[Contact]
    page_info: PageInfo


@strawberry.type
class DealConnection:
    nodes: List[Deal]
    page_info: PageInfo


@strawberry.type
class ActivityConnection:
    nodes: List[Activity]
    page_info: PageInfo


@strawberry.type
class ProductConnection:
    nodes: List[Product]
    page_info: PageInfo


@strawberry.type
class WarehouseConnection:
    nodes: List[Warehouse]
    page_info: PageInfo


@strawberry.type
class InventoryItemConnection:
    nodes: List[InventoryItem]
    page_info: PageInfo


@strawberry.type
class SupplierConnection:
    nodes: List[Supplier]
    page_info: PageInfo


@strawberry.type
class OrderConnection:
    nodes: List[Order]
    page_info: PageInfo


@strawberry.type
class NotificationTemplateConnection:
    nodes: List[NotificationTemplate]
    page_info: PageInfo


@strawberry.type
class NotificationConnection:
    nodes: List[Notification]
    page_info: PageInfo


@strawberry.type
class WebhookConnection:
    nodes: List[Webhook]
    page_info: PageInfo


# Input Types for mutations
@strawberry.input
class AccountInput:
    name: str
    account_type: str
    industry: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    annual_revenue: Optional[DecimalType] = None
    employee_count: Optional[int] = None


@strawberry.input
class ContactInput:
    account_id: Optional[int] = None
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None


@strawberry.input
class DealInput:
    account_id: Optional[int] = None
    contact_id: Optional[int] = None
    title: str
    amount: Optional[DecimalType] = None
    stage: str
    probability: Optional[int] = None
    close_date: Optional[DateTime] = None


@strawberry.input
class ActivityInput:
    account_id: Optional[int] = None
    contact_id: Optional[int] = None
    deal_id: Optional[int] = None
    activity_type: str
    subject: str
    description: Optional[str] = None
    due_date: Optional[DateTime] = None


@strawberry.input
class ProductInput:
    name: str
    sku: str
    product_type: str = "simple"
    status: str = "active"
    cost_price: Optional[DecimalType] = None
    selling_price: Optional[DecimalType] = None
    track_inventory: bool = True
    minimum_stock_level: Optional[int] = 0
    category: Optional[str] = None
    brand: Optional[str] = None


@strawberry.input
class WarehouseInput:
    name: str
    code: str
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    is_default: bool = False


@strawberry.input
class InventoryItemInput:
    product_id: int
    warehouse_id: int
    quantity_on_hand: int = 0
    reorder_point: Optional[int] = None
    bin_location: Optional[str] = None


@strawberry.input
class SupplierInput:
    name: str
    code: str
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    payment_terms: Optional[str] = None


@strawberry.input
class OrderInput:
    order_type: str
    order_date: DateTime
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    required_date: Optional[DateTime] = None
    notes: Optional[str] = None


@strawberry.input
class NotificationTemplateInput:
    name: str
    template_type: str
    subject: Optional[str] = None
    content: str
    html_content: Optional[str] = None
    description: Optional[str] = None
    language: str = "en"
    variables: Optional[JSONType] = None


@strawberry.input
class NotificationInput:
    notification_type: str
    recipient_id: Optional[str] = None
    recipient_email: Optional[str] = None
    recipient_phone: Optional[str] = None
    subject: Optional[str] = None
    content: str
    html_content: Optional[str] = None
    template_id: Optional[int] = None
    template_variables: Optional[JSONType] = None
    priority: str = "normal"
    scheduled_at: Optional[DateTime] = None
    source_service: Optional[str] = None
    source_event: Optional[str] = None


@strawberry.input
class NotificationPreferenceInput:
    user_id: str
    email_enabled: bool = True
    sms_enabled: bool = True
    push_enabled: bool = True
    in_app_enabled: bool = True
    email: Optional[str] = None
    phone: Optional[str] = None
    device_tokens: Optional[List[str]] = None
    timezone: str = "UTC"


@strawberry.input
class WebhookInput:
    name: str
    url: str
    events: List[str]
    secret: Optional[str] = None
    http_method: str = "POST"
    timeout_seconds: int = 30
    headers: Optional[JSONType] = None
    max_retries: int = 3
    description: Optional[str] = None


# Query root
@strawberry.type
class Query:
    # CRM Queries
    @strawberry.field
    async def accounts(
        self,
        search: Optional[str] = None,
        account_type: Optional[str] = None,
        industry: Optional[str] = None,
        first: int = 20,
        skip: int = 0
    ) -> AccountConnection:
        resolver = CRMResolver()
        return await resolver.get_accounts(search, account_type, industry, first, skip)

    @strawberry.field
    async def account(self, id: int) -> Optional[Account]:
        resolver = CRMResolver()
        return await resolver.get_account(id)

    @strawberry.field
    async def contacts(
        self,
        search: Optional[str] = None,
        account_id: Optional[int] = None,
        first: int = 20,
        skip: int = 0
    ) -> ContactConnection:
        resolver = CRMResolver()
        return await resolver.get_contacts(search, account_id, first, skip)

    @strawberry.field
    async def contact(self, id: int) -> Optional[Contact]:
        resolver = CRMResolver()
        return await resolver.get_contact(id)

    @strawberry.field
    async def deals(
        self,
        search: Optional[str] = None,
        stage: Optional[str] = None,
        account_id: Optional[int] = None,
        first: int = 20,
        skip: int = 0
    ) -> DealConnection:
        resolver = CRMResolver()
        return await resolver.get_deals(search, stage, account_id, first, skip)

    @strawberry.field
    async def deal(self, id: int) -> Optional[Deal]:
        resolver = CRMResolver()
        return await resolver.get_deal(id)

    @strawberry.field
    async def activities(
        self,
        activity_type: Optional[str] = None,
        account_id: Optional[int] = None,
        contact_id: Optional[int] = None,
        deal_id: Optional[int] = None,
        completed: Optional[bool] = None,
        first: int = 20,
        skip: int = 0
    ) -> ActivityConnection:
        resolver = CRMResolver()
        return await resolver.get_activities(activity_type, account_id, contact_id, deal_id, completed, first, skip)

    # ERP Queries
    @strawberry.field
    async def products(
        self,
        search: Optional[str] = None,
        category: Optional[str] = None,
        brand: Optional[str] = None,
        status: Optional[str] = None,
        first: int = 20,
        skip: int = 0
    ) -> ProductConnection:
        resolver = ERPResolver()
        return await resolver.get_products(search, category, brand, status, first, skip)

    @strawberry.field
    async def product(self, id: int) -> Optional[Product]:
        resolver = ERPResolver()
        return await resolver.get_product(id)

    @strawberry.field
    async def product_by_sku(self, sku: str) -> Optional[Product]:
        resolver = ERPResolver()
        return await resolver.get_product_by_sku(sku)

    @strawberry.field
    async def warehouses(
        self,
        first: int = 20,
        skip: int = 0
    ) -> WarehouseConnection:
        resolver = ERPResolver()
        return await resolver.get_warehouses(first, skip)

    @strawberry.field
    async def warehouse(self, id: int) -> Optional[Warehouse]:
        resolver = ERPResolver()
        return await resolver.get_warehouse(id)

    @strawberry.field
    async def inventory_items(
        self,
        product_id: Optional[int] = None,
        warehouse_id: Optional[int] = None,
        first: int = 20,
        skip: int = 0
    ) -> InventoryItemConnection:
        resolver = ERPResolver()
        return await resolver.get_inventory_items(product_id, warehouse_id, first, skip)

    @strawberry.field
    async def suppliers(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        first: int = 20,
        skip: int = 0
    ) -> SupplierConnection:
        resolver = ERPResolver()
        return await resolver.get_suppliers(search, status, first, skip)

    @strawberry.field
    async def supplier(self, id: int) -> Optional[Supplier]:
        resolver = ERPResolver()
        return await resolver.get_supplier(id)

    @strawberry.field
    async def orders(
        self,
        search: Optional[str] = None,
        order_type: Optional[str] = None,
        status: Optional[str] = None,
        customer_name: Optional[str] = None,
        first: int = 20,
        skip: int = 0
    ) -> OrderConnection:
        resolver = ERPResolver()
        return await resolver.get_orders(search, order_type, status, customer_name, first, skip)

    @strawberry.field
    async def order(self, id: int) -> Optional[Order]:
        resolver = ERPResolver()
        return await resolver.get_order(id)

    # Notification Queries
    @strawberry.field
    async def notification_templates(
        self,
        search: Optional[str] = None,
        template_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        first: int = 20,
        skip: int = 0
    ) -> NotificationTemplateConnection:
        resolver = NotificationResolver()
        return await resolver.get_notification_templates(search, template_type, is_active, first, skip)

    @strawberry.field
    async def notification_template(self, id: int) -> Optional[NotificationTemplate]:
        resolver = NotificationResolver()
        return await resolver.get_notification_template(id)

    @strawberry.field
    async def notifications(
        self,
        search: Optional[str] = None,
        notification_type: Optional[str] = None,
        status: Optional[str] = None,
        recipient: Optional[str] = None,
        source_service: Optional[str] = None,
        first: int = 20,
        skip: int = 0
    ) -> NotificationConnection:
        resolver = NotificationResolver()
        return await resolver.get_notifications(search, notification_type, status, recipient, source_service, first, skip)

    @strawberry.field
    async def notification(self, id: int) -> Optional[Notification]:
        resolver = NotificationResolver()
        return await resolver.get_notification(id)

    @strawberry.field
    async def notification_preference_by_user(self, user_id: str) -> Optional[NotificationPreference]:
        resolver = NotificationResolver()
        return await resolver.get_notification_preference_by_user(user_id)

    @strawberry.field
    async def webhooks(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        first: int = 20,
        skip: int = 0
    ) -> WebhookConnection:
        resolver = NotificationResolver()
        return await resolver.get_webhooks(search, status, first, skip)

    @strawberry.field
    async def webhook(self, id: int) -> Optional[Webhook]:
        resolver = NotificationResolver()
        return await resolver.get_webhook(id)


# Mutation root
@strawberry.type
class Mutation:
    # CRM Mutations
    @strawberry.field
    async def create_account(self, input: AccountInput) -> Account:
        resolver = CRMResolver()
        return await resolver.create_account(input)

    @strawberry.field
    async def update_account(self, id: int, input: AccountInput) -> Optional[Account]:
        resolver = CRMResolver()
        return await resolver.update_account(id, input)

    @strawberry.field
    async def delete_account(self, id: int) -> bool:
        resolver = CRMResolver()
        return await resolver.delete_account(id)

    @strawberry.field
    async def create_contact(self, input: ContactInput) -> Contact:
        resolver = CRMResolver()
        return await resolver.create_contact(input)

    @strawberry.field
    async def update_contact(self, id: int, input: ContactInput) -> Optional[Contact]:
        resolver = CRMResolver()
        return await resolver.update_contact(id, input)

    @strawberry.field
    async def delete_contact(self, id: int) -> bool:
        resolver = CRMResolver()
        return await resolver.delete_contact(id)

    @strawberry.field
    async def create_deal(self, input: DealInput) -> Deal:
        resolver = CRMResolver()
        return await resolver.create_deal(input)

    @strawberry.field
    async def update_deal(self, id: int, input: DealInput) -> Optional[Deal]:
        resolver = CRMResolver()
        return await resolver.update_deal(id, input)

    @strawberry.field
    async def delete_deal(self, id: int) -> bool:
        resolver = CRMResolver()
        return await resolver.delete_deal(id)

    @strawberry.field
    async def create_activity(self, input: ActivityInput) -> Activity:
        resolver = CRMResolver()
        return await resolver.create_activity(input)

    @strawberry.field
    async def update_activity(self, id: int, input: ActivityInput) -> Optional[Activity]:
        resolver = CRMResolver()
        return await resolver.update_activity(id, input)

    @strawberry.field
    async def delete_activity(self, id: int) -> bool:
        resolver = CRMResolver()
        return await resolver.delete_activity(id)

    # ERP Mutations
    @strawberry.field
    async def create_product(self, input: ProductInput) -> Product:
        resolver = ERPResolver()
        return await resolver.create_product(input)

    @strawberry.field
    async def update_product(self, id: int, input: ProductInput) -> Optional[Product]:
        resolver = ERPResolver()
        return await resolver.update_product(id, input)

    @strawberry.field
    async def delete_product(self, id: int) -> bool:
        resolver = ERPResolver()
        return await resolver.delete_product(id)

    @strawberry.field
    async def create_warehouse(self, input: WarehouseInput) -> Warehouse:
        resolver = ERPResolver()
        return await resolver.create_warehouse(input)

    @strawberry.field
    async def update_warehouse(self, id: int, input: WarehouseInput) -> Optional[Warehouse]:
        resolver = ERPResolver()
        return await resolver.update_warehouse(id, input)

    @strawberry.field
    async def delete_warehouse(self, id: int) -> bool:
        resolver = ERPResolver()
        return await resolver.delete_warehouse(id)

    @strawberry.field
    async def create_inventory_item(self, input: InventoryItemInput) -> InventoryItem:
        resolver = ERPResolver()
        return await resolver.create_inventory_item(input)

    @strawberry.field
    async def update_inventory_item(self, id: int, input: InventoryItemInput) -> Optional[InventoryItem]:
        resolver = ERPResolver()
        return await resolver.update_inventory_item(id, input)

    @strawberry.field
    async def receive_inventory(
        self,
        product_id: int,
        warehouse_id: int,
        quantity: int,
        reference: Optional[str] = None
    ) -> InventoryItem:
        resolver = ERPResolver()
        return await resolver.receive_inventory(product_id, warehouse_id, quantity, reference)

    @strawberry.field
    async def reserve_inventory(
        self,
        product_id: int,
        warehouse_id: int,
        quantity: int
    ) -> bool:
        resolver = ERPResolver()
        return await resolver.reserve_inventory(product_id, warehouse_id, quantity)

    @strawberry.field
    async def fulfill_inventory(
        self,
        product_id: int,
        warehouse_id: int,
        quantity: int
    ) -> bool:
        resolver = ERPResolver()
        return await resolver.fulfill_inventory(product_id, warehouse_id, quantity)

    @strawberry.field
    async def create_supplier(self, input: SupplierInput) -> Supplier:
        resolver = ERPResolver()
        return await resolver.create_supplier(input)

    @strawberry.field
    async def update_supplier(self, id: int, input: SupplierInput) -> Optional[Supplier]:
        resolver = ERPResolver()
        return await resolver.update_supplier(id, input)

    @strawberry.field
    async def delete_supplier(self, id: int) -> bool:
        resolver = ERPResolver()
        return await resolver.delete_supplier(id)

    @strawberry.field
    async def create_order(self, input: OrderInput) -> Order:
        resolver = ERPResolver()
        return await resolver.create_order(input)

    @strawberry.field
    async def update_order(self, id: int, input: OrderInput) -> Optional[Order]:
        resolver = ERPResolver()
        return await resolver.update_order(id, input)

    @strawberry.field
    async def delete_order(self, id: int) -> bool:
        resolver = ERPResolver()
        return await resolver.delete_order(id)

    # Notification Mutations
    @strawberry.field
    async def create_notification_template(self, input: NotificationTemplateInput) -> NotificationTemplate:
        resolver = NotificationResolver()
        return await resolver.create_notification_template(input)

    @strawberry.field
    async def update_notification_template(self, id: int, input: NotificationTemplateInput) -> Optional[NotificationTemplate]:
        resolver = NotificationResolver()
        return await resolver.update_notification_template(id, input)

    @strawberry.field
    async def delete_notification_template(self, id: int) -> bool:
        resolver = NotificationResolver()
        return await resolver.delete_notification_template(id)

    @strawberry.field
    async def create_notification(self, input: NotificationInput) -> Notification:
        resolver = NotificationResolver()
        return await resolver.create_notification(input)

    @strawberry.field
    async def send_notification(self, id: int) -> Notification:
        resolver = NotificationResolver()
        return await resolver.send_notification(id)

    @strawberry.field
    async def create_notification_preference(self, input: NotificationPreferenceInput) -> NotificationPreference:
        resolver = NotificationResolver()
        return await resolver.create_notification_preference(input)

    @strawberry.field
    async def update_notification_preference(self, id: int, input: NotificationPreferenceInput) -> Optional[NotificationPreference]:
        resolver = NotificationResolver()
        return await resolver.update_notification_preference(id, input)

    @strawberry.field
    async def delete_notification_preference(self, id: int) -> bool:
        resolver = NotificationResolver()
        return await resolver.delete_notification_preference(id)

    @strawberry.field
    async def create_webhook(self, input: WebhookInput) -> Webhook:
        resolver = NotificationResolver()
        return await resolver.create_webhook(input)

    @strawberry.field
    async def update_webhook(self, id: int, input: WebhookInput) -> Optional[Webhook]:
        resolver = NotificationResolver()
        return await resolver.update_webhook(id, input)

    @strawberry.field
    async def delete_webhook(self, id: int) -> bool:
        resolver = NotificationResolver()
        return await resolver.delete_webhook(id)


# Create the schema
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    # Enable GraphQL Playground in development
    extensions=[
        # Enable tracing
        # strawberry.extensions.QueryDepthLimiter(max_depth=10),
        # strawberry.extensions.ValidationCache(),
    ]
)