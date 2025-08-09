#!/bin/bash

# TTS Service Startup Script
# Usage: ./start.sh [development|production|test]

set -e

MODE=${1:-development}
SERVICE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SERVICE_DIR/.." && pwd)"

echo "Starting TTS Service in $MODE mode..."

case $MODE in
    "development")
        echo "Setting up development environment..."
        
        # Set environment variables
        export SERVICE_NAME="tts-service"
        export PORT=8002
        export HOST="0.0.0.0"
        export TTS_MODEL_PATH="$SERVICE_DIR/models/piper"
        export REDIS_HOST="localhost"
        export REDIS_PORT=6379
        export LOG_LEVEL="DEBUG"
        export DEBUG="true"
        export PYTHONPATH="$ROOT_DIR"
        
        # Create directories
        mkdir -p "$SERVICE_DIR/models/piper"
        mkdir -p "$SERVICE_DIR/cache"
        mkdir -p "$SERVICE_DIR/logs"
        
        # Check if Redis is running
        if ! redis-cli ping > /dev/null 2>&1; then
            echo "Warning: Redis is not running. Starting with local Redis..."
            redis-server --daemonize yes --port $REDIS_PORT
        fi
        
        # Start the service with hot reload
        cd "$ROOT_DIR"
        python -m uvicorn tts-service.main:app \
            --host $HOST \
            --port $PORT \
            --reload \
            --reload-dir tts-service \
            --reload-dir shared
        ;;
        
    "production")
        echo "Starting production service..."
        
        # Use Docker Compose for production
        cd "$SERVICE_DIR"
        docker-compose up -d
        
        echo "Service started. Waiting for health check..."
        sleep 10
        
        # Check service health
        if curl -f http://localhost:8002/health > /dev/null 2>&1; then
            echo "✓ TTS Service is healthy!"
            echo "  - Service URL: http://localhost:8002"
            echo "  - Health check: http://localhost:8002/health"
            echo "  - API docs: http://localhost:8002/docs"
        else
            echo "✗ TTS Service health check failed"
            echo "Check logs: docker-compose logs tts-service"
            exit 1
        fi
        ;;
        
    "test")
        echo "Running tests..."
        
        # Start service in background for testing
        export SERVICE_NAME="tts-service"
        export PORT=8003  # Use different port for testing
        export HOST="localhost"
        export TTS_MODEL_PATH="$SERVICE_DIR/models/piper"
        export REDIS_HOST="localhost"
        export LOG_LEVEL="INFO"
        export PYTHONPATH="$ROOT_DIR"
        
        # Start service in background
        cd "$ROOT_DIR"
        python -m uvicorn tts-service.main:app \
            --host $HOST \
            --port $PORT \
            --workers 1 &
        
        SERVICE_PID=$!
        
        # Wait for service to start
        echo "Waiting for service to start..."
        sleep 5
        
        # Run tests
        cd "$SERVICE_DIR"
        if python test_tts.py --host localhost --port $PORT; then
            echo "✓ All tests passed!"
            TEST_RESULT=0
        else
            echo "✗ Some tests failed"
            TEST_RESULT=1
        fi
        
        # Cleanup
        kill $SERVICE_PID 2>/dev/null || true
        exit $TEST_RESULT
        ;;
        
    *)
        echo "Usage: $0 [development|production|test]"
        echo ""
        echo "Modes:"
        echo "  development  - Start service with hot reload for development"
        echo "  production   - Start service with Docker Compose"
        echo "  test         - Run comprehensive test suite"
        exit 1
        ;;
esac