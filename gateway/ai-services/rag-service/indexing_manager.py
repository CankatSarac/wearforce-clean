"""Enhanced incremental indexing manager with document tracking and bulk operations."""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set, Tuple
from enum import Enum
import structlog
from shared.models import Document
from shared.database import RedisManager
from .document_processor import ProcessedDocument, DataFormat

logger = structlog.get_logger(__name__)

class IndexingStatus(str, Enum):
    """Document indexing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"

@dataclass
class IndexedDocument:
    """Indexed document tracking information."""
    id: str
    source: str
    status: IndexingStatus
    created_at: datetime
    updated_at: datetime
    chunk_count: int
    data_format: str
    metadata: Dict[str, Any]
    error_message: Optional[str] = None
    retry_count: int = 0
    processing_time: Optional[float] = None
    version: int = 1

@dataclass
class IndexingJob:
    """Indexing job information."""
    job_id: str
    document_ids: List[str]
    job_type: str  # single, batch, bulk
    status: IndexingStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: int = 0
    total_documents: int = 0
    success_count: int = 0
    failure_count: int = 0
    error_summary: List[str] = None

class IndexingManager:
    """Enhanced indexing manager with document tracking and bulk operations."""
    
    def __init__(
        self, 
        vector_db, 
        embedding_engine, 
        document_processor, 
        redis_manager: RedisManager,
        max_retry_attempts: int = 3,
        bulk_batch_size: int = 100,
        concurrent_workers: int = 4
    ):
        self.vector_db = vector_db
        self.embedding_engine = embedding_engine
        self.document_processor = document_processor
        self.redis_manager = redis_manager
        self.max_retry_attempts = max_retry_attempts
        self.bulk_batch_size = bulk_batch_size
        self.concurrent_workers = concurrent_workers
        
        # Redis keys
        self.queue_key = "rag:indexing_queue"
        self.bulk_queue_key = "rag:bulk_indexing_queue"
        self.document_registry_key = "rag:document_registry"
        self.job_registry_key = "rag:job_registry"
        self.stats_key = "rag:indexing_stats"
        
        # State management
        self.is_running = False
        self.processor_tasks: List[asyncio.Task] = []
        self.bulk_processor_task: Optional[asyncio.Task] = None
        
        # In-memory caches
        self.document_cache: Dict[str, IndexedDocument] = {}
        self.active_jobs: Dict[str, IndexingJob] = {}
        
        # Statistics
        self.stats = {
            "indexed_documents": 0,
            "failed_documents": 0,
            "bulk_jobs_completed": 0,
            "total_processing_time": 0.0,
            "average_processing_time": 0.0,
            "last_indexing_time": None,
            "cache_hits": 0,
            "cache_misses": 0,
        }
    
    async def start(self) -> None:
        """Start the indexing processors."""
        if self.is_running:
            return
        
        logger.info(
            "Starting enhanced indexing manager",
            concurrent_workers=self.concurrent_workers,
            bulk_batch_size=self.bulk_batch_size
        )
        self.is_running = True
        
        # Load existing statistics
        await self._load_stats()
        
        # Load document registry cache
        await self._load_document_cache()
        
        # Start multiple worker tasks for concurrent processing
        for i in range(self.concurrent_workers):
            task = asyncio.create_task(self._process_queue_worker(f"worker-{i}"))
            self.processor_tasks.append(task)
        
        # Start bulk processing task
        self.bulk_processor_task = asyncio.create_task(self._process_bulk_queue())
        
        # Start periodic cleanup task
        asyncio.create_task(self._periodic_cleanup())
    
    async def stop(self) -> None:
        """Stop the indexing processors."""
        if not self.is_running:
            return
        
        logger.info("Stopping enhanced indexing manager")
        self.is_running = False
        
        # Cancel all worker tasks
        for task in self.processor_tasks:
            task.cancel()
        
        if self.bulk_processor_task:
            self.bulk_processor_task.cancel()
        
        # Wait for tasks to complete
        try:
            await asyncio.gather(*self.processor_tasks, return_exceptions=True)
            if self.bulk_processor_task:
                await self.bulk_processor_task
        except asyncio.CancelledError:
            pass
        
        # Save statistics
        await self._save_stats()
        
        logger.info("Enhanced indexing manager stopped")
    
    async def index_document(self, document: Document, job_type: str = "single") -> str:
        """Queue single document for indexing."""
        try:
            # Create job
            job_id = str(uuid.uuid4())
            job = IndexingJob(
                job_id=job_id,
                document_ids=[document.id],
                job_type=job_type,
                status=IndexingStatus.PENDING,
                created_at=datetime.utcnow(),
                total_documents=1
            )
            
            # Register job
            await self._save_job(job)
            self.active_jobs[job_id] = job
            
            # Create indexed document record
            indexed_doc = IndexedDocument(
                id=document.id,
                source=document.source or "unknown",
                status=IndexingStatus.PENDING,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                chunk_count=0,
                data_format="text",
                metadata=document.metadata or {}
            )
            
            await self._save_indexed_document(indexed_doc)
            self.document_cache[document.id] = indexed_doc
            
            # Queue document data
            document_data = {
                "id": document.id,
                "content": document.content,
                "source": document.source,
                "metadata": document.metadata,
                "created_at": document.created_at.isoformat(),
                "job_id": job_id,
                "job_type": job_type,
            }
            
            await self.redis_manager.lpush(
                self.queue_key,
                json.dumps(document_data, default=str)
            )
            
            logger.info(
                "Document queued for indexing",
                document_id=document.id,
                job_id=job_id,
                source=document.source
            )
            
            return job_id
            
        except Exception as e:
            logger.error("Failed to queue document for indexing", error=str(e))
            raise
    
    async def index_documents_bulk(
        self, 
        documents: List[Document], 
        priority: int = 0
    ) -> str:
        """Queue multiple documents for bulk indexing."""
        try:
            job_id = str(uuid.uuid4())
            
            # Create bulk job
            job = IndexingJob(
                job_id=job_id,
                document_ids=[doc.id for doc in documents],
                job_type="bulk",
                status=IndexingStatus.PENDING,
                created_at=datetime.utcnow(),
                total_documents=len(documents)
            )
            
            await self._save_job(job)
            self.active_jobs[job_id] = job
            
            # Prepare bulk data
            bulk_data = {
                "job_id": job_id,
                "priority": priority,
                "created_at": datetime.utcnow().isoformat(),
                "documents": [
                    {
                        "id": doc.id,
                        "content": doc.content,
                        "source": doc.source,
                        "metadata": doc.metadata or {},
                        "created_at": doc.created_at.isoformat(),
                    }
                    for doc in documents
                ]
            }
            
            # Queue bulk job
            await self.redis_manager.lpush(
                self.bulk_queue_key,
                json.dumps(bulk_data, default=str)
            )
            
            logger.info(
                "Bulk indexing job queued",
                job_id=job_id,
                document_count=len(documents),
                priority=priority
            )
            
            return job_id
            
        except Exception as e:
            logger.error("Failed to queue bulk indexing job", error=str(e))
            raise
    
    async def delete_document(self, document_id: str) -> bool:
        """Delete document from index with proper tracking."""
        try:
            # Get document info
            indexed_doc = await self._get_indexed_document(document_id)
            if not indexed_doc:
                logger.warning("Document not found in registry", document_id=document_id)
                return False
            
            # Delete from vector database
            # In a real implementation, you'd track chunk IDs properly
            chunk_ids = [f"{document_id}_{i}" for i in range(indexed_doc.chunk_count)]
            if chunk_ids:
                await self.vector_db.delete_vectors(chunk_ids)
            
            # Remove from registry
            await self.redis_manager.hdel(self.document_registry_key, document_id)
            if document_id in self.document_cache:
                del self.document_cache[document_id]
            
            logger.info(
                "Document deleted successfully",
                document_id=document_id,
                chunk_count=indexed_doc.chunk_count
            )
            
            return True
            
        except Exception as e:
            logger.error("Failed to delete document", error=str(e), document_id=document_id)
            return False
    
    async def get_job_status(self, job_id: str) -> Optional[IndexingJob]:
        """Get job status information."""
        # Check active jobs first
        if job_id in self.active_jobs:
            return self.active_jobs[job_id]
        
        # Load from Redis
        return await self._load_job(job_id)
    
    async def list_documents(
        self, 
        limit: int = 50, 
        offset: int = 0,
        status_filter: Optional[IndexingStatus] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List indexed documents with filtering and pagination."""
        try:
            # Get all document IDs from registry
            all_doc_data = await self.redis_manager.hgetall(self.document_registry_key)
            
            documents = []
            for doc_id, doc_json in all_doc_data.items():
                try:
                    doc_data = json.loads(doc_json)
                    indexed_doc = IndexedDocument(**doc_data)
                    
                    # Apply status filter
                    if status_filter and indexed_doc.status != status_filter:
                        continue
                    
                    documents.append(asdict(indexed_doc))
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning("Invalid document data in registry", doc_id=doc_id, error=str(e))
                    continue
            
            # Sort by updated_at (most recent first)
            documents.sort(key=lambda x: x['updated_at'], reverse=True)
            
            # Apply pagination
            total_count = len(documents)
            paginated_docs = documents[offset:offset + limit]
            
            return paginated_docs, total_count
            
        except Exception as e:
            logger.error("Failed to list documents", error=str(e))
            return [], 0
    
    async def reindex_document(self, document_id: str) -> str:
        """Reindex an existing document."""
        try:
            indexed_doc = await self._get_indexed_document(document_id)
            if not indexed_doc:
                raise ValueError(f"Document {document_id} not found in registry")
            
            # Update status to retry
            indexed_doc.status = IndexingStatus.RETRY
            indexed_doc.retry_count += 1
            indexed_doc.updated_at = datetime.utcnow()
            indexed_doc.version += 1
            
            await self._save_indexed_document(indexed_doc)
            
            # Re-queue document (would need original document content)
            logger.info("Document marked for reindexing", document_id=document_id)
            
            # Return a new job ID for tracking
            return str(uuid.uuid4())
            
        except Exception as e:
            logger.error("Failed to reindex document", error=str(e), document_id=document_id)
            raise
    
    async def get_indexing_stats(self) -> Dict[str, Any]:
        """Get comprehensive indexing statistics."""
        await self._refresh_stats()
        
        # Get queue lengths
        queue_length = await self.redis_manager.client.llen(self.queue_key)
        bulk_queue_length = await self.redis_manager.client.llen(self.bulk_queue_key)
        
        # Get document status distribution
        status_distribution = {}
        for doc in self.document_cache.values():
            status = doc.status.value
            status_distribution[status] = status_distribution.get(status, 0) + 1
        
        return {
            **self.stats,
            "queue_length": queue_length,
            "bulk_queue_length": bulk_queue_length,
            "document_count": len(self.document_cache),
            "status_distribution": status_distribution,
            "active_jobs": len(self.active_jobs),
            "concurrent_workers": self.concurrent_workers,
            "bulk_batch_size": self.bulk_batch_size,
        }
    
    # Private methods
    
    async def _process_queue_worker(self, worker_id: str) -> None:
        """Process the indexing queue with a single worker."""
        logger.info("Indexing queue worker started", worker_id=worker_id)
        
        try:
            while self.is_running:
                try:
                    # Get document from queue
                    document_data = await self.redis_manager.rpop(self.queue_key)
                    
                    if document_data:
                        await self._index_single_document(json.loads(document_data), worker_id)
                    else:
                        # No documents in queue, sleep briefly
                        await asyncio.sleep(1)
                        
                except Exception as e:
                    logger.error("Error in indexing worker", error=str(e), worker_id=worker_id)
                    await asyncio.sleep(5)  # Wait before retrying
                    
        except asyncio.CancelledError:
            logger.info("Indexing queue worker cancelled", worker_id=worker_id)
        finally:
            logger.info("Indexing queue worker stopped", worker_id=worker_id)
    
    async def _process_bulk_queue(self) -> None:
        """Process bulk indexing jobs."""
        logger.info("Bulk indexing processor started")
        
        try:
            while self.is_running:
                try:
                    # Get bulk job from queue
                    bulk_data = await self.redis_manager.rpop(self.bulk_queue_key)
                    
                    if bulk_data:
                        await self._process_bulk_job(json.loads(bulk_data))
                    else:
                        await asyncio.sleep(5)  # Longer sleep for bulk jobs
                        
                except Exception as e:
                    logger.error("Error in bulk indexing processor", error=str(e))
                    await asyncio.sleep(10)
                    
        except asyncio.CancelledError:
            logger.info("Bulk indexing processor cancelled")
        finally:
            logger.info("Bulk indexing processor stopped")
    
    async def _index_single_document(self, document_data: Dict[str, Any], worker_id: str) -> None:
        """Index a single document with enhanced tracking."""
        document_id = document_data["id"]
        job_id = document_data.get("job_id")
        
        start_time = time.time()
        
        try:
            # Update document status
            indexed_doc = self.document_cache.get(document_id)
            if indexed_doc:
                indexed_doc.status = IndexingStatus.PROCESSING
                indexed_doc.updated_at = datetime.utcnow()
                await self._save_indexed_document(indexed_doc)
            
            # Update job progress
            if job_id and job_id in self.active_jobs:
                job = self.active_jobs[job_id]
                if job.started_at is None:
                    job.started_at = datetime.utcnow()
                    job.status = IndexingStatus.PROCESSING
                    await self._save_job(job)
            
            # Recreate document object
            document = Document(
                id=document_id,
                content=document_data["content"],
                source=document_data.get("source"),
                metadata=document_data.get("metadata", {}),
            )
            
            # Process document
            processed = await self.document_processor.process_document(document)
            
            # Generate embeddings for chunks
            if processed.chunks:
                chunk_texts = [chunk.content for chunk in processed.chunks]
                
                # Use optimized encoding method
                if hasattr(self.embedding_engine, 'encode_documents'):
                    embeddings = await self.embedding_engine.encode_documents(chunk_texts)
                else:
                    embeddings = await self.embedding_engine.encode_batch(chunk_texts)
                
                # Prepare vectors for Qdrant
                vectors = []
                payloads = []
                ids = []
                
                for i, (chunk, embedding) in enumerate(zip(processed.chunks, embeddings)):
                    chunk_id = f"{document_id}_{i}"
                    
                    vectors.append(embedding)
                    payloads.append({
                        "content": chunk.content,
                        "document_id": document_id,
                        "chunk_index": chunk.chunk_index,
                        "source": document.source,
                        "data_format": processed.data_format.value,
                        "metadata": {**document.metadata, **chunk.metadata},
                        "indexed_at": datetime.utcnow().isoformat(),
                        "worker_id": worker_id,
                    })
                    ids.append(chunk_id)
                
                # Upsert to vector database
                await self.vector_db.upsert_vectors(
                    vectors=vectors,
                    payloads=payloads,
                    ids=ids,
                )
            
            processing_time = time.time() - start_time
            
            # Update document status
            if indexed_doc:
                indexed_doc.status = IndexingStatus.COMPLETED
                indexed_doc.chunk_count = len(processed.chunks)
                indexed_doc.data_format = processed.data_format.value
                indexed_doc.processing_time = processing_time
                indexed_doc.updated_at = datetime.utcnow()
                await self._save_indexed_document(indexed_doc)
            
            # Update job
            if job_id and job_id in self.active_jobs:
                job = self.active_jobs[job_id]
                job.success_count += 1
                job.progress = int((job.success_count / job.total_documents) * 100)
                
                if job.success_count + job.failure_count >= job.total_documents:
                    job.status = IndexingStatus.COMPLETED
                    job.completed_at = datetime.utcnow()
                
                await self._save_job(job)
            
            # Update statistics
            self.stats["indexed_documents"] += 1
            self.stats["total_processing_time"] += processing_time
            self.stats["average_processing_time"] = (
                self.stats["total_processing_time"] / self.stats["indexed_documents"]
            )
            self.stats["last_indexing_time"] = datetime.utcnow().isoformat()
            
            logger.info(
                "Document indexed successfully",
                document_id=document_id,
                worker_id=worker_id,
                processing_time=processing_time,
                chunk_count=len(processed.chunks),
                data_format=processed.data_format.value
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = str(e)
            
            # Update document status
            if indexed_doc:
                indexed_doc.status = IndexingStatus.FAILED
                indexed_doc.error_message = error_msg
                indexed_doc.updated_at = datetime.utcnow()
                
                # Retry logic
                if indexed_doc.retry_count < self.max_retry_attempts:
                    indexed_doc.status = IndexingStatus.RETRY
                    indexed_doc.retry_count += 1
                    # Re-queue for retry (simplified)
                    await self.redis_manager.lpush(
                        self.queue_key,
                        json.dumps(document_data, default=str)
                    )
                
                await self._save_indexed_document(indexed_doc)
            
            # Update job
            if job_id and job_id in self.active_jobs:
                job = self.active_jobs[job_id]
                job.failure_count += 1
                if not job.error_summary:
                    job.error_summary = []
                job.error_summary.append(f"{document_id}: {error_msg}")
                
                if job.success_count + job.failure_count >= job.total_documents:
                    job.status = IndexingStatus.FAILED if job.failure_count > 0 else IndexingStatus.COMPLETED
                    job.completed_at = datetime.utcnow()
                
                await self._save_job(job)
            
            self.stats["failed_documents"] += 1
            
            logger.error(
                "Document indexing failed",
                document_id=document_id,
                worker_id=worker_id,
                error=error_msg,
                processing_time=processing_time,
                retry_count=indexed_doc.retry_count if indexed_doc else 0
            )
    
    async def _process_bulk_job(self, bulk_data: Dict[str, Any]) -> None:
        """Process a bulk indexing job."""
        job_id = bulk_data["job_id"]
        documents_data = bulk_data["documents"]
        
        try:
            job = self.active_jobs.get(job_id)
            if job:
                job.status = IndexingStatus.PROCESSING
                job.started_at = datetime.utcnow()
                await self._save_job(job)
            
            # Process documents in batches
            for i in range(0, len(documents_data), self.bulk_batch_size):
                batch = documents_data[i:i + self.bulk_batch_size]
                
                # Process batch concurrently
                tasks = []
                for doc_data in batch:
                    doc_data["job_id"] = job_id
                    doc_data["job_type"] = "bulk"
                    task = asyncio.create_task(
                        self._index_single_document(doc_data, f"bulk-{job_id[:8]}")
                    )
                    tasks.append(task)
                
                # Wait for batch completion
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # Small delay between batches
                await asyncio.sleep(0.1)
            
            self.stats["bulk_jobs_completed"] += 1
            
            logger.info(
                "Bulk job completed",
                job_id=job_id,
                document_count=len(documents_data)
            )
            
        except Exception as e:
            logger.error("Bulk job processing failed", job_id=job_id, error=str(e))
    
    async def _get_indexed_document(self, document_id: str) -> Optional[IndexedDocument]:
        """Get indexed document from cache or Redis."""
        # Check cache first
        if document_id in self.document_cache:
            self.stats["cache_hits"] += 1
            return self.document_cache[document_id]
        
        # Load from Redis
        doc_json = await self.redis_manager.hget(self.document_registry_key, document_id)
        if doc_json:
            try:
                doc_data = json.loads(doc_json)
                indexed_doc = IndexedDocument(**doc_data)
                self.document_cache[document_id] = indexed_doc
                self.stats["cache_misses"] += 1
                return indexed_doc
            except (json.JSONDecodeError, TypeError):
                logger.warning("Invalid document data", document_id=document_id)
        
        return None
    
    async def _save_indexed_document(self, indexed_doc: IndexedDocument) -> None:
        """Save indexed document to Redis."""
        doc_json = json.dumps(asdict(indexed_doc), default=str)
        await self.redis_manager.hset(
            self.document_registry_key, 
            {indexed_doc.id: doc_json}
        )
        self.document_cache[indexed_doc.id] = indexed_doc
    
    async def _load_job(self, job_id: str) -> Optional[IndexingJob]:
        """Load job from Redis."""
        job_json = await self.redis_manager.hget(self.job_registry_key, job_id)
        if job_json:
            try:
                job_data = json.loads(job_json)
                return IndexingJob(**job_data)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Invalid job data", job_id=job_id)
        return None
    
    async def _save_job(self, job: IndexingJob) -> None:
        """Save job to Redis."""
        job_json = json.dumps(asdict(job), default=str)
        await self.redis_manager.hset(
            self.job_registry_key,
            {job.job_id: job_json}
        )
    
    async def _load_document_cache(self) -> None:
        """Load document registry into cache."""
        try:
            all_docs = await self.redis_manager.hgetall(self.document_registry_key)
            for doc_id, doc_json in all_docs.items():
                try:
                    doc_data = json.loads(doc_json)
                    self.document_cache[doc_id] = IndexedDocument(**doc_data)
                except (json.JSONDecodeError, TypeError):
                    logger.warning("Invalid cached document data", doc_id=doc_id)
            
            logger.info("Document cache loaded", document_count=len(self.document_cache))
            
        except Exception as e:
            logger.error("Failed to load document cache", error=str(e))
    
    async def _load_stats(self) -> None:
        """Load statistics from Redis."""
        try:
            stats_json = await self.redis_manager.get(self.stats_key)
            if stats_json:
                saved_stats = json.loads(stats_json)
                self.stats.update(saved_stats)
        except Exception as e:
            logger.warning("Failed to load statistics", error=str(e))
    
    async def _save_stats(self) -> None:
        """Save statistics to Redis."""
        try:
            stats_json = json.dumps(self.stats, default=str)
            await self.redis_manager.set(self.stats_key, stats_json, ex=86400)  # 24 hours
        except Exception as e:
            logger.warning("Failed to save statistics", error=str(e))
    
    async def _refresh_stats(self) -> None:
        """Refresh statistics from current state."""
        # This would update stats based on current cache state
        pass
    
    async def _periodic_cleanup(self) -> None:
        """Periodic cleanup of old jobs and stats."""
        while self.is_running:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                # Clean up completed jobs older than 7 days
                cutoff_time = datetime.utcnow() - timedelta(days=7)
                
                # Clean up active jobs that are completed
                completed_jobs = []
                for job_id, job in self.active_jobs.items():
                    if (job.status in [IndexingStatus.COMPLETED, IndexingStatus.FAILED] and
                        job.completed_at and job.completed_at < cutoff_time):
                        completed_jobs.append(job_id)
                
                for job_id in completed_jobs:
                    del self.active_jobs[job_id]
                
                # Save stats periodically
                await self._save_stats()
                
                logger.debug("Periodic cleanup completed", cleaned_jobs=len(completed_jobs))
                
            except Exception as e:
                logger.error("Periodic cleanup failed", error=str(e))