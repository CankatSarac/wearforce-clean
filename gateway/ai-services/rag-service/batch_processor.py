"""Batch processing service for nightly CRM/ERP data ingestion with incremental updates."""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set, Tuple
from enum import Enum
from dataclasses import dataclass, asdict
import structlog
from shared.models import Document
from shared.database import RedisManager, DatabaseManager
from .document_processor import DocumentProcessor, DataFormat
from .indexing_manager import IndexingManager, IndexingStatus
from .embeddings import EmbeddingEngine

logger = structlog.get_logger(__name__)

class BatchJobType(str, Enum):
    """Batch job types."""
    FULL_SYNC = "full_sync"
    INCREMENTAL_SYNC = "incremental_sync"
    CLEANUP = "cleanup"
    REINDEX = "reindex"

class BatchJobStatus(str, Enum):
    """Batch job status."""
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class BatchJob:
    """Batch processing job definition."""
    id: str
    job_type: BatchJobType
    source_system: str  # crm, erp, etc.
    scheduled_time: datetime
    started_time: Optional[datetime] = None
    completed_time: Optional[datetime] = None
    status: BatchJobStatus = BatchJobStatus.SCHEDULED
    parameters: Dict[str, Any] = None
    progress: int = 0
    total_records: int = 0
    processed_records: int = 0
    failed_records: int = 0
    error_messages: List[str] = None
    last_sync_timestamp: Optional[datetime] = None

@dataclass
class DataSourceConfig:
    """Data source configuration."""
    name: str
    type: str  # crm, erp
    connection_params: Dict[str, Any]
    sync_frequency: str  # cron expression
    incremental_field: str  # field to check for incremental updates
    batch_size: int = 1000
    enabled: bool = True
    last_sync: Optional[datetime] = None

class BatchProcessor:
    """Batch processing service for CRM/ERP data ingestion."""
    
    def __init__(
        self,
        indexing_manager: IndexingManager,
        embedding_engine: EmbeddingEngine,
        document_processor: DocumentProcessor,
        redis_manager: RedisManager,
        database_manager: DatabaseManager,
        batch_size: int = 1000,
        max_concurrent_jobs: int = 3,
        cleanup_retention_days: int = 30
    ):
        self.indexing_manager = indexing_manager
        self.embedding_engine = embedding_engine
        self.document_processor = document_processor
        self.redis_manager = redis_manager
        self.database_manager = database_manager
        self.batch_size = batch_size
        self.max_concurrent_jobs = max_concurrent_jobs
        self.cleanup_retention_days = cleanup_retention_days
        
        # Redis keys
        self.jobs_key = "rag:batch_jobs"
        self.schedule_key = "rag:batch_schedule"
        self.sources_key = "rag:data_sources"
        self.sync_state_key = "rag:sync_state"
        
        # Runtime state
        self.is_running = False
        self.active_jobs: Dict[str, BatchJob] = {}
        self.data_sources: Dict[str, DataSourceConfig] = {}
        self.scheduler_task: Optional[asyncio.Task] = None
        
        # Statistics
        self.stats = {
            "total_jobs_executed": 0,
            "successful_jobs": 0,
            "failed_jobs": 0,
            "total_records_processed": 0,
            "last_execution": None,
            "average_execution_time": 0.0,
        }
    
    async def start(self) -> None:
        """Start the batch processing service."""
        if self.is_running:
            return
        
        logger.info("Starting batch processing service")
        self.is_running = True
        
        # Load configuration
        await self._load_data_sources()
        await self._load_stats()
        
        # Start scheduler
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        # Schedule initial jobs if needed
        await self._schedule_initial_jobs()
        
        logger.info(
            "Batch processing service started",
            data_sources=len(self.data_sources),
            max_concurrent_jobs=self.max_concurrent_jobs
        )
    
    async def stop(self) -> None:
        """Stop the batch processing service."""
        if not self.is_running:
            return
        
        logger.info("Stopping batch processing service")
        self.is_running = False
        
        # Cancel scheduler
        if self.scheduler_task:
            self.scheduler_task.cancel()
        
        # Wait for active jobs to complete (with timeout)
        if self.active_jobs:
            logger.info("Waiting for active jobs to complete", count=len(self.active_jobs))
            try:
                await asyncio.wait_for(
                    asyncio.gather(*[self._wait_for_job(job_id) for job_id in self.active_jobs.keys()]),
                    timeout=300  # 5 minutes
                )
            except asyncio.TimeoutError:
                logger.warning("Some jobs did not complete within timeout")
        
        await self._save_stats()
        logger.info("Batch processing service stopped")
    
    async def register_data_source(self, config: DataSourceConfig) -> None:
        """Register a new data source."""
        try:
            self.data_sources[config.name] = config
            await self._save_data_source(config)
            
            logger.info(
                "Data source registered",
                name=config.name,
                type=config.type,
                enabled=config.enabled
            )
            
        except Exception as e:
            logger.error("Failed to register data source", error=str(e))
            raise
    
    async def schedule_job(
        self,
        job_type: BatchJobType,
        source_system: str,
        scheduled_time: Optional[datetime] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> str:
        """Schedule a batch job."""
        try:
            job_id = str(uuid.uuid4())
            
            job = BatchJob(
                id=job_id,
                job_type=job_type,
                source_system=source_system,
                scheduled_time=scheduled_time or datetime.utcnow(),
                parameters=parameters or {},
                error_messages=[]
            )
            
            # Save job
            await self._save_job(job)
            
            logger.info(
                "Batch job scheduled",
                job_id=job_id,
                job_type=job_type.value,
                source_system=source_system,
                scheduled_time=job.scheduled_time.isoformat()
            )
            
            return job_id
            
        except Exception as e:
            logger.error("Failed to schedule batch job", error=str(e))
            raise
    
    async def get_job_status(self, job_id: str) -> Optional[BatchJob]:
        """Get batch job status."""
        # Check active jobs first
        if job_id in self.active_jobs:
            return self.active_jobs[job_id]
        
        # Load from Redis
        return await self._load_job(job_id)
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a scheduled or running job."""
        try:
            job = await self.get_job_status(job_id)
            if not job:
                return False
            
            if job.status in [BatchJobStatus.COMPLETED, BatchJobStatus.FAILED, BatchJobStatus.CANCELLED]:
                return False
            
            job.status = BatchJobStatus.CANCELLED
            job.completed_time = datetime.utcnow()
            
            # Remove from active jobs
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
            
            await self._save_job(job)
            
            logger.info("Batch job cancelled", job_id=job_id)
            return True
            
        except Exception as e:
            logger.error("Failed to cancel job", error=str(e), job_id=job_id)
            return False
    
    async def trigger_immediate_sync(
        self,
        source_system: str,
        job_type: BatchJobType = BatchJobType.INCREMENTAL_SYNC
    ) -> str:
        """Trigger immediate synchronization for a data source."""
        return await self.schedule_job(job_type, source_system, datetime.utcnow())
    
    async def get_batch_stats(self) -> Dict[str, Any]:
        """Get batch processing statistics."""
        await self._refresh_stats()
        
        # Add current state
        current_stats = {
            **self.stats,
            "active_jobs": len(self.active_jobs),
            "registered_sources": len(self.data_sources),
            "enabled_sources": sum(1 for s in self.data_sources.values() if s.enabled),
            "service_running": self.is_running,
        }
        
        return current_stats
    
    # Private methods
    
    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        logger.info("Batch scheduler started")
        
        try:
            while self.is_running:
                try:
                    # Check for scheduled jobs
                    await self._process_scheduled_jobs()
                    
                    # Check for periodic jobs (daily, weekly, etc.)
                    await self._schedule_periodic_jobs()
                    
                    # Clean up old completed jobs
                    await self._cleanup_old_jobs()
                    
                    # Sleep for a minute before next check
                    await asyncio.sleep(60)
                    
                except Exception as e:
                    logger.error("Error in scheduler loop", error=str(e))
                    await asyncio.sleep(60)
                    
        except asyncio.CancelledError:
            logger.info("Batch scheduler cancelled")
        finally:
            logger.info("Batch scheduler stopped")
    
    async def _process_scheduled_jobs(self) -> None:
        """Process jobs that are ready to run."""
        try:
            # Get all scheduled jobs
            all_jobs_data = await self.redis_manager.hgetall(self.jobs_key)
            
            ready_jobs = []
            current_time = datetime.utcnow()
            
            for job_id, job_json in all_jobs_data.items():
                try:
                    job_data = json.loads(job_json)
                    job = BatchJob(**job_data)
                    
                    if (job.status == BatchJobStatus.SCHEDULED and 
                        job.scheduled_time <= current_time and
                        len(self.active_jobs) < self.max_concurrent_jobs):
                        ready_jobs.append(job)
                        
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning("Invalid job data", job_id=job_id, error=str(e))
                    continue
            
            # Process ready jobs
            for job in ready_jobs[:self.max_concurrent_jobs - len(self.active_jobs)]:
                asyncio.create_task(self._execute_job(job))
            
        except Exception as e:
            logger.error("Failed to process scheduled jobs", error=str(e))
    
    async def _execute_job(self, job: BatchJob) -> None:
        """Execute a batch job."""
        job_id = job.id
        
        try:
            logger.info(
                "Starting batch job execution",
                job_id=job_id,
                job_type=job.job_type.value,
                source_system=job.source_system
            )
            
            # Update job status
            job.status = BatchJobStatus.RUNNING
            job.started_time = datetime.utcnow()
            self.active_jobs[job_id] = job
            await self._save_job(job)
            
            start_time = time.time()
            
            # Execute based on job type
            if job.job_type == BatchJobType.FULL_SYNC:
                await self._execute_full_sync(job)
            elif job.job_type == BatchJobType.INCREMENTAL_SYNC:
                await self._execute_incremental_sync(job)
            elif job.job_type == BatchJobType.CLEANUP:
                await self._execute_cleanup(job)
            elif job.job_type == BatchJobType.REINDEX:
                await self._execute_reindex(job)
            
            # Job completed successfully
            execution_time = time.time() - start_time
            
            job.status = BatchJobStatus.COMPLETED
            job.completed_time = datetime.utcnow()
            job.progress = 100
            
            # Update statistics
            self.stats["total_jobs_executed"] += 1
            self.stats["successful_jobs"] += 1
            self.stats["total_records_processed"] += job.processed_records
            self.stats["last_execution"] = datetime.utcnow().isoformat()
            
            # Update average execution time
            if self.stats["average_execution_time"] > 0:
                self.stats["average_execution_time"] = (
                    self.stats["average_execution_time"] + execution_time
                ) / 2
            else:
                self.stats["average_execution_time"] = execution_time
            
            logger.info(
                "Batch job completed successfully",
                job_id=job_id,
                execution_time=execution_time,
                processed_records=job.processed_records,
                failed_records=job.failed_records
            )
            
        except Exception as e:
            # Job failed
            job.status = BatchJobStatus.FAILED
            job.completed_time = datetime.utcnow()
            if not job.error_messages:
                job.error_messages = []
            job.error_messages.append(str(e))
            
            self.stats["failed_jobs"] += 1
            
            logger.error(
                "Batch job failed",
                job_id=job_id,
                error=str(e),
                processed_records=job.processed_records
            )
            
        finally:
            # Clean up
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
            await self._save_job(job)
    
    async def _execute_full_sync(self, job: BatchJob) -> None:
        """Execute full synchronization."""
        source_name = job.source_system
        source_config = self.data_sources.get(source_name)
        
        if not source_config:
            raise ValueError(f"Data source '{source_name}' not found")
        
        if not source_config.enabled:
            raise ValueError(f"Data source '{source_name}' is disabled")
        
        logger.info("Starting full sync", source=source_name)
        
        # Get all records from source
        records = await self._fetch_all_records(source_config)
        job.total_records = len(records)
        
        # Process in batches
        batch_size = source_config.batch_size
        total_batches = (len(records) + batch_size - 1) // batch_size
        
        for batch_idx in range(0, len(records), batch_size):
            batch = records[batch_idx:batch_idx + batch_size]
            
            try:
                # Convert records to documents
                documents = await self._records_to_documents(batch, source_config)
                
                # Index documents
                if documents:
                    job_id = await self.indexing_manager.index_documents_bulk(documents)
                    
                    # Wait for indexing to complete (simplified)
                    await asyncio.sleep(1)  # In practice, monitor the indexing job
                
                job.processed_records += len(batch)
                job.progress = int((job.processed_records / job.total_records) * 100)
                
                # Update job progress
                await self._save_job(job)
                
                logger.debug(
                    "Batch processed",
                    source=source_name,
                    batch_idx=batch_idx // batch_size + 1,
                    total_batches=total_batches,
                    records=len(batch)
                )
                
            except Exception as e:
                job.failed_records += len(batch)
                if not job.error_messages:
                    job.error_messages = []
                job.error_messages.append(f"Batch {batch_idx//batch_size + 1}: {str(e)}")
                logger.error("Batch processing failed", error=str(e))
        
        # Update last sync time
        source_config.last_sync = datetime.utcnow()
        await self._save_data_source(source_config)
        
        logger.info(
            "Full sync completed",
            source=source_name,
            total_records=job.total_records,
            processed=job.processed_records,
            failed=job.failed_records
        )
    
    async def _execute_incremental_sync(self, job: BatchJob) -> None:
        """Execute incremental synchronization."""
        source_name = job.source_system
        source_config = self.data_sources.get(source_name)
        
        if not source_config:
            raise ValueError(f"Data source '{source_name}' not found")
        
        if not source_config.enabled:
            raise ValueError(f"Data source '{source_name}' is disabled")
        
        logger.info("Starting incremental sync", source=source_name)
        
        # Get records modified since last sync
        last_sync = source_config.last_sync or datetime.utcnow() - timedelta(days=1)
        records = await self._fetch_incremental_records(source_config, last_sync)
        
        job.total_records = len(records)
        
        if job.total_records == 0:
            logger.info("No new records to sync", source=source_name)
            return
        
        # Process records
        documents = await self._records_to_documents(records, source_config)
        
        if documents:
            # Index documents
            indexing_job_id = await self.indexing_manager.index_documents_bulk(documents)
            job.processed_records = len(documents)
        
        # Update last sync time
        source_config.last_sync = datetime.utcnow()
        await self._save_data_source(source_config)
        
        logger.info(
            "Incremental sync completed",
            source=source_name,
            records_processed=job.processed_records
        )
    
    async def _execute_cleanup(self, job: BatchJob) -> None:
        """Execute cleanup of old documents."""
        logger.info("Starting cleanup job")
        
        cutoff_date = datetime.utcnow() - timedelta(days=self.cleanup_retention_days)
        
        # Get old documents (simplified - would need proper tracking)
        # This is a placeholder implementation
        
        job.total_records = 0  # Would be set based on actual cleanup
        job.processed_records = 0
        
        logger.info("Cleanup completed")
    
    async def _execute_reindex(self, job: BatchJob) -> None:
        """Execute reindexing job."""
        source_name = job.source_system
        
        logger.info("Starting reindex job", source=source_name)
        
        # This would involve:
        # 1. Getting all documents for the source
        # 2. Re-processing them with current settings
        # 3. Re-indexing with updated embeddings
        
        # Placeholder implementation
        job.total_records = 0
        job.processed_records = 0
        
        logger.info("Reindex completed")
    
    async def _fetch_all_records(self, source_config: DataSourceConfig) -> List[Dict[str, Any]]:
        """Fetch all records from data source."""
        try:
            if source_config.type == "crm":
                return await self._fetch_crm_records(source_config)
            elif source_config.type == "erp":
                return await self._fetch_erp_records(source_config)
            else:
                raise ValueError(f"Unknown source type: {source_config.type}")
                
        except Exception as e:
            logger.error("Failed to fetch records", error=str(e), source=source_config.name)
            raise
    
    async def _fetch_incremental_records(
        self, 
        source_config: DataSourceConfig, 
        since: datetime
    ) -> List[Dict[str, Any]]:
        """Fetch records modified since given timestamp."""
        try:
            if source_config.type == "crm":
                return await self._fetch_crm_records(source_config, since=since)
            elif source_config.type == "erp":
                return await self._fetch_erp_records(source_config, since=since)
            else:
                raise ValueError(f"Unknown source type: {source_config.type}")
                
        except Exception as e:
            logger.error("Failed to fetch incremental records", error=str(e))
            raise
    
    async def _fetch_crm_records(
        self, 
        source_config: DataSourceConfig, 
        since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Fetch records from CRM system."""
        try:
            # This would connect to the actual CRM system
            # For now, we'll simulate fetching from a database table
            
            conn_params = source_config.connection_params
            table_name = conn_params.get("table_name", "crm_contacts")
            
            async with self.database_manager.get_session() as session:
                # Build query
                if since:
                    # Incremental query
                    query = f"SELECT * FROM {table_name} WHERE updated_at > '{since.isoformat()}' ORDER BY updated_at"
                else:
                    # Full query
                    query = f"SELECT * FROM {table_name} ORDER BY id"
                
                result = await session.execute(query)
                records = [dict(row) for row in result.fetchall()]
                
                logger.debug(
                    "Fetched CRM records",
                    table=table_name,
                    count=len(records),
                    incremental=since is not None
                )
                
                return records
                
        except Exception as e:
            logger.error("Failed to fetch CRM records", error=str(e))
            raise
    
    async def _fetch_erp_records(
        self, 
        source_config: DataSourceConfig, 
        since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Fetch records from ERP system."""
        try:
            conn_params = source_config.connection_params
            table_name = conn_params.get("table_name", "erp_products")
            
            async with self.database_manager.get_session() as session:
                # Build query
                if since:
                    query = f"SELECT * FROM {table_name} WHERE updated_at > '{since.isoformat()}' ORDER BY updated_at"
                else:
                    query = f"SELECT * FROM {table_name} ORDER BY id"
                
                result = await session.execute(query)
                records = [dict(row) for row in result.fetchall()]
                
                logger.debug(
                    "Fetched ERP records",
                    table=table_name,
                    count=len(records),
                    incremental=since is not None
                )
                
                return records
                
        except Exception as e:
            logger.error("Failed to fetch ERP records", error=str(e))
            raise
    
    async def _records_to_documents(
        self, 
        records: List[Dict[str, Any]], 
        source_config: DataSourceConfig
    ) -> List[Document]:
        """Convert database records to Document objects."""
        documents = []
        
        for record in records:
            try:
                # Create document ID
                record_id = record.get('id') or str(uuid.uuid4())
                doc_id = f"{source_config.name}_{record_id}"
                
                # Convert record to JSON string for content
                content = json.dumps(record, default=str, indent=2)
                
                # Create metadata
                metadata = {
                    "source_system": source_config.name,
                    "source_type": source_config.type,
                    "record_type": source_config.connection_params.get("record_type", "unknown"),
                    "table_name": source_config.connection_params.get("table_name"),
                    "record_id": record_id,
                    "last_updated": record.get(source_config.incremental_field),
                    "format": "database_record",
                }
                
                # Create document
                document = Document(
                    id=doc_id,
                    content=content,
                    source=f"{source_config.type}://{source_config.name}",
                    metadata=metadata
                )
                
                documents.append(document)
                
            except Exception as e:
                logger.error(
                    "Failed to convert record to document", 
                    error=str(e), 
                    record_id=record.get('id')
                )
                continue
        
        logger.debug(
            "Converted records to documents",
            source=source_config.name,
            records=len(records),
            documents=len(documents)
        )
        
        return documents
    
    async def _schedule_periodic_jobs(self) -> None:
        """Schedule periodic jobs based on data source configurations."""
        try:
            current_time = datetime.utcnow()
            
            for source_config in self.data_sources.values():
                if not source_config.enabled:
                    continue
                
                # Simple daily scheduling (would be enhanced with cron expressions)
                if source_config.sync_frequency == "daily":
                    # Check if we need to schedule today's job
                    last_sync = source_config.last_sync
                    if not last_sync or (current_time - last_sync).days >= 1:
                        # Schedule incremental sync
                        next_run = current_time.replace(hour=2, minute=0, second=0, microsecond=0)
                        if next_run <= current_time:
                            next_run += timedelta(days=1)
                        
                        # Check if job already scheduled
                        existing_job = await self._find_scheduled_job(
                            source_config.name, 
                            BatchJobType.INCREMENTAL_SYNC,
                            next_run.date()
                        )
                        
                        if not existing_job:
                            await self.schedule_job(
                                BatchJobType.INCREMENTAL_SYNC,
                                source_config.name,
                                next_run
                            )
                
                # Weekly full sync
                elif source_config.sync_frequency == "weekly":
                    # Schedule full sync every Sunday at 1 AM
                    if current_time.weekday() == 6:  # Sunday
                        next_run = current_time.replace(hour=1, minute=0, second=0, microsecond=0)
                        if next_run <= current_time:
                            next_run += timedelta(weeks=1)
                        
                        existing_job = await self._find_scheduled_job(
                            source_config.name,
                            BatchJobType.FULL_SYNC,
                            next_run.date()
                        )
                        
                        if not existing_job:
                            await self.schedule_job(
                                BatchJobType.FULL_SYNC,
                                source_config.name,
                                next_run
                            )
        
        except Exception as e:
            logger.error("Failed to schedule periodic jobs", error=str(e))
    
    async def _find_scheduled_job(
        self, 
        source_system: str, 
        job_type: BatchJobType, 
        target_date: datetime.date
    ) -> Optional[BatchJob]:
        """Find if a job is already scheduled for the given date."""
        try:
            all_jobs_data = await self.redis_manager.hgetall(self.jobs_key)
            
            for job_id, job_json in all_jobs_data.items():
                try:
                    job_data = json.loads(job_json)
                    job = BatchJob(**job_data)
                    
                    if (job.source_system == source_system and
                        job.job_type == job_type and
                        job.status == BatchJobStatus.SCHEDULED and
                        job.scheduled_time.date() == target_date):
                        return job
                        
                except (json.JSONDecodeError, TypeError):
                    continue
            
            return None
            
        except Exception as e:
            logger.error("Failed to find scheduled job", error=str(e))
            return None
    
    async def _cleanup_old_jobs(self) -> None:
        """Clean up old completed jobs."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=7)  # Keep jobs for 7 days
            
            all_jobs_data = await self.redis_manager.hgetall(self.jobs_key)
            jobs_to_delete = []
            
            for job_id, job_json in all_jobs_data.items():
                try:
                    job_data = json.loads(job_json)
                    job = BatchJob(**job_data)
                    
                    if (job.status in [BatchJobStatus.COMPLETED, BatchJobStatus.FAILED, BatchJobStatus.CANCELLED] and
                        job.completed_time and job.completed_time < cutoff_time):
                        jobs_to_delete.append(job_id)
                        
                except (json.JSONDecodeError, TypeError):
                    # Invalid job data, mark for deletion
                    jobs_to_delete.append(job_id)
                    continue
            
            if jobs_to_delete:
                await self.redis_manager.hdel(self.jobs_key, *jobs_to_delete)
                logger.debug("Cleaned up old jobs", count=len(jobs_to_delete))
            
        except Exception as e:
            logger.error("Failed to cleanup old jobs", error=str(e))
    
    async def _schedule_initial_jobs(self) -> None:
        """Schedule initial jobs if needed."""
        try:
            for source_config in self.data_sources.values():
                if source_config.enabled and not source_config.last_sync:
                    # Schedule initial full sync
                    await self.schedule_job(
                        BatchJobType.FULL_SYNC,
                        source_config.name,
                        datetime.utcnow() + timedelta(minutes=5)  # Start in 5 minutes
                    )
                    
                    logger.info(
                        "Scheduled initial full sync",
                        source=source_config.name
                    )
        
        except Exception as e:
            logger.error("Failed to schedule initial jobs", error=str(e))
    
    async def _wait_for_job(self, job_id: str) -> None:
        """Wait for a job to complete."""
        while job_id in self.active_jobs:
            await asyncio.sleep(1)
    
    # Persistence methods
    
    async def _save_job(self, job: BatchJob) -> None:
        """Save job to Redis."""
        try:
            job_json = json.dumps(asdict(job), default=str)
            await self.redis_manager.hset(self.jobs_key, {job.id: job_json})
        except Exception as e:
            logger.error("Failed to save job", error=str(e), job_id=job.id)
    
    async def _load_job(self, job_id: str) -> Optional[BatchJob]:
        """Load job from Redis."""
        try:
            job_json = await self.redis_manager.hget(self.jobs_key, job_id)
            if job_json:
                job_data = json.loads(job_json)
                return BatchJob(**job_data)
            return None
        except Exception as e:
            logger.error("Failed to load job", error=str(e), job_id=job_id)
            return None
    
    async def _save_data_source(self, config: DataSourceConfig) -> None:
        """Save data source configuration."""
        try:
            config_json = json.dumps(asdict(config), default=str)
            await self.redis_manager.hset(self.sources_key, {config.name: config_json})
        except Exception as e:
            logger.error("Failed to save data source", error=str(e), name=config.name)
    
    async def _load_data_sources(self) -> None:
        """Load data source configurations."""
        try:
            sources_data = await self.redis_manager.hgetall(self.sources_key)
            
            for name, config_json in sources_data.items():
                try:
                    config_data = json.loads(config_json)
                    self.data_sources[name] = DataSourceConfig(**config_data)
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning("Invalid data source config", name=name, error=str(e))
                    continue
            
            logger.info("Data sources loaded", count=len(self.data_sources))
            
        except Exception as e:
            logger.error("Failed to load data sources", error=str(e))
    
    async def _save_stats(self) -> None:
        """Save statistics to Redis."""
        try:
            stats_json = json.dumps(self.stats, default=str)
            await self.redis_manager.set("rag:batch_stats", stats_json, ex=86400)
        except Exception as e:
            logger.warning("Failed to save stats", error=str(e))
    
    async def _load_stats(self) -> None:
        """Load statistics from Redis."""
        try:
            stats_json = await self.redis_manager.get("rag:batch_stats")
            if stats_json:
                saved_stats = json.loads(stats_json)
                self.stats.update(saved_stats)
        except Exception as e:
            logger.warning("Failed to load stats", error=str(e))
    
    async def _refresh_stats(self) -> None:
        """Refresh statistics from current state."""
        # This would recalculate stats from job history
        pass