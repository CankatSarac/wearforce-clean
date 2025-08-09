from datetime import datetime, date
from typing import Optional, List
from enum import Enum
from decimal import Decimal

from sqlmodel import SQLModel, Field, Relationship
from pydantic import validator

from ..shared.database import TimestampMixin, SoftDeleteMixin, AuditMixin


class ProductStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISCONTINUED = "discontinued"


class ProductType(str, Enum):
    SIMPLE = "simple"
    CONFIGURABLE = "configurable"
    BUNDLE = "bundle"
    VIRTUAL = "virtual"


class StockStatus(str, Enum):
    IN_STOCK = "in_stock"
    LOW_STOCK = "low_stock"
    OUT_OF_STOCK = "out_of_stock"
    BACKORDER = "backorder"


class OrderStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURNED = "returned"


class OrderType(str, Enum):
    SALES = "sales"
    PURCHASE = "purchase"
    RETURN = "return"
    EXCHANGE = "exchange"


class MovementType(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    ADJUSTMENT = "adjustment"
    TRANSFER = "transfer"


class SupplierStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


# Database Models
class Product(SQLModel, TimestampMixin, SoftDeleteMixin, AuditMixin, table=True):
    __tablename__ = "products"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(nullable=False, index=True)
    sku: str = Field(nullable=False, unique=True, index=True)
    product_type: ProductType = Field(default=ProductType.SIMPLE)
    status: ProductStatus = Field(default=ProductStatus.ACTIVE)
    
    # Pricing
    cost_price: Optional[Decimal] = Field(default=None, decimal_places=2)
    selling_price: Optional[Decimal] = Field(default=None, decimal_places=2)
    msrp: Optional[Decimal] = Field(default=None, decimal_places=2)  # Manufacturer's Suggested Retail Price
    
    # Physical attributes
    weight: Optional[Decimal] = Field(default=None, decimal_places=3)
    dimensions: Optional[str] = Field(default=None)  # JSON string: {"length": 10, "width": 5, "height": 2}
    
    # Inventory tracking
    track_inventory: bool = Field(default=True)
    allow_backorder: bool = Field(default=False)
    minimum_stock_level: Optional[int] = Field(default=0)
    maximum_stock_level: Optional[int] = Field(default=None)
    
    # Product information
    description: Optional[str] = Field(default=None)
    short_description: Optional[str] = Field(default=None)
    category: Optional[str] = Field(default=None)
    brand: Optional[str] = Field(default=None)
    manufacturer: Optional[str] = Field(default=None)
    
    # SEO and media
    meta_title: Optional[str] = Field(default=None)
    meta_description: Optional[str] = Field(default=None)
    image_url: Optional[str] = Field(default=None)
    
    # Relationships
    inventory_items: List["InventoryItem"] = Relationship(back_populates="product")
    order_items: List["OrderItem"] = Relationship(back_populates="product")
    stock_movements: List["StockMovement"] = Relationship(back_populates="product")


class Warehouse(SQLModel, TimestampMixin, SoftDeleteMixin, AuditMixin, table=True):
    __tablename__ = "warehouses"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(nullable=False, index=True)
    code: str = Field(nullable=False, unique=True, index=True)
    
    # Address
    address_line1: Optional[str] = Field(default=None)
    address_line2: Optional[str] = Field(default=None)
    city: Optional[str] = Field(default=None)
    state: Optional[str] = Field(default=None)
    postal_code: Optional[str] = Field(default=None)
    country: Optional[str] = Field(default=None)
    
    # Contact information
    phone: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)
    manager: Optional[str] = Field(default=None)
    
    # Warehouse details
    is_default: bool = Field(default=False)
    is_active: bool = Field(default=True)
    capacity: Optional[int] = Field(default=None)
    
    # Relationships
    inventory_items: List["InventoryItem"] = Relationship(back_populates="warehouse")
    stock_movements: List["StockMovement"] = Relationship(back_populates="warehouse")


class InventoryItem(SQLModel, TimestampMixin, SoftDeleteMixin, AuditMixin, table=True):
    __tablename__ = "inventory_items"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Foreign keys
    product_id: int = Field(foreign_key="products.id", nullable=False)
    warehouse_id: int = Field(foreign_key="warehouses.id", nullable=False)
    
    # Stock levels
    quantity_on_hand: int = Field(default=0, nullable=False)
    quantity_reserved: int = Field(default=0, nullable=False)  # Reserved for orders
    quantity_available: int = Field(default=0, nullable=False)  # Available for sale
    
    # Reorder information
    reorder_point: Optional[int] = Field(default=None)
    reorder_quantity: Optional[int] = Field(default=None)
    
    # Status
    stock_status: StockStatus = Field(default=StockStatus.IN_STOCK)
    
    # Location in warehouse
    bin_location: Optional[str] = Field(default=None)
    
    # Relationships
    product: Product = Relationship(back_populates="inventory_items")
    warehouse: Warehouse = Relationship(back_populates="inventory_items")
    
    # Unique constraint on product + warehouse
    __table_args__ = ({"sqlite_autoincrement": True},)


class Supplier(SQLModel, TimestampMixin, SoftDeleteMixin, AuditMixin, table=True):
    __tablename__ = "suppliers"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(nullable=False, index=True)
    code: str = Field(nullable=False, unique=True, index=True)
    status: SupplierStatus = Field(default=SupplierStatus.ACTIVE)
    
    # Contact information
    contact_person: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    website: Optional[str] = Field(default=None)
    
    # Address
    address_line1: Optional[str] = Field(default=None)
    address_line2: Optional[str] = Field(default=None)
    city: Optional[str] = Field(default=None)
    state: Optional[str] = Field(default=None)
    postal_code: Optional[str] = Field(default=None)
    country: Optional[str] = Field(default=None)
    
    # Business details
    tax_id: Optional[str] = Field(default=None)
    payment_terms: Optional[str] = Field(default=None)
    lead_time_days: Optional[int] = Field(default=None)
    minimum_order_value: Optional[Decimal] = Field(default=None, decimal_places=2)
    
    # Rating and notes
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    notes: Optional[str] = Field(default=None)
    
    # Relationships
    purchase_orders: List["PurchaseOrder"] = Relationship(back_populates="supplier")


class Order(SQLModel, TimestampMixin, SoftDeleteMixin, AuditMixin, table=True):
    __tablename__ = "orders"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    order_number: str = Field(nullable=False, unique=True, index=True)
    order_type: OrderType = Field(nullable=False)
    status: OrderStatus = Field(default=OrderStatus.DRAFT)
    
    # Dates
    order_date: date = Field(nullable=False)
    required_date: Optional[date] = Field(default=None)
    shipped_date: Optional[date] = Field(default=None)
    delivered_date: Optional[date] = Field(default=None)
    
    # Customer information (for sales orders)
    customer_name: Optional[str] = Field(default=None)
    customer_email: Optional[str] = Field(default=None)
    customer_phone: Optional[str] = Field(default=None)
    
    # Addresses
    billing_address: Optional[str] = Field(default=None)  # JSON string
    shipping_address: Optional[str] = Field(default=None)  # JSON string
    
    # Financial totals
    subtotal: Decimal = Field(default=0, decimal_places=2)
    tax_amount: Decimal = Field(default=0, decimal_places=2)
    shipping_amount: Decimal = Field(default=0, decimal_places=2)
    discount_amount: Decimal = Field(default=0, decimal_places=2)
    total_amount: Decimal = Field(default=0, decimal_places=2)
    
    # Shipping
    shipping_method: Optional[str] = Field(default=None)
    tracking_number: Optional[str] = Field(default=None)
    
    # Notes
    notes: Optional[str] = Field(default=None)
    internal_notes: Optional[str] = Field(default=None)
    
    # Relationships
    order_items: List["OrderItem"] = Relationship(back_populates="order")


class OrderItem(SQLModel, TimestampMixin, table=True):
    __tablename__ = "order_items"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Foreign keys
    order_id: int = Field(foreign_key="orders.id", nullable=False)
    product_id: int = Field(foreign_key="products.id", nullable=False)
    
    # Item details
    quantity: int = Field(nullable=False, gt=0)
    unit_price: Decimal = Field(nullable=False, decimal_places=2)
    total_price: Decimal = Field(nullable=False, decimal_places=2)
    
    # Product info snapshot (at time of order)
    product_name: str = Field(nullable=False)
    product_sku: str = Field(nullable=False)
    
    # Fulfillment
    quantity_shipped: int = Field(default=0)
    quantity_delivered: int = Field(default=0)
    quantity_returned: int = Field(default=0)
    
    # Notes
    notes: Optional[str] = Field(default=None)
    
    # Relationships
    order: Order = Relationship(back_populates="order_items")
    product: Product = Relationship(back_populates="order_items")


class PurchaseOrder(SQLModel, TimestampMixin, SoftDeleteMixin, AuditMixin, table=True):
    __tablename__ = "purchase_orders"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    po_number: str = Field(nullable=False, unique=True, index=True)
    status: OrderStatus = Field(default=OrderStatus.DRAFT)
    
    # Supplier
    supplier_id: int = Field(foreign_key="suppliers.id", nullable=False)
    
    # Dates
    order_date: date = Field(nullable=False)
    expected_delivery_date: Optional[date] = Field(default=None)
    delivered_date: Optional[date] = Field(default=None)
    
    # Financial
    subtotal: Decimal = Field(default=0, decimal_places=2)
    tax_amount: Decimal = Field(default=0, decimal_places=2)
    shipping_amount: Decimal = Field(default=0, decimal_places=2)
    total_amount: Decimal = Field(default=0, decimal_places=2)
    
    # Terms
    payment_terms: Optional[str] = Field(default=None)
    delivery_terms: Optional[str] = Field(default=None)
    
    # Notes
    notes: Optional[str] = Field(default=None)
    
    # Relationships
    supplier: Supplier = Relationship(back_populates="purchase_orders")
    purchase_order_items: List["PurchaseOrderItem"] = Relationship(back_populates="purchase_order")


class PurchaseOrderItem(SQLModel, TimestampMixin, table=True):
    __tablename__ = "purchase_order_items"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Foreign keys
    purchase_order_id: int = Field(foreign_key="purchase_orders.id", nullable=False)
    product_id: int = Field(foreign_key="products.id", nullable=False)
    
    # Item details
    quantity_ordered: int = Field(nullable=False, gt=0)
    quantity_received: int = Field(default=0)
    unit_cost: Decimal = Field(nullable=False, decimal_places=2)
    total_cost: Decimal = Field(nullable=False, decimal_places=2)
    
    # Product info snapshot
    product_name: str = Field(nullable=False)
    product_sku: str = Field(nullable=False)
    
    # Notes
    notes: Optional[str] = Field(default=None)
    
    # Relationships
    purchase_order: PurchaseOrder = Relationship(back_populates="purchase_order_items")


class StockMovement(SQLModel, TimestampMixin, table=True):
    __tablename__ = "stock_movements"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Foreign keys
    product_id: int = Field(foreign_key="products.id", nullable=False)
    warehouse_id: int = Field(foreign_key="warehouses.id", nullable=False)
    
    # Movement details
    movement_type: MovementType = Field(nullable=False)
    quantity: int = Field(nullable=False)  # Positive for inbound, negative for outbound
    reference_number: Optional[str] = Field(default=None)  # Order number, PO number, etc.
    
    # Before and after quantities
    quantity_before: int = Field(nullable=False)
    quantity_after: int = Field(nullable=False)
    
    # Reason and notes
    reason: Optional[str] = Field(default=None)
    notes: Optional[str] = Field(default=None)
    
    # Relationships
    product: Product = Relationship(back_populates="stock_movements")
    warehouse: Warehouse = Relationship(back_populates="stock_movements")


# API Models
class ProductCreate(SQLModel):
    name: str
    sku: str
    product_type: ProductType = ProductType.SIMPLE
    status: ProductStatus = ProductStatus.ACTIVE
    cost_price: Optional[Decimal] = None
    selling_price: Optional[Decimal] = None
    weight: Optional[Decimal] = None
    track_inventory: bool = True
    minimum_stock_level: Optional[int] = 0
    description: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None


class ProductUpdate(SQLModel):
    name: Optional[str] = None
    status: Optional[ProductStatus] = None
    cost_price: Optional[Decimal] = None
    selling_price: Optional[Decimal] = None
    weight: Optional[Decimal] = None
    minimum_stock_level: Optional[int] = None
    description: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None


class ProductRead(SQLModel):
    id: int
    name: str
    sku: str
    product_type: ProductType
    status: ProductStatus
    cost_price: Optional[Decimal]
    selling_price: Optional[Decimal]
    track_inventory: bool
    minimum_stock_level: Optional[int]
    category: Optional[str]
    brand: Optional[str]
    created_at: datetime
    updated_at: datetime


class WarehouseCreate(SQLModel):
    name: str
    code: str
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    is_default: bool = False


class WarehouseUpdate(SQLModel):
    name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    is_active: Optional[bool] = None


class WarehouseRead(SQLModel):
    id: int
    name: str
    code: str
    city: Optional[str]
    state: Optional[str]
    country: Optional[str]
    is_default: bool
    is_active: bool
    created_at: datetime


class InventoryItemCreate(SQLModel):
    product_id: int
    warehouse_id: int
    quantity_on_hand: int = 0
    reorder_point: Optional[int] = None
    bin_location: Optional[str] = None


class InventoryItemUpdate(SQLModel):
    quantity_on_hand: Optional[int] = None
    reorder_point: Optional[int] = None
    bin_location: Optional[str] = None


class InventoryItemRead(SQLModel):
    id: int
    product_id: int
    warehouse_id: int
    quantity_on_hand: int
    quantity_reserved: int
    quantity_available: int
    stock_status: StockStatus
    reorder_point: Optional[int]
    created_at: datetime
    updated_at: datetime


class SupplierCreate(SQLModel):
    name: str
    code: str
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    payment_terms: Optional[str] = None


class SupplierUpdate(SQLModel):
    name: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[SupplierStatus] = None
    payment_terms: Optional[str] = None


class SupplierRead(SQLModel):
    id: int
    name: str
    code: str
    status: SupplierStatus
    contact_person: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    payment_terms: Optional[str]
    created_at: datetime


class OrderCreate(SQLModel):
    order_type: OrderType
    order_date: date
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    required_date: Optional[date] = None
    notes: Optional[str] = None


class OrderUpdate(SQLModel):
    status: Optional[OrderStatus] = None
    required_date: Optional[date] = None
    shipped_date: Optional[date] = None
    delivered_date: Optional[date] = None
    notes: Optional[str] = None


class OrderRead(SQLModel):
    id: int
    order_number: str
    order_type: OrderType
    status: OrderStatus
    order_date: date
    customer_name: Optional[str]
    total_amount: Decimal
    created_at: datetime


class OrderItemCreate(SQLModel):
    product_id: int
    quantity: int
    unit_price: Decimal


class OrderItemRead(SQLModel):
    id: int
    product_id: int
    product_name: str
    product_sku: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal