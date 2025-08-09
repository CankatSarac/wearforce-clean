# TTS Service Dockerfile with Piper TTS integration
FROM python:3.11-slim-bookworm as base

# Set environment variables
ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=on \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    POETRY_VERSION=1.7.1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    wget \
    git \
    pkg-config \
    libsndfile1-dev \
    libffi-dev \
    libssl-dev \
    libportaudio2 \
    libportaudiocpp0 \
    portaudio19-dev \
    espeak-ng \
    espeak-ng-data \
    alsa-utils \
    sox \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry==$POETRY_VERSION

# Set work directory
WORKDIR /app

# Copy Poetry files
COPY pyproject.toml poetry.lock* ./

# Configure poetry
RUN poetry config virtualenvs.create false

# Install Python dependencies
RUN poetry install --no-dev --no-interaction --no-ansi

# Install Piper TTS from GitHub releases
ARG PIPER_VERSION=1.2.0
RUN architecture=$(dpkg --print-architecture) && \
    if [ "$architecture" = "amd64" ]; then \
        PIPER_ARCH="x86_64"; \
    elif [ "$architecture" = "arm64" ]; then \
        PIPER_ARCH="aarch64"; \
    else \
        echo "Unsupported architecture: $architecture" && exit 1; \
    fi && \
    curl -L "https://github.com/rhasspy/piper/releases/download/v${PIPER_VERSION}/piper_${PIPER_ARCH}.tar.gz" | tar -xzC /usr/local/bin --strip-components=1 && \
    chmod +x /usr/local/bin/piper && \
    piper --version

# Create directories
RUN mkdir -p /app/models/piper /app/cache /app/logs /app/temp

# Copy shared modules
COPY shared/ ./shared/

# Copy TTS service code
COPY tts-service/ ./tts-service/

# Set permissions
RUN chown -R nobody:nogroup /app && \
    chmod -R 755 /app

# Download default voice models (optional - can be done at runtime)
# English voices
RUN mkdir -p /app/models/piper/en_US-lessac-high && \
    curl -L "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/high/en_US-lessac-high.onnx" \
         -o /app/models/piper/en_US-lessac-high/en_US-lessac-high.onnx && \
    curl -L "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/high/en_US-lessac-high.onnx.json" \
         -o /app/models/piper/en_US-lessac-high/en_US-lessac-high.onnx.json || echo "Failed to download en_US-lessac voice"

# Turkish voice (if available)
RUN mkdir -p /app/models/piper/tr_TR-dfki-medium && \
    curl -L "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/tr/tr_TR/dfki/medium/tr_TR-dfki-medium.onnx" \
         -o /app/models/piper/tr_TR-dfki-medium/tr_TR-dfki-medium.onnx && \
    curl -L "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/tr/tr_TR/dfki/medium/tr_TR-dfki-medium.onnx.json" \
         -o /app/models/piper/tr_TR-dfki-medium/tr_TR-dfki-medium.onnx.json || echo "Failed to download tr_TR-dfki voice"

# Create a script to download additional voices at runtime
RUN cat > /app/download_voices.sh << 'EOF'
#!/bin/bash

# Function to download a voice
download_voice() {
    local voice_id=$1
    local base_url=$2
    
    echo "Downloading voice: $voice_id"
    mkdir -p "/app/models/piper/$voice_id"
    
    curl -L "$base_url/$voice_id.onnx" -o "/app/models/piper/$voice_id/$voice_id.onnx"
    curl -L "$base_url/$voice_id.onnx.json" -o "/app/models/piper/$voice_id/$voice_id.onnx.json"
    
    if [ -f "/app/models/piper/$voice_id/$voice_id.onnx" ]; then
        echo "Successfully downloaded $voice_id"
    else
        echo "Failed to download $voice_id"
    fi
}

# Download additional English voices
download_voice "en_US-amy-medium" "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium"
download_voice "en_GB-northern_english_male-medium" "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/northern_english_male/medium"

echo "Voice download completed!"
EOF

RUN chmod +x /app/download_voices.sh

# Switch to non-root user
USER nobody

# Expose port
EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

# Environment variables for the service
ENV SERVICE_NAME=tts-service \
    PORT=8002 \
    HOST=0.0.0.0 \
    TTS_MODEL_PATH=/app/models/piper \
    PYTHONPATH=/app \
    LOG_LEVEL=INFO

# Command to run the service
CMD ["python", "-m", "uvicorn", "tts-service.main:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "1"]