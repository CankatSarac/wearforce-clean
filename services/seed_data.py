#!/usr/bin/env python3
"""
Seed data script for WearForce application.

This script populates the database with sample data for development and testing.
Run with: python seed_data.py
"""

import asyncio
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
import logging

# Add the services directory to Python path
sys.path.append('.')

from shared.config import get_settings
from shared.database import get_database

# Import models
from crm.models import Account, Contact, Deal, Activity, AccountType, ContactStatus, DealStage, ActivityType, Priority
from erp.models import (
    Product, Warehouse, InventoryItem, Supplier, Order, OrderItem, 
    ProductType, ProductStatus, StockStatus, SupplierStatus, OrderType, OrderStatus
)
from notification.models import NotificationTemplate, TemplateType

logger = logging.getLogger(__name__)


class DataSeeder:
    """Handles seeding data into the database."""
    
    def __init__(self):
        self.settings = get_settings()
        self.database = get_database()
    
    async def seed_all(self):
        """Seed all data."""
        logger.info("Starting data seeding...")
        
        async with self.database.session() as session:
            try:
                # Seed in order of dependencies
                await self.seed_accounts(session)
                await self.seed_contacts(session)
                await self.seed_deals(session)
                await self.seed_activities(session)
                
                await self.seed_warehouses(session)
                await self.seed_products(session)
                await self.seed_inventory(session)
                await self.seed_suppliers(session)
                await self.seed_orders(session)
                
                await self.seed_notification_templates(session)
                
                await session.commit()
                logger.info("Data seeding completed successfully!")
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error seeding data: {e}")
                raise
    
    async def seed_accounts(self, session):
        """Seed CRM accounts."""
        logger.info("Seeding accounts...")
        
        accounts_data = [
            {
                "name": "TechCorp Solutions",
                "account_type": AccountType.CUSTOMER,
                "status": "active",
                "industry": "Technology",
                "website": "https://techcorp.com",
                "phone": "+1-555-0101",
                "billing_street": "123 Tech Street",
                "billing_city": "San Francisco",
                "billing_state": "CA",
                "billing_postal_code": "94105",
                "billing_country": "USA",
                "annual_revenue": Decimal("50000000"),
                "employees": 500,
                "description": "Leading technology solutions provider",
                "created_by": "system"
            },
            {
                "name": "Global Manufacturing Inc",
                "account_type": AccountType.CUSTOMER,
                "status": "active",
                "industry": "Manufacturing",
                "website": "https://globalmanufacturing.com",
                "phone": "+1-555-0102",
                "billing_street": "456 Industrial Blvd",
                "billing_city": "Detroit",
                "billing_state": "MI",
                "billing_postal_code": "48201",
                "billing_country": "USA",
                "annual_revenue": Decimal("75000000"),
                "employees": 1200,
                "description": "Global manufacturing and logistics company",
                "created_by": "system"
            },
            {
                "name": "Retail Giants LLC",
                "account_type": AccountType.PROSPECT,
                "status": "active",
                "industry": "Retail",
                "website": "https://retailgiants.com",
                "phone": "+1-555-0103",
                "billing_street": "789 Commerce Ave",
                "billing_city": "New York",
                "billing_state": "NY",
                "billing_postal_code": "10001",
                "billing_country": "USA",
                "annual_revenue": Decimal("25000000"),
                "employees": 800,
                "description": "Major retail chain with nationwide presence",
                "created_by": "system"
            },
            {
                "name": "Innovation Startups",
                "account_type": AccountType.PARTNER,
                "status": "active",
                "industry": "Technology",
                "website": "https://innovationstartups.io",
                "phone": "+1-555-0104",
                "billing_street": "321 Innovation Way",
                "billing_city": "Austin",
                "billing_state": "TX",
                "billing_postal_code": "73301",
                "billing_country": "USA",
                "annual_revenue": Decimal("5000000"),
                "employees": 50,
                "description": "Emerging technology startup accelerator",
                "created_by": "system"
            }
        ]
        
        for account_data in accounts_data:
            account = Account(**account_data)
            session.add(account)
        
        await session.flush()  # Get IDs without committing


async def main():
    """Main function to run the seeder."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    seeder = DataSeeder()
    
    try:
        await seeder.seed_all()
        print("✅ Seed data created successfully!")
        
    except Exception as e:
        print(f"❌ Error creating seed data: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())