import httpx
from typing import Optional, List, Dict, Any
from ..shared.config import get_graphql_settings
from .schema import (
    Account, Contact, Deal, Activity, AccountConnection, ContactConnection, DealConnection, ActivityConnection,
    Product, Warehouse, InventoryItem, Supplier, Order, ProductConnection, WarehouseConnection, 
    InventoryItemConnection, SupplierConnection, OrderConnection,
    NotificationTemplate, Notification, NotificationPreference, Webhook,
    NotificationTemplateConnection, NotificationConnection, WebhookConnection,
    PageInfo, AccountInput, ContactInput, DealInput, ActivityInput,
    ProductInput, WarehouseInput, InventoryItemInput, SupplierInput, OrderInput,
    NotificationTemplateInput, NotificationInput, NotificationPreferenceInput, WebhookInput
)


class BaseResolver:
    """Base resolver with common HTTP client functionality."""
    
    def __init__(self):
        self.settings = get_graphql_settings()
        self.http_client = httpx.AsyncClient(timeout=30.0)
    
    async def _make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to service."""
        try:
            response = await self.http_client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            # Log error and re-raise
            raise Exception(f"Service request failed: {str(e)}")
    
    def _create_page_info(self, total: int, skip: int, limit: int) -> PageInfo:
        """Create pagination info."""
        has_next = (skip + limit) < total
        has_previous = skip > 0
        page = (skip // limit) + 1
        
        return PageInfo(
            has_next_page=has_next,
            has_previous_page=has_previous,
            total_count=total,
            page=page,
            page_size=limit
        )


class CRMResolver(BaseResolver):
    """Resolver for CRM operations."""
    
    def __init__(self):
        super().__init__()
        self.service_url = self.settings.crm_service_url
    
    # Account operations
    async def get_accounts(
        self, 
        search: Optional[str] = None, 
        account_type: Optional[str] = None, 
        industry: Optional[str] = None,
        first: int = 20, 
        skip: int = 0
    ) -> AccountConnection:
        """Get accounts with pagination and filtering."""
        params = {"skip": skip, "limit": first}
        if search:
            params["search"] = search
        if account_type:
            params["account_type"] = account_type
        if industry:
            params["industry"] = industry
        
        data = await self._make_request("GET", f"{self.service_url}/api/v1/accounts", params=params)
        
        accounts = [Account(**item) for item in data["items"]]
        page_info = self._create_page_info(data["total"], skip, first)
        
        return AccountConnection(nodes=accounts, page_info=page_info)
    
    async def get_account(self, id: int) -> Optional[Account]:
        """Get account by ID."""
        try:
            data = await self._make_request("GET", f"{self.service_url}/api/v1/accounts/{id}")
            return Account(**data)
        except Exception:
            return None
    
    async def create_account(self, input: AccountInput) -> Account:
        """Create new account."""
        data = await self._make_request(
            "POST",
            f"{self.service_url}/api/v1/accounts",
            json=input.__dict__
        )
        return Account(**data)
    
    async def update_account(self, id: int, input: AccountInput) -> Optional[Account]:
        """Update account."""
        try:
            data = await self._make_request(
                "PUT",
                f"{self.service_url}/api/v1/accounts/{id}",
                json=input.__dict__
            )
            return Account(**data)
        except Exception:
            return None
    
    async def delete_account(self, id: int) -> bool:
        """Delete account."""
        try:
            await self._make_request("DELETE", f"{self.service_url}/api/v1/accounts/{id}")
            return True
        except Exception:
            return False
    
    # Contact operations
    async def get_contacts(
        self,
        search: Optional[str] = None,
        account_id: Optional[int] = None,
        first: int = 20,
        skip: int = 0
    ) -> ContactConnection:
        """Get contacts with pagination and filtering."""
        params = {"skip": skip, "limit": first}
        if search:
            params["search"] = search
        if account_id:
            params["account_id"] = account_id
        
        data = await self._make_request("GET", f"{self.service_url}/api/v1/contacts", params=params)
        
        contacts = [Contact(**item) for item in data["items"]]
        page_info = self._create_page_info(data["total"], skip, first)
        
        return ContactConnection(nodes=contacts, page_info=page_info)
    
    async def get_contact(self, id: int) -> Optional[Contact]:
        """Get contact by ID."""
        try:
            data = await self._make_request("GET", f"{self.service_url}/api/v1/contacts/{id}")
            return Contact(**data)
        except Exception:
            return None
    
    async def create_contact(self, input: ContactInput) -> Contact:
        """Create new contact."""
        data = await self._make_request(
            "POST",
            f"{self.service_url}/api/v1/contacts",
            json=input.__dict__
        )
        return Contact(**data)
    
    async def update_contact(self, id: int, input: ContactInput) -> Optional[Contact]:
        """Update contact."""
        try:
            data = await self._make_request(
                "PUT",
                f"{self.service_url}/api/v1/contacts/{id}",
                json=input.__dict__
            )
            return Contact(**data)
        except Exception:
            return None
    
    async def delete_contact(self, id: int) -> bool:
        """Delete contact."""
        try:
            await self._make_request("DELETE", f"{self.service_url}/api/v1/contacts/{id}")
            return True
        except Exception:
            return False
    
    # Deal operations
    async def get_deals(
        self,
        search: Optional[str] = None,
        stage: Optional[str] = None,
        account_id: Optional[int] = None,
        first: int = 20,
        skip: int = 0
    ) -> DealConnection:
        """Get deals with pagination and filtering."""
        params = {"skip": skip, "limit": first}
        if search:
            params["search"] = search
        if stage:
            params["stage"] = stage
        if account_id:
            params["account_id"] = account_id
        
        data = await self._make_request("GET", f"{self.service_url}/api/v1/deals", params=params)
        
        deals = [Deal(**item) for item in data["items"]]
        page_info = self._create_page_info(data["total"], skip, first)
        
        return DealConnection(nodes=deals, page_info=page_info)
    
    async def get_deal(self, id: int) -> Optional[Deal]:
        """Get deal by ID."""
        try:
            data = await self._make_request("GET", f"{self.service_url}/api/v1/deals/{id}")
            return Deal(**data)
        except Exception:
            return None
    
    async def create_deal(self, input: DealInput) -> Deal:
        """Create new deal."""
        data = await self._make_request(
            "POST",
            f"{self.service_url}/api/v1/deals",
            json=input.__dict__
        )
        return Deal(**data)
    
    async def update_deal(self, id: int, input: DealInput) -> Optional[Deal]:
        """Update deal."""
        try:
            data = await self._make_request(
                "PUT",
                f"{self.service_url}/api/v1/deals/{id}",
                json=input.__dict__
            )
            return Deal(**data)
        except Exception:
            return None
    
    async def delete_deal(self, id: int) -> bool:
        """Delete deal."""
        try:
            await self._make_request("DELETE", f"{self.service_url}/api/v1/deals/{id}")
            return True
        except Exception:
            return False
    
    # Activity operations
    async def get_activities(
        self,
        activity_type: Optional[str] = None,
        account_id: Optional[int] = None,
        contact_id: Optional[int] = None,
        deal_id: Optional[int] = None,
        completed: Optional[bool] = None,
        first: int = 20,
        skip: int = 0
    ) -> ActivityConnection:
        """Get activities with pagination and filtering."""
        params = {"skip": skip, "limit": first}
        if activity_type:
            params["activity_type"] = activity_type
        if account_id:
            params["account_id"] = account_id
        if contact_id:
            params["contact_id"] = contact_id
        if deal_id:
            params["deal_id"] = deal_id
        if completed is not None:
            params["completed"] = completed
        
        data = await self._make_request("GET", f"{self.service_url}/api/v1/activities", params=params)
        
        activities = [Activity(**item) for item in data["items"]]
        page_info = self._create_page_info(data["total"], skip, first)
        
        return ActivityConnection(nodes=activities, page_info=page_info)
    
    async def create_activity(self, input: ActivityInput) -> Activity:
        """Create new activity."""
        data = await self._make_request(
            "POST",
            f"{self.service_url}/api/v1/activities",
            json=input.__dict__
        )
        return Activity(**data)
    
    async def update_activity(self, id: int, input: ActivityInput) -> Optional[Activity]:
        """Update activity."""
        try:
            data = await self._make_request(
                "PUT",
                f"{self.service_url}/api/v1/activities/{id}",
                json=input.__dict__
            )
            return Activity(**data)
        except Exception:
            return None
    
    async def delete_activity(self, id: int) -> bool:
        """Delete activity."""
        try:
            await self._make_request("DELETE", f"{self.service_url}/api/v1/activities/{id}")
            return True
        except Exception:
            return False


class ERPResolver(BaseResolver):
    """Resolver for ERP operations."""
    
    def __init__(self):
        super().__init__()
        self.service_url = self.settings.erp_service_url
    
    # Product operations
    async def get_products(
        self,
        search: Optional[str] = None,
        category: Optional[str] = None,
        brand: Optional[str] = None,
        status: Optional[str] = None,
        first: int = 20,
        skip: int = 0
    ) -> ProductConnection:
        """Get products with pagination and filtering."""
        params = {"skip": skip, "limit": first}
        if search:
            params["search"] = search
        if category:
            params["category"] = category
        if brand:
            params["brand"] = brand
        if status:
            params["status"] = status
        
        data = await self._make_request("GET", f"{self.service_url}/api/v1/products", params=params)
        
        products = [Product(**item) for item in data["items"]]
        page_info = self._create_page_info(data["total"], skip, first)
        
        return ProductConnection(nodes=products, page_info=page_info)
    
    async def get_product(self, id: int) -> Optional[Product]:
        """Get product by ID."""
        try:
            data = await self._make_request("GET", f"{self.service_url}/api/v1/products/{id}")
            return Product(**data)
        except Exception:
            return None
    
    async def get_product_by_sku(self, sku: str) -> Optional[Product]:
        """Get product by SKU."""
        try:
            data = await self._make_request("GET", f"{self.service_url}/api/v1/products/sku/{sku}")
            return Product(**data)
        except Exception:
            return None
    
    async def create_product(self, input: ProductInput) -> Product:
        """Create new product."""
        data = await self._make_request(
            "POST",
            f"{self.service_url}/api/v1/products",
            json=input.__dict__
        )
        return Product(**data)
    
    async def update_product(self, id: int, input: ProductInput) -> Optional[Product]:
        """Update product."""
        try:
            data = await self._make_request(
                "PUT",
                f"{self.service_url}/api/v1/products/{id}",
                json=input.__dict__
            )
            return Product(**data)
        except Exception:
            return None
    
    async def delete_product(self, id: int) -> bool:
        """Delete product."""
        try:
            await self._make_request("DELETE", f"{self.service_url}/api/v1/products/{id}")
            return True
        except Exception:
            return False
    
    # Warehouse operations
    async def get_warehouses(self, first: int = 20, skip: int = 0) -> WarehouseConnection:
        """Get warehouses with pagination."""
        params = {"skip": skip, "limit": first}
        data = await self._make_request("GET", f"{self.service_url}/api/v1/warehouses", params=params)
        
        warehouses = [Warehouse(**item) for item in data["items"]]
        page_info = self._create_page_info(data["total"], skip, first)
        
        return WarehouseConnection(nodes=warehouses, page_info=page_info)
    
    async def get_warehouse(self, id: int) -> Optional[Warehouse]:
        """Get warehouse by ID."""
        try:
            data = await self._make_request("GET", f"{self.service_url}/api/v1/warehouses/{id}")
            return Warehouse(**data)
        except Exception:
            return None
    
    async def create_warehouse(self, input: WarehouseInput) -> Warehouse:
        """Create new warehouse."""
        data = await self._make_request(
            "POST",
            f"{self.service_url}/api/v1/warehouses",
            json=input.__dict__
        )
        return Warehouse(**data)
    
    async def update_warehouse(self, id: int, input: WarehouseInput) -> Optional[Warehouse]:
        """Update warehouse."""
        try:
            data = await self._make_request(
                "PUT",
                f"{self.service_url}/api/v1/warehouses/{id}",
                json=input.__dict__
            )
            return Warehouse(**data)
        except Exception:
            return None
    
    async def delete_warehouse(self, id: int) -> bool:
        """Delete warehouse."""
        try:
            await self._make_request("DELETE", f"{self.service_url}/api/v1/warehouses/{id}")
            return True
        except Exception:
            return False
    
    # Inventory operations
    async def get_inventory_items(
        self,
        product_id: Optional[int] = None,
        warehouse_id: Optional[int] = None,
        first: int = 20,
        skip: int = 0
    ) -> InventoryItemConnection:
        """Get inventory items with pagination and filtering."""
        if product_id:
            # Get inventory for specific product
            data = await self._make_request("GET", f"{self.service_url}/api/v1/inventory/product/{product_id}")
            items = [InventoryItem(**item) for item in data]
            page_info = self._create_page_info(len(items), 0, len(items))
            return InventoryItemConnection(nodes=items, page_info=page_info)
        else:
            # This would need a general inventory endpoint
            # For now, return empty
            return InventoryItemConnection(
                nodes=[],
                page_info=self._create_page_info(0, skip, first)
            )
    
    async def create_inventory_item(self, input: InventoryItemInput) -> InventoryItem:
        """Create new inventory item."""
        data = await self._make_request(
            "POST",
            f"{self.service_url}/api/v1/inventory",
            json=input.__dict__
        )
        return InventoryItem(**data)
    
    async def update_inventory_item(self, id: int, input: InventoryItemInput) -> Optional[InventoryItem]:
        """Update inventory item."""
        try:
            data = await self._make_request(
                "PUT",
                f"{self.service_url}/api/v1/inventory/{id}",
                json=input.__dict__
            )
            return InventoryItem(**data)
        except Exception:
            return None
    
    async def receive_inventory(
        self,
        product_id: int,
        warehouse_id: int,
        quantity: int,
        reference: Optional[str] = None
    ) -> InventoryItem:
        """Receive inventory."""
        params = {
            "product_id": product_id,
            "warehouse_id": warehouse_id,
            "quantity": quantity
        }
        if reference:
            params["reference"] = reference
        
        data = await self._make_request(
            "POST",
            f"{self.service_url}/api/v1/inventory/receive",
            params=params
        )
        return InventoryItem(**data)
    
    async def reserve_inventory(self, product_id: int, warehouse_id: int, quantity: int) -> bool:
        """Reserve inventory."""
        try:
            await self._make_request(
                "POST",
                f"{self.service_url}/api/v1/inventory/reserve",
                params={
                    "product_id": product_id,
                    "warehouse_id": warehouse_id,
                    "quantity": quantity
                }
            )
            return True
        except Exception:
            return False
    
    async def fulfill_inventory(self, product_id: int, warehouse_id: int, quantity: int) -> bool:
        """Fulfill inventory."""
        try:
            await self._make_request(
                "POST",
                f"{self.service_url}/api/v1/inventory/fulfill",
                params={
                    "product_id": product_id,
                    "warehouse_id": warehouse_id,
                    "quantity": quantity
                }
            )
            return True
        except Exception:
            return False
    
    # Supplier operations
    async def get_suppliers(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        first: int = 20,
        skip: int = 0
    ) -> SupplierConnection:
        """Get suppliers with pagination and filtering."""
        params = {"skip": skip, "limit": first}
        if search:
            params["search"] = search
        if status:
            params["status"] = status
        
        data = await self._make_request("GET", f"{self.service_url}/api/v1/suppliers", params=params)
        
        suppliers = [Supplier(**item) for item in data["items"]]
        page_info = self._create_page_info(data["total"], skip, first)
        
        return SupplierConnection(nodes=suppliers, page_info=page_info)
    
    async def get_supplier(self, id: int) -> Optional[Supplier]:
        """Get supplier by ID."""
        try:
            data = await self._make_request("GET", f"{self.service_url}/api/v1/suppliers/{id}")
            return Supplier(**data)
        except Exception:
            return None
    
    async def create_supplier(self, input: SupplierInput) -> Supplier:
        """Create new supplier."""
        data = await self._make_request(
            "POST",
            f"{self.service_url}/api/v1/suppliers",
            json=input.__dict__
        )
        return Supplier(**data)
    
    async def update_supplier(self, id: int, input: SupplierInput) -> Optional[Supplier]:
        """Update supplier."""
        try:
            data = await self._make_request(
                "PUT",
                f"{self.service_url}/api/v1/suppliers/{id}",
                json=input.__dict__
            )
            return Supplier(**data)
        except Exception:
            return None
    
    async def delete_supplier(self, id: int) -> bool:
        """Delete supplier."""
        try:
            await self._make_request("DELETE", f"{self.service_url}/api/v1/suppliers/{id}")
            return True
        except Exception:
            return False
    
    # Order operations
    async def get_orders(
        self,
        search: Optional[str] = None,
        order_type: Optional[str] = None,
        status: Optional[str] = None,
        customer_name: Optional[str] = None,
        first: int = 20,
        skip: int = 0
    ) -> OrderConnection:
        """Get orders with pagination and filtering."""
        params = {"skip": skip, "limit": first}
        if search:
            params["search"] = search
        if order_type:
            params["order_type"] = order_type
        if status:
            params["status"] = status
        if customer_name:
            params["customer_name"] = customer_name
        
        data = await self._make_request("GET", f"{self.service_url}/api/v1/orders", params=params)
        
        orders = [Order(**item) for item in data["items"]]
        page_info = self._create_page_info(data["total"], skip, first)
        
        return OrderConnection(nodes=orders, page_info=page_info)
    
    async def get_order(self, id: int) -> Optional[Order]:
        """Get order by ID."""
        try:
            data = await self._make_request("GET", f"{self.service_url}/api/v1/orders/{id}")
            return Order(**data)
        except Exception:
            return None
    
    async def create_order(self, input: OrderInput) -> Order:
        """Create new order."""
        data = await self._make_request(
            "POST",
            f"{self.service_url}/api/v1/orders",
            json=input.__dict__
        )
        return Order(**data)
    
    async def update_order(self, id: int, input: OrderInput) -> Optional[Order]:
        """Update order."""
        try:
            data = await self._make_request(
                "PUT",
                f"{self.service_url}/api/v1/orders/{id}",
                json=input.__dict__
            )
            return Order(**data)
        except Exception:
            return None
    
    async def delete_order(self, id: int) -> bool:
        """Delete order."""
        try:
            await self._make_request("DELETE", f"{self.service_url}/api/v1/orders/{id}")
            return True
        except Exception:
            return False


class NotificationResolver(BaseResolver):
    """Resolver for notification operations."""
    
    def __init__(self):
        super().__init__()
        self.service_url = self.settings.notification_service_url
    
    # Notification template operations
    async def get_notification_templates(
        self,
        search: Optional[str] = None,
        template_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        first: int = 20,
        skip: int = 0
    ) -> NotificationTemplateConnection:
        """Get notification templates with pagination and filtering."""
        params = {"skip": skip, "limit": first}
        if search:
            params["search"] = search
        if template_type:
            params["template_type"] = template_type
        if is_active is not None:
            params["is_active"] = is_active
        
        data = await self._make_request("GET", f"{self.service_url}/api/v1/templates", params=params)
        
        templates = [NotificationTemplate(**item) for item in data["items"]]
        page_info = self._create_page_info(data["total"], skip, first)
        
        return NotificationTemplateConnection(nodes=templates, page_info=page_info)
    
    async def get_notification_template(self, id: int) -> Optional[NotificationTemplate]:
        """Get notification template by ID."""
        try:
            data = await self._make_request("GET", f"{self.service_url}/api/v1/templates/{id}")
            return NotificationTemplate(**data)
        except Exception:
            return None
    
    async def create_notification_template(self, input: NotificationTemplateInput) -> NotificationTemplate:
        """Create new notification template."""
        data = await self._make_request(
            "POST",
            f"{self.service_url}/api/v1/templates",
            json=input.__dict__
        )
        return NotificationTemplate(**data)
    
    async def update_notification_template(self, id: int, input: NotificationTemplateInput) -> Optional[NotificationTemplate]:
        """Update notification template."""
        try:
            data = await self._make_request(
                "PUT",
                f"{self.service_url}/api/v1/templates/{id}",
                json=input.__dict__
            )
            return NotificationTemplate(**data)
        except Exception:
            return None
    
    async def delete_notification_template(self, id: int) -> bool:
        """Delete notification template."""
        try:
            await self._make_request("DELETE", f"{self.service_url}/api/v1/templates/{id}")
            return True
        except Exception:
            return False
    
    # Notification operations
    async def get_notifications(
        self,
        search: Optional[str] = None,
        notification_type: Optional[str] = None,
        status: Optional[str] = None,
        recipient: Optional[str] = None,
        source_service: Optional[str] = None,
        first: int = 20,
        skip: int = 0
    ) -> NotificationConnection:
        """Get notifications with pagination and filtering."""
        params = {"skip": skip, "limit": first}
        if search:
            params["search"] = search
        if notification_type:
            params["notification_type"] = notification_type
        if status:
            params["status"] = status
        if recipient:
            params["recipient"] = recipient
        if source_service:
            params["source_service"] = source_service
        
        data = await self._make_request("GET", f"{self.service_url}/api/v1/notifications", params=params)
        
        notifications = [Notification(**item) for item in data["items"]]
        page_info = self._create_page_info(data["total"], skip, first)
        
        return NotificationConnection(nodes=notifications, page_info=page_info)
    
    async def get_notification(self, id: int) -> Optional[Notification]:
        """Get notification by ID."""
        try:
            data = await self._make_request("GET", f"{self.service_url}/api/v1/notifications/{id}")
            return Notification(**data)
        except Exception:
            return None
    
    async def create_notification(self, input: NotificationInput) -> Notification:
        """Create new notification."""
        data = await self._make_request(
            "POST",
            f"{self.service_url}/api/v1/notifications",
            json=input.__dict__
        )
        return Notification(**data)
    
    async def send_notification(self, id: int) -> Notification:
        """Send notification."""
        data = await self._make_request(
            "POST",
            f"{self.service_url}/api/v1/notifications/{id}/send"
        )
        return Notification(**data)
    
    # Notification preference operations
    async def get_notification_preference_by_user(self, user_id: str) -> Optional[NotificationPreference]:
        """Get notification preference by user ID."""
        try:
            data = await self._make_request("GET", f"{self.service_url}/api/v1/preferences/user/{user_id}")
            return NotificationPreference(**data)
        except Exception:
            return None
    
    async def create_notification_preference(self, input: NotificationPreferenceInput) -> NotificationPreference:
        """Create new notification preference."""
        data = await self._make_request(
            "POST",
            f"{self.service_url}/api/v1/preferences",
            json=input.__dict__
        )
        return NotificationPreference(**data)
    
    async def update_notification_preference(self, id: int, input: NotificationPreferenceInput) -> Optional[NotificationPreference]:
        """Update notification preference."""
        try:
            data = await self._make_request(
                "PUT",
                f"{self.service_url}/api/v1/preferences/{id}",
                json=input.__dict__
            )
            return NotificationPreference(**data)
        except Exception:
            return None
    
    async def delete_notification_preference(self, id: int) -> bool:
        """Delete notification preference."""
        try:
            await self._make_request("DELETE", f"{self.service_url}/api/v1/preferences/{id}")
            return True
        except Exception:
            return False
    
    # Webhook operations
    async def get_webhooks(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        first: int = 20,
        skip: int = 0
    ) -> WebhookConnection:
        """Get webhooks with pagination and filtering."""
        params = {"skip": skip, "limit": first}
        if search:
            params["search"] = search
        if status:
            params["status"] = status
        
        data = await self._make_request("GET", f"{self.service_url}/api/v1/webhooks", params=params)
        
        webhooks = [Webhook(**item) for item in data["items"]]
        page_info = self._create_page_info(data["total"], skip, first)
        
        return WebhookConnection(nodes=webhooks, page_info=page_info)
    
    async def get_webhook(self, id: int) -> Optional[Webhook]:
        """Get webhook by ID."""
        try:
            data = await self._make_request("GET", f"{self.service_url}/api/v1/webhooks/{id}")
            return Webhook(**data)
        except Exception:
            return None
    
    async def create_webhook(self, input: WebhookInput) -> Webhook:
        """Create new webhook."""
        data = await self._make_request(
            "POST",
            f"{self.service_url}/api/v1/webhooks",
            json=input.__dict__
        )
        return Webhook(**data)
    
    async def update_webhook(self, id: int, input: WebhookInput) -> Optional[Webhook]:
        """Update webhook."""
        try:
            data = await self._make_request(
                "PUT",
                f"{self.service_url}/api/v1/webhooks/{id}",
                json=input.__dict__
            )
            return Webhook(**data)
        except Exception:
            return None
    
    async def delete_webhook(self, id: int) -> bool:
        """Delete webhook."""
        try:
            await self._make_request("DELETE", f"{self.service_url}/api/v1/webhooks/{id}")
            return True
        except Exception:
            return False