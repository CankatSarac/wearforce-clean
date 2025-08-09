# LLM Inference Service Dockerfile
# Use latest CUDA image for better vLLM support
FROM nvidia/cuda:12.1-devel-ubuntu20.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV CUDA_HOME=/usr/local/cuda
ENV PATH=${CUDA_HOME}/bin:${PATH}
ENV LD_LIBRARY_PATH=${CUDA_HOME}/lib64:${LD_LIBRARY_PATH}

# vLLM specific environment variables
ENV VLLM_USE_MODELSCOPE=True
ENV VLLM_ATTENTION_BACKEND=FLASHINFER
ENV MAX_JOBS=4

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-pip \
    python3.11-dev \
    python3.11-venv \
    git \
    curl \
    wget \
    build-essential \
    cmake \
    ninja-build \
    ccache \
    pkg-config \
    libaio-dev \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic links
RUN ln -s /usr/bin/python3.11 /usr/bin/python
RUN ln -s /usr/bin/pip3 /usr/bin/pip

# Set working directory
WORKDIR /app

# Install Python dependencies with optimizations
RUN pip install --upgrade pip setuptools wheel

# Install PyTorch with CUDA support first
RUN pip install --no-cache-dir torch==2.1.0 torchvision==0.16.0 torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cu121

# Install vLLM with optimizations
RUN pip install --no-cache-dir vllm==0.2.6 \
    xformers==0.0.22.post7 \
    flash-attn==2.3.6 --no-build-isolation

# Install additional dependencies
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    pydantic==2.5.0 \
    redis==5.0.1 \
    structlog==23.2.0 \
    prometheus-client==0.19.0 \
    psutil==5.9.6 \
    httpx==0.25.2

# Create model cache directory with proper permissions
RUN mkdir -p /app/models /app/cache && chmod 755 /app/models /app/cache

# Copy shared components
COPY shared/ /app/shared/

# Copy service code
COPY llm-service/ /app/llm-service/

# Set Python path
ENV PYTHONPATH=/app:/app/shared

# Expose port
EXPOSE 8004

# GPU runtime configuration
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8004/health || exit 1

# Optimization for production
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1

# Run the service with optimizations
CMD ["python", "-O", "llm-service/main.py"]