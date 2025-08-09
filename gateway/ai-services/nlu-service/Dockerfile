# Production-ready NLU/Agent Router Service Dockerfile
FROM python:3.11-slim as builder

# Set build arguments
ARG ENVIRONMENT=production
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION

# Metadata labels
LABEL maintainer="WearForce Team" \
      description="NLU/Agent Router Service for WearForce AI Pipeline" \
      version=$VERSION \
      build-date=$BUILD_DATE \
      vcs-ref=$VCS_REF

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    build-essential \
    curl \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Production stage
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    SERVICE_NAME=nlu-service \
    PORT=8003

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy shared components
COPY --chown=appuser:appuser shared/ /app/shared/

# Copy service code
COPY --chown=appuser:appuser nlu-service/ /app/nlu-service/

# Create directories for logs and data
RUN mkdir -p /app/logs /app/data /app/models && \
    chown -R appuser:appuser /app

# Set Python path
ENV PYTHONPATH=/app:/app/shared

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8003

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8003/health || exit 1

# Add startup script
COPY --chown=appuser:appuser nlu-service/docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# Run the service
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "nlu-service/main.py"]

# Development stage
FROM production as development

# Switch back to root for installing dev dependencies
USER root

# Install development dependencies
RUN pip install --no-cache-dir \
    pytest>=7.4.3 \
    pytest-asyncio>=0.21.1 \
    pytest-cov>=4.1.0 \
    pytest-mock>=3.12.0 \
    black>=23.11.0 \
    isort>=5.12.0 \
    flake8>=6.1.0 \
    mypy>=1.7.1 \
    ruff>=0.1.6

# Install additional development tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    vim \
    htop \
    net-tools \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set development environment
ENV ENVIRONMENT=development \
    DEBUG=true \
    LOG_LEVEL=DEBUG

# Switch back to appuser
USER appuser

# Override for development
CMD ["python", "nlu-service/main.py"]