#!/usr/bin/env python3
"""
Database management script for WearForce services.

This script provides utilities for managing database migrations,
creating initial data, and performing database operations.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import typer
from alembic import command
from alembic.config import Config
from sqlalchemy import text

# Add the current directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent))

from shared.database import get_database
from shared.config import get_settings

app = typer.Typer(help="Database management utilities for WearForce services")


def get_alembic_config() -> Config:
    """Get Alembic configuration."""
    alembic_cfg = Config("alembic.ini")
    
    # Override database URL from settings
    settings = get_settings()
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database.url)
    
    return alembic_cfg


@app.command()
def init_db():
    """Initialize the database with all tables."""
    typer.echo("Initializing database...")
    
    async def _init():
        database = get_database()
        await database.init_database()
        typer.echo("✅ Database initialized successfully!")
    
    asyncio.run(_init())


@app.command()
def create_migration(message: str):
    """Create a new database migration."""
    if not message:
        typer.echo("❌ Migration message is required")
        raise typer.Exit(1)
    
    typer.echo(f"Creating migration: {message}")
    
    alembic_cfg = get_alembic_config()
    command.revision(alembic_cfg, message=message, autogenerate=True)
    
    typer.echo("✅ Migration created successfully!")


@app.command()
def migrate():
    """Run database migrations to the latest version."""
    typer.echo("Running database migrations...")
    
    alembic_cfg = get_alembic_config()
    command.upgrade(alembic_cfg, "head")
    
    typer.echo("✅ Migrations completed successfully!")


@app.command()
def rollback(revision: Optional[str] = None):
    """Rollback database to a specific revision."""
    if not revision:
        revision = "-1"  # Rollback one revision
    
    typer.echo(f"Rolling back to revision: {revision}")
    
    alembic_cfg = get_alembic_config()
    command.downgrade(alembic_cfg, revision)
    
    typer.echo("✅ Rollback completed successfully!")


@app.command()
def migration_history():
    """Show migration history."""
    typer.echo("Migration history:")
    
    alembic_cfg = get_alembic_config()
    command.history(alembic_cfg, verbose=True)


@app.command()
def current_revision():
    """Show current database revision."""
    typer.echo("Current database revision:")
    
    alembic_cfg = get_alembic_config()
    command.current(alembic_cfg, verbose=True)


@app.command()
def reset_db():
    """Reset database - DROP ALL TABLES and recreate."""
    if not typer.confirm("⚠️  This will DELETE ALL DATA in the database. Are you sure?"):
        typer.echo("Aborted.")
        return
    
    typer.echo("Resetting database...")
    
    async def _reset():
        database = get_database()
        
        # Drop all tables
        async with database.engine.begin() as conn:
            await conn.run_sync(database.metadata.drop_all)
            typer.echo("🗑️  All tables dropped")
        
        # Recreate all tables
        await database.init_database()
        typer.echo("✅ Database reset successfully!")
    
    asyncio.run(_reset())


@app.command()
def check_connection():
    """Check database connection."""
    typer.echo("Checking database connection...")
    
    async def _check():
        try:
            database = get_database()
            async with database.session() as session:
                result = await session.exec(text("SELECT 1"))
                if result.first():
                    typer.echo("✅ Database connection successful!")
                else:
                    typer.echo("❌ Database connection failed!")
        except Exception as e:
            typer.echo(f"❌ Database connection failed: {e}")
    
    asyncio.run(_check())


@app.command()
def seed_data():
    """Seed the database with initial data."""
    typer.echo("Seeding database with initial data...")
    
    async def _seed():
        from seed_data import seed_all_data
        await seed_all_data()
        typer.echo("✅ Database seeded successfully!")
    
    asyncio.run(_seed())


@app.command()
def create_indexes():
    """Create additional database indexes for performance."""
    typer.echo("Creating database indexes...")
    
    async def _create_indexes():
        database = get_database()
        
        indexes = [
            # CRM indexes
            "CREATE INDEX IF NOT EXISTS idx_accounts_name ON accounts(name)",
            "CREATE INDEX IF NOT EXISTS idx_accounts_type_industry ON accounts(account_type, industry)",
            "CREATE INDEX IF NOT EXISTS idx_contacts_name ON contacts(first_name, last_name)",
            "CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email)",
            "CREATE INDEX IF NOT EXISTS idx_deals_stage_amount ON deals(stage, amount)",
            "CREATE INDEX IF NOT EXISTS idx_activities_due_date ON activities(due_date)",
            "CREATE INDEX IF NOT EXISTS idx_activities_completed ON activities(completed)",
            
            # ERP indexes
            "CREATE INDEX IF NOT EXISTS idx_products_name_sku ON products(name, sku)",
            "CREATE INDEX IF NOT EXISTS idx_products_category_brand ON products(category, brand)",
            "CREATE INDEX IF NOT EXISTS idx_inventory_product_warehouse ON inventory_items(product_id, warehouse_id)",
            "CREATE INDEX IF NOT EXISTS idx_inventory_stock_status ON inventory_items(stock_status)",
            "CREATE INDEX IF NOT EXISTS idx_orders_number_date ON orders(order_number, order_date)",
            "CREATE INDEX IF NOT EXISTS idx_orders_status_type ON orders(status, order_type)",
            "CREATE INDEX IF NOT EXISTS idx_suppliers_name_code ON suppliers(name, code)",
            
            # Notification indexes
            "CREATE INDEX IF NOT EXISTS idx_notifications_status_type ON notifications(status, notification_type)",
            "CREATE INDEX IF NOT EXISTS idx_notifications_recipient ON notifications(recipient_email, recipient_phone)",
            "CREATE INDEX IF NOT EXISTS idx_notifications_scheduled ON notifications(scheduled_at)",
            "CREATE INDEX IF NOT EXISTS idx_templates_type_active ON notification_templates(template_type, is_active)",
            "CREATE INDEX IF NOT EXISTS idx_webhooks_status ON webhooks(status)",
        ]
        
        async with database.engine.begin() as conn:
            for index_sql in indexes:
                await conn.exec(text(index_sql))
        
        typer.echo("✅ Database indexes created successfully!")
    
    asyncio.run(_create_indexes())


@app.command()
def backup_data(output_file: str):
    """Backup database data to a file."""
    typer.echo(f"Backing up database to {output_file}...")
    
    # This would implement a data backup mechanism
    # For now, just show the command would work
    typer.echo("ℹ️  Backup functionality would be implemented here")
    typer.echo("💡 Consider using pg_dump for PostgreSQL backups")


@app.command()
def restore_data(input_file: str):
    """Restore database data from a file."""
    typer.echo(f"Restoring database from {input_file}...")
    
    # This would implement a data restore mechanism
    # For now, just show the command would work
    typer.echo("ℹ️  Restore functionality would be implemented here")
    typer.echo("💡 Consider using pg_restore for PostgreSQL restores")


if __name__ == "__main__":
    app()