"""
Test factories for ERP models.
"""

import factory
from datetime import datetime, date
from decimal import Decimal
from faker import Faker

from erp.models import (
    Product, Warehouse, InventoryItem, Supplier, Order, OrderItem,
    ProductType, ProductStatus, StockStatus, OrderType, OrderStatus, SupplierStatus
)

fake = Faker()


class ProductFactory(factory.Factory):
    """Factory for Product model."""
    
    class Meta:
        model = Product
    
    name = factory.LazyAttribute(lambda obj: fake.catch_phrase())
    sku = factory.LazyAttribute(lambda obj: fake.bothify(text='PROD-####-??').upper())
    product_type = factory.LazyAttribute(lambda obj: fake.random_element(elements=[e.value for e in ProductType]))
    status = factory.LazyAttribute(lambda obj: fake.random_element(elements=[e.value for e in ProductStatus]))
    cost_price = factory.LazyAttribute(lambda obj: Decimal(str(fake.pyfloat(left_digits=3, right_digits=2, positive=True))))
    selling_price = factory.LazyAttribute(lambda obj: Decimal(str(fake.pyfloat(left_digits=3, right_digits=2, positive=True))))
    msrp = factory.LazyAttribute(lambda obj: Decimal(str(fake.pyfloat(left_digits=3, right_digits=2, positive=True))))
    weight = factory.LazyAttribute(lambda obj: Decimal(str(fake.pyfloat(left_digits=1, right_digits=3, positive=True))))
    dimensions = factory.LazyAttribute(lambda obj: f'{{"length": {fake.random_int(10, 100)}, "width": {fake.random_int(10, 100)}, "height": {fake.random_int(1, 50)}}}')
    track_inventory = factory.LazyAttribute(lambda obj: fake.boolean(chance_of_getting_true=80))
    allow_backorder = factory.LazyAttribute(lambda obj: fake.boolean(chance_of_getting_true=30))
    minimum_stock_level = factory.LazyAttribute(lambda obj: fake.random_int(min=10, max=100))
    maximum_stock_level = factory.LazyAttribute(lambda obj: fake.random_int(min=500, max=2000))
    description = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=300))
    short_description = factory.LazyAttribute(lambda obj: fake.sentence(nb_words=10))
    category = factory.LazyAttribute(lambda obj: fake.random_element(elements=[
        "Apparel", "Electronics", "Home & Garden", "Sports", "Books", "Toys"
    ]))
    brand = factory.LazyAttribute(lambda obj: fake.company())
    manufacturer = factory.LazyAttribute(lambda obj: fake.company())
    meta_title = factory.LazyAttribute(lambda obj: fake.sentence(nb_words=8))
    meta_description = factory.LazyAttribute(lambda obj: fake.sentence(nb_words=15))
    image_url = factory.LazyAttribute(lambda obj: fake.image_url())
    created_by = "test_user"
    created_at = factory.LazyAttribute(lambda obj: datetime.utcnow())
    updated_at = factory.LazyAttribute(lambda obj: datetime.utcnow())


class WarehouseFactory(factory.Factory):
    """Factory for Warehouse model."""
    
    class Meta:
        model = Warehouse
    
    name = factory.LazyAttribute(lambda obj: f"{fake.city()} Warehouse")
    code = factory.LazyAttribute(lambda obj: fake.bothify(text='WH-####').upper())
    address_line1 = factory.LazyAttribute(lambda obj: fake.street_address())
    address_line2 = factory.LazyAttribute(lambda obj: fake.secondary_address() if fake.boolean(chance_of_getting_true=30) else None)
    city = factory.LazyAttribute(lambda obj: fake.city())
    state = factory.LazyAttribute(lambda obj: fake.state_abbr())
    postal_code = factory.LazyAttribute(lambda obj: fake.postcode())
    country = factory.LazyAttribute(lambda obj: fake.country_code())
    phone = factory.LazyAttribute(lambda obj: fake.phone_number())
    email = factory.LazyAttribute(lambda obj: fake.email())
    manager = factory.LazyAttribute(lambda obj: fake.name())
    is_default = factory.LazyAttribute(lambda obj: fake.boolean(chance_of_getting_true=10))
    is_active = factory.LazyAttribute(lambda obj: fake.boolean(chance_of_getting_true=90))
    capacity = factory.LazyAttribute(lambda obj: fake.random_int(min=1000, max=50000))
    created_by = "test_user"
    created_at = factory.LazyAttribute(lambda obj: datetime.utcnow())
    updated_at = factory.LazyAttribute(lambda obj: datetime.utcnow())


class InventoryItemFactory(factory.Factory):
    """Factory for InventoryItem model."""
    
    class Meta:
        model = InventoryItem
    
    product_id = None  # Set explicitly in tests
    warehouse_id = None  # Set explicitly in tests
    quantity_on_hand = factory.LazyAttribute(lambda obj: fake.random_int(min=0, max=1000))
    quantity_reserved = factory.LazyAttribute(lambda obj: fake.random_int(min=0, max=100))
    quantity_available = factory.LazyAttribute(lambda obj: max(0, obj.quantity_on_hand - obj.quantity_reserved))
    reorder_point = factory.LazyAttribute(lambda obj: fake.random_int(min=10, max=100))
    reorder_quantity = factory.LazyAttribute(lambda obj: fake.random_int(min=100, max=500))
    stock_status = factory.LazyAttribute(lambda obj: fake.random_element(elements=[e.value for e in StockStatus]))
    bin_location = factory.LazyAttribute(lambda obj: f"{fake.random_element(elements=['A', 'B', 'C'])}{fake.random_int(1, 10)}-{fake.random_element(elements=['L', 'M', 'H'])}{fake.random_int(1, 5)}")
    created_by = "test_user"
    created_at = factory.LazyAttribute(lambda obj: datetime.utcnow())
    updated_at = factory.LazyAttribute(lambda obj: datetime.utcnow())


class SupplierFactory(factory.Factory):
    """Factory for Supplier model."""
    
    class Meta:
        model = Supplier
    
    name = factory.LazyAttribute(lambda obj: fake.company())
    code = factory.LazyAttribute(lambda obj: fake.bothify(text='SUP-####').upper())
    status = factory.LazyAttribute(lambda obj: fake.random_element(elements=[e.value for e in SupplierStatus]))
    contact_person = factory.LazyAttribute(lambda obj: fake.name())
    email = factory.LazyAttribute(lambda obj: fake.company_email())
    phone = factory.LazyAttribute(lambda obj: fake.phone_number())
    website = factory.LazyAttribute(lambda obj: fake.url())
    address_line1 = factory.LazyAttribute(lambda obj: fake.street_address())
    city = factory.LazyAttribute(lambda obj: fake.city())
    state = factory.LazyAttribute(lambda obj: fake.state_abbr())
    postal_code = factory.LazyAttribute(lambda obj: fake.postcode())
    country = factory.LazyAttribute(lambda obj: fake.country_code())
    tax_id = factory.LazyAttribute(lambda obj: fake.bothify(text='##-#######'))
    payment_terms = factory.LazyAttribute(lambda obj: fake.random_element(elements=["NET 30", "NET 15", "COD", "2/10 NET 30"]))
    lead_time_days = factory.LazyAttribute(lambda obj: fake.random_int(min=1, max=30))
    minimum_order_value = factory.LazyAttribute(lambda obj: Decimal(str(fake.pyfloat(left_digits=4, right_digits=2, positive=True))))
    rating = factory.LazyAttribute(lambda obj: fake.random_int(min=1, max=5))
    notes = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=200))
    created_by = "test_user"
    created_at = factory.LazyAttribute(lambda obj: datetime.utcnow())
    updated_at = factory.LazyAttribute(lambda obj: datetime.utcnow())


class OrderFactory(factory.Factory):
    """Factory for Order model."""
    
    class Meta:
        model = Order
    
    order_number = factory.LazyAttribute(lambda obj: fake.bothify(text='SO######').upper())
    order_type = factory.LazyAttribute(lambda obj: fake.random_element(elements=[e.value for e in OrderType]))
    status = factory.LazyAttribute(lambda obj: fake.random_element(elements=[e.value for e in OrderStatus]))
    order_date = factory.LazyAttribute(lambda obj: fake.date_between(start_date='-30d', end_date='today'))
    required_date = factory.LazyAttribute(lambda obj: fake.date_between(start_date='today', end_date='+30d'))
    shipped_date = factory.LazyAttribute(lambda obj: fake.date_between(start_date='today', end_date='+7d') if fake.boolean(chance_of_getting_true=30) else None)
    delivered_date = factory.LazyAttribute(lambda obj: fake.date_between(start_date='today', end_date='+14d') if fake.boolean(chance_of_getting_true=20) else None)
    customer_name = factory.LazyAttribute(lambda obj: fake.company())
    customer_email = factory.LazyAttribute(lambda obj: fake.company_email())
    customer_phone = factory.LazyAttribute(lambda obj: fake.phone_number())
    billing_address = factory.LazyAttribute(lambda obj: fake.json())
    shipping_address = factory.LazyAttribute(lambda obj: fake.json())
    subtotal = factory.LazyAttribute(lambda obj: Decimal(str(fake.pyfloat(left_digits=4, right_digits=2, positive=True))))
    tax_amount = factory.LazyAttribute(lambda obj: Decimal(str(fake.pyfloat(left_digits=3, right_digits=2, positive=True))))
    shipping_amount = factory.LazyAttribute(lambda obj: Decimal(str(fake.pyfloat(left_digits=2, right_digits=2, positive=True))))
    discount_amount = factory.LazyAttribute(lambda obj: Decimal(str(fake.pyfloat(left_digits=2, right_digits=2, positive=True))))
    total_amount = factory.LazyAttribute(lambda obj: obj.subtotal + obj.tax_amount + obj.shipping_amount - obj.discount_amount)
    shipping_method = factory.LazyAttribute(lambda obj: fake.random_element(elements=["Standard", "Express", "Overnight", "Ground"]))
    tracking_number = factory.LazyAttribute(lambda obj: fake.bothify(text='1Z###W###########') if fake.boolean(chance_of_getting_true=50) else None)
    notes = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=200))
    internal_notes = factory.LazyAttribute(lambda obj: fake.text(max_nb_chars=100))
    created_by = "test_user"
    created_at = factory.LazyAttribute(lambda obj: datetime.utcnow())
    updated_at = factory.LazyAttribute(lambda obj: datetime.utcnow())


class OrderItemFactory(factory.Factory):
    """Factory for OrderItem model."""
    
    class Meta:
        model = OrderItem
    
    order_id = None  # Set explicitly in tests
    product_id = None  # Set explicitly in tests
    quantity = factory.LazyAttribute(lambda obj: fake.random_int(min=1, max=10))
    unit_price = factory.LazyAttribute(lambda obj: Decimal(str(fake.pyfloat(left_digits=3, right_digits=2, positive=True))))
    total_price = factory.LazyAttribute(lambda obj: obj.unit_price * obj.quantity)
    product_name = factory.LazyAttribute(lambda obj: fake.catch_phrase())
    product_sku = factory.LazyAttribute(lambda obj: fake.bothify(text='PROD-####-??').upper())
    quantity_shipped = factory.LazyAttribute(lambda obj: fake.random_int(min=0, max=obj.quantity))
    quantity_delivered = factory.LazyAttribute(lambda obj: fake.random_int(min=0, max=obj.quantity_shipped))
    quantity_returned = factory.LazyAttribute(lambda obj: fake.random_int(min=0, max=obj.quantity_delivered) if fake.boolean(chance_of_getting_true=10) else 0)
    notes = factory.LazyAttribute(lambda obj: fake.sentence() if fake.boolean(chance_of_getting_true=30) else None)
    created_at = factory.LazyAttribute(lambda obj: datetime.utcnow())
    updated_at = factory.LazyAttribute(lambda obj: datetime.utcnow())


# Factories with relationships
class InventoryItemWithRelationshipsFactory(InventoryItemFactory):
    """Inventory item factory with product and warehouse relationships."""
    
    product = factory.SubFactory(ProductFactory)
    warehouse = factory.SubFactory(WarehouseFactory)
    product_id = factory.LazyAttribute(lambda obj: obj.product.id)
    warehouse_id = factory.LazyAttribute(lambda obj: obj.warehouse.id)


class OrderItemWithRelationshipsFactory(OrderItemFactory):
    """Order item factory with order and product relationships."""
    
    order = factory.SubFactory(OrderFactory)
    product = factory.SubFactory(ProductFactory)
    order_id = factory.LazyAttribute(lambda obj: obj.order.id)
    product_id = factory.LazyAttribute(lambda obj: obj.product.id)
    product_name = factory.LazyAttribute(lambda obj: obj.product.name)
    product_sku = factory.LazyAttribute(lambda obj: obj.product.sku)


# Pytest fixtures
import pytest


@pytest.fixture
def product_factory():
    """Product factory fixture."""
    return ProductFactory


@pytest.fixture
def warehouse_factory():
    """Warehouse factory fixture."""
    return WarehouseFactory


@pytest.fixture
def inventory_item_factory():
    """Inventory item factory fixture."""
    return InventoryItemFactory


@pytest.fixture
def supplier_factory():
    """Supplier factory fixture."""
    return SupplierFactory


@pytest.fixture
def order_factory():
    """Order factory fixture."""
    return OrderFactory


@pytest.fixture
def order_item_factory():
    """Order item factory fixture."""
    return OrderItemFactory


@pytest.fixture
async def sample_product(db_session):
    """Create a sample product for testing."""
    product = ProductFactory()
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product


@pytest.fixture
async def sample_warehouse(db_session):
    """Create a sample warehouse for testing."""
    warehouse = WarehouseFactory()
    db_session.add(warehouse)
    await db_session.commit()
    await db_session.refresh(warehouse)
    return warehouse


@pytest.fixture
async def sample_inventory_item(db_session, sample_product, sample_warehouse):
    """Create a sample inventory item for testing."""
    inventory_item = InventoryItemFactory(
        product_id=sample_product.id,
        warehouse_id=sample_warehouse.id
    )
    db_session.add(inventory_item)
    await db_session.commit()
    await db_session.refresh(inventory_item)
    return inventory_item


@pytest.fixture
async def sample_supplier(db_session):
    """Create a sample supplier for testing."""
    supplier = SupplierFactory()
    db_session.add(supplier)
    await db_session.commit()
    await db_session.refresh(supplier)
    return supplier


@pytest.fixture
async def sample_order(db_session):
    """Create a sample order for testing."""
    order = OrderFactory()
    db_session.add(order)
    await db_session.commit()
    await db_session.refresh(order)
    return order


@pytest.fixture
async def sample_order_item(db_session, sample_order, sample_product):
    """Create a sample order item for testing."""
    order_item = OrderItemFactory(
        order_id=sample_order.id,
        product_id=sample_product.id,
        product_name=sample_product.name,
        product_sku=sample_product.sku
    )
    db_session.add(order_item)
    await db_session.commit()
    await db_session.refresh(order_item)
    return order_item