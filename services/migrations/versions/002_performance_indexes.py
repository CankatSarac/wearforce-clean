"""Add performance optimization indexes

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add critical performance indexes for all tables"""
    
    # ### CRM Tables Indexes ###
    
    # Accounts table indexes
    op.create_index('ix_accounts_status', 'accounts', ['status'], unique=False)
    op.create_index('ix_accounts_industry', 'accounts', ['industry'], unique=False)
    op.create_index('ix_accounts_created_at', 'accounts', ['created_at'], unique=False)
    op.create_index('ix_accounts_updated_at', 'accounts', ['updated_at'], unique=False)
    op.create_index('ix_accounts_deleted', 'accounts', ['is_deleted', 'deleted_at'], unique=False)
    op.create_index('ix_accounts_created_by', 'accounts', ['created_by'], unique=False)
    op.create_index('ix_accounts_parent_account', 'accounts', ['parent_account_id'], unique=False)
    
    # Contacts table indexes
    op.create_index('ix_contacts_account_id', 'contacts', ['account_id'], unique=False)
    op.create_index('ix_contacts_created_at', 'contacts', ['created_at'], unique=False)
    op.create_index('ix_contacts_updated_at', 'contacts', ['updated_at'], unique=False)
    op.create_index('ix_contacts_deleted', 'contacts', ['is_deleted', 'deleted_at'], unique=False)
    op.create_index('ix_contacts_created_by', 'contacts', ['created_by'], unique=False)
    op.create_index('ix_contacts_lead_source', 'contacts', ['lead_source'], unique=False)
    op.create_index('ix_contacts_phone', 'contacts', ['phone'], unique=False)
    op.create_index('ix_contacts_mobile', 'contacts', ['mobile'], unique=False)
    
    # Deals table indexes
    op.create_index('ix_deals_stage', 'deals', ['stage'], unique=False)
    op.create_index('ix_deals_priority', 'deals', ['priority'], unique=False)
    op.create_index('ix_deals_close_date', 'deals', ['close_date'], unique=False)
    op.create_index('ix_deals_account_id', 'deals', ['account_id'], unique=False)
    op.create_index('ix_deals_contact_id', 'deals', ['contact_id'], unique=False)
    op.create_index('ix_deals_created_at', 'deals', ['created_at'], unique=False)
    op.create_index('ix_deals_updated_at', 'deals', ['updated_at'], unique=False)
    op.create_index('ix_deals_deleted', 'deals', ['is_deleted', 'deleted_at'], unique=False)
    op.create_index('ix_deals_created_by', 'deals', ['created_by'], unique=False)
    op.create_index('ix_deals_amount', 'deals', ['amount'], unique=False)
    op.create_index('ix_deals_probability', 'deals', ['probability'], unique=False)
    
    # Activities table indexes  
    op.create_index('ix_activities_type', 'activities', ['activity_type'], unique=False)
    op.create_index('ix_activities_status', 'activities', ['status'], unique=False)
    op.create_index('ix_activities_priority', 'activities', ['priority'], unique=False)
    op.create_index('ix_activities_start_date', 'activities', ['start_date'], unique=False)
    op.create_index('ix_activities_due_date', 'activities', ['due_date'], unique=False)
    op.create_index('ix_activities_account_id', 'activities', ['account_id'], unique=False)
    op.create_index('ix_activities_contact_id', 'activities', ['contact_id'], unique=False)
    op.create_index('ix_activities_deal_id', 'activities', ['deal_id'], unique=False)
    op.create_index('ix_activities_created_at', 'activities', ['created_at'], unique=False)
    op.create_index('ix_activities_updated_at', 'activities', ['updated_at'], unique=False)
    op.create_index('ix_activities_deleted', 'activities', ['is_deleted', 'deleted_at'], unique=False)
    op.create_index('ix_activities_created_by', 'activities', ['created_by'], unique=False)
    
    # ### ERP Tables Indexes ###
    
    # Warehouses table indexes
    op.create_index('ix_warehouses_is_active', 'warehouses', ['is_active'], unique=False)
    op.create_index('ix_warehouses_is_default', 'warehouses', ['is_default'], unique=False)
    op.create_index('ix_warehouses_created_at', 'warehouses', ['created_at'], unique=False)
    op.create_index('ix_warehouses_updated_at', 'warehouses', ['updated_at'], unique=False)
    op.create_index('ix_warehouses_deleted', 'warehouses', ['is_deleted', 'deleted_at'], unique=False)
    
    # Products table indexes
    op.create_index('ix_products_product_type', 'products', ['product_type'], unique=False)
    op.create_index('ix_products_status', 'products', ['status'], unique=False)
    op.create_index('ix_products_category', 'products', ['category'], unique=False)
    op.create_index('ix_products_brand', 'products', ['brand'], unique=False)
    op.create_index('ix_products_manufacturer', 'products', ['manufacturer'], unique=False)
    op.create_index('ix_products_track_inventory', 'products', ['track_inventory'], unique=False)
    op.create_index('ix_products_created_at', 'products', ['created_at'], unique=False)
    op.create_index('ix_products_updated_at', 'products', ['updated_at'], unique=False)
    op.create_index('ix_products_deleted', 'products', ['is_deleted', 'deleted_at'], unique=False)
    op.create_index('ix_products_created_by', 'products', ['created_by'], unique=False)
    op.create_index('ix_products_selling_price', 'products', ['selling_price'], unique=False)
    
    # Inventory items table indexes
    op.create_index('ix_inventory_warehouse_id', 'inventory_items', ['warehouse_id'], unique=False)
    op.create_index('ix_inventory_product_id', 'inventory_items', ['product_id'], unique=False)
    op.create_index('ix_inventory_stock_status', 'inventory_items', ['stock_status'], unique=False)
    op.create_index('ix_inventory_created_at', 'inventory_items', ['created_at'], unique=False)
    op.create_index('ix_inventory_updated_at', 'inventory_items', ['updated_at'], unique=False)
    op.create_index('ix_inventory_deleted', 'inventory_items', ['is_deleted', 'deleted_at'], unique=False)
    op.create_index('ix_inventory_quantity_on_hand', 'inventory_items', ['quantity_on_hand'], unique=False)
    op.create_index('ix_inventory_quantity_available', 'inventory_items', ['quantity_available'], unique=False)
    
    # Suppliers table indexes
    op.create_index('ix_suppliers_status', 'suppliers', ['status'], unique=False)
    op.create_index('ix_suppliers_email', 'suppliers', ['email'], unique=False)
    op.create_index('ix_suppliers_phone', 'suppliers', ['phone'], unique=False)
    op.create_index('ix_suppliers_created_at', 'suppliers', ['created_at'], unique=False)
    op.create_index('ix_suppliers_updated_at', 'suppliers', ['updated_at'], unique=False)
    op.create_index('ix_suppliers_deleted', 'suppliers', ['is_deleted', 'deleted_at'], unique=False)
    op.create_index('ix_suppliers_rating', 'suppliers', ['rating'], unique=False)
    
    # Orders table indexes
    op.create_index('ix_orders_order_type', 'orders', ['order_type'], unique=False)
    op.create_index('ix_orders_status', 'orders', ['status'], unique=False)
    op.create_index('ix_orders_order_date', 'orders', ['order_date'], unique=False)
    op.create_index('ix_orders_required_date', 'orders', ['required_date'], unique=False)
    op.create_index('ix_orders_shipped_date', 'orders', ['shipped_date'], unique=False)
    op.create_index('ix_orders_delivered_date', 'orders', ['delivered_date'], unique=False)
    op.create_index('ix_orders_customer_email', 'orders', ['customer_email'], unique=False)
    op.create_index('ix_orders_customer_phone', 'orders', ['customer_phone'], unique=False)
    op.create_index('ix_orders_created_at', 'orders', ['created_at'], unique=False)
    op.create_index('ix_orders_updated_at', 'orders', ['updated_at'], unique=False)
    op.create_index('ix_orders_deleted', 'orders', ['is_deleted', 'deleted_at'], unique=False)
    op.create_index('ix_orders_created_by', 'orders', ['created_by'], unique=False)
    op.create_index('ix_orders_total_amount', 'orders', ['total_amount'], unique=False)
    op.create_index('ix_orders_tracking_number', 'orders', ['tracking_number'], unique=False)
    
    # Order items table indexes
    op.create_index('ix_order_items_order_id', 'order_items', ['order_id'], unique=False)
    op.create_index('ix_order_items_product_id', 'order_items', ['product_id'], unique=False)
    op.create_index('ix_order_items_product_sku', 'order_items', ['product_sku'], unique=False)
    op.create_index('ix_order_items_created_at', 'order_items', ['created_at'], unique=False)
    op.create_index('ix_order_items_updated_at', 'order_items', ['updated_at'], unique=False)
    op.create_index('ix_order_items_quantity', 'order_items', ['quantity'], unique=False)
    op.create_index('ix_order_items_unit_price', 'order_items', ['unit_price'], unique=False)
    
    # Purchase orders table indexes
    op.create_index('ix_purchase_orders_status', 'purchase_orders', ['status'], unique=False)
    op.create_index('ix_purchase_orders_supplier_id', 'purchase_orders', ['supplier_id'], unique=False)
    op.create_index('ix_purchase_orders_order_date', 'purchase_orders', ['order_date'], unique=False)
    op.create_index('ix_purchase_orders_expected_delivery', 'purchase_orders', ['expected_delivery_date'], unique=False)
    op.create_index('ix_purchase_orders_delivered_date', 'purchase_orders', ['delivered_date'], unique=False)
    op.create_index('ix_purchase_orders_created_at', 'purchase_orders', ['created_at'], unique=False)
    op.create_index('ix_purchase_orders_updated_at', 'purchase_orders', ['updated_at'], unique=False)
    op.create_index('ix_purchase_orders_deleted', 'purchase_orders', ['is_deleted', 'deleted_at'], unique=False)
    op.create_index('ix_purchase_orders_created_by', 'purchase_orders', ['created_by'], unique=False)
    op.create_index('ix_purchase_orders_total_amount', 'purchase_orders', ['total_amount'], unique=False)
    
    # Purchase order items table indexes
    op.create_index('ix_purchase_order_items_po_id', 'purchase_order_items', ['purchase_order_id'], unique=False)
    op.create_index('ix_purchase_order_items_product_id', 'purchase_order_items', ['product_id'], unique=False)
    op.create_index('ix_purchase_order_items_product_sku', 'purchase_order_items', ['product_sku'], unique=False)
    op.create_index('ix_purchase_order_items_created_at', 'purchase_order_items', ['created_at'], unique=False)
    op.create_index('ix_purchase_order_items_updated_at', 'purchase_order_items', ['updated_at'], unique=False)
    
    # Stock movements table indexes
    op.create_index('ix_stock_movements_product_id', 'stock_movements', ['product_id'], unique=False)
    op.create_index('ix_stock_movements_warehouse_id', 'stock_movements', ['warehouse_id'], unique=False)
    op.create_index('ix_stock_movements_type', 'stock_movements', ['movement_type'], unique=False)
    op.create_index('ix_stock_movements_created_at', 'stock_movements', ['created_at'], unique=False)
    op.create_index('ix_stock_movements_updated_at', 'stock_movements', ['updated_at'], unique=False)
    op.create_index('ix_stock_movements_reference', 'stock_movements', ['reference_number'], unique=False)
    op.create_index('ix_stock_movements_reason', 'stock_movements', ['reason'], unique=False)
    
    # Composite indexes for common query patterns
    op.create_index('ix_stock_movements_product_warehouse_date', 'stock_movements', 
                   ['product_id', 'warehouse_id', 'created_at'], unique=False)
    
    # ### Notification Tables Indexes ###
    
    # Notification templates table indexes
    op.create_index('ix_notification_templates_type', 'notification_templates', ['template_type'], unique=False)
    op.create_index('ix_notification_templates_active', 'notification_templates', ['is_active'], unique=False)
    op.create_index('ix_notification_templates_language', 'notification_templates', ['language'], unique=False)
    op.create_index('ix_notification_templates_created_at', 'notification_templates', ['created_at'], unique=False)
    op.create_index('ix_notification_templates_updated_at', 'notification_templates', ['updated_at'], unique=False)
    op.create_index('ix_notification_templates_deleted', 'notification_templates', ['is_deleted', 'deleted_at'], unique=False)
    
    # Notifications table indexes
    op.create_index('ix_notifications_priority', 'notifications', ['priority'], unique=False)
    op.create_index('ix_notifications_recipient_email', 'notifications', ['recipient_email'], unique=False)
    op.create_index('ix_notifications_recipient_phone', 'notifications', ['recipient_phone'], unique=False)
    op.create_index('ix_notifications_template_id', 'notifications', ['template_id'], unique=False)
    op.create_index('ix_notifications_scheduled_at', 'notifications', ['scheduled_at'], unique=False)
    op.create_index('ix_notifications_sent_at', 'notifications', ['sent_at'], unique=False)
    op.create_index('ix_notifications_delivered_at', 'notifications', ['delivered_at'], unique=False)
    op.create_index('ix_notifications_created_at', 'notifications', ['created_at'], unique=False)
    op.create_index('ix_notifications_updated_at', 'notifications', ['updated_at'], unique=False)
    op.create_index('ix_notifications_external_id', 'notifications', ['external_id'], unique=False)
    op.create_index('ix_notifications_retry_count', 'notifications', ['retry_count'], unique=False)
    op.create_index('ix_notifications_source', 'notifications', ['source_service', 'source_event'], unique=False)
    op.create_index('ix_notifications_correlation_id', 'notifications', ['correlation_id'], unique=False)
    
    # Webhooks table indexes
    op.create_index('ix_webhooks_status', 'webhooks', ['status'], unique=False)
    op.create_index('ix_webhooks_url', 'webhooks', ['url'], unique=False)
    op.create_index('ix_webhooks_created_at', 'webhooks', ['created_at'], unique=False)
    op.create_index('ix_webhooks_updated_at', 'webhooks', ['updated_at'], unique=False)
    op.create_index('ix_webhooks_deleted', 'webhooks', ['is_deleted', 'deleted_at'], unique=False)
    op.create_index('ix_webhooks_last_triggered', 'webhooks', ['last_triggered_at'], unique=False)
    op.create_index('ix_webhooks_last_success', 'webhooks', ['last_success_at'], unique=False)
    op.create_index('ix_webhooks_failure_count', 'webhooks', ['failure_count'], unique=False)
    
    # Webhook deliveries table indexes
    op.create_index('ix_webhook_deliveries_webhook_id', 'webhook_deliveries', ['webhook_id'], unique=False)
    op.create_index('ix_webhook_deliveries_event_type', 'webhook_deliveries', ['event_type'], unique=False)
    op.create_index('ix_webhook_deliveries_sent_at', 'webhook_deliveries', ['sent_at'], unique=False)
    op.create_index('ix_webhook_deliveries_created_at', 'webhook_deliveries', ['created_at'], unique=False)
    op.create_index('ix_webhook_deliveries_updated_at', 'webhook_deliveries', ['updated_at'], unique=False)
    op.create_index('ix_webhook_deliveries_is_success', 'webhook_deliveries', ['is_success'], unique=False)
    op.create_index('ix_webhook_deliveries_retry_count', 'webhook_deliveries', ['retry_count'], unique=False)
    op.create_index('ix_webhook_deliveries_response_status', 'webhook_deliveries', ['response_status'], unique=False)
    
    # Composite indexes for performance-critical query patterns
    op.create_index('ix_notifications_status_scheduled', 'notifications', 
                   ['status', 'scheduled_at'], unique=False)
    op.create_index('ix_notifications_recipient_status', 'notifications', 
                   ['recipient_id', 'status'], unique=False)
    op.create_index('ix_webhook_deliveries_webhook_success', 'webhook_deliveries', 
                   ['webhook_id', 'is_success'], unique=False)
    op.create_index('ix_deals_stage_close_date', 'deals', 
                   ['stage', 'close_date'], unique=False)
    op.create_index('ix_orders_status_date', 'orders', 
                   ['status', 'order_date'], unique=False)
    op.create_index('ix_activities_type_status_date', 'activities', 
                   ['activity_type', 'status', 'due_date'], unique=False)


def downgrade() -> None:
    """Remove performance optimization indexes"""
    
    # Drop composite indexes
    op.drop_index('ix_activities_type_status_date', 'activities')
    op.drop_index('ix_orders_status_date', 'orders')
    op.drop_index('ix_deals_stage_close_date', 'deals')
    op.drop_index('ix_webhook_deliveries_webhook_success', 'webhook_deliveries')
    op.drop_index('ix_notifications_recipient_status', 'notifications')
    op.drop_index('ix_notifications_status_scheduled', 'notifications')
    op.drop_index('ix_stock_movements_product_warehouse_date', 'stock_movements')
    
    # Drop webhook deliveries indexes
    op.drop_index('ix_webhook_deliveries_response_status', 'webhook_deliveries')
    op.drop_index('ix_webhook_deliveries_retry_count', 'webhook_deliveries')
    op.drop_index('ix_webhook_deliveries_is_success', 'webhook_deliveries')
    op.drop_index('ix_webhook_deliveries_updated_at', 'webhook_deliveries')
    op.drop_index('ix_webhook_deliveries_created_at', 'webhook_deliveries')
    op.drop_index('ix_webhook_deliveries_sent_at', 'webhook_deliveries')
    op.drop_index('ix_webhook_deliveries_event_type', 'webhook_deliveries')
    op.drop_index('ix_webhook_deliveries_webhook_id', 'webhook_deliveries')
    
    # Drop webhooks indexes
    op.drop_index('ix_webhooks_failure_count', 'webhooks')
    op.drop_index('ix_webhooks_last_success', 'webhooks')
    op.drop_index('ix_webhooks_last_triggered', 'webhooks')
    op.drop_index('ix_webhooks_deleted', 'webhooks')
    op.drop_index('ix_webhooks_updated_at', 'webhooks')
    op.drop_index('ix_webhooks_created_at', 'webhooks')
    op.drop_index('ix_webhooks_url', 'webhooks')
    op.drop_index('ix_webhooks_status', 'webhooks')
    
    # Drop notifications indexes
    op.drop_index('ix_notifications_correlation_id', 'notifications')
    op.drop_index('ix_notifications_source', 'notifications')
    op.drop_index('ix_notifications_retry_count', 'notifications')
    op.drop_index('ix_notifications_external_id', 'notifications')
    op.drop_index('ix_notifications_updated_at', 'notifications')
    op.drop_index('ix_notifications_created_at', 'notifications')
    op.drop_index('ix_notifications_delivered_at', 'notifications')
    op.drop_index('ix_notifications_sent_at', 'notifications')
    op.drop_index('ix_notifications_scheduled_at', 'notifications')
    op.drop_index('ix_notifications_template_id', 'notifications')
    op.drop_index('ix_notifications_recipient_phone', 'notifications')
    op.drop_index('ix_notifications_recipient_email', 'notifications')
    op.drop_index('ix_notifications_priority', 'notifications')
    
    # Drop notification templates indexes
    op.drop_index('ix_notification_templates_deleted', 'notification_templates')
    op.drop_index('ix_notification_templates_updated_at', 'notification_templates')
    op.drop_index('ix_notification_templates_created_at', 'notification_templates')
    op.drop_index('ix_notification_templates_language', 'notification_templates')
    op.drop_index('ix_notification_templates_active', 'notification_templates')
    op.drop_index('ix_notification_templates_type', 'notification_templates')
    
    # Drop stock movements indexes
    op.drop_index('ix_stock_movements_reason', 'stock_movements')
    op.drop_index('ix_stock_movements_reference', 'stock_movements')
    op.drop_index('ix_stock_movements_updated_at', 'stock_movements')
    op.drop_index('ix_stock_movements_created_at', 'stock_movements')
    op.drop_index('ix_stock_movements_type', 'stock_movements')
    op.drop_index('ix_stock_movements_warehouse_id', 'stock_movements')
    op.drop_index('ix_stock_movements_product_id', 'stock_movements')
    
    # Drop purchase order items indexes
    op.drop_index('ix_purchase_order_items_updated_at', 'purchase_order_items')
    op.drop_index('ix_purchase_order_items_created_at', 'purchase_order_items')
    op.drop_index('ix_purchase_order_items_product_sku', 'purchase_order_items')
    op.drop_index('ix_purchase_order_items_product_id', 'purchase_order_items')
    op.drop_index('ix_purchase_order_items_po_id', 'purchase_order_items')
    
    # Drop purchase orders indexes
    op.drop_index('ix_purchase_orders_total_amount', 'purchase_orders')
    op.drop_index('ix_purchase_orders_created_by', 'purchase_orders')
    op.drop_index('ix_purchase_orders_deleted', 'purchase_orders')
    op.drop_index('ix_purchase_orders_updated_at', 'purchase_orders')
    op.drop_index('ix_purchase_orders_created_at', 'purchase_orders')
    op.drop_index('ix_purchase_orders_delivered_date', 'purchase_orders')
    op.drop_index('ix_purchase_orders_expected_delivery', 'purchase_orders')
    op.drop_index('ix_purchase_orders_order_date', 'purchase_orders')
    op.drop_index('ix_purchase_orders_supplier_id', 'purchase_orders')
    op.drop_index('ix_purchase_orders_status', 'purchase_orders')
    
    # Drop order items indexes
    op.drop_index('ix_order_items_unit_price', 'order_items')
    op.drop_index('ix_order_items_quantity', 'order_items')
    op.drop_index('ix_order_items_updated_at', 'order_items')
    op.drop_index('ix_order_items_created_at', 'order_items')
    op.drop_index('ix_order_items_product_sku', 'order_items')
    op.drop_index('ix_order_items_product_id', 'order_items')
    op.drop_index('ix_order_items_order_id', 'order_items')
    
    # Drop orders indexes
    op.drop_index('ix_orders_tracking_number', 'orders')
    op.drop_index('ix_orders_total_amount', 'orders')
    op.drop_index('ix_orders_created_by', 'orders')
    op.drop_index('ix_orders_deleted', 'orders')
    op.drop_index('ix_orders_updated_at', 'orders')
    op.drop_index('ix_orders_created_at', 'orders')
    op.drop_index('ix_orders_customer_phone', 'orders')
    op.drop_index('ix_orders_customer_email', 'orders')
    op.drop_index('ix_orders_delivered_date', 'orders')
    op.drop_index('ix_orders_shipped_date', 'orders')
    op.drop_index('ix_orders_required_date', 'orders')
    op.drop_index('ix_orders_order_date', 'orders')
    op.drop_index('ix_orders_status', 'orders')
    op.drop_index('ix_orders_order_type', 'orders')
    
    # Drop suppliers indexes
    op.drop_index('ix_suppliers_rating', 'suppliers')
    op.drop_index('ix_suppliers_deleted', 'suppliers')
    op.drop_index('ix_suppliers_updated_at', 'suppliers')
    op.drop_index('ix_suppliers_created_at', 'suppliers')
    op.drop_index('ix_suppliers_phone', 'suppliers')
    op.drop_index('ix_suppliers_email', 'suppliers')
    op.drop_index('ix_suppliers_status', 'suppliers')
    
    # Drop inventory items indexes
    op.drop_index('ix_inventory_quantity_available', 'inventory_items')
    op.drop_index('ix_inventory_quantity_on_hand', 'inventory_items')
    op.drop_index('ix_inventory_deleted', 'inventory_items')
    op.drop_index('ix_inventory_updated_at', 'inventory_items')
    op.drop_index('ix_inventory_created_at', 'inventory_items')
    op.drop_index('ix_inventory_stock_status', 'inventory_items')
    op.drop_index('ix_inventory_product_id', 'inventory_items')
    op.drop_index('ix_inventory_warehouse_id', 'inventory_items')
    
    # Drop products indexes
    op.drop_index('ix_products_selling_price', 'products')
    op.drop_index('ix_products_created_by', 'products')
    op.drop_index('ix_products_deleted', 'products')
    op.drop_index('ix_products_updated_at', 'products')
    op.drop_index('ix_products_created_at', 'products')
    op.drop_index('ix_products_track_inventory', 'products')
    op.drop_index('ix_products_manufacturer', 'products')
    op.drop_index('ix_products_brand', 'products')
    op.drop_index('ix_products_category', 'products')
    op.drop_index('ix_products_status', 'products')
    op.drop_index('ix_products_product_type', 'products')
    
    # Drop warehouses indexes
    op.drop_index('ix_warehouses_deleted', 'warehouses')
    op.drop_index('ix_warehouses_updated_at', 'warehouses')
    op.drop_index('ix_warehouses_created_at', 'warehouses')
    op.drop_index('ix_warehouses_is_default', 'warehouses')
    op.drop_index('ix_warehouses_is_active', 'warehouses')
    
    # Drop activities indexes
    op.drop_index('ix_activities_created_by', 'activities')
    op.drop_index('ix_activities_deleted', 'activities')
    op.drop_index('ix_activities_updated_at', 'activities')
    op.drop_index('ix_activities_created_at', 'activities')
    op.drop_index('ix_activities_deal_id', 'activities')
    op.drop_index('ix_activities_contact_id', 'activities')
    op.drop_index('ix_activities_account_id', 'activities')
    op.drop_index('ix_activities_due_date', 'activities')
    op.drop_index('ix_activities_start_date', 'activities')
    op.drop_index('ix_activities_priority', 'activities')
    op.drop_index('ix_activities_status', 'activities')
    op.drop_index('ix_activities_type', 'activities')
    
    # Drop deals indexes
    op.drop_index('ix_deals_probability', 'deals')
    op.drop_index('ix_deals_amount', 'deals')
    op.drop_index('ix_deals_created_by', 'deals')
    op.drop_index('ix_deals_deleted', 'deals')
    op.drop_index('ix_deals_updated_at', 'deals')
    op.drop_index('ix_deals_created_at', 'deals')
    op.drop_index('ix_deals_contact_id', 'deals')
    op.drop_index('ix_deals_account_id', 'deals')
    op.drop_index('ix_deals_close_date', 'deals')
    op.drop_index('ix_deals_priority', 'deals')
    op.drop_index('ix_deals_stage', 'deals')
    
    # Drop contacts indexes
    op.drop_index('ix_contacts_mobile', 'contacts')
    op.drop_index('ix_contacts_phone', 'contacts')
    op.drop_index('ix_contacts_lead_source', 'contacts')
    op.drop_index('ix_contacts_created_by', 'contacts')
    op.drop_index('ix_contacts_deleted', 'contacts')
    op.drop_index('ix_contacts_updated_at', 'contacts')
    op.drop_index('ix_contacts_created_at', 'contacts')
    op.drop_index('ix_contacts_account_id', 'contacts')
    
    # Drop accounts indexes
    op.drop_index('ix_accounts_parent_account', 'accounts')
    op.drop_index('ix_accounts_created_by', 'accounts')
    op.drop_index('ix_accounts_deleted', 'accounts')
    op.drop_index('ix_accounts_updated_at', 'accounts')
    op.drop_index('ix_accounts_created_at', 'accounts')
    op.drop_index('ix_accounts_industry', 'accounts')
    op.drop_index('ix_accounts_status', 'accounts')