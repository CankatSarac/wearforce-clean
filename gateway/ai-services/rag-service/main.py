"""
RAG Pipeline Service - FastAPI app with Qdrant vector database.

Provides:
- Document ingestion and processing
- BGE-small embeddings with sentence-transformers
- Hybrid search (semantic + keyword)
- Citation generation and source tracking
- Incremental indexing
- RAG query processing
"""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, List, Optional

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response, BackgroundTasks, UploadFile, File
from fastapi.responses import StreamingResponse

from shared.config import RAGServiceConfig, get_config, setup_logging
from shared.database import VectorDatabaseManager, RedisManager, CacheStore
from shared.exceptions import ValidationError, ServiceUnavailableError
from shared.middleware import setup_middleware
from shared.models import (
    Document,
    VectorSearchRequest,
    VectorSearchResponse,
    RAGRequest,
    RAGResponse,
    SearchResult,
    HealthResponse,
    HealthStatus,
    VectorSearchType,
)
from shared.monitoring import init_metrics, get_metrics, health_checker, metrics_endpoint
from shared.utils import generate_uuid

from .embeddings import EmbeddingEngine
from .document_processor import DocumentProcessor
from .search_engine import HybridSearchEngine
from .indexing_manager import IndexingManager
from .citation_generator import CitationGenerator

logger = structlog.get_logger(__name__)


# Global managers
embedding_engine: Optional[EmbeddingEngine] = None
document_processor: Optional[DocumentProcessor] = None
search_engine: Optional[HybridSearchEngine] = None
indexing_manager: Optional[IndexingManager] = None
citation_generator: Optional[CitationGenerator] = None
vector_db: Optional[VectorDatabaseManager] = None
redis_manager: Optional[RedisManager] = None
cache_store: Optional[CacheStore] = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage service lifecycle."""
    global embedding_engine, document_processor, search_engine, indexing_manager
    global citation_generator, vector_db, redis_manager, cache_store
    
    config = get_config()
    rag_config = RAGServiceConfig()
    
    try:
        logger.info("Starting RAG Pipeline Service", service=rag_config.name)
        
        # Initialize Redis
        redis_manager = RedisManager(config.redis)
        await redis_manager.health_check()
        logger.info("Redis connection established")
        
        # Initialize cache
        cache_store = CacheStore(redis_manager, default_ttl=300)
        
        # Initialize Qdrant vector database
        vector_db = VectorDatabaseManager(config.qdrant)
        await vector_db.create_collection()
        logger.info("Qdrant vector database initialized")
        
        # Initialize embedding engine
        embedding_engine = EmbeddingEngine(config.models.embedding_model)
        await embedding_engine.initialize()
        logger.info("Embedding engine initialized")
        
        # Initialize document processor
        document_processor = DocumentProcessor(
            chunk_size=rag_config.chunk_size,
            chunk_overlap=rag_config.chunk_overlap,
        )
        
        # Initialize search engine
        search_engine = HybridSearchEngine(
            vector_db=vector_db,
            embedding_engine=embedding_engine,
            dense_weight=rag_config.dense_weight,
            sparse_weight=rag_config.sparse_weight,
        )
        
        # Initialize citation generator
        citation_generator = CitationGenerator()
        
        # Initialize indexing manager
        indexing_manager = IndexingManager(
            vector_db=vector_db,
            embedding_engine=embedding_engine,
            document_processor=document_processor,
            redis_manager=redis_manager,
        )
        await indexing_manager.start()
        logger.info("Indexing manager started")
        
        # Setup health checks
        health_checker.add_check("redis", redis_manager.health_check)
        health_checker.add_check("vector_db", vector_db.health_check)
        health_checker.add_check("embedding_engine", embedding_engine.health_check)
        
        logger.info("RAG Pipeline Service started successfully")
        yield
        
    except Exception as e:
        logger.error("Failed to start RAG service", error=str(e))
        raise
    finally:
        logger.info("Shutting down RAG Pipeline Service")
        
        # Cleanup resources
        if indexing_manager:
            await indexing_manager.stop()
        if vector_db:
            await vector_db.close()
        if redis_manager:
            await redis_manager.close()


# Create FastAPI app
config = get_config()
rag_config = RAGServiceConfig()

app = FastAPI(
    title="WearForce RAG Pipeline Service",
    description="Retrieval-Augmented Generation service with vector search",
    version="1.0.0",
    lifespan=lifespan,
)

# Setup logging and metrics
setup_logging(config.logging)
init_metrics(rag_config.name)

# Setup middleware
setup_middleware(
    app,
    service_name=rag_config.name,
    cors_origins=rag_config.cors_origins,
    requests_per_minute=rag_config.rate_limit_per_minute,
    enable_gzip=True,
    enable_cache=True,
    cache_ttl=300,
)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    checks = await health_checker.check_health()
    
    status = HealthStatus.HEALTHY
    if checks["status"] != "healthy":
        status = HealthStatus.UNHEALTHY
    
    return HealthResponse(
        status=status,
        service=rag_config.name,
        checks=checks,
    )


@app.get("/metrics")
async def get_metrics_endpoint() -> Response:
    """Prometheus metrics endpoint."""
    return metrics_endpoint()


@app.post("/documents", response_model=Dict[str, str])
async def upload_document(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    source: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> Dict[str, str]:
    """Upload and index a document."""
    if not indexing_manager:
        raise ServiceUnavailableError("Indexing manager not initialized")
    
    try:
        # Read file content
        content = await file.read()
        
        if isinstance(content, bytes):
            content = content.decode('utf-8')
        
        # Create document
        document = Document(
            content=content,
            source=source or file.filename,
            metadata=metadata or {},
        )
        
        # Queue for indexing
        background_tasks.add_task(
            indexing_manager.index_document,
            document,
        )
        
        return {
            "document_id": document.id,
            "status": "queued_for_indexing",
            "filename": file.filename,
        }
        
    except ValidationError as e:
        logger.error("Document validation failed", error=str(e))
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    except ServiceUnavailableError as e:
        logger.error("Service unavailable during upload", error=str(e))
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Document upload failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during document upload")


@app.post("/documents/text", response_model=Dict[str, str])
async def upload_text_document(
    request: Dict,
    background_tasks: BackgroundTasks,
) -> Dict[str, str]:
    """Upload text content as document."""
    if not indexing_manager:
        raise ServiceUnavailableError("Indexing manager not initialized")
    
    try:
        content = request.get("content", "")
        source = request.get("source", "text_upload")
        metadata = request.get("metadata", {})
        
        if not content:
            raise ValidationError("Content is required")
        
        # Create document
        document = Document(
            content=content,
            source=source,
            metadata=metadata,
        )
        
        # Queue for indexing
        background_tasks.add_task(
            indexing_manager.index_document,
            document,
        )
        
        return {
            "document_id": document.id,
            "status": "queued_for_indexing",
        }
        
    except ValidationError as e:
        logger.error("Text document validation failed", error=str(e))
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    except ServiceUnavailableError as e:
        logger.error("Service unavailable during text upload", error=str(e))
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Text document upload failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during text document upload")


@app.post("/search", response_model=VectorSearchResponse)
async def search_documents(request: VectorSearchRequest) -> VectorSearchResponse:
    """Search documents using hybrid search."""
    if not search_engine:
        raise ServiceUnavailableError("Search engine not initialized")
    
    start_time = time.time()
    
    try:
        # Check cache
        cache_key = None
        if cache_store:
            cache_key = cache_store.cache_key(
                "search",
                request.query,
                str(request.top_k),
                str(request.search_type.value),
                str(request.similarity_threshold),
            )
            cached_result = await cache_store.get(cache_key)
            if cached_result:
                logger.info("Cache hit for search query")
                return VectorSearchResponse(**cached_result)
        
        # Perform search
        results = await search_engine.search(
            query=request.query,
            top_k=request.top_k,
            search_type=request.search_type,
            similarity_threshold=request.similarity_threshold,
            filters=request.filters,
            include_metadata=request.include_metadata,
        )
        
        processing_time = time.time() - start_time
        
        # Create response
        response = VectorSearchResponse(
            query=request.query,
            results=results,
            total_results=len(results),
            processing_time=processing_time,
        )
        
        # Cache response
        if cache_key and cache_store:
            await cache_store.set(cache_key, response.dict(), ttl=300)
        
        # Record metrics
        metrics = get_metrics()
        if metrics:
            metrics.record_vector_operation("search", processing_time)
        
        return response
        
    except ValidationError as e:
        logger.error("Search request validation failed", error=str(e))
        metrics = get_metrics()
        if metrics:
            metrics.record_error("search_validation_error", "rag_service")
        raise HTTPException(status_code=400, detail=f"Invalid search request: {str(e)}")
    except ServiceUnavailableError as e:
        logger.error("Search service unavailable", error=str(e))
        metrics = get_metrics()
        if metrics:
            metrics.record_error("search_service_unavailable", "rag_service")
        raise HTTPException(status_code=503, detail=str(e))
    except TimeoutError as e:
        logger.error("Search timeout", error=str(e))
        metrics = get_metrics()
        if metrics:
            metrics.record_error("search_timeout", "rag_service")
        raise HTTPException(status_code=504, detail="Search request timed out")
    except Exception as e:
        logger.error("Search failed", error=str(e), exc_info=True)
        metrics = get_metrics()
        if metrics:
            metrics.record_error("search_error", "rag_service")
        raise HTTPException(status_code=500, detail="Internal server error during search")


@app.post("/rag", response_model=RAGResponse)
async def rag_query(
    request: RAGRequest,
    background_tasks: BackgroundTasks,
) -> RAGResponse:
    """Process RAG query with retrieval and generation."""
    if not search_engine or not citation_generator:
        raise ServiceUnavailableError("RAG components not initialized")
    
    start_time = time.time()
    
    try:
        # Search for relevant documents
        search_results = await search_engine.search(
            query=request.question,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
            search_type=VectorSearchType.HYBRID,
            include_metadata=True,
        )
        
        # Generate answer using LLM service
        answer = await _generate_rag_answer(
            question=request.question,
            search_results=search_results,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        
        # Generate citations
        sources = search_results if request.include_sources else []
        if request.include_sources and citation_generator:
            sources = await citation_generator.generate_citations(
                search_results, request.question
            )
        
        processing_time = time.time() - start_time
        
        # Record metrics
        metrics = get_metrics()
        if metrics:
            metrics.record_inference("rag", processing_time)
        
        return RAGResponse(
            question=request.question,
            answer=answer,
            sources=sources,
            confidence=_calculate_confidence(search_results),
            model_used=request.model,
            processing_time=processing_time,
        )
        
    except ValidationError as e:
        logger.error("RAG request validation failed", error=str(e))
        metrics = get_metrics()
        if metrics:
            metrics.record_error("rag_validation_error", "rag_service")
        raise HTTPException(status_code=400, detail=f"Invalid RAG request: {str(e)}")
    except ServiceUnavailableError as e:
        logger.error("RAG service unavailable", error=str(e))
        metrics = get_metrics()
        if metrics:
            metrics.record_error("rag_service_unavailable", "rag_service")
        raise HTTPException(status_code=503, detail=str(e))
    except TimeoutError as e:
        logger.error("RAG query timeout", error=str(e))
        metrics = get_metrics()
        if metrics:
            metrics.record_error("rag_timeout", "rag_service")
        raise HTTPException(status_code=504, detail="RAG query timed out")
    except Exception as e:
        logger.error("RAG query failed", error=str(e), exc_info=True)
        metrics = get_metrics()
        if metrics:
            metrics.record_error("rag_query_error", "rag_service")
        raise HTTPException(status_code=500, detail="Internal server error during RAG query")


@app.delete("/documents/{document_id}")
async def delete_document(document_id: str) -> Dict[str, str]:
    """Delete a document from the index."""
    if not indexing_manager:
        raise ServiceUnavailableError("Indexing manager not initialized")
    
    try:
        await indexing_manager.delete_document(document_id)
        
        return {
            "document_id": document_id,
            "status": "deleted",
        }
        
    except Exception as e:
        logger.error("Document deletion failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents")
async def list_documents(
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, List[Dict]]:
    """List indexed documents."""
    if not indexing_manager:
        raise ServiceUnavailableError("Indexing manager not initialized")
    
    try:
        documents = await indexing_manager.list_documents(limit, offset)
        
        return {
            "documents": documents,
            "total": len(documents),
        }
        
    except Exception as e:
        logger.error("Document listing failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/collections/{collection_name}/stats")
async def get_collection_stats(collection_name: str) -> Dict:
    """Get collection statistics."""
    if not vector_db:
        raise ServiceUnavailableError("Vector database not initialized")
    
    try:
        # This would need to be implemented in the VectorDatabaseManager
        stats = {
            "collection_name": collection_name,
            "document_count": 0,
            "vector_count": 0,
            "last_updated": None,
        }
        
        return stats
        
    except Exception as e:
        logger.error("Failed to get collection stats", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/embeddings")
async def generate_embeddings(request: Dict) -> Dict:
    """Generate embeddings for text."""
    if not embedding_engine:
        raise ServiceUnavailableError("Embedding engine not initialized")
    
    try:
        texts = request.get("texts", [])
        if not texts:
            raise ValidationError("Texts list is required")
        
        embeddings = await embedding_engine.encode_batch(texts)
        
        return {
            "embeddings": embeddings,
            "model": embedding_engine.model_name,
            "dimension": len(embeddings[0]) if embeddings else 0,
        }
        
    except Exception as e:
        logger.error("Embedding generation failed", error=str(e))
        raise


async def _generate_rag_answer(
    question: str,
    search_results: List[SearchResult],
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    """Generate answer using LLM service with retrieved context."""
    try:
        # Prepare context from search results
        context_parts = []
        for i, result in enumerate(search_results[:5]):  # Top 5 results
            context_parts.append(f"Context {i+1}: {result.content}")
        
        context = "\n\n".join(context_parts)
        
        # Create prompt
        prompt = f"""Based on the following context, please answer the question.

Context:
{context}

Question: {question}

Answer: Please provide a comprehensive answer based on the context above. If the context doesn't contain enough information to fully answer the question, please state that clearly."""
        
        # Call LLM service (simplified implementation)
        # In production, this would make an HTTP request to the LLM service
        import httpx
        
        async with httpx.AsyncClient() as client:
            llm_response = await client.post(
                "http://localhost:8004/v1/completions",
                json={
                    "model": model,
                    "prompt": prompt,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=30.0,
            )
            
            if llm_response.status_code == 200:
                result = llm_response.json()
                if result.get("choices"):
                    return result["choices"][0]["text"].strip()
        
        # Fallback response
        return "I apologize, but I couldn't generate an answer based on the available context."
        
    except Exception as e:
        logger.error("RAG answer generation failed", error=str(e))
        return "I encountered an error while generating the answer. Please try again."


def _calculate_confidence(search_results: List[SearchResult]) -> float:
    """Calculate confidence score based on search results."""
    if not search_results:
        return 0.0
    
    # Simple confidence calculation based on top result score
    return min(search_results[0].score, 1.0)


if __name__ == "__main__":
    config = RAGServiceConfig()
    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        log_level="info",
        reload=config.debug,
        access_log=True,
    )