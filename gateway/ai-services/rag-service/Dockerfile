# RAG Pipeline Service Dockerfile
# Multi-stage build for optimal production image
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies needed for building
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    curl \
    git \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install poetry==1.7.1

# Configure poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VENV_IN_PROJECT=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

# Copy poetry files
WORKDIR /app
COPY pyproject.toml poetry.lock* ./

# Install dependencies
RUN poetry install --only=main --no-dev && rm -rf $POETRY_CACHE_DIR

# Production stage
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/app/.venv/bin:$PATH"

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN groupadd -r raguser && useradd -r -g raguser raguser

# Set working directory
WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder --chown=raguser:raguser /app/.venv /app/.venv

# Copy shared components and service code
COPY --chown=raguser:raguser shared/ /app/shared/
COPY --chown=raguser:raguser rag-service/ /app/rag-service/

# Set Python path
ENV PYTHONPATH=/app:/app/shared

# Create directories for logs and cache
RUN mkdir -p /app/logs /app/cache /app/models && \
    chown -R raguser:raguser /app

# Switch to non-root user
USER raguser

# Expose port
EXPOSE 8005

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8005/health || exit 1

# Set resource limits (can be overridden)
ENV MAX_WORKERS=4
ENV WORKER_TIMEOUT=300
ENV KEEPALIVE=2

# Add labels for better container management
LABEL maintainer="WearForce AI Team" \
      version="1.0.0" \
      description="RAG Pipeline Service with vector search and document processing" \
      service="rag-service"

# Run the service with production settings
CMD ["python", "-m", "uvicorn", "rag-service.main:app", "--host", "0.0.0.0", "--port", "8005", "--workers", "1", "--access-log", "--log-level", "info"]