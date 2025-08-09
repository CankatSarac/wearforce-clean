# WearForce-Clean RAG Pipeline Service

A comprehensive Retrieval-Augmented Generation (RAG) service designed for WearForce-Clean's CRM/ERP data processing and intelligent document search.

## Features

### Core Capabilities
- **Hybrid Search**: Combines dense vector search with sparse keyword search (BM25) using Reciprocal Rank Fusion
- **Multi-Format Document Processing**: Handles CRM contacts, ERP products, JSON records, and plain text
- **Advanced Embeddings**: Uses BGE, E5, and Instructor models with caching and batch processing
- **Smart Citations**: Automatic source attribution with multiple citation formats (APA, MLA, Chicago, IEEE, Harvard)
- **Batch Processing**: Nightly data ingestion with incremental updates
- **Real-time Indexing**: Live document processing and vector indexing

### Architecture Components

#### 1. Document Processor (`document_processor.py`)
- **Format Detection**: Automatically identifies CRM/ERP data formats
- **Data Transformation**: Converts structured data to searchable text
- **Intelligent Chunking**: Optimized text segmentation with overlap
- **Field Mapping**: Standardized field extraction for CRM/ERP systems

```python
# Supported data formats
DataFormat.CRM_CONTACT          # Customer contact records
DataFormat.CRM_OPPORTUNITY      # Sales opportunities  
DataFormat.ERP_PRODUCT         # Product catalog
DataFormat.ERP_ORDER           # Order records
DataFormat.ERP_INVOICE         # Invoice data
DataFormat.DATABASE_RECORD     # Generic database records
DataFormat.JSON                # JSON documents
DataFormat.TEXT                # Plain text
```

#### 2. Embedding Engine (`embeddings.py`)
- **Multi-Model Support**: BGE, E5, Instructor models
- **Performance Optimization**: Caching, batching, GPU acceleration
- **Model-Specific Encoding**: Query vs document optimizations
- **Comprehensive Stats**: Performance monitoring and cache analytics

```python
# Supported models
EmbeddingModel.BGE_SMALL       # BAAI/bge-small-en-v1.5 (384d)
EmbeddingModel.BGE_BASE        # BAAI/bge-base-en-v1.5 (768d) 
EmbeddingModel.BGE_LARGE       # BAAI/bge-large-en-v1.5 (1024d)
EmbeddingModel.E5_SMALL        # intfloat/e5-small-v2 (384d)
EmbeddingModel.INSTRUCTOR_XL   # hkunlp/instructor-xl (768d)
```

#### 3. Hybrid Search Engine (`search_engine.py`)
- **Dense Vector Search**: Semantic similarity using embeddings
- **Sparse Keyword Search**: BM25-based text matching
- **Reciprocal Rank Fusion**: Advanced result combination algorithm
- **Score Normalization**: Consistent ranking across search types
- **Metadata Filtering**: Flexible query constraints

#### 4. Citation Generator (`citation_generator.py`)
- **Academic Formats**: APA, MLA, Chicago, IEEE, Harvard
- **Source Analysis**: Credibility scoring and relevance assessment
- **Deduplication**: Smart duplicate detection and removal
- **Context Extraction**: Relevant snippet generation
- **Bibliography Generation**: Formatted reference lists

#### 5. Indexing Manager (`indexing_manager.py`)
- **Concurrent Processing**: Multi-worker document indexing
- **Job Tracking**: Comprehensive status monitoring
- **Bulk Operations**: Efficient batch processing
- **Retry Logic**: Automatic failure recovery
- **Document Registry**: Complete indexing history

#### 6. Batch Processor (`batch_processor.py`)
- **Scheduled Jobs**: Cron-based automation
- **Incremental Sync**: Delta updates from CRM/ERP
- **Data Source Management**: Multi-system integration
- **Progress Tracking**: Real-time job monitoring
- **Error Handling**: Comprehensive failure management

## API Endpoints

### Document Management
```http
POST /documents              # Upload single document
POST /documents/text         # Upload text content
POST /documents/bulk         # Bulk document upload
DELETE /documents/{id}       # Delete document
GET /documents              # List documents
```

### Search & RAG
```http
POST /search                # Vector search
POST /rag                   # RAG query with generation
POST /embeddings            # Generate embeddings
```

### Management
```http
GET /health                 # Health check
GET /metrics                # Prometheus metrics
GET /collections/{name}/stats  # Collection statistics
```

## Configuration

### Environment Variables
```bash
# Service Configuration
SERVICE_NAME=rag-service
HOST=0.0.0.0
PORT=8005
DEBUG=false

# Database Configuration  
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=password
DB_NAME=wearforce-clean

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# Qdrant Configuration
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=wearforce-clean_docs
EMBEDDING_DIM=384

# RAG Settings
CHUNK_SIZE=512
CHUNK_OVERLAP=50
TOP_K=5
SIMILARITY_THRESHOLD=0.7
DENSE_WEIGHT=0.7
SPARSE_WEIGHT=0.3

# Model Configuration
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
```

### RAG Service Config
```python
from shared.config import RAGServiceConfig

config = RAGServiceConfig(
    name="rag-service",
    port=8005,
    chunk_size=512,
    chunk_overlap=50,
    top_k=5,
    similarity_threshold=0.7,
    dense_weight=0.7,
    sparse_weight=0.3
)
```

## Usage Examples

### 1. Document Upload and Search
```python
import httpx
import asyncio

async def example_usage():
    client = httpx.AsyncClient()
    
    # Upload CRM contact
    crm_contact = {
        "content": '{"name": "John Smith", "company": "Acme Corp", "email": "john@acme.com"}',
        "source": "crm://contacts",
        "metadata": {"format": "crm_contact"}
    }
    
    response = await client.post(
        "http://localhost:8005/documents/text",
        json=crm_contact
    )
    print(f"Document uploaded: {response.json()}")
    
    # Search for documents
    search_request = {
        "query": "Find contacts from Acme Corp",
        "top_k": 5,
        "search_type": "hybrid",
        "similarity_threshold": 0.7
    }
    
    response = await client.post(
        "http://localhost:8005/search",
        json=search_request
    )
    print(f"Search results: {response.json()}")
    
    # RAG query
    rag_request = {
        "question": "What contacts do we have from Acme Corp?",
        "top_k": 5,
        "include_sources": True,
        "model": "gpt-oss-20b"
    }
    
    response = await client.post(
        "http://localhost:8005/rag", 
        json=rag_request
    )
    print(f"RAG response: {response.json()}")

asyncio.run(example_usage())
```

### 2. Batch Data Processing
```python
from rag_service.batch_processor import BatchProcessor, DataSourceConfig, BatchJobType

# Configure CRM data source
crm_config = DataSourceConfig(
    name="salesforce_crm",
    type="crm",
    connection_params={
        "table_name": "contacts",
        "connection_string": "postgresql://user:pass@host/db"
    },
    sync_frequency="daily",
    incremental_field="updated_at",
    batch_size=1000
)

# Schedule batch job
batch_processor = BatchProcessor(...)
await batch_processor.register_data_source(crm_config)

job_id = await batch_processor.schedule_job(
    BatchJobType.INCREMENTAL_SYNC,
    "salesforce_crm"
)
```

### 3. Custom Citation Generation
```python
from rag_service.citation_generator import CitationGenerator, CitationFormat

citation_gen = CitationGenerator(
    default_format=CitationFormat.APA,
    min_relevance_threshold=0.7,
    enable_deduplication=True
)

citations = await citation_gen.generate_citations(
    search_results,
    question="What is CRM?",
    format_type=CitationFormat.MLA,
    max_citations=10
)

bibliography = await citation_gen.generate_bibliography(
    citations,
    CitationFormat.MLA
)
```

## Performance Optimization

### Embedding Caching
- **LRU Cache**: Configurable cache size (default: 10,000 entries)
- **Hit Rate Monitoring**: Real-time cache performance metrics
- **Batch Processing**: Optimized for bulk operations

### Search Optimization
- **Parallel Execution**: Dense and sparse search run concurrently
- **Result Fusion**: Advanced ranking with reciprocal rank fusion
- **Score Normalization**: Consistent cross-model ranking

### Database Optimization
- **Connection Pooling**: Efficient database connection management
- **Bulk Operations**: Batch insertions and updates
- **Indexing Strategy**: Optimized vector and metadata indices

## Monitoring & Observability

### Health Checks
```json
{
  "status": "healthy",
  "service": "rag-service", 
  "checks": {
    "redis": "healthy",
    "vector_db": "healthy", 
    "embedding_engine": "healthy"
  }
}
```

### Metrics (Prometheus)
```
# Indexing metrics
rag_documents_indexed_total
rag_indexing_duration_seconds
rag_indexing_errors_total

# Search metrics  
rag_search_requests_total
rag_search_duration_seconds
rag_search_results_returned

# Embedding metrics
rag_embeddings_generated_total
rag_embedding_cache_hits_total
rag_embedding_cache_misses_total
```

### Logging
- **Structured Logging**: JSON format with structured data
- **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Context Tracking**: Request IDs and trace information

## Development & Testing

### Running Tests
```bash
# Install dependencies
poetry install

# Run component tests
python rag-service/test_rag_service.py

# Run full test suite
pytest tests/test_rag_service.py -v

# Run with coverage
pytest tests/test_rag_service.py --cov=rag_service --cov-report=html
```

### Local Development
```bash
# Start services with docker-compose
docker-compose up -d postgres redis qdrant

# Run RAG service
cd rag-service
python main.py

# Or with uvicorn
uvicorn main:app --host 0.0.0.0 --port 8005 --reload
```

## Deployment

### Docker
```dockerfile
# Production deployment
docker build -t wearforce-clean-rag-service .
docker run -d \
  -p 8005:8005 \
  --env-file .env \
  wearforce-clean-rag-service
```

### Kubernetes
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app: rag-service
  template:
    metadata:
      labels:
        app: rag-service
    spec:
      containers:
      - name: rag-service
        image: wearforce-clean-rag-service:latest
        ports:
        - containerPort: 8005
        env:
        - name: REDIS_HOST
          value: "redis-service"
        - name: QDRANT_HOST
          value: "qdrant-service"
```

## Data Processing Pipeline

### 1. Data Ingestion
- **Source Systems**: CRM (Salesforce, HubSpot), ERP (SAP, Oracle)
- **Data Formats**: JSON records, CSV exports, API responses
- **Frequency**: Real-time webhooks + scheduled batch jobs

### 2. Data Transformation
- **Field Standardization**: Normalize field names across systems
- **Data Enrichment**: Add metadata and context information
- **Content Generation**: Convert structured data to searchable text

### 3. Vector Processing
- **Embedding Generation**: Create dense vector representations
- **Indexing**: Store vectors in Qdrant with metadata
- **Optimization**: Batch processing for efficiency

### 4. Search & Retrieval
- **Multi-Modal Search**: Vector similarity + keyword matching
- **Relevance Ranking**: Advanced fusion algorithms
- **Result Enhancement**: Add context and citations

## Best Practices

### Data Quality
- **Validation**: Schema validation for all input data
- **Cleaning**: Remove duplicate and low-quality content
- **Monitoring**: Track data freshness and completeness

### Performance
- **Caching Strategy**: Multi-level caching (Redis + in-memory)
- **Batch Operations**: Minimize database round trips
- **Connection Pooling**: Efficient resource utilization

### Security
- **Input Validation**: Sanitize all user inputs
- **Access Control**: Role-based permissions
- **Data Privacy**: PII handling and anonymization

### Scalability
- **Horizontal Scaling**: Stateless service design
- **Load Balancing**: Distribute requests across instances
- **Resource Management**: CPU/memory optimization

## Troubleshooting

### Common Issues

#### 1. Embedding Model Loading
```bash
# Error: Model not found
# Solution: Download model manually
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"
```

#### 2. Qdrant Connection
```bash
# Error: Connection refused
# Solution: Check Qdrant service
docker ps | grep qdrant
curl http://localhost:6333/collections
```

#### 3. Memory Issues
```bash
# Error: Out of memory during embedding
# Solution: Reduce batch size
export EMBEDDING_BATCH_SIZE=16
```

#### 4. Search Performance
```bash
# Issue: Slow search responses
# Solution: Check index size and enable caching
curl http://localhost:8005/collections/wearforce-clean_docs/stats
```

### Log Analysis
```bash
# Check service logs
docker logs rag-service --tail 100 -f

# Search for errors
grep ERROR /var/log/rag-service.log | tail -20

# Monitor performance
grep "processing_time" /var/log/rag-service.log | tail -10
```

## Contributing

### Development Setup
1. Clone repository
2. Install dependencies: `poetry install`
3. Start development services: `docker-compose up -d`
4. Run tests: `pytest`
5. Start service: `python main.py`

### Code Standards
- **Formatting**: Black, isort
- **Linting**: Ruff, mypy
- **Testing**: pytest with >90% coverage
- **Documentation**: Comprehensive docstrings

### Pull Request Process
1. Create feature branch
2. Add tests for new functionality
3. Update documentation
4. Run full test suite
5. Submit PR with detailed description

## License

Copyright (c) 2024 WearForce-Clean. All rights reserved.