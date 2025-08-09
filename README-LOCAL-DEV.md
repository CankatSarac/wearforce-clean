# WearForce-Clean Local Development Setup Guide

## Table of Contents
- [Prerequisites](#prerequisites)
- [System Requirements](#system-requirements)
- [Environment Setup](#environment-setup)
- [Database Configuration](#database-configuration)
- [Service Startup](#service-startup)
- [Client Applications](#client-applications)
- [Docker Setup](#docker-setup)
- [Non-Docker Setup](#non-docker-setup)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Performance Tuning](#performance-tuning)
- [Development Workflow](#development-workflow)
- [Port Configuration](#port-configuration)

## Port Configuration

**IMPORTANT**: This project is configured to run alongside the original WearForce project without conflicts.

### WearForce-Clean Port Allocation
```
Web Dashboard:      3001 (instead of 3000)
Gateway HTTP:       8180 (instead of 8080)  
Gateway gRPC:       8181 (instead of 8081)
GraphQL Gateway:    9000 (instead of 8000)
CRM Service:        9001 (instead of 8001)
ERP Service:        9002 (instead of 8002)
Notification:       9003 (instead of 8003)
NLU Service:        9003 (instead of 8003)
LLM Service:        9004 (instead of 8004)
RAG Service:        9005 (instead of 8005)
PostgreSQL:         5532 (instead of 5432)
Redis:              6479 (instead of 6379)  
Keycloak:           8190 (instead of 8090)
pgAdmin:            5150 (instead of 5050)
Redis Commander:    8181 (instead of 8081)
RQ Dashboard:       9281 (instead of 9181)
Prometheus:         9191 (instead of 9091)
Grafana:            3002 (instead of 3001)
```

## Prerequisites

### Required Software
```bash
# Node.js 18+ and npm
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Docker and Docker Compose
sudo apt-get install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER
# Log out and back in for docker group changes

# Go 1.21+ (for gateway development)
wget https://go.dev/dl/go1.21.5.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.21.5.linux-amd64.tar.gz
echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
source ~/.bashrc

# Python 3.11+ and Poetry
sudo apt-get install -y python3.11 python3.11-pip python3.11-venv
curl -sSL https://install.python-poetry.org | python3 -
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Git and essential tools
sudo apt-get install -y git curl wget make build-essential
```

### Optional Tools
```bash
# PostgreSQL client tools
sudo apt-get install -y postgresql-client

# Redis client tools
sudo apt-get install -y redis-tools

# For mobile development
# Android Studio: Download from https://developer.android.com/studio
# Xcode: Available on macOS App Store
```

## System Requirements

### Minimum Requirements
- **CPU**: 4 cores, 2.0 GHz (8+ cores recommended when running both projects)
- **RAM**: 8 GB (16+ GB recommended when running both projects)
- **Storage**: 20 GB free space
- **OS**: Ubuntu 20.04+, macOS 10.15+, Windows 10+ (with WSL2)

### Recommended Requirements (Dual Project Setup)
- **CPU**: 12+ cores, 3.0 GHz
- **RAM**: 24+ GB
- **Storage**: 75+ GB SSD
- **Network**: Stable broadband connection

## Environment Setup

### 1. Clone Repository
```bash
cd /mnt/c/Users/Cankat/Documents/Startup-Clean
# Repository is already cloned at this location
```

### 2. Create Environment Files
```bash
# Backend services environment
cat > services/.env <<EOF
# Database Configuration (Modified Ports)
DATABASE_URL=postgresql+asyncpg://wearforce-clean_clean:wearforce-clean_clean_password@localhost:5532/wearforce-clean_clean
CRM_DATABASE_URL=postgresql+asyncpg://wearforce-clean_clean:wearforce-clean_clean_password@localhost:5532/wearforce-clean_clean_crm
ERP_DATABASE_URL=postgresql+asyncpg://wearforce-clean_clean:wearforce-clean_clean_password@localhost:5532/wearforce-clean_clean_erp
NOTIFICATION_DATABASE_URL=postgresql+asyncpg://wearforce-clean_clean:wearforce-clean_clean_password@localhost:5532/wearforce-clean_clean_notification

# Redis Configuration (Modified Port)
REDIS_URL=redis://localhost:6479/0
CRM_REDIS_URL=redis://localhost:6479/1
ERP_REDIS_URL=redis://localhost:6479/2
NOTIFICATION_REDIS_URL=redis://localhost:6479/3

# NATS Configuration (Modified Port)
NATS_URL=nats://localhost:4322

# JWT Configuration (Different from original)
JWT_SECRET_KEY=wearforce-clean-super-secret-jwt-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Email Configuration (Optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# SMS Configuration (Optional)
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_FROM_PHONE=+1234567890

# Debug Mode
DEBUG=true
LOG_LEVEL=INFO
EOF

# Web client environment (Modified Ports)
cat > clients/web/.env <<EOF
VITE_API_URL=http://localhost:9000
VITE_WEBSOCKET_URL=ws://localhost:8180/ws
VITE_GATEWAY_URL=http://localhost:8180
VITE_ENVIRONMENT=development
EOF

# Mobile client environment (Modified Ports)
cat > clients/mobile/.env <<EOF
API_URL=http://localhost:9000
WEBSOCKET_URL=ws://localhost:8180/ws
GATEWAY_URL=http://localhost:8180
ENVIRONMENT=development
EOF

# Gateway environment (Modified Configuration)
cat > gateway/.env <<EOF
GATEWAY_REDIS_ADDRESS=localhost:6479
GATEWAY_JWT_KEYCLOAK_BASE_URL=http://localhost:8190
GATEWAY_JWT_KEYCLOAK_REALM=wearforce-clean
GATEWAY_JWT_KEYCLOAK_CLIENT_ID=wearforce-clean-gateway
GATEWAY_JWT_ISSUER=http://localhost:8190/auth/realms/wearforce-clean
GATEWAY_JWT_AUDIENCE=wearforce-clean-gateway
GATEWAY_TRACING_ENABLED=true
GATEWAY_TRACING_EXPORTER_ENDPOINT=http://localhost:14268/api/traces
GATEWAY_LOGGING_LEVEL=info
EOF
```

## Database Configuration

### Using Docker (Recommended)
```bash
# Create modified docker-compose override for port changes
cat > services/docker-compose.clean.override.yml <<EOF
version: '3.8'
services:
  postgres:
    ports:
      - "5532:5432"
    container_name: wearforce-clean_postgres_custom
  
  redis:
    ports:
      - "6479:6379"
    container_name: wearforce-clean_redis_custom
    
  nats:
    ports:
      - "4322:4222"
      - "8322:8222"
    container_name: wearforce-clean_nats_custom

  graphql-gateway:
    ports:
      - "9000:8000"
      
  crm-service:
    ports:
      - "9001:8001"
      
  erp-service:
    ports:
      - "9002:8002"
      
  notification-service:
    ports:
      - "9003:8003"

  pgadmin:
    ports:
      - "5150:80"
      
  redis-commander:
    ports:
      - "8181:8081"
      
  rq-dashboard:
    ports:
      - "9281:9181"
EOF

# Start PostgreSQL and Redis with custom ports
cd services
docker-compose -f docker-compose.yml -f docker-compose.clean.override.yml up -d postgres redis nats

# Wait for database to be ready
docker-compose exec postgres pg_isready -U wearforce-clean_clean

# Run database migrations
python manage_db.py upgrade
```

### Manual Database Setup (Modified for Clean Project)
```bash
# Install PostgreSQL (if not already installed)
sudo apt-get install -y postgresql postgresql-contrib

# Create user and databases for clean project
sudo -u postgres psql <<EOF
CREATE USER "wearforce-clean_clean" WITH PASSWORD 'wearforce-clean_clean_password';
CREATE DATABASE "wearforce-clean_clean" OWNER "wearforce-clean_clean";
CREATE DATABASE "wearforce-clean_clean_crm" OWNER "wearforce-clean_clean";
CREATE DATABASE "wearforce-clean_clean_erp" OWNER "wearforce-clean_clean";
CREATE DATABASE "wearforce-clean_clean_notification" OWNER "wearforce-clean_clean";
GRANT ALL PRIVILEGES ON DATABASE "wearforce-clean_clean" TO "wearforce-clean_clean";
GRANT ALL PRIVILEGES ON DATABASE "wearforce-clean_clean_crm" TO "wearforce-clean_clean";
GRANT ALL PRIVILEGES ON DATABASE "wearforce-clean_clean_erp" TO "wearforce-clean_clean";
GRANT ALL PRIVILEGES ON DATABASE "wearforce-clean_clean_notification" TO "wearforce-clean_clean";
EOF

# Configure PostgreSQL to listen on alternative port
sudo sed -i 's/#port = 5432/port = 5532/' /etc/postgresql/14/main/postgresql.conf
sudo systemctl restart postgresql

# Install and configure Redis on alternative port
sudo apt-get install -y redis-server
sudo cp /etc/redis/redis.conf /etc/redis/redis-clean.conf
sudo sed -i 's/port 6379/port 6479/' /etc/redis/redis-clean.conf
sudo sed -i 's/dir \/var\/lib\/redis/dir \/var\/lib\/redis-clean/' /etc/redis/redis-clean.conf
sudo mkdir -p /var/lib/redis-clean
sudo chown redis:redis /var/lib/redis-clean
sudo systemctl start redis-server@clean
```

## Service Startup

### Docker-Based Development (Recommended)

#### Option 1: Full Stack with Docker (Modified Ports)
```bash
# Start all infrastructure services
cd services
docker-compose -f docker-compose.yml -f docker-compose.clean.override.yml up -d

# Check service health (note the modified ports)
curl http://localhost:9000/health  # GraphQL Gateway
curl http://localhost:9001/health  # CRM Service  
curl http://localhost:9002/health  # ERP Service
curl http://localhost:9003/health  # Notification Service
```

#### Option 2: Infrastructure Only (Modified Ports)
```bash
# Start only databases and infrastructure
cd services
docker-compose -f docker-compose.yml -f docker-compose.clean.override.yml up -d postgres redis nats pgadmin redis-commander

# Start services locally for development with modified ports
cd ../
python -m uvicorn services.graphql.main:app --host 0.0.0.0 --port 9000 --reload &
python -m uvicorn services.crm.main:app --host 0.0.0.0 --port 9001 --reload &
python -m uvicorn services.erp.main:app --host 0.0.0.0 --port 9002 --reload &
python -m uvicorn services.notification.main:app --host 0.0.0.0 --port 9003 --reload &
```

#### Start Gateway Services (Modified Ports)
```bash
# Create gateway override file
cat > gateway/docker-compose.clean.override.yml <<EOF
version: '3.8'
services:
  gateway:
    ports:
      - "8180:8080"
      - "8181:8081"  
      - "9190:9090"
    environment:
      - GATEWAY_REDIS_ADDRESS=redis:6379
      - GATEWAY_JWT_KEYCLOAK_BASE_URL=http://keycloak:8080
      - GATEWAY_JWT_KEYCLOAK_REALM=wearforce-clean
      - GATEWAY_JWT_KEYCLOAK_CLIENT_ID=wearforce-clean-gateway

  redis:
    ports:
      - "6479:6379"

  keycloak:
    ports:
      - "8190:8080"
    environment:
      - KEYCLOAK_ADMIN=admin
      - KEYCLOAK_ADMIN_PASSWORD=admin123
      - KC_DB=postgres
      - KC_DB_URL=jdbc:postgresql://postgres:5432/keycloak
      - KC_DB_USERNAME=keycloak
      - KC_DB_PASSWORD=keycloak123
      - SERVICE_CLIENT_SECRET=wearforce-clean-services-secret-2025

  postgres:
    ports:
      - "5532:5432"

  qdrant:
    ports:
      - "6433:6333"
      - "6434:6334"

  llm-service:
    ports:
      - "9004:8004"
    environment:
      - DB_USER=wearforce-clean
      - DB_PASSWORD=wearforce-clean123
      - DB_NAME=wearforce-clean

  nlu-service:
    ports:
      - "9003:8003"
    environment:
      - DB_USER=wearforce-clean
      - DB_PASSWORD=wearforce-clean123
      - DB_NAME=wearforce-clean

  rag-service:
    ports:
      - "9005:8005"
    environment:
      - DB_USER=wearforce-clean
      - DB_PASSWORD=wearforce-clean123
      - DB_NAME=wearforce-clean
      - QDRANT_COLLECTION=wearforce_clean_docs

  prometheus:
    ports:
      - "9191:9090"

  grafana:
    ports:
      - "3002:3000"

  jaeger:
    ports:
      - "16687:16686"
      - "14269:14268"

  nginx:
    ports:
      - "8280:80"
      - "8443:443"
EOF

# Start gateway with modified configuration
cd gateway
docker-compose -f docker-compose.yml -f docker-compose.clean.override.yml up -d

# Check gateway health
curl http://localhost:8180/health
```

### Development Mode Services
```bash
# Start services with hot reload and custom ports
cd services
docker-compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.clean.override.yml up -d

# View logs
docker-compose logs -f graphql-gateway
docker-compose logs -f crm-service
```

## Client Applications

### Web Dashboard (Modified Port)
```bash
cd clients/web

# Install dependencies
npm install

# Start development server on port 3001
npm run dev -- --port 3001
# App will be available at http://localhost:3001

# Or modify vite.config.ts to set default port
cat >> vite.config.ts <<EOF
export default defineConfig({
  server: {
    port: 3001
  },
  // ... other config
})
EOF

# Then just run
npm run dev

# Build for production
npm run build

# Run tests
npm run test
npm run test:coverage
```

### Mobile Application (Modified API Endpoints)
```bash
cd clients/mobile

# Install dependencies
npm install

# Update configuration for modified ports
# Edit src/config/api.ts or similar to use modified endpoints

# For iOS (macOS only)
cd ios && pod install && cd ..
npm run ios

# For Android
npm run android

# Start Metro bundler
npm start

# Run tests
npm test
```

### Wearable Applications

#### watchOS (macOS + Xcode required)
```bash
cd clients/watchos
# Update API endpoints in Constants.swift to use modified ports
# Open WearForce.xcodeproj in Xcode
# Build and run on simulator or device
```

#### Wear OS (Android Studio required)
```bash
cd clients/wear-os
# Update API configuration to use modified ports
# Open project in Android Studio
# Build and deploy to Wear OS device/emulator
```

## Docker Setup

### Complete Docker Environment (Clean Project)
```bash
# Start everything with Docker using clean configuration
docker-compose -f services/docker-compose.yml -f services/docker-compose.clean.override.yml up -d
docker-compose -f gateway/docker-compose.yml -f gateway/docker-compose.clean.override.yml up -d

# Scale services
docker-compose -f services/docker-compose.yml -f services/docker-compose.clean.override.yml up -d --scale crm-worker=3

# Stop all services
docker-compose -f services/docker-compose.yml -f services/docker-compose.clean.override.yml down
docker-compose -f gateway/docker-compose.yml -f gateway/docker-compose.clean.override.yml down

# Clean up volumes (WARNING: This deletes data)
docker-compose down -v
docker system prune -a
```

### Development Override (Clean Project)
```bash
# Use development configuration with clean ports
cd services
docker-compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.clean.override.yml up -d

# This enables:
# - Code hot reload
# - Debug mode  
# - Volume mounting for live code changes
# - Development tools (MailHog)
# - Modified ports to avoid conflicts
```

## Non-Docker Setup

### Python Services (Modified Ports)
```bash
cd services

# Install dependencies
poetry install --with test

# Activate virtual environment
poetry shell

# Run database migrations
alembic upgrade head

# Start services with modified ports
python -m uvicorn graphql.main:app --reload --port 9000 &
python -m uvicorn crm.main:app --reload --port 9001 &
python -m uvicorn erp.main:app --reload --port 9002 &
python -m uvicorn notification.main:app --reload --port 9003 &

# Start background workers with modified Redis port
python -m rq worker crm_tasks --url redis://localhost:6479/1 &
python -m rq worker erp_tasks --url redis://localhost:6479/2 &
python -m rq worker notification_tasks --url redis://localhost:6479/3 &
```

### Gateway Service (Modified Configuration)
```bash
cd gateway

# Create clean-specific configuration
cp configs/gateway.yaml configs/gateway-clean.yaml

# Edit gateway-clean.yaml to use modified ports and settings
cat > configs/gateway-clean.yaml <<EOF
server:
  http_port: 8180
  grpc_port: 8181
  metrics_port: 9190

redis:
  address: "localhost:6479"
  
jwt:
  keycloak_base_url: "http://localhost:8190"
  keycloak_realm: "wearforce-clean"
  keycloak_client_id: "wearforce-clean-gateway"
  issuer: "http://localhost:8190/auth/realms/wearforce-clean"
  audience: "wearforce-clean-gateway"

services:
  crm_url: "http://localhost:9001"
  erp_url: "http://localhost:9002"
  notification_url: "http://localhost:9003"
  llm_url: "http://localhost:9004"
  nlu_url: "http://localhost:9003"
  rag_url: "http://localhost:9005"
EOF

# Build and run with clean config
go build -o bin/gateway-clean cmd/gateway/main.go
./bin/gateway-clean --config=configs/gateway-clean.yaml

# Or run directly
go run cmd/gateway/main.go --config=configs/gateway-clean.yaml
```

## Testing

### Backend Services (Modified Endpoints)
```bash
cd services

# Update test configuration for modified ports
export DATABASE_URL="postgresql+asyncpg://wearforce-clean_clean:wearforce-clean_clean_password@localhost:5532/wearforce-clean_clean_test"
export REDIS_URL="redis://localhost:6479/15"

# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=. --cov-report=html

# Run specific service tests
poetry run pytest tests/unit/test_crm_services.py
poetry run pytest tests/integration/

# Load test data
python seed_data.py
```

### API Testing (Modified Ports)
```bash
# Test endpoints with modified ports
curl -X GET http://localhost:9000/health
curl -X GET http://localhost:9001/api/crm/customers
curl -X GET http://localhost:9002/api/erp/products
curl -X GET http://localhost:8180/health  # Gateway

# Load testing with artillery
npm install -g artillery
artillery quick --count 100 --num 10 http://localhost:9000/health
```

## Troubleshooting

### Port Conflict Verification
```bash
# Verify clean project is using correct ports
sudo netstat -tulpn | grep :9000  # GraphQL should be here
sudo netstat -tulpn | grep :8180  # Gateway should be here
sudo netstat -tulpn | grep :5532  # PostgreSQL should be here
sudo netstat -tulpn | grep :6479  # Redis should be here

# Original project ports should also be visible
sudo netstat -tulpn | grep :8000  # Original GraphQL
sudo netstat -tulpn | grep :8080  # Original Gateway
```

### Database Connection Issues (Clean Project)
```bash
# Check clean database status  
docker-compose exec postgres pg_isready -U "wearforce-clean_clean"
docker-compose logs postgres

# Connect manually to clean database
docker-compose exec postgres psql -U "wearforce-clean_clean" -d "wearforce-clean_clean"
```

### Service Communication (Modified URLs)
```bash
# Check clean service logs
docker-compose logs -f graphql-gateway
docker-compose logs -f crm-service

# Test service connectivity with modified ports
curl http://localhost:9000/health
curl http://localhost:9001/health  
curl http://localhost:8180/health
```

### Redis Connection (Modified Port)
```bash
# Test Redis on clean port
redis-cli -h localhost -p 6479 ping
docker-compose exec redis redis-cli ping
```

## Performance Tuning

### Resource Allocation (Dual Project Setup)
```yaml
# Recommended Docker resource limits for dual setup
# Add to docker-compose.clean.override.yml
services:
  graphql-gateway:
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: '0.25'
        reservations:
          memory: 128M
          cpus: '0.125'

  postgres:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
          cpus: '0.25'
```

### Database Optimization (Clean Instance)
```sql
-- PostgreSQL tuning for clean instance
-- Connect to clean database
psql -h localhost -p 5532 -U "wearforce-clean_clean" -d "wearforce-clean_clean"

-- Reduce memory usage for dual setup
ALTER SYSTEM SET shared_buffers = '128MB';
ALTER SYSTEM SET effective_cache_size = '512MB';  
ALTER SYSTEM SET maintenance_work_mem = '32MB';
SELECT pg_reload_conf();
```

## Development Workflow

### Dual Project Development
```bash
# Start both projects simultaneously
cd /mnt/c/Users/Cankat/Documents/

# Terminal 1 - Original Project
cd Startup
./scripts/dev-start.sh

# Terminal 2 - Clean Project  
cd Startup-Clean
./scripts/dev-start-clean.sh

# Both projects now running without conflicts!
# Original: http://localhost:3000
# Clean: http://localhost:3001
```

### Clean Project Scripts
```bash
# Create clean-specific development scripts
mkdir -p scripts

# Start script for clean project
cat > scripts/dev-start-clean.sh <<'EOF'
#!/bin/bash
set -e
echo "Starting WearForce-Clean development environment..."
docker-compose -f services/docker-compose.yml -f services/docker-compose.dev.yml -f services/docker-compose.clean.override.yml up -d
docker-compose -f gateway/docker-compose.yml -f gateway/docker-compose.clean.override.yml up -d
echo "Clean services started. Web dashboard will be at http://localhost:3001"
echo "API Gateway at http://localhost:8180"
echo "Services: GraphQL(9000), CRM(9001), ERP(9002), Notification(9003)"
EOF

# Stop script for clean project
cat > scripts/dev-stop-clean.sh <<'EOF' 
#!/bin/bash
echo "Stopping WearForce-Clean development environment..."
docker-compose -f services/docker-compose.yml -f services/docker-compose.clean.override.yml down
docker-compose -f gateway/docker-compose.yml -f gateway/docker-compose.clean.override.yml down
echo "Clean services stopped."
EOF

chmod +x scripts/*.sh
```

### Monitoring Clean Project
```bash
# Access clean project monitoring dashboards
open http://localhost:5150   # pgAdmin (Clean)
open http://localhost:8181   # Redis Commander (Clean)  
open http://localhost:9281   # RQ Dashboard (Clean)
open http://localhost:3002   # Grafana (Clean)
open http://localhost:9191   # Prometheus (Clean)
open http://localhost:8190   # Keycloak (Clean)
```

## Additional Resources

### Documentation
- **API Documentation**: http://localhost:9000/docs (when clean services are running)
- **GraphQL Playground**: http://localhost:9000/graphql
- **Gateway Health**: http://localhost:8180/health

### Monitoring and Management (Clean Project)
- **pgAdmin**: http://localhost:5150 (admin@wearforce-clean.com / admin_password)
- **Redis Commander**: http://localhost:8181
- **RQ Dashboard**: http://localhost:9281

### Development Tools (Clean Project)
- **Keycloak Admin**: http://localhost:8190 (admin / admin123)
- **Mailhog (Email Testing)**: http://localhost:8125 (dev environment only)

### Support
- Check logs: `docker-compose logs -f [service-name]`
- Service health: `curl http://localhost:[clean-port]/health`
- Database access: `docker-compose exec postgres psql -U "wearforce-clean_clean"`

### Comparison Testing
```bash
# Compare both projects simultaneously
# Original endpoints
curl http://localhost:8000/health
curl http://localhost:8080/health

# Clean project endpoints  
curl http://localhost:9000/health
curl http://localhost:8180/health

# Both should respond without conflicts
```

---

**Last Updated**: January 2025  
**Version**: 1.0 (Clean Project Configuration)  
**Contact**: WearForce-Clean Development Team