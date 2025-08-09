"""Database utilities and models."""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, List, Optional

import asyncpg
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import DeclarativeBase

from .config import DatabaseConfig


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""
    pass


class DatabaseManager:
    """Database connection manager."""
    
    def __init__(self, config: DatabaseConfig) -> None:
        """Initialize database manager."""
        self.config = config
        self.engine = create_async_engine(
            config.url,
            echo=config.debug if hasattr(config, 'debug') else False,
            pool_size=20,
            max_overflow=0,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session with context management."""
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def health_check(self) -> bool:
        """Check database health."""
        try:
            async with self.engine.connect() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception:
            return False
    
    async def close(self) -> None:
        """Close database connections."""
        await self.engine.dispose()


class RedisManager:
    """Redis connection manager."""
    
    def __init__(self, config: Any) -> None:
        """Initialize Redis manager."""
        import redis.asyncio as redis
        
        self.config = config
        self.pool = redis.ConnectionPool.from_url(
            config.url,
            max_connections=config.max_connections,
            retry_on_timeout=True,
            socket_keepalive=True,
            socket_keepalive_options={},
        )
        self.client = redis.Redis(connection_pool=self.pool)
    
    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        return await self.client.get(key)
    
    async def set(
        self,
        key: str,
        value: str,
        ex: Optional[int] = None,
        px: Optional[int] = None,
    ) -> bool:
        """Set key-value pair with optional expiration."""
        return await self.client.set(key, value, ex=ex, px=px)
    
    async def delete(self, *keys: str) -> int:
        """Delete keys."""
        return await self.client.delete(*keys)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        return bool(await self.client.exists(key))
    
    async def lpush(self, key: str, *values: str) -> int:
        """Push values to list (left side)."""
        return await self.client.lpush(key, *values)
    
    async def rpop(self, key: str) -> Optional[str]:
        """Pop value from list (right side)."""
        return await self.client.rpop(key)
    
    async def lrange(self, key: str, start: int = 0, end: int = -1) -> List[str]:
        """Get list range."""
        return await self.client.lrange(key, start, end)
    
    async def ltrim(self, key: str, start: int, end: int) -> bool:
        """Trim list to specified range."""
        return await self.client.ltrim(key, start, end)
    
    async def hset(self, name: str, mapping: Dict[str, str]) -> int:
        """Set hash fields."""
        return await self.client.hset(name, mapping=mapping)
    
    async def hget(self, name: str, key: str) -> Optional[str]:
        """Get hash field value."""
        return await self.client.hget(name, key)
    
    async def hgetall(self, name: str) -> Dict[str, str]:
        """Get all hash fields."""
        return await self.client.hgetall(name)
    
    async def hdel(self, name: str, *keys: str) -> int:
        """Delete hash fields."""
        return await self.client.hdel(name, *keys)
    
    async def expire(self, key: str, time: int) -> bool:
        """Set key expiration."""
        return await self.client.expire(key, time)
    
    async def health_check(self) -> bool:
        """Check Redis health."""
        try:
            await self.client.ping()
            return True
        except Exception:
            return False
    
    async def close(self) -> None:
        """Close Redis connections."""
        await self.client.close()
        await self.pool.disconnect()


class VectorDatabaseManager:
    """Qdrant vector database manager."""
    
    def __init__(self, config: Any) -> None:
        """Initialize vector database manager."""
        from qdrant_client import AsyncQdrantClient
        from qdrant_client.models import Distance, VectorParams
        
        self.config = config
        self.client = AsyncQdrantClient(
            host=config.host,
            port=config.port,
            api_key=config.api_key,
        )
        self.collection_name = config.collection_name
        self.embedding_dim = config.embedding_dim
        
    async def create_collection(self) -> None:
        """Create collection if it doesn't exist."""
        from qdrant_client.models import Distance, VectorParams
        
        collections = await self.client.get_collections()
        collection_names = [c.name for c in collections.collections]
        
        if self.collection_name not in collection_names:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_dim,
                    distance=Distance.COSINE,
                ),
            )
    
    async def upsert_vectors(
        self,
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
        ids: Optional[List[str]] = None,
    ) -> None:
        """Upsert vectors with payloads."""
        from qdrant_client.models import PointStruct
        
        if ids is None:
            ids = [str(i) for i in range(len(vectors))]
        
        points = [
            PointStruct(id=id_, vector=vector, payload=payload)
            for id_, vector, payload in zip(ids, vectors, payloads)
        ]
        
        await self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
    
    async def search(
        self,
        query_vector: List[float],
        limit: int = 5,
        score_threshold: Optional[float] = None,
        filter_conditions: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search similar vectors."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        search_filter = None
        if filter_conditions:
            conditions = []
            for field, value in filter_conditions.items():
                conditions.append(
                    FieldCondition(key=field, match=MatchValue(value=value))
                )
            search_filter = Filter(must=conditions)
        
        results = await self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=search_filter,
        )
        
        return [
            {
                "id": hit.id,
                "score": hit.score,
                "payload": hit.payload,
            }
            for hit in results
        ]
    
    async def delete_vectors(self, ids: List[str]) -> None:
        """Delete vectors by IDs."""
        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=ids,
        )
    
    async def health_check(self) -> bool:
        """Check Qdrant health."""
        try:
            collections = await self.client.get_collections()
            return True
        except Exception:
            return False
    
    async def close(self) -> None:
        """Close Qdrant client."""
        await self.client.close()


class ConversationStore:
    """Redis-based conversation storage."""
    
    def __init__(self, redis_manager: RedisManager, ttl: int = 3600):
        self.redis = redis_manager
        self.ttl = ttl
    
    async def save_conversation(
        self,
        conversation_id: str,
        conversation: Dict[str, Any],
    ) -> None:
        """Save conversation to Redis."""
        import json
        key = f"conversation:{conversation_id}"
        value = json.dumps(conversation, default=str)
        await self.redis.set(key, value, ex=self.ttl)
    
    async def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation from Redis."""
        import json
        key = f"conversation:{conversation_id}"
        value = await self.redis.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    
    async def add_message(
        self,
        conversation_id: str,
        message: Dict[str, Any],
    ) -> None:
        """Add message to conversation."""
        conversation = await self.get_conversation(conversation_id)
        if conversation is None:
            conversation = {
                "id": conversation_id,
                "messages": [],
                "created_at": message.get("timestamp"),
            }
        
        conversation["messages"].append(message)
        conversation["updated_at"] = message.get("timestamp")
        
        # Keep only last N messages
        max_messages = 100
        if len(conversation["messages"]) > max_messages:
            conversation["messages"] = conversation["messages"][-max_messages:]
        
        await self.save_conversation(conversation_id, conversation)
    
    async def get_messages(
        self,
        conversation_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get conversation messages."""
        conversation = await self.get_conversation(conversation_id)
        if conversation is None:
            return []
        
        messages = conversation.get("messages", [])
        return messages[-limit:] if limit > 0 else messages
    
    async def delete_conversation(self, conversation_id: str) -> None:
        """Delete conversation from Redis."""
        key = f"conversation:{conversation_id}"
        await self.redis.delete(key)


class CacheStore:
    """Redis-based caching utilities."""
    
    def __init__(self, redis_manager: RedisManager, default_ttl: int = 300):
        self.redis = redis_manager
        self.default_ttl = default_ttl
    
    async def get(self, key: str) -> Optional[Any]:
        """Get cached value."""
        import json
        value = await self.redis.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value  # Return as string if not JSON
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """Set cached value."""
        import json
        try:
            if isinstance(value, (dict, list)):
                json_value = json.dumps(value, default=str)
            else:
                json_value = str(value)
            return await self.redis.set(key, json_value, ex=ttl or self.default_ttl)
        except (TypeError, ValueError):
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete cached value."""
        result = await self.redis.delete(key)
        return result > 0
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        return await self.redis.exists(key)
    
    def cache_key(self, prefix: str, *args: str) -> str:
        """Generate cache key."""
        parts = [prefix] + list(args)
        return ":".join(parts)


class SessionStore:
    """Session management with Redis."""
    
    def __init__(self, redis_manager: RedisManager, session_ttl: int = 3600):
        self.redis = redis_manager
        self.session_ttl = session_ttl
    
    async def create_session(
        self,
        session_id: str,
        data: Dict[str, Any],
    ) -> None:
        """Create a new session."""
        import json
        key = f"session:{session_id}"
        value = json.dumps(data, default=str)
        await self.redis.set(key, value, ex=self.session_ttl)
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data."""
        import json
        key = f"session:{session_id}"
        value = await self.redis.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    
    async def update_session(
        self,
        session_id: str,
        data: Dict[str, Any],
    ) -> None:
        """Update session data."""
        await self.create_session(session_id, data)
    
    async def delete_session(self, session_id: str) -> None:
        """Delete session."""
        key = f"session:{session_id}"
        await self.redis.delete(key)
    
    async def extend_session(self, session_id: str) -> bool:
        """Extend session TTL."""
        key = f"session:{session_id}"
        return await self.redis.expire(key, self.session_ttl)