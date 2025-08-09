from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func, and_, or_

from ..shared.database import BaseRepository
from ..shared.exceptions import NotFoundException, ValidationException
from .models import (
    Product, ProductCreate, ProductUpdate,
    Warehouse, WarehouseCreate, WarehouseUpdate,
    InventoryItem, InventoryItemCreate, InventoryItemUpdate, StockStatus,
    Supplier, SupplierCreate, SupplierUpdate,
    Order, OrderCreate, OrderUpdate, OrderStatus, OrderType,
    OrderItem, OrderItemCreate,
    PurchaseOrder, PurchaseOrderItem,
    StockMovement, MovementType
)


class ProductRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Product)
    
    async def create_product(self, product_data: ProductCreate, created_by: str = None) -> Product:
        """Create a new product."""
        data = product_data.model_dump(exclude_unset=True)
        if created_by:
            data['created_by'] = created_by
        return await self.create(data)
    
    async def update_product(self, product_id: int, product_data: ProductUpdate, updated_by: str = None) -> Optional[Product]:
        """Update a product."""
        data = product_data.model_dump(exclude_unset=True)
        if updated_by:
            data['updated_by'] = updated_by
        return await self.update(product_id, data)
    
    async def get_by_sku(self, sku: str) -> Optional[Product]:
        """Get product by SKU."""
        statement = select(Product).where(
            and_(Product.sku == sku, Product.is_deleted == False)
        )
        result = await self.session.exec(statement)
        return result.first()
    
    async def search_products(
        self,
        search: Optional[str] = None,
        category: Optional[str] = None,
        brand: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[Product], int]:
        """Search products with filters."""
        statement = select(Product).where(Product.is_deleted == False)
        
        if search:
            search_term = f"%{search}%"
            statement = statement.where(
                or_(
                    Product.name.ilike(search_term),
                    Product.sku.ilike(search_term),
                    Product.description.ilike(search_term),
                    Product.brand.ilike(search_term)
                )
            )
        
        if category:
            statement = statement.where(Product.category == category)
        
        if brand:
            statement = statement.where(Product.brand == brand)
        
        if status:
            statement = statement.where(Product.status == status)
        
        # Get total count
        count_statement = select(func.count()).select_from(statement.subquery())
        count_result = await self.session.exec(count_statement)
        total = count_result.first()
        
        # Get paginated results
        statement = statement.offset(skip).limit(limit).order_by(Product.name)
        result = await self.session.exec(statement)
        products = result.all()
        
        return products, total
    
    async def get_low_stock_products(self, warehouse_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get products with low stock levels."""
        from sqlalchemy import join
        
        statement = select(
            Product.id,
            Product.name,
            Product.sku,
            Product.minimum_stock_level,
            InventoryItem.quantity_on_hand,
            InventoryItem.warehouse_id,
            Warehouse.name.label('warehouse_name')
        ).select_from(
            join(Product, InventoryItem, Product.id == InventoryItem.product_id)
            .join(Warehouse, InventoryItem.warehouse_id == Warehouse.id)
        ).where(
            and_(
                Product.is_deleted == False,
                Product.track_inventory == True,
                InventoryItem.quantity_on_hand <= Product.minimum_stock_level
            )
        )
        
        if warehouse_id:
            statement = statement.where(InventoryItem.warehouse_id == warehouse_id)
        
        result = await self.session.exec(statement)
        return result.all()


class WarehouseRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Warehouse)
    
    async def create_warehouse(self, warehouse_data: WarehouseCreate, created_by: str = None) -> Warehouse:
        """Create a new warehouse."""
        data = warehouse_data.model_dump(exclude_unset=True)
        if created_by:
            data['created_by'] = created_by
        
        # If this is set as default, unset other defaults
        if data.get('is_default', False):
            await self._unset_default_warehouses()
        
        return await self.create(data)
    
    async def update_warehouse(self, warehouse_id: int, warehouse_data: WarehouseUpdate, updated_by: str = None) -> Optional[Warehouse]:
        """Update a warehouse."""
        data = warehouse_data.model_dump(exclude_unset=True)
        if updated_by:
            data['updated_by'] = updated_by
        
        # If this is being set as default, unset other defaults
        if data.get('is_default', False):
            await self._unset_default_warehouses(exclude_id=warehouse_id)
        
        return await self.update(warehouse_id, data)
    
    async def _unset_default_warehouses(self, exclude_id: Optional[int] = None):
        """Unset default flag for all warehouses."""
        statement = select(Warehouse).where(
            and_(Warehouse.is_default == True, Warehouse.is_deleted == False)
        )
        
        if exclude_id:
            statement = statement.where(Warehouse.id != exclude_id)
        
        result = await self.session.exec(statement)
        warehouses = result.all()
        
        for warehouse in warehouses:
            warehouse.is_default = False
    
    async def get_by_code(self, code: str) -> Optional[Warehouse]:
        """Get warehouse by code."""
        statement = select(Warehouse).where(
            and_(Warehouse.code == code, Warehouse.is_deleted == False)
        )
        result = await self.session.exec(statement)
        return result.first()
    
    async def get_default_warehouse(self) -> Optional[Warehouse]:
        """Get the default warehouse."""
        statement = select(Warehouse).where(
            and_(Warehouse.is_default == True, Warehouse.is_deleted == False)
        )
        result = await self.session.exec(statement)
        return result.first()


class InventoryRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, InventoryItem)
    
    async def create_inventory_item(self, inventory_data: InventoryItemCreate, created_by: str = None) -> InventoryItem:
        """Create a new inventory item."""
        data = inventory_data.model_dump(exclude_unset=True)
        if created_by:
            data['created_by'] = created_by
        
        # Set initial available quantity
        data['quantity_available'] = data['quantity_on_hand']
        data['stock_status'] = self._calculate_stock_status(data['quantity_available'])
        
        return await self.create(data)
    
    async def update_inventory_item(self, item_id: int, inventory_data: InventoryItemUpdate, updated_by: str = None) -> Optional[InventoryItem]:
        """Update an inventory item."""
        data = inventory_data.model_dump(exclude_unset=True)
        if updated_by:
            data['updated_by'] = updated_by
        
        # Recalculate available quantity and status if on_hand changed
        if 'quantity_on_hand' in data:
            item = await self.get(item_id)
            if item:
                data['quantity_available'] = data['quantity_on_hand'] - item.quantity_reserved
                data['stock_status'] = self._calculate_stock_status(data['quantity_available'])
        
        return await self.update(item_id, data)
    
    def _calculate_stock_status(self, available_quantity: int) -> StockStatus:
        """Calculate stock status based on available quantity."""
        if available_quantity <= 0:
            return StockStatus.OUT_OF_STOCK
        elif available_quantity <= 10:  # Configure this threshold
            return StockStatus.LOW_STOCK
        else:
            return StockStatus.IN_STOCK
    
    async def get_by_product_warehouse(self, product_id: int, warehouse_id: int) -> Optional[InventoryItem]:
        """Get inventory item by product and warehouse."""
        statement = select(InventoryItem).where(
            and_(
                InventoryItem.product_id == product_id,
                InventoryItem.warehouse_id == warehouse_id,
                InventoryItem.is_deleted == False
            )
        )
        result = await self.session.exec(statement)
        return result.first()
    
    async def get_product_inventory(self, product_id: int) -> List[InventoryItem]:
        """Get all inventory items for a product across warehouses."""
        statement = select(InventoryItem).where(
            and_(
                InventoryItem.product_id == product_id,
                InventoryItem.is_deleted == False
            )
        )
        result = await self.session.exec(statement)
        return result.all()
    
    async def reserve_inventory(self, product_id: int, warehouse_id: int, quantity: int) -> bool:
        """Reserve inventory for an order."""
        item = await self.get_by_product_warehouse(product_id, warehouse_id)
        if not item:
            return False
        
        if item.quantity_available < quantity:
            return False
        
        item.quantity_reserved += quantity
        item.quantity_available -= quantity
        item.stock_status = self._calculate_stock_status(item.quantity_available)
        
        return True
    
    async def release_inventory(self, product_id: int, warehouse_id: int, quantity: int) -> bool:
        """Release reserved inventory."""
        item = await self.get_by_product_warehouse(product_id, warehouse_id)
        if not item:
            return False
        
        if item.quantity_reserved < quantity:
            return False
        
        item.quantity_reserved -= quantity
        item.quantity_available += quantity
        item.stock_status = self._calculate_stock_status(item.quantity_available)
        
        return True
    
    async def fulfill_inventory(self, product_id: int, warehouse_id: int, quantity: int) -> bool:
        """Fulfill inventory (reduce on-hand and reserved quantities)."""
        item = await self.get_by_product_warehouse(product_id, warehouse_id)
        if not item:
            return False
        
        if item.quantity_reserved < quantity or item.quantity_on_hand < quantity:
            return False
        
        item.quantity_on_hand -= quantity
        item.quantity_reserved -= quantity
        item.stock_status = self._calculate_stock_status(item.quantity_available)
        
        # Record stock movement
        await self._record_stock_movement(
            product_id, warehouse_id, MovementType.OUTBOUND, 
            -quantity, item.quantity_on_hand + quantity, item.quantity_on_hand
        )
        
        return True
    
    async def receive_inventory(self, product_id: int, warehouse_id: int, quantity: int, reference: Optional[str] = None) -> bool:
        """Receive inventory (increase on-hand and available quantities)."""
        item = await self.get_by_product_warehouse(product_id, warehouse_id)
        if not item:
            return False
        
        old_quantity = item.quantity_on_hand
        item.quantity_on_hand += quantity
        item.quantity_available += quantity
        item.stock_status = self._calculate_stock_status(item.quantity_available)
        
        # Record stock movement
        await self._record_stock_movement(
            product_id, warehouse_id, MovementType.INBOUND,
            quantity, old_quantity, item.quantity_on_hand, reference
        )
        
        return True
    
    async def _record_stock_movement(
        self, 
        product_id: int, 
        warehouse_id: int, 
        movement_type: MovementType,
        quantity: int,
        quantity_before: int,
        quantity_after: int,
        reference: Optional[str] = None
    ):
        """Record a stock movement."""
        movement = StockMovement(
            product_id=product_id,
            warehouse_id=warehouse_id,
            movement_type=movement_type,
            quantity=quantity,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            reference_number=reference
        )
        self.session.add(movement)


class SupplierRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Supplier)
    
    async def create_supplier(self, supplier_data: SupplierCreate, created_by: str = None) -> Supplier:
        """Create a new supplier."""
        data = supplier_data.model_dump(exclude_unset=True)
        if created_by:
            data['created_by'] = created_by
        return await self.create(data)
    
    async def update_supplier(self, supplier_id: int, supplier_data: SupplierUpdate, updated_by: str = None) -> Optional[Supplier]:
        """Update a supplier."""
        data = supplier_data.model_dump(exclude_unset=True)
        if updated_by:
            data['updated_by'] = updated_by
        return await self.update(supplier_id, data)
    
    async def get_by_code(self, code: str) -> Optional[Supplier]:
        """Get supplier by code."""
        statement = select(Supplier).where(
            and_(Supplier.code == code, Supplier.is_deleted == False)
        )
        result = await self.session.exec(statement)
        return result.first()
    
    async def search_suppliers(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[Supplier], int]:
        """Search suppliers with filters."""
        statement = select(Supplier).where(Supplier.is_deleted == False)
        
        if search:
            search_term = f"%{search}%"
            statement = statement.where(
                or_(
                    Supplier.name.ilike(search_term),
                    Supplier.code.ilike(search_term),
                    Supplier.contact_person.ilike(search_term)
                )
            )
        
        if status:
            statement = statement.where(Supplier.status == status)
        
        # Get total count
        count_statement = select(func.count()).select_from(statement.subquery())
        count_result = await self.session.exec(count_statement)
        total = count_result.first()
        
        # Get paginated results
        statement = statement.offset(skip).limit(limit).order_by(Supplier.name)
        result = await self.session.exec(statement)
        suppliers = result.all()
        
        return suppliers, total


class OrderRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Order)
    
    async def create_order(self, order_data: OrderCreate, created_by: str = None) -> Order:
        """Create a new order."""
        data = order_data.model_dump(exclude_unset=True)
        if created_by:
            data['created_by'] = created_by
        
        # Generate order number
        data['order_number'] = await self._generate_order_number(order_data.order_type)
        
        return await self.create(data)
    
    async def update_order(self, order_id: int, order_data: OrderUpdate, updated_by: str = None) -> Optional[Order]:
        """Update an order."""
        data = order_data.model_dump(exclude_unset=True)
        if updated_by:
            data['updated_by'] = updated_by
        return await self.update(order_id, data)
    
    async def _generate_order_number(self, order_type: OrderType) -> str:
        """Generate a unique order number."""
        prefix = {
            OrderType.SALES: "SO",
            OrderType.PURCHASE: "PO",
            OrderType.RETURN: "RO",
            OrderType.EXCHANGE: "EO"
        }.get(order_type, "OR")
        
        # Get the latest order number for this type
        statement = select(func.max(Order.order_number)).where(
            Order.order_number.like(f"{prefix}%")
        )
        result = await self.session.exec(statement)
        latest = result.first()
        
        if latest:
            # Extract number and increment
            try:
                number = int(latest.replace(prefix, "")) + 1
            except (ValueError, AttributeError):
                number = 1
        else:
            number = 1
        
        return f"{prefix}{number:06d}"
    
    async def get_by_order_number(self, order_number: str) -> Optional[Order]:
        """Get order by order number."""
        statement = select(Order).where(
            and_(Order.order_number == order_number, Order.is_deleted == False)
        )
        result = await self.session.exec(statement)
        return result.first()
    
    async def search_orders(
        self,
        search: Optional[str] = None,
        order_type: Optional[str] = None,
        status: Optional[str] = None,
        customer_name: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[Order], int]:
        """Search orders with filters."""
        statement = select(Order).where(Order.is_deleted == False)
        
        if search:
            search_term = f"%{search}%"
            statement = statement.where(
                or_(
                    Order.order_number.ilike(search_term),
                    Order.customer_name.ilike(search_term),
                    Order.customer_email.ilike(search_term)
                )
            )
        
        if order_type:
            statement = statement.where(Order.order_type == order_type)
        
        if status:
            statement = statement.where(Order.status == status)
        
        if customer_name:
            statement = statement.where(Order.customer_name.ilike(f"%{customer_name}%"))
        
        if date_from:
            statement = statement.where(Order.order_date >= date_from)
        
        if date_to:
            statement = statement.where(Order.order_date <= date_to)
        
        # Get total count
        count_statement = select(func.count()).select_from(statement.subquery())
        count_result = await self.session.exec(count_statement)
        total = count_result.first()
        
        # Get paginated results
        statement = statement.offset(skip).limit(limit).order_by(Order.order_date.desc())
        result = await self.session.exec(statement)
        orders = result.all()
        
        return orders, total
    
    async def add_order_item(self, order_id: int, item_data: OrderItemCreate) -> OrderItem:
        """Add an item to an order."""
        # Get product details
        product_repo = ProductRepository(self.session)
        product = await product_repo.get(item_data.product_id)
        if not product:
            raise ValidationException(f"Product with ID {item_data.product_id} not found")
        
        # Create order item
        order_item = OrderItem(
            order_id=order_id,
            product_id=item_data.product_id,
            quantity=item_data.quantity,
            unit_price=item_data.unit_price,
            total_price=item_data.unit_price * item_data.quantity,
            product_name=product.name,
            product_sku=product.sku
        )
        
        self.session.add(order_item)
        await self.session.flush()
        
        # Update order totals
        await self._recalculate_order_totals(order_id)
        
        return order_item
    
    async def _recalculate_order_totals(self, order_id: int):
        """Recalculate order totals based on items."""
        statement = select(func.sum(OrderItem.total_price)).where(OrderItem.order_id == order_id)
        result = await self.session.exec(statement)
        subtotal = result.first() or Decimal('0.00')
        
        order = await self.get(order_id)
        if order:
            order.subtotal = subtotal
            order.total_amount = subtotal + order.tax_amount + order.shipping_amount - order.discount_amount