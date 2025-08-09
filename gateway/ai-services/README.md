# WearForce-Clean AI Services

This directory contains the complete AI services infrastructure for the WearForce-Clean project, providing production-ready implementations of LLM inference, natural language understanding, and retrieval-augmented generation capabilities.

## Services Overview

### 1. LLM Inference Service (`llm-service/`)
**Port: 8004**

High-performance LLM inference service with vLLM backend providing:
- **vLLM Integration**: Support for gpt-oss-120b and gpt-oss-20b models
- **OpenAI-Compatible API**: Drop-in replacement for OpenAI API
- **Request Batching**: Optimized batch processing for efficiency  
- **Token Usage Tracking**: Detailed billing and usage analytics
- **Function Calling**: Tool execution with load balancing
- **Multi-model Load Balancing**: Automatic model selection and scaling

#### Key Features:
- GPU acceleration with CUDA support
- Streaming and non-streaming responses
- Built-in caching for improved performance
- Comprehensive metrics and monitoring
- Production-ready error handling

### 2. NLU/Agent Router Service (`nlu-service/`)
**Port: 8003**

Intelligent conversation orchestration using LangGraph:
- **LangGraph Workflows**: State-based conversation management
- **Intent Classification**: ML and rule-based intent detection
- **Entity Extraction**: Named entity recognition and extraction
- **Tool Dispatcher**: Integration with CRM/ERP systems
- **Multi-agent Handling**: Specialized agents for different domains
- **Redis-based History**: Persistent conversation memory

#### Key Features:
- Workflow orchestration with conditional routing
- Real-time streaming responses  
- Context-aware agent selection
- Tool execution and result integration
- Comprehensive conversation management

### 3. RAG Pipeline Service (`rag-service/`)
**Port: 8005**

Advanced retrieval-augmented generation pipeline:
- **Qdrant Integration**: High-performance vector database
- **BGE-small Embeddings**: Efficient semantic embeddings
- **Hybrid Search**: Semantic + keyword search combination
- **Document Processing**: Intelligent chunking and preprocessing
- **Citation Generation**: Source tracking and attribution
- **Incremental Indexing**: Real-time document updates

#### Key Features:
- Multi-modal document support
- Asynchronous batch processing
- Citation and source tracking
- Performance optimization and caching
- Scalable vector storage

## Architecture

### Shared Components (`shared/`)
Common utilities and models used across all services:
- **Configuration Management**: Centralized settings with environment support
- **Database Abstractions**: PostgreSQL, Redis, and Qdrant integrations
- **Monitoring & Metrics**: Prometheus metrics and structured logging
- **Middleware**: Authentication, rate limiting, error handling
- **Data Models**: Pydantic models for request/response validation

### Dependencies
- **Vector Database**: Qdrant for semantic search
- **Cache Layer**: Redis for sessions and caching
- **Database**: PostgreSQL for persistent data
- **Message Queue**: Redis-based task queues
- **Monitoring**: Prometheus + Grafana stack

## Quick Start

### Prerequisites
- Docker and Docker Compose
- NVIDIA GPU (for LLM service)
- Python 3.11+
- Poetry for dependency management

### Development Setup
```bash
# Install dependencies
cd ai-services
poetry install

# Set environment variables
export DB_HOST=localhost
export REDIS_HOST=localhost  
export QDRANT_HOST=localhost

# Run individual services
python llm-service/main.py    # Port 8004
python nlu-service/main.py    # Port 8003  
python rag-service/main.py    # Port 8005
```

### Production Deployment
```bash
# Build and deploy all services
docker-compose up -d

# Services will be available at:
# - LLM Service: http://localhost:8004
# - NLU Service: http://localhost:8003
# - RAG Service: http://localhost:8005
```

## API Documentation

### LLM Service Endpoints
- `POST /v1/chat/completions` - OpenAI-compatible chat completions
- `POST /v1/completions` - Text completions
- `POST /batch` - Batch processing
- `GET /models` - List available models

### NLU Service Endpoints  
- `POST /nlu` - Natural language understanding
- `POST /agent` - Agent processing with workflows
- `POST /agent/stream` - Streaming agent responses
- `GET /tools` - List available tools

### RAG Service Endpoints
- `POST /documents` - Document upload and indexing
- `POST /search` - Vector similarity search
- `POST /rag` - Retrieval-augmented generation
- `POST /embeddings` - Generate text embeddings

## Configuration

Each service supports extensive configuration through environment variables:

### Common Settings
- `SERVICE_NAME`: Service identifier
- `PORT`: Service port
- `DEBUG`: Debug mode flag
- `LOG_LEVEL`: Logging verbosity

### Database Configuration
- `DB_HOST`, `DB_PORT`: PostgreSQL connection
- `REDIS_HOST`, `REDIS_PORT`: Redis connection  
- `QDRANT_HOST`, `QDRANT_PORT`: Qdrant connection

### Service-Specific Settings
See individual service directories for detailed configuration options.

## Monitoring & Observability

### Health Checks
All services provide `/health` endpoints with detailed status information.

### Metrics
Prometheus metrics available at `/metrics` endpoints covering:
- Request rates and latencies
- Model inference performance
- Token usage and costs
- Error rates and types
- Resource utilization

### Logging
Structured logging with configurable levels and JSON output for production environments.

## Testing

Comprehensive test suite covering all services:

```bash
# Run all tests
poetry run pytest

# Run specific service tests
poetry run pytest tests/test_llm_service.py
poetry run pytest tests/test_nlu_service.py  
poetry run pytest tests/test_rag_service.py

# Run with coverage
poetry run pytest --cov=. --cov-report=html
```

## Security

Production security features:
- JWT authentication middleware
- Rate limiting and request validation
- CORS protection
- Input sanitization and validation
- Secure headers and HTTPS support

## Performance Optimization

- **Request Batching**: Automatic batching for LLM requests
- **Caching**: Multi-layer caching strategy
- **Connection Pooling**: Optimized database connections
- **Async Processing**: Non-blocking I/O throughout
- **GPU Acceleration**: CUDA support for model inference

## Deployment Considerations

### Resource Requirements
- **LLM Service**: GPU with 16GB+ VRAM for large models
- **NLU Service**: 2-4 CPU cores, 8GB RAM
- **RAG Service**: 2-4 CPU cores, 8GB RAM
- **Vector DB**: SSD storage recommended

### Scaling
Services designed for horizontal scaling:
- Stateless design with external state storage
- Load balancer friendly
- Database connection pooling
- Queue-based background processing

## Contributing

1. Follow the established code structure
2. Add comprehensive tests for new features
3. Update documentation as needed
4. Ensure proper error handling and logging
5. Follow security best practices

## License

This implementation is part of the WearForce-Clean project and follows the project's licensing terms.