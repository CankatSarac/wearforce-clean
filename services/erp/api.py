from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..shared.database import get_database
from ..shared.auth import get_role_based_auth, Permissions
from ..shared.utils import PaginatedResponse, paginate_query_params
from ..shared.exceptions import WearForceException, exception_handler
from .models import (
    ProductCreate, ProductUpdate, ProductRead,
    WarehouseCreate, WarehouseUpdate, WarehouseRead,
    InventoryItemCreate, InventoryItemUpdate, InventoryItemRead,
    SupplierCreate, SupplierUpdate, SupplierRead,
    OrderCreate, OrderUpdate, OrderRead,
    OrderItemCreate, OrderItemRead,
)
from .services import (
    ProductService, WarehouseService, InventoryService,
    SupplierService, OrderService
)

# Initialize router
router = APIRouter(prefix="/api/v1", tags=["ERP"])

# Dependencies
async def get_session() -> AsyncSession:
    db = get_database()
    async with db.session() as session:
        yield session

auth = get_role_based_auth()
require_erp_read = auth.require_permission(Permissions.ERP_READ)
require_erp_write = auth.require_permission(Permissions.ERP_WRITE)
require_erp_delete = auth.require_permission(Permissions.ERP_DELETE)


# Product endpoints
@router.post("/products", response_model=ProductRead, dependencies=[Depends(require_erp_write)])
async def create_product(
    product_data: ProductCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new product."""
    try:
        service = ProductService(session)
        return await service.create_product(product_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/products/{product_id}", response_model=ProductRead, dependencies=[Depends(require_erp_read)])
async def get_product(
    product_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get product by ID."""
    try:
        service = ProductService(session)
        return await service.get_product(product_id)
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/products/sku/{sku}", response_model=ProductRead, dependencies=[Depends(require_erp_read)])
async def get_product_by_sku(
    sku: str,
    session: AsyncSession = Depends(get_session)
):
    """Get product by SKU."""
    try:
        service = ProductService(session)
        return await service.get_product_by_sku(sku)
    except WearForceException as e:
        raise exception_handler(e)


@router.put("/products/{product_id}", response_model=ProductRead, dependencies=[Depends(require_erp_write)])
async def update_product(
    product_id: int,
    product_data: ProductUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Update a product."""
    try:
        service = ProductService(session)
        return await service.update_product(product_id, product_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.delete("/products/{product_id}", dependencies=[Depends(require_erp_delete)])
async def delete_product(
    product_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Delete a product."""
    try:
        service = ProductService(session)
        await service.delete_product(product_id)
        return {"message": "Product deleted successfully"}
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/products", response_model=PaginatedResponse, dependencies=[Depends(require_erp_read)])
async def search_products(
    search: Optional[str] = Query(None, description="Search term for name, SKU, description, or brand"),
    category: Optional[str] = Query(None, description="Product category filter"),
    brand: Optional[str] = Query(None, description="Brand filter"),
    status: Optional[str] = Query(None, description="Product status filter"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    session: AsyncSession = Depends(get_session)
):
    """Search products with filters and pagination."""
    try:
        skip, limit = paginate_query_params(skip, limit)
        service = ProductService(session)
        products, total = await service.search_products(search, category, brand, status, skip, limit)
        return PaginatedResponse.create(products, total, skip, limit)
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/products/low-stock", dependencies=[Depends(require_erp_read)])
async def get_low_stock_products(
    warehouse_id: Optional[int] = Query(None, description="Filter by warehouse ID"),
    session: AsyncSession = Depends(get_session)
):
    """Get products with low stock levels."""
    try:
        service = ProductService(session)
        return await service.get_low_stock_products(warehouse_id)
    except WearForceException as e:
        raise exception_handler(e)


# Warehouse endpoints
@router.post("/warehouses", response_model=WarehouseRead, dependencies=[Depends(require_erp_write)])
async def create_warehouse(
    warehouse_data: WarehouseCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new warehouse."""
    try:
        service = WarehouseService(session)
        return await service.create_warehouse(warehouse_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/warehouses/{warehouse_id}", response_model=WarehouseRead, dependencies=[Depends(require_erp_read)])
async def get_warehouse(
    warehouse_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get warehouse by ID."""
    try:
        service = WarehouseService(session)
        return await service.get_warehouse(warehouse_id)
    except WearForceException as e:
        raise exception_handler(e)


@router.put("/warehouses/{warehouse_id}", response_model=WarehouseRead, dependencies=[Depends(require_erp_write)])
async def update_warehouse(
    warehouse_id: int,
    warehouse_data: WarehouseUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Update a warehouse."""
    try:
        service = WarehouseService(session)
        return await service.update_warehouse(warehouse_id, warehouse_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.delete("/warehouses/{warehouse_id}", dependencies=[Depends(require_erp_delete)])
async def delete_warehouse(
    warehouse_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Delete a warehouse."""
    try:
        service = WarehouseService(session)
        await service.delete_warehouse(warehouse_id)
        return {"message": "Warehouse deleted successfully"}
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/warehouses", response_model=PaginatedResponse, dependencies=[Depends(require_erp_read)])
async def get_warehouses(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    session: AsyncSession = Depends(get_session)
):
    """Get all warehouses."""
    try:
        skip, limit = paginate_query_params(skip, limit)
        service = WarehouseService(session)
        warehouses, total = await service.get_all_warehouses(skip, limit)
        return PaginatedResponse.create(warehouses, total, skip, limit)
    except WearForceException as e:
        raise exception_handler(e)


# Inventory endpoints
@router.post("/inventory", response_model=InventoryItemRead, dependencies=[Depends(require_erp_write)])
async def create_inventory_item(
    inventory_data: InventoryItemCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new inventory item."""
    try:
        service = InventoryService(session)
        return await service.create_inventory_item(inventory_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/inventory/{item_id}", response_model=InventoryItemRead, dependencies=[Depends(require_erp_read)])
async def get_inventory_item(
    item_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get inventory item by ID."""
    try:
        service = InventoryService(session)
        return await service.get_inventory_item(item_id)
    except WearForceException as e:
        raise exception_handler(e)


@router.put("/inventory/{item_id}", response_model=InventoryItemRead, dependencies=[Depends(require_erp_write)])
async def update_inventory_item(
    item_id: int,
    inventory_data: InventoryItemUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Update an inventory item."""
    try:
        service = InventoryService(session)
        return await service.update_inventory_item(item_id, inventory_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/inventory/product/{product_id}", response_model=List[InventoryItemRead], dependencies=[Depends(require_erp_read)])
async def get_product_inventory(
    product_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get all inventory items for a product across warehouses."""
    try:
        service = InventoryService(session)
        return await service.get_product_inventory(product_id)
    except WearForceException as e:
        raise exception_handler(e)


@router.post("/inventory/receive", response_model=InventoryItemRead, dependencies=[Depends(require_erp_write)])
async def receive_inventory(
    product_id: int = Query(..., description="Product ID"),
    warehouse_id: int = Query(..., description="Warehouse ID"),
    quantity: int = Query(..., gt=0, description="Quantity to receive"),
    reference: Optional[str] = Query(None, description="Reference number (e.g., PO number)"),
    session: AsyncSession = Depends(get_session)
):
    """Receive inventory (increase stock)."""
    try:
        service = InventoryService(session)
        return await service.receive_inventory(product_id, warehouse_id, quantity, reference)
    except WearForceException as e:
        raise exception_handler(e)


@router.post("/inventory/reserve", dependencies=[Depends(require_erp_write)])
async def reserve_inventory(
    product_id: int = Query(..., description="Product ID"),
    warehouse_id: int = Query(..., description="Warehouse ID"),
    quantity: int = Query(..., gt=0, description="Quantity to reserve"),
    session: AsyncSession = Depends(get_session)
):
    """Reserve inventory for an order."""
    try:
        service = InventoryService(session)
        success = await service.reserve_inventory(product_id, warehouse_id, quantity)
        if success:
            return {"message": "Inventory reserved successfully"}
        else:
            raise HTTPException(status_code=400, detail="Insufficient inventory to reserve")
    except WearForceException as e:
        raise exception_handler(e)


@router.post("/inventory/release", dependencies=[Depends(require_erp_write)])
async def release_inventory(
    product_id: int = Query(..., description="Product ID"),
    warehouse_id: int = Query(..., description="Warehouse ID"),
    quantity: int = Query(..., gt=0, description="Quantity to release"),
    session: AsyncSession = Depends(get_session)
):
    """Release reserved inventory."""
    try:
        service = InventoryService(session)
        success = await service.release_inventory(product_id, warehouse_id, quantity)
        if success:
            return {"message": "Inventory released successfully"}
        else:
            raise HTTPException(status_code=400, detail="Cannot release more than reserved quantity")
    except WearForceException as e:
        raise exception_handler(e)


@router.post("/inventory/fulfill", dependencies=[Depends(require_erp_write)])
async def fulfill_inventory(
    product_id: int = Query(..., description="Product ID"),
    warehouse_id: int = Query(..., description="Warehouse ID"),
    quantity: int = Query(..., gt=0, description="Quantity to fulfill"),
    session: AsyncSession = Depends(get_session)
):
    """Fulfill inventory (ship out)."""
    try:
        service = InventoryService(session)
        success = await service.fulfill_inventory(product_id, warehouse_id, quantity)
        if success:
            return {"message": "Inventory fulfilled successfully"}
        else:
            raise HTTPException(status_code=400, detail="Insufficient inventory to fulfill")
    except WearForceException as e:
        raise exception_handler(e)


# Supplier endpoints
@router.post("/suppliers", response_model=SupplierRead, dependencies=[Depends(require_erp_write)])
async def create_supplier(
    supplier_data: SupplierCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new supplier."""
    try:
        service = SupplierService(session)
        return await service.create_supplier(supplier_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/suppliers/{supplier_id}", response_model=SupplierRead, dependencies=[Depends(require_erp_read)])
async def get_supplier(
    supplier_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get supplier by ID."""
    try:
        service = SupplierService(session)
        return await service.get_supplier(supplier_id)
    except WearForceException as e:
        raise exception_handler(e)


@router.put("/suppliers/{supplier_id}", response_model=SupplierRead, dependencies=[Depends(require_erp_write)])
async def update_supplier(
    supplier_id: int,
    supplier_data: SupplierUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Update a supplier."""
    try:
        service = SupplierService(session)
        return await service.update_supplier(supplier_id, supplier_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.delete("/suppliers/{supplier_id}", dependencies=[Depends(require_erp_delete)])
async def delete_supplier(
    supplier_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Delete a supplier."""
    try:
        service = SupplierService(session)
        await service.delete_supplier(supplier_id)
        return {"message": "Supplier deleted successfully"}
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/suppliers", response_model=PaginatedResponse, dependencies=[Depends(require_erp_read)])
async def search_suppliers(
    search: Optional[str] = Query(None, description="Search term for name, code, or contact person"),
    status: Optional[str] = Query(None, description="Supplier status filter"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    session: AsyncSession = Depends(get_session)
):
    """Search suppliers with filters and pagination."""
    try:
        skip, limit = paginate_query_params(skip, limit)
        service = SupplierService(session)
        suppliers, total = await service.search_suppliers(search, status, skip, limit)
        return PaginatedResponse.create(suppliers, total, skip, limit)
    except WearForceException as e:
        raise exception_handler(e)


# Order endpoints
@router.post("/orders", response_model=OrderRead, dependencies=[Depends(require_erp_write)])
async def create_order(
    order_data: OrderCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new order."""
    try:
        service = OrderService(session)
        return await service.create_order(order_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/orders/{order_id}", response_model=OrderRead, dependencies=[Depends(require_erp_read)])
async def get_order(
    order_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get order by ID."""
    try:
        service = OrderService(session)
        return await service.get_order(order_id)
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/orders/number/{order_number}", response_model=OrderRead, dependencies=[Depends(require_erp_read)])
async def get_order_by_number(
    order_number: str,
    session: AsyncSession = Depends(get_session)
):
    """Get order by order number."""
    try:
        service = OrderService(session)
        return await service.get_order_by_number(order_number)
    except WearForceException as e:
        raise exception_handler(e)


@router.put("/orders/{order_id}", response_model=OrderRead, dependencies=[Depends(require_erp_write)])
async def update_order(
    order_id: int,
    order_data: OrderUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Update an order."""
    try:
        service = OrderService(session)
        return await service.update_order(order_id, order_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.delete("/orders/{order_id}", dependencies=[Depends(require_erp_delete)])
async def delete_order(
    order_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Delete an order."""
    try:
        service = OrderService(session)
        await service.delete_order(order_id)
        return {"message": "Order deleted successfully"}
    except WearForceException as e:
        raise exception_handler(e)


@router.get("/orders", response_model=PaginatedResponse, dependencies=[Depends(require_erp_read)])
async def search_orders(
    search: Optional[str] = Query(None, description="Search term for order number or customer"),
    order_type: Optional[str] = Query(None, description="Order type filter"),
    status: Optional[str] = Query(None, description="Order status filter"),
    customer_name: Optional[str] = Query(None, description="Customer name filter"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    session: AsyncSession = Depends(get_session)
):
    """Search orders with filters and pagination."""
    try:
        skip, limit = paginate_query_params(skip, limit)
        service = OrderService(session)
        orders, total = await service.search_orders(search, order_type, status, customer_name, skip, limit)
        return PaginatedResponse.create(orders, total, skip, limit)
    except WearForceException as e:
        raise exception_handler(e)


@router.post("/orders/{order_id}/items", response_model=OrderItemRead, dependencies=[Depends(require_erp_write)])
async def add_order_item(
    order_id: int,
    item_data: OrderItemCreate,
    session: AsyncSession = Depends(get_session)
):
    """Add an item to an order."""
    try:
        service = OrderService(session)
        return await service.add_order_item(order_id, item_data)
    except WearForceException as e:
        raise exception_handler(e)


@router.post("/orders/{order_id}/confirm", response_model=OrderRead, dependencies=[Depends(require_erp_write)])
async def confirm_order(
    order_id: int,
    warehouse_id: Optional[int] = Query(None, description="Warehouse to fulfill from (uses default if not specified)"),
    session: AsyncSession = Depends(get_session)
):
    """Confirm an order and reserve inventory."""
    try:
        service = OrderService(session)
        return await service.confirm_order(order_id, warehouse_id)
    except WearForceException as e:
        raise exception_handler(e)


# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "erp-service"}