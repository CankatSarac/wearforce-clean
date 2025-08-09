#!/bin/bash

# WearForce RAG Service - Development Start Script
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting WearForce RAG Service in Development Mode${NC}"
echo "=================================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed.${NC}"
    exit 1
fi

# Check if Poetry is available
if ! command -v poetry &> /dev/null; then
    echo -e "${YELLOW}⚠️  Poetry not found. Installing dependencies with pip...${NC}"
    pip install -r requirements.txt 2>/dev/null || echo -e "${YELLOW}⚠️  requirements.txt not found, continuing...${NC}"
else
    echo -e "${GREEN}📦 Installing dependencies with Poetry...${NC}"
    poetry install
fi

# Set environment variables for development
export SERVICE_NAME=rag-service
export HOST=0.0.0.0
export PORT=8005
export DEBUG=true
export ENVIRONMENT=development

# Database settings
export DB_HOST=localhost
export DB_PORT=5432
export DB_USER=postgres
export DB_PASSWORD=postgres
export DB_NAME=wearforce

# Redis settings
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_DB=0

# Qdrant settings
export QDRANT_HOST=localhost
export QDRANT_PORT=6333
export QDRANT_COLLECTION=wearforce_docs
export EMBEDDING_DIM=384

# RAG settings
export CHUNK_SIZE=512
export CHUNK_OVERLAP=50
export TOP_K=5
export SIMILARITY_THRESHOLD=0.7
export DENSE_WEIGHT=0.7
export SPARSE_WEIGHT=0.3

# Model settings
export EMBEDDING_MODEL=BAAI/bge-small-en-v1.5

# Logging settings
export LOG_LEVEL=DEBUG
export LOG_STRUCTURED=true

echo -e "${YELLOW}🔧 Starting supporting services with Docker Compose...${NC}"

# Start supporting services (PostgreSQL, Redis, Qdrant)
docker-compose up -d postgres redis qdrant

# Wait for services to be ready
echo -e "${YELLOW}⏳ Waiting for services to be ready...${NC}"

# Wait for PostgreSQL
echo -n "Waiting for PostgreSQL..."
until docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; do
    echo -n "."
    sleep 1
done
echo -e " ${GREEN}✓${NC}"

# Wait for Redis
echo -n "Waiting for Redis..."
until docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; do
    echo -n "."
    sleep 1
done
echo -e " ${GREEN}✓${NC}"

# Wait for Qdrant
echo -n "Waiting for Qdrant..."
until curl -f http://localhost:6333/health > /dev/null 2>&1; do
    echo -n "."
    sleep 1
done
echo -e " ${GREEN}✓${NC}"

echo -e "${GREEN}✅ All supporting services are ready!${NC}"

# Create logs directory if it doesn't exist
mkdir -p logs cache

# Set Python path
export PYTHONPATH="/mnt/c/Users/Cankat/Documents/Startup/gateway/ai-services:/mnt/c/Users/Cankat/Documents/Startup/gateway/ai-services/shared"

echo -e "${GREEN}🎯 Starting RAG Service...${NC}"
echo -e "${BLUE}Service will be available at: http://localhost:8005${NC}"
echo -e "${BLUE}Health check: http://localhost:8005/health${NC}"
echo -e "${BLUE}API docs: http://localhost:8005/docs${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the service${NC}"
echo ""

# Change to the correct directory
cd "/mnt/c/Users/Cankat/Documents/Startup/gateway/ai-services"

# Start the RAG service
if command -v poetry &> /dev/null; then
    poetry run python rag-service/main.py
else
    python rag-service/main.py
fi

# Cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}🛑 Shutting down services...${NC}"
    docker-compose down
    echo -e "${GREEN}✅ Cleanup completed${NC}"
}

trap cleanup EXIT