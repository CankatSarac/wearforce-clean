# STT Service Dockerfile with whisper.cpp support - Multi-stage build for GPU and CPU variants
# Usage:
#   GPU build: docker build --target gpu-runtime .
#   CPU build: docker build --target cpu-runtime .

# =============================================================================
# GPU Base Stage
# =============================================================================
FROM nvidia/cuda:11.8-devel-ubuntu22.04 AS gpu-base

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CMAKE_BUILD_PARALLEL_LEVEL=8 \
    CUDA_VISIBLE_DEVICES=0 \
    WHISPER_CUDA=1

# Install system dependencies with optimizations
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-pip \
    python3.11-dev \
    python3.11-venv \
    build-essential \
    cmake \
    ninja-build \
    git \
    curl \
    wget \
    unzip \
    # Audio libraries
    ffmpeg \
    libsndfile1 \
    libsndfile1-dev \
    libasound2-dev \
    portaudio19-dev \
    libportaudio2 \
    libportaudiocpp0 \
    libopenblas-dev \
    liblapack-dev \
    # System utilities
    pkg-config \
    ca-certificates \
    # Cleanup in same layer
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create symbolic links and upgrade pip
RUN ln -sf /usr/bin/python3.11 /usr/bin/python \
    && ln -sf /usr/bin/pip3 /usr/bin/pip \
    && python -m pip install --upgrade pip setuptools wheel

# =============================================================================
# CPU Base Stage
# =============================================================================
FROM ubuntu:22.04 AS cpu-base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CMAKE_BUILD_PARALLEL_LEVEL=8 \
    WHISPER_CUDA=0

# Install system dependencies (CPU optimized)
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-pip \
    python3.11-dev \
    python3.11-venv \
    build-essential \
    cmake \
    ninja-build \
    git \
    curl \
    wget \
    unzip \
    # Audio libraries
    ffmpeg \
    libsndfile1 \
    libsndfile1-dev \
    libasound2-dev \
    portaudio19-dev \
    libportaudio2 \
    libportaudiocpp0 \
    # CPU optimization libraries
    libopenblas-dev \
    liblapack-dev \
    libeigen3-dev \
    # System utilities
    pkg-config \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create symbolic links and upgrade pip
RUN ln -sf /usr/bin/python3.11 /usr/bin/python \
    && ln -sf /usr/bin/pip3 /usr/bin/pip \
    && python -m pip install --upgrade pip setuptools wheel

# =============================================================================
# Build Stage for whisper.cpp (GPU)
# =============================================================================
FROM gpu-base AS gpu-whisper-build

WORKDIR /tmp

# Clone and build whisper.cpp with CUDA support
RUN git clone https://github.com/ggerganov/whisper.cpp.git whisper.cpp \
    && cd whisper.cpp \
    && mkdir build \
    && cd build \
    && cmake .. \
        -DWHISPER_CUDA=ON \
        -DCMAKE_BUILD_TYPE=Release \
        -DWHISPER_CUBLAS=ON \
        -DCMAKE_CUDA_ARCHITECTURES="70;75;80;86" \
        -GNinja \
    && ninja \
    && cp libwhisper.so /usr/local/lib/ \
    && cp ../whisper.h /usr/local/include/ \
    && cp main /usr/local/bin/whisper-main \
    && ldconfig

# Install optimized Python packages for GPU
RUN pip install --no-cache-dir \
    torch==2.1.0+cu118 \
    torchvision==0.16.0+cu118 \
    torchaudio==2.1.0+cu118 \
    --index-url https://download.pytorch.org/whl/cu118

# =============================================================================
# Build Stage for whisper.cpp (CPU)
# =============================================================================
FROM cpu-base AS cpu-whisper-build

WORKDIR /tmp

# Clone and build whisper.cpp with CPU optimizations
RUN git clone https://github.com/ggerganov/whisper.cpp.git whisper.cpp \
    && cd whisper.cpp \
    && mkdir build \
    && cd build \
    && cmake .. \
        -DCMAKE_BUILD_TYPE=Release \
        -DWHISPER_OPENBLAS=ON \
        -DCMAKE_C_FLAGS="-march=native -mtune=native -O3" \
        -DCMAKE_CXX_FLAGS="-march=native -mtune=native -O3" \
        -GNinja \
    && ninja \
    && cp libwhisper.so /usr/local/lib/ \
    && cp ../whisper.h /usr/local/include/ \
    && cp main /usr/local/bin/whisper-main \
    && ldconfig

# Install CPU-optimized Python packages
RUN pip install --no-cache-dir \
    torch==2.1.0+cpu \
    torchvision==0.16.0+cpu \
    torchaudio==2.1.0+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# =============================================================================
# Requirements Installation Stage
# =============================================================================
FROM gpu-base AS requirements-stage

WORKDIR /app

# Copy and install requirements
COPY pyproject.toml requirements.txt* ./

# Install Python dependencies with optimization
RUN pip install --no-cache-dir \
    # Core dependencies
    fastapi[all]==0.104.1 \
    uvicorn[standard]==0.24.0 \
    pydantic==2.5.0 \
    structlog==23.2.0 \
    redis==5.0.1 \
    grpcio==1.59.3 \
    grpcio-tools==1.59.3 \
    # Audio processing
    librosa==0.10.1 \
    soundfile==0.12.1 \
    pydub==0.25.1 \
    scipy==1.11.4 \
    numpy==1.24.3 \
    # ML dependencies (will be overridden by stage-specific torch installs)
    faster-whisper==0.9.0 \
    openai-whisper==20231117 \
    # Optional performance dependencies
    numba==0.58.1 \
    # System dependencies
    psutil==5.9.6 \
    httpx==0.25.2 \
    tenacity==8.2.3 \
    prometheus-client==0.19.0

# Install whisper.cpp Python bindings
RUN pip install --no-cache-dir git+https://github.com/stlukey/whispercpp.py.git

# =============================================================================
# Model Download Stage
# =============================================================================
FROM requirements-stage AS model-download

WORKDIR /app/models

# Download Whisper models efficiently
RUN echo "Downloading Whisper models..." \
    && curl -L --progress-bar -o ggml-tiny.bin "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin" \
    && curl -L --progress-bar -o ggml-tiny.en.bin "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin" \
    && curl -L --progress-bar -o ggml-base.bin "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin" \
    && curl -L --progress-bar -o ggml-base.en.bin "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin" \
    && curl -L --progress-bar -o ggml-small.bin "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin" \
    && curl -L --progress-bar -o ggml-small.en.bin "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en.bin" \
    && ls -la \
    && echo "Models downloaded successfully"

# =============================================================================
# GPU Runtime Stage
# =============================================================================
FROM gpu-whisper-build AS gpu-runtime

# Copy built whisper.cpp libraries
COPY --from=gpu-whisper-build /usr/local/lib/libwhisper.so /usr/local/lib/
COPY --from=gpu-whisper-build /usr/local/include/whisper.h /usr/local/include/
COPY --from=gpu-whisper-build /usr/local/bin/whisper-main /usr/local/bin/
RUN ldconfig

WORKDIR /app

# Copy Python dependencies
COPY --from=requirements-stage /usr/local/lib/python3.11/dist-packages/ /usr/local/lib/python3.11/dist-packages/

# Copy models
COPY --from=model-download /app/models/ /app/models/

# Copy application code
COPY --from=requirements-stage /app/ /app/
COPY shared/ /app/shared/
COPY stt-service/ /app/stt-service/

# Set environment variables
ENV PYTHONPATH=/app:/app/shared \
    WHISPER_DEVICE=cuda \
    CUDA_VISIBLE_DEVICES=0 \
    OMP_NUM_THREADS=4 \
    MKL_NUM_THREADS=4

# Create directories and non-root user
RUN mkdir -p /app/logs /app/tmp \
    && useradd -r -u 1001 -g users sttuser \
    && chown -R sttuser:users /app \
    && chmod +x /app/stt-service/main.py

USER sttuser

EXPOSE 8001 9001

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8001/health/live || exit 1

CMD ["python", "/app/stt-service/main.py"]

# =============================================================================
# CPU Runtime Stage  
# =============================================================================
FROM cpu-whisper-build AS cpu-runtime

# Copy built whisper.cpp libraries
COPY --from=cpu-whisper-build /usr/local/lib/libwhisper.so /usr/local/lib/
COPY --from=cpu-whisper-build /usr/local/include/whisper.h /usr/local/include/
COPY --from=cpu-whisper-build /usr/local/bin/whisper-main /usr/local/bin/
RUN ldconfig

WORKDIR /app

# Copy Python dependencies (note: CPU stage will have CPU torch packages)
COPY --from=cpu-whisper-build /usr/local/lib/python3.11/dist-packages/ /usr/local/lib/python3.11/dist-packages/

# Install remaining dependencies for CPU
RUN pip install --no-cache-dir \
    fastapi[all]==0.104.1 \
    uvicorn[standard]==0.24.0 \
    pydantic==2.5.0 \
    structlog==23.2.0 \
    redis==5.0.1 \
    grpcio==1.59.3 \
    grpcio-tools==1.59.3 \
    librosa==0.10.1 \
    soundfile==0.12.1 \
    pydub==0.25.1 \
    scipy==1.11.4 \
    numpy==1.24.3 \
    faster-whisper==0.9.0 \
    openai-whisper==20231117 \
    numba==0.58.1 \
    psutil==5.9.6 \
    httpx==0.25.2 \
    tenacity==8.2.3 \
    prometheus-client==0.19.0 \
    && pip install --no-cache-dir git+https://github.com/stlukey/whispercpp.py.git

# Copy models
COPY --from=model-download /app/models/ /app/models/

# Copy application code
COPY shared/ /app/shared/
COPY stt-service/ /app/stt-service/

# Set environment variables for CPU optimization
ENV PYTHONPATH=/app:/app/shared \
    WHISPER_DEVICE=cpu \
    OMP_NUM_THREADS=8 \
    MKL_NUM_THREADS=8 \
    OPENBLAS_NUM_THREADS=8 \
    NUMBA_NUM_THREADS=8

# Create directories and non-root user
RUN mkdir -p /app/logs /app/tmp \
    && useradd -r -u 1001 -g users sttuser \
    && chown -R sttuser:users /app \
    && chmod +x /app/stt-service/main.py

USER sttuser

EXPOSE 8001 9001

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8001/health/live || exit 1

CMD ["python", "/app/stt-service/main.py"]