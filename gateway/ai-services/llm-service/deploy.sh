#!/bin/bash

# LLM Service Deployment Script
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DEPLOYMENT_TYPE=${DEPLOYMENT_TYPE:-edge}
GPU_COUNT=${GPU_COUNT:-1}
MODEL_CACHE_DIR=${MODEL_CACHE_DIR:-./models}

echo -e "${BLUE}🚀 WearForce LLM Service Deployment${NC}"
echo "================================="

# Check system requirements
echo -e "${YELLOW}📋 Checking system requirements...${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed${NC}"
    exit 1
fi

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose is not installed${NC}"
    exit 1
fi

# Check NVIDIA Docker (for GPU support)
if ! docker info | grep -q "nvidia"; then
    echo -e "${YELLOW}⚠️  NVIDIA Docker runtime not detected${NC}"
    echo -e "${YELLOW}   GPU acceleration may not be available${NC}"
fi

# Check available GPU memory
if command -v nvidia-smi &> /dev/null; then
    echo -e "${GREEN}✅ NVIDIA GPU detected${NC}"
    nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1 | while read memory; do
        if [ "$memory" -lt 8000 ]; then
            echo -e "${YELLOW}⚠️  Available GPU memory: ${memory}MB (Recommended: >8GB for edge, >80GB for cloud)${NC}"
        else
            echo -e "${GREEN}✅ Available GPU memory: ${memory}MB${NC}"
        fi
    done
else
    echo -e "${YELLOW}⚠️  nvidia-smi not available, cannot check GPU memory${NC}"
fi

echo -e "${GREEN}✅ System requirements check completed${NC}"

# Create necessary directories
echo -e "${YELLOW}📁 Creating directories...${NC}"
mkdir -p ${MODEL_CACHE_DIR}
mkdir -p ./cache
mkdir -p ./logs

# Set deployment type
echo -e "${YELLOW}🔧 Setting deployment configuration...${NC}"
if [ "$DEPLOYMENT_TYPE" = "cloud" ]; then
    echo "DEPLOYMENT_TYPE=cloud" > .env
    echo "TENSOR_PARALLEL_SIZE=4" >> .env
    echo "MAX_NUM_SEQS=512" >> .env
    echo "LLM_GPU_MEMORY=0.90" >> .env
    echo -e "${GREEN}✅ Configured for cloud deployment (80GB A100)${NC}"
elif [ "$DEPLOYMENT_TYPE" = "edge" ]; then
    echo "DEPLOYMENT_TYPE=edge" > .env
    echo "TENSOR_PARALLEL_SIZE=1" >> .env
    echo "MAX_NUM_SEQS=128" >> .env
    echo "LLM_GPU_MEMORY=0.75" >> .env
    echo -e "${GREEN}✅ Configured for edge deployment (16GB GPU)${NC}"
else
    echo -e "${RED}❌ Invalid deployment type: $DEPLOYMENT_TYPE (use 'cloud' or 'edge')${NC}"
    exit 1
fi

# Build and deploy
echo -e "${YELLOW}🔨 Building LLM service...${NC}"
docker-compose build --no-cache llm-service

echo -e "${YELLOW}🚀 Starting services...${NC}"
docker-compose up -d

# Wait for services to be healthy
echo -e "${YELLOW}⏳ Waiting for services to start...${NC}"
sleep 30

# Health check
echo -e "${YELLOW}🏥 Performing health checks...${NC}"
for i in {1..12}; do
    if curl -f http://localhost:8004/health >/dev/null 2>&1; then
        echo -e "${GREEN}✅ LLM service is healthy${NC}"
        break
    fi
    if [ $i -eq 12 ]; then
        echo -e "${RED}❌ LLM service failed to start properly${NC}"
        echo "Checking logs..."
        docker-compose logs llm-service
        exit 1
    fi
    echo -e "${YELLOW}⏳ Waiting for LLM service... ($i/12)${NC}"
    sleep 10
done

# Display service information
echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo ""
echo "Service URLs:"
echo "  - LLM Service: http://localhost:8004"
echo "  - Health Check: http://localhost:8004/health"
echo "  - Metrics: http://localhost:8000/metrics"
echo "  - API Docs: http://localhost:8004/docs"
echo "  - Prometheus: http://localhost:9090"
echo "  - Grafana: http://localhost:3000 (admin/admin)"
echo ""
echo "Available models:"
curl -s http://localhost:8004/models | jq .
echo ""
echo -e "${BLUE}📊 To view logs: docker-compose logs -f llm-service${NC}"
echo -e "${BLUE}🛑 To stop: docker-compose down${NC}"