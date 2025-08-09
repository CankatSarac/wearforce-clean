import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from ..shared.events import BaseEvent, EventType, get_event_publisher
from ..shared.exceptions import NotFoundException, ValidationException, AlreadyExistsException
from ..shared.middleware import get_current_user_id
from .models import (
    Product, ProductCreate, ProductUpdate, ProductRead,
    Warehouse, WarehouseCreate, WarehouseUpdate, WarehouseRead,
    InventoryItem, InventoryItemCreate, InventoryItemUpdate, InventoryItemRead, StockStatus,
    Supplier, SupplierCreate, SupplierUpdate, SupplierRead,
    Order, OrderCreate, OrderUpdate, OrderRead, OrderStatus,
    OrderItem, OrderItemCreate, OrderItemRead,
)
from .repositories import (
    ProductRepository, WarehouseRepository, InventoryRepository,
    SupplierRepository, OrderRepository
)


class ERPService:
    """Main ERP service with business logic."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.product_repo = ProductRepository(session)
        self.warehouse_repo = WarehouseRepository(session)
        self.inventory_repo = InventoryRepository(session)
        self.supplier_repo = SupplierRepository(session)
        self.order_repo = OrderRepository(session)
        self.event_publisher = get_event_publisher()
    
    async def _publish_event(self, event_type: EventType, data: Dict[str, Any], entity_id: int = None):
        """Publish an event."""
        event = BaseEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            service="erp-service",
            timestamp=datetime.utcnow(),
            data=data,
            user_id=get_current_user_id(),
            metadata={"entity_id": entity_id} if entity_id else None
        )
        await self.event_publisher.publish(event)


class ProductService(ERPService):
    """Product management service."""
    
    async def create_product(self, product_data: ProductCreate) -> ProductRead:
        """Create a new product."""
        # Check if product with same SKU already exists
        existing = await self.product_repo.get_by_sku(product_data.sku)
        if existing:
            raise AlreadyExistsException(f"Product with SKU '{product_data.sku}' already exists")
        
        product = await self.product_repo.create_product(product_data, get_current_user_id())
        
        # Publish event
        await self._publish_event(
            EventType.PRODUCT_CREATED,
            {"product": product.model_dump()},
            product.id
        )
        
        return ProductRead.model_validate(product)
    
    async def get_product(self, product_id: int) -> ProductRead:
        """Get product by ID."""
        product = await self.product_repo.get(product_id)
        if not product:
            raise NotFoundException(f"Product with ID {product_id} not found")
        
        return ProductRead.model_validate(product)
    
    async def get_product_by_sku(self, sku: str) -> ProductRead:
        """Get product by SKU."""
        product = await self.product_repo.get_by_sku(sku)
        if not product:
            raise NotFoundException(f"Product with SKU '{sku}' not found")
        
        return ProductRead.model_validate(product)
    
    async def update_product(self, product_id: int, product_data: ProductUpdate) -> ProductRead:
        """Update a product."""
        product = await self.product_repo.update_product(product_id, product_data, get_current_user_id())
        if not product:
            raise NotFoundException(f"Product with ID {product_id} not found")
        
        # Publish event
        await self._publish_event(
            EventType.PRODUCT_UPDATED,
            {"product": product.model_dump()},
            product.id
        )
        
        return ProductRead.model_validate(product)
    
    async def delete_product(self, product_id: int) -> bool:
        """Delete a product (soft delete)."""
        success = await self.product_repo.delete(product_id)
        if not success:
            raise NotFoundException(f"Product with ID {product_id} not found")
        
        # Publish event
        await self._publish_event(
            EventType.PRODUCT_DELETED,
            {"product_id": product_id},
            product_id
        )
        
        return True
    
    async def search_products(
        self,
        search: Optional[str] = None,
        category: Optional[str] = None,
        brand: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[ProductRead], int]:
        """Search products with filters."""
        products, total = await self.product_repo.search_products(
            search, category, brand, status, skip, limit
        )
        
        product_reads = [ProductRead.model_validate(product) for product in products]
        return product_reads, total
    
    async def get_low_stock_products(self, warehouse_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get products with low stock levels."""
        return await self.product_repo.get_low_stock_products(warehouse_id)


class WarehouseService(ERPService):
    """Warehouse management service."""
    
    async def create_warehouse(self, warehouse_data: WarehouseCreate) -> WarehouseRead:
        """Create a new warehouse."""
        # Check if warehouse with same code already exists
        existing = await self.warehouse_repo.get_by_code(warehouse_data.code)
        if existing:
            raise AlreadyExistsException(f"Warehouse with code '{warehouse_data.code}' already exists")
        
        warehouse = await self.warehouse_repo.create_warehouse(warehouse_data, get_current_user_id())
        
        return WarehouseRead.model_validate(warehouse)
    
    async def get_warehouse(self, warehouse_id: int) -> WarehouseRead:
        """Get warehouse by ID."""
        warehouse = await self.warehouse_repo.get(warehouse_id)
        if not warehouse:
            raise NotFoundException(f"Warehouse with ID {warehouse_id} not found")
        
        return WarehouseRead.model_validate(warehouse)
    
    async def update_warehouse(self, warehouse_id: int, warehouse_data: WarehouseUpdate) -> WarehouseRead:
        """Update a warehouse."""
        warehouse = await self.warehouse_repo.update_warehouse(warehouse_id, warehouse_data, get_current_user_id())
        if not warehouse:
            raise NotFoundException(f"Warehouse with ID {warehouse_id} not found")
        
        return WarehouseRead.model_validate(warehouse)
    
    async def delete_warehouse(self, warehouse_id: int) -> bool:
        """Delete a warehouse (soft delete)."""
        success = await self.warehouse_repo.delete(warehouse_id)
        if not success:
            raise NotFoundException(f"Warehouse with ID {warehouse_id} not found")
        
        return True
    
    async def get_all_warehouses(self, skip: int = 0, limit: int = 100) -> tuple[List[WarehouseRead], int]:
        """Get all warehouses."""
        warehouses = await self.warehouse_repo.get_all(skip, limit)
        total = await self.warehouse_repo.count()
        
        warehouse_reads = [WarehouseRead.model_validate(warehouse) for warehouse in warehouses]
        return warehouse_reads, total


class InventoryService(ERPService):
    """Inventory management service."""
    
    async def create_inventory_item(self, inventory_data: InventoryItemCreate) -> InventoryItemRead:
        """Create a new inventory item."""
        # Check if inventory item already exists for this product/warehouse combination
        existing = await self.inventory_repo.get_by_product_warehouse(
            inventory_data.product_id, inventory_data.warehouse_id
        )
        if existing:
            raise AlreadyExistsException(
                f"Inventory item already exists for product {inventory_data.product_id} "
                f"in warehouse {inventory_data.warehouse_id}"
            )
        
        # Validate product and warehouse exist
        product = await self.product_repo.get(inventory_data.product_id)
        if not product:
            raise ValidationException(f"Product with ID {inventory_data.product_id} not found")
        
        warehouse = await self.warehouse_repo.get(inventory_data.warehouse_id)
        if not warehouse:
            raise ValidationException(f"Warehouse with ID {inventory_data.warehouse_id} not found")
        
        inventory_item = await self.inventory_repo.create_inventory_item(inventory_data, get_current_user_id())
        
        # Publish event
        await self._publish_event(
            EventType.INVENTORY_UPDATED,
            {
                "product_id": inventory_item.product_id,
                "warehouse_id": inventory_item.warehouse_id,
                "quantity_on_hand": inventory_item.quantity_on_hand,
                "stock_status": inventory_item.stock_status.value
            },
            inventory_item.id
        )
        
        return InventoryItemRead.model_validate(inventory_item)
    
    async def get_inventory_item(self, item_id: int) -> InventoryItemRead:
        """Get inventory item by ID."""
        item = await self.inventory_repo.get(item_id)
        if not item:
            raise NotFoundException(f"Inventory item with ID {item_id} not found")
        
        return InventoryItemRead.model_validate(item)
    
    async def update_inventory_item(self, item_id: int, inventory_data: InventoryItemUpdate) -> InventoryItemRead:
        """Update an inventory item."""
        item = await self.inventory_repo.update_inventory_item(item_id, inventory_data, get_current_user_id())
        if not item:
            raise NotFoundException(f"Inventory item with ID {item_id} not found")
        
        # Publish event
        await self._publish_event(
            EventType.INVENTORY_UPDATED,
            {
                "product_id": item.product_id,
                "warehouse_id": item.warehouse_id,
                "quantity_on_hand": item.quantity_on_hand,
                "stock_status": item.stock_status.value
            },
            item.id
        )
        
        # Check for low stock
        if item.stock_status == StockStatus.LOW_STOCK:
            await self._publish_event(
                EventType.STOCK_LOW,
                {
                    "product_id": item.product_id,
                    "warehouse_id": item.warehouse_id,
                    "quantity_on_hand": item.quantity_on_hand,
                    "reorder_point": item.reorder_point
                },
                item.id
            )
        elif item.stock_status == StockStatus.OUT_OF_STOCK:
            await self._publish_event(
                EventType.STOCK_OUT,
                {
                    "product_id": item.product_id,
                    "warehouse_id": item.warehouse_id,
                    "quantity_on_hand": item.quantity_on_hand
                },
                item.id
            )
        
        return InventoryItemRead.model_validate(item)
    
    async def get_product_inventory(self, product_id: int) -> List[InventoryItemRead]:
        """Get all inventory items for a product across warehouses."""
        items = await self.inventory_repo.get_product_inventory(product_id)
        return [InventoryItemRead.model_validate(item) for item in items]
    
    async def receive_inventory(
        self, 
        product_id: int, 
        warehouse_id: int, 
        quantity: int, 
        reference: Optional[str] = None
    ) -> InventoryItemRead:
        """Receive inventory (increase stock)."""
        success = await self.inventory_repo.receive_inventory(product_id, warehouse_id, quantity, reference)
        if not success:
            raise ValidationException("Failed to receive inventory")
        
        item = await self.inventory_repo.get_by_product_warehouse(product_id, warehouse_id)
        
        # Publish event
        await self._publish_event(
            EventType.INVENTORY_UPDATED,
            {
                "product_id": product_id,
                "warehouse_id": warehouse_id,
                "quantity_received": quantity,
                "quantity_on_hand": item.quantity_on_hand,
                "reference": reference
            },
            item.id
        )
        
        return InventoryItemRead.model_validate(item)
    
    async def reserve_inventory(self, product_id: int, warehouse_id: int, quantity: int) -> bool:
        """Reserve inventory for an order."""
        success = await self.inventory_repo.reserve_inventory(product_id, warehouse_id, quantity)
        return success
    
    async def release_inventory(self, product_id: int, warehouse_id: int, quantity: int) -> bool:
        """Release reserved inventory."""
        success = await self.inventory_repo.release_inventory(product_id, warehouse_id, quantity)
        return success
    
    async def fulfill_inventory(self, product_id: int, warehouse_id: int, quantity: int) -> bool:
        """Fulfill inventory (ship out)."""
        success = await self.inventory_repo.fulfill_inventory(product_id, warehouse_id, quantity)
        
        if success:
            item = await self.inventory_repo.get_by_product_warehouse(product_id, warehouse_id)
            
            # Publish event
            await self._publish_event(
                EventType.INVENTORY_UPDATED,
                {
                    "product_id": product_id,
                    "warehouse_id": warehouse_id,
                    "quantity_fulfilled": quantity,
                    "quantity_on_hand": item.quantity_on_hand,
                    "stock_status": item.stock_status.value
                },
                item.id
            )
        
        return success


class SupplierService(ERPService):
    """Supplier management service."""
    
    async def create_supplier(self, supplier_data: SupplierCreate) -> SupplierRead:
        """Create a new supplier."""
        # Check if supplier with same code already exists
        existing = await self.supplier_repo.get_by_code(supplier_data.code)
        if existing:
            raise AlreadyExistsException(f"Supplier with code '{supplier_data.code}' already exists")
        
        supplier = await self.supplier_repo.create_supplier(supplier_data, get_current_user_id())
        
        return SupplierRead.model_validate(supplier)
    
    async def get_supplier(self, supplier_id: int) -> SupplierRead:
        """Get supplier by ID."""
        supplier = await self.supplier_repo.get(supplier_id)
        if not supplier:
            raise NotFoundException(f"Supplier with ID {supplier_id} not found")
        
        return SupplierRead.model_validate(supplier)
    
    async def update_supplier(self, supplier_id: int, supplier_data: SupplierUpdate) -> SupplierRead:
        """Update a supplier."""
        supplier = await self.supplier_repo.update_supplier(supplier_id, supplier_data, get_current_user_id())
        if not supplier:
            raise NotFoundException(f"Supplier with ID {supplier_id} not found")
        
        return SupplierRead.model_validate(supplier)
    
    async def delete_supplier(self, supplier_id: int) -> bool:
        """Delete a supplier (soft delete)."""
        success = await self.supplier_repo.delete(supplier_id)
        if not success:
            raise NotFoundException(f"Supplier with ID {supplier_id} not found")
        
        return True
    
    async def search_suppliers(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[SupplierRead], int]:
        """Search suppliers with filters."""
        suppliers, total = await self.supplier_repo.search_suppliers(search, status, skip, limit)
        
        supplier_reads = [SupplierRead.model_validate(supplier) for supplier in suppliers]
        return supplier_reads, total


class OrderService(ERPService):
    """Order management service."""
    
    async def create_order(self, order_data: OrderCreate) -> OrderRead:
        """Create a new order."""
        order = await self.order_repo.create_order(order_data, get_current_user_id())
        
        # Publish event
        await self._publish_event(
            EventType.ORDER_CREATED,
            {"order": order.model_dump()},
            order.id
        )
        
        return OrderRead.model_validate(order)
    
    async def get_order(self, order_id: int) -> OrderRead:
        """Get order by ID."""
        order = await self.order_repo.get(order_id)
        if not order:
            raise NotFoundException(f"Order with ID {order_id} not found")
        
        return OrderRead.model_validate(order)
    
    async def get_order_by_number(self, order_number: str) -> OrderRead:
        """Get order by order number."""
        order = await self.order_repo.get_by_order_number(order_number)
        if not order:
            raise NotFoundException(f"Order with number '{order_number}' not found")
        
        return OrderRead.model_validate(order)
    
    async def update_order(self, order_id: int, order_data: OrderUpdate) -> OrderRead:
        """Update an order."""
        # Get current order to check for status changes
        current_order = await self.order_repo.get(order_id)
        if not current_order:
            raise NotFoundException(f"Order with ID {order_id} not found")
        
        order = await self.order_repo.update_order(order_id, order_data, get_current_user_id())
        
        # Publish events
        await self._publish_event(
            EventType.ORDER_UPDATED,
            {"order": order.model_dump()},
            order.id
        )
        
        # Check for status changes and publish specific events
        if order_data.status and current_order.status != order_data.status:
            if order_data.status == OrderStatus.CANCELLED:
                await self._publish_event(
                    EventType.ORDER_CANCELLED,
                    {"order_id": order.id, "order_number": order.order_number},
                    order.id
                )
            elif order_data.status == OrderStatus.SHIPPED:
                await self._publish_event(
                    EventType.ORDER_SHIPPED,
                    {"order_id": order.id, "order_number": order.order_number},
                    order.id
                )
            elif order_data.status == OrderStatus.DELIVERED:
                await self._publish_event(
                    EventType.ORDER_DELIVERED,
                    {"order_id": order.id, "order_number": order.order_number},
                    order.id
                )
        
        return OrderRead.model_validate(order)
    
    async def delete_order(self, order_id: int) -> bool:
        """Delete an order (soft delete)."""
        success = await self.order_repo.delete(order_id)
        if not success:
            raise NotFoundException(f"Order with ID {order_id} not found")
        
        return True
    
    async def search_orders(
        self,
        search: Optional[str] = None,
        order_type: Optional[str] = None,
        status: Optional[str] = None,
        customer_name: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[OrderRead], int]:
        """Search orders with filters."""
        orders, total = await self.order_repo.search_orders(
            search, order_type, status, customer_name, None, None, skip, limit
        )
        
        order_reads = [OrderRead.model_validate(order) for order in orders]
        return order_reads, total
    
    async def add_order_item(self, order_id: int, item_data: OrderItemCreate) -> OrderItemRead:
        """Add an item to an order."""
        # Validate order exists
        order = await self.order_repo.get(order_id)
        if not order:
            raise NotFoundException(f"Order with ID {order_id} not found")
        
        if order.status not in [OrderStatus.DRAFT, OrderStatus.PENDING]:
            raise ValidationException("Cannot add items to orders that are not in draft or pending status")
        
        order_item = await self.order_repo.add_order_item(order_id, item_data)
        
        return OrderItemRead.model_validate(order_item)
    
    async def confirm_order(self, order_id: int, warehouse_id: Optional[int] = None) -> OrderRead:
        """Confirm an order and reserve inventory."""
        order = await self.order_repo.get(order_id)
        if not order:
            raise NotFoundException(f"Order with ID {order_id} not found")
        
        if order.status != OrderStatus.PENDING:
            raise ValidationException("Only pending orders can be confirmed")
        
        # Use default warehouse if not specified
        if not warehouse_id:
            default_warehouse = await self.warehouse_repo.get_default_warehouse()
            if not default_warehouse:
                raise ValidationException("No warehouse specified and no default warehouse found")
            warehouse_id = default_warehouse.id
        
        # Reserve inventory for all order items
        for item in order.order_items:
            success = await self.inventory_repo.reserve_inventory(
                item.product_id, warehouse_id, item.quantity
            )
            if not success:
                raise ValidationException(
                    f"Insufficient inventory for product {item.product_sku}. "
                    f"Requested: {item.quantity}"
                )
        
        # Update order status
        updated_order = await self.order_repo.update_order(
            order_id, 
            OrderUpdate(status=OrderStatus.CONFIRMED),
            get_current_user_id()
        )
        
        return OrderRead.model_validate(updated_order)