#!/bin/bash
# Development startup script for NLU Service

set -e

echo "🚀 Starting WearForce NLU Service Development Environment"
echo "=================================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose not found. Please install docker-compose."
    exit 1
fi

# Create directories if they don't exist
mkdir -p logs
mkdir -p models
mkdir -p data

# Set environment variables for development
export COMPOSE_PROJECT_NAME=wearforce-nlu-dev
export COMPOSE_FILE=docker-compose.dev.yml

echo "📦 Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi

echo "🐳 Starting Docker services..."
docker-compose -f docker-compose.dev.yml up -d redis postgres crm-mock erp-mock qdrant prometheus grafana

echo "⏳ Waiting for services to be ready..."
sleep 10

# Check if services are ready
echo "🔍 Checking service health..."

# Check Redis
if docker-compose -f docker-compose.dev.yml exec -T redis redis-cli ping | grep -q "PONG"; then
    echo "✅ Redis is ready"
else
    echo "❌ Redis is not ready"
fi

# Check PostgreSQL
if docker-compose -f docker-compose.dev.yml exec -T postgres pg_isready -U nlu_user -d nlu_db | grep -q "accepting connections"; then
    echo "✅ PostgreSQL is ready"
else
    echo "❌ PostgreSQL is not ready"
fi

# Download spaCy model if not present
echo "📥 Downloading spaCy model..."
python -m spacy download en_core_web_sm || echo "⚠️  Could not download spaCy model. Entity extraction may be limited."

echo "🧪 Running tests..."
if [ -f "test_nlu_service.py" ]; then
    python -m pytest test_nlu_service.py -v --tb=short || echo "⚠️  Some tests failed"
fi

echo "🎯 Starting NLU Service..."
echo "Service will be available at: http://localhost:8003"
echo "Health check: http://localhost:8003/health"
echo "API docs: http://localhost:8003/docs"
echo "Prometheus: http://localhost:9090"
echo "Grafana: http://localhost:3003 (admin/admin)"
echo ""
echo "To stop services: docker-compose -f docker-compose.dev.yml down"
echo "To view logs: docker-compose -f docker-compose.dev.yml logs -f nlu-service"
echo ""

# Start the NLU service
python main.py