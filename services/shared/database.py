import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlmodel import SQLModel, Field, select
from sqlalchemy import MetaData

from .config import DatabaseSettings


class TimestampMixin(SQLModel):
    """Mixin to add created_at and updated_at timestamps."""
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class SoftDeleteMixin(SQLModel):
    """Mixin to add soft delete functionality."""
    deleted_at: Optional[datetime] = Field(default=None, nullable=True)
    is_deleted: bool = Field(default=False, nullable=False)


class AuditMixin(SQLModel):
    """Mixin to add audit trail fields."""
    created_by: Optional[str] = Field(default=None, nullable=True)
    updated_by: Optional[str] = Field(default=None, nullable=True)
    version: int = Field(default=1, nullable=False)


class DatabaseManager:
    """Database connection and session management."""
    
    def __init__(self, settings: DatabaseSettings):
        self.settings = settings
        self.engine = create_async_engine(
            settings.url,
            pool_size=settings.pool_size,
            max_overflow=settings.max_overflow,
            echo=settings.echo,
            future=True,
        )
        self.session_maker = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    
    async def create_tables(self):
        """Create all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
    
    async def drop_tables(self):
        """Drop all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session."""
        async with self.session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def close(self):
        """Close the database connection."""
        await self.engine.dispose()


class BaseRepository:
    """Base repository class with common CRUD operations."""
    
    def __init__(self, session: AsyncSession, model_class):
        self.session = session
        self.model_class = model_class
    
    async def create(self, obj_data: dict) -> SQLModel:
        """Create a new record."""
        obj = self.model_class(**obj_data)
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj
    
    async def get(self, obj_id: int) -> Optional[SQLModel]:
        """Get a record by ID."""
        statement = select(self.model_class).where(self.model_class.id == obj_id)
        if hasattr(self.model_class, 'is_deleted'):
            statement = statement.where(self.model_class.is_deleted == False)
        result = await self.session.exec(statement)
        return result.first()
    
    async def get_all(self, skip: int = 0, limit: int = 100) -> list[SQLModel]:
        """Get all records with pagination."""
        statement = select(self.model_class).offset(skip).limit(limit)
        if hasattr(self.model_class, 'is_deleted'):
            statement = statement.where(self.model_class.is_deleted == False)
        result = await self.session.exec(statement)
        return result.all()
    
    async def update(self, obj_id: int, obj_data: dict) -> Optional[SQLModel]:
        """Update a record."""
        obj = await self.get(obj_id)
        if not obj:
            return None
        
        for key, value in obj_data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        
        if hasattr(obj, 'updated_at'):
            obj.updated_at = datetime.utcnow()
        
        if hasattr(obj, 'version'):
            obj.version += 1
        
        await self.session.flush()
        await self.session.refresh(obj)
        return obj
    
    async def delete(self, obj_id: int) -> bool:
        """Delete a record (soft delete if supported, otherwise hard delete)."""
        obj = await self.get(obj_id)
        if not obj:
            return False
        
        if hasattr(obj, 'is_deleted'):
            # Soft delete
            obj.is_deleted = True
            obj.deleted_at = datetime.utcnow()
            if hasattr(obj, 'updated_at'):
                obj.updated_at = datetime.utcnow()
        else:
            # Hard delete
            await self.session.delete(obj)
        
        return True
    
    async def count(self) -> int:
        """Count total records."""
        statement = select(self.model_class)
        if hasattr(self.model_class, 'is_deleted'):
            statement = statement.where(self.model_class.is_deleted == False)
        result = await self.session.exec(statement)
        return len(result.all())


# Global database manager instance
db_manager: Optional[DatabaseManager] = None


def init_database(settings: DatabaseSettings) -> DatabaseManager:
    """Initialize the database manager."""
    global db_manager
    db_manager = DatabaseManager(settings)
    return db_manager


def get_database() -> DatabaseManager:
    """Get the global database manager instance."""
    if db_manager is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return db_manager