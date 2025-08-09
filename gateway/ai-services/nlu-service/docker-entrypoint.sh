#!/bin/bash
set -e

# Docker entrypoint script for NLU Service
echo "🚀 Starting WearForce NLU Service"
echo "Environment: ${ENVIRONMENT:-production}"
echo "Port: ${PORT:-8003}"
echo "Debug: ${DEBUG:-false}"

# Wait for dependencies to be ready
wait_for_service() {
    local host=$1
    local port=$2
    local service_name=$3
    local max_attempts=30
    local attempt=0

    echo "⏳ Waiting for $service_name to be ready at $host:$port..."
    
    while [ $attempt -lt $max_attempts ]; do
        if nc -z "$host" "$port" 2>/dev/null; then
            echo "✅ $service_name is ready"
            return 0
        fi
        
        attempt=$((attempt + 1))
        echo "Attempt $attempt/$max_attempts: $service_name not ready yet..."
        sleep 2
    done
    
    echo "❌ $service_name is not ready after $max_attempts attempts"
    return 1
}

# Wait for Redis if configured
if [ -n "${REDIS_HOST}" ] && [ -n "${REDIS_PORT}" ]; then
    wait_for_service "${REDIS_HOST}" "${REDIS_PORT}" "Redis"
fi

# Wait for PostgreSQL if configured
if [ -n "${DB_HOST}" ] && [ -n "${DB_PORT}" ]; then
    wait_for_service "${DB_HOST}" "${DB_PORT}" "PostgreSQL"
fi

# Create necessary directories
mkdir -p /app/logs /app/data /app/models

# Set up logging
export LOG_FILE="/app/logs/nlu-service.log"

# Development vs Production setup
if [ "${ENVIRONMENT}" = "development" ]; then
    echo "🔧 Development mode enabled"
    
    # Install additional development dependencies if needed
    if [ -f "/app/nlu-service/requirements-dev.txt" ]; then
        pip install -r /app/nlu-service/requirements-dev.txt
    fi
    
    # Enable hot reloading and debug logging
    export LOG_LEVEL="DEBUG"
    export DEBUG="true"
    
else
    echo "🏭 Production mode enabled"
    
    # Ensure production settings
    export LOG_LEVEL="${LOG_LEVEL:-INFO}"
    export DEBUG="false"
    
    # Security hardening
    umask 0077
fi

# Check if spaCy model is available, download if not
echo "📥 Checking spaCy model..."
python -c "import spacy; spacy.load('en_core_web_sm')" 2>/dev/null || {
    echo "Downloading spaCy model..."
    python -m spacy download en_core_web_sm
}

# Run database migrations if needed
if [ -n "${DB_HOST}" ] && [ "${ENVIRONMENT}" != "test" ]; then
    echo "🔄 Running database migrations..."
    # Add migration command here if using Alembic
    # alembic upgrade head
fi

# Validate configuration
echo "🔍 Validating configuration..."
python -c "
import os
import sys

required_vars = ['SERVICE_NAME', 'PORT']
optional_vars = ['REDIS_HOST', 'DB_HOST', 'LLM_SERVICE_URL', 'RAG_SERVICE_URL']

missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    print(f'❌ Missing required environment variables: {missing_vars}')
    sys.exit(1)

print('✅ Configuration validated')
"

# Start the service based on environment
echo "🎯 Starting NLU Service..."

# Handle shutdown gracefully
cleanup() {
    echo "🛑 Shutting down NLU Service..."
    # Kill background processes
    jobs -p | xargs -r kill
    exit 0
}

trap cleanup SIGTERM SIGINT

# Execute the main command
if [ "${1}" = "python" ] && [ "${2}" = "nlu-service/main.py" ]; then
    # Normal service startup
    cd /app
    exec "$@"
elif [ "${1}" = "test" ]; then
    # Run tests
    cd /app/nlu-service
    exec python -m pytest test_nlu_service.py -v
elif [ "${1}" = "migrate" ]; then
    # Run migrations only
    echo "Running database migrations..."
    # Add migration command
    exit 0
elif [ "${1}" = "shell" ]; then
    # Interactive shell for debugging
    cd /app
    exec /bin/bash
else
    # Pass through any other commands
    exec "$@"
fi