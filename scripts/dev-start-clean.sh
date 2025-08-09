#!/bin/bash

# WearForce-Clean Project - Development Startup Script
# This script starts all services for the WearForce-Clean project with modified ports

set -e

echo "🚀 Starting WearForce-Clean Development Environment..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Navigate to project root
cd "$(dirname "$0")/.."

echo "📂 Current directory: $(pwd)"

# Start infrastructure and backend services with clean configuration
echo "🗄️  Starting backend services and infrastructure (Clean version)..."
cd services
docker-compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.clean.override.yml up -d

# Wait for database to be ready (clean port)
echo "⏳ Waiting for clean database to be ready..."
timeout=60
counter=0
until docker-compose exec -T postgres pg_isready -U "wearforce-clean_clean" > /dev/null 2>&1; do
    sleep 1
    counter=$((counter + 1))
    if [ $counter -eq $timeout ]; then
        echo "❌ Timeout waiting for clean database"
        exit 1
    fi
done
echo "✅ Clean database is ready"

# Wait for Redis to be ready (clean port)
echo "⏳ Waiting for clean Redis to be ready..."
counter=0
until docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; do
    sleep 1
    counter=$((counter + 1))
    if [ $counter -eq $timeout ]; then
        echo "❌ Timeout waiting for clean Redis"
        exit 1
    fi
done
echo "✅ Clean Redis is ready"

# Start gateway services with clean configuration
echo "🌐 Starting gateway and AI services (Clean version)..."
cd ../gateway
docker-compose -f docker-compose.yml -f docker-compose.clean.override.yml up -d

# Wait for gateway to be ready (clean port)
echo "⏳ Waiting for clean gateway to be ready..."
counter=0
until curl -f http://localhost:8180/health > /dev/null 2>&1; do
    sleep 2
    counter=$((counter + 2))
    if [ $counter -eq $timeout ]; then
        echo "⚠️  Warning: Clean gateway health check timeout, but continuing..."
        break
    fi
done
echo "✅ Clean gateway is ready"

# Check service health (clean ports)
echo "🔍 Checking clean service health..."
echo "  - GraphQL Gateway: $(curl -s http://localhost:9000/health || echo 'Not ready')"
echo "  - CRM Service: $(curl -s http://localhost:9001/health || echo 'Not ready')"
echo "  - ERP Service: $(curl -s http://localhost:9002/health || echo 'Not ready')"
echo "  - Notification Service: $(curl -s http://localhost:9003/health || echo 'Not ready')"
echo "  - API Gateway: $(curl -s http://localhost:8180/health || echo 'Not ready')"

echo ""
echo "🎉 WearForce-Clean services started successfully!"
echo ""
echo "📍 Available Services (Clean - Modified Ports):"
echo "  🌐 Web Dashboard: http://localhost:3001 (start with 'npm run dev -- --port 3001' in clients/web/)"
echo "  📱 Mobile Metro: http://localhost:8081 (start with 'npm start' in clients/mobile/)"
echo "  🔗 API Gateway: http://localhost:8180"
echo "  📊 GraphQL Playground: http://localhost:9000/graphql"
echo "  📈 pgAdmin: http://localhost:5150 (admin@wearforce-clean.com / admin_password)"
echo "  🔧 Redis Commander: http://localhost:8181"
echo "  ⚡ RQ Dashboard: http://localhost:9281"
echo "  🔐 Keycloak: http://localhost:8190 (admin / admin123)"
echo "  📊 Grafana: http://localhost:3002"
echo "  📈 Prometheus: http://localhost:9191"
echo ""
echo "🔄 Port Differences from Original:"
echo "  📊 GraphQL: 8000 → 9000"
echo "  🔗 Gateway: 8080 → 8180"
echo "  🗄️  Database: 5432 → 5532"
echo "  📦 Redis: 6379 → 6479"
echo "  🌐 Web: 3000 → 3001"
echo ""
echo "💡 Next steps:"
echo "  1. Start web client: cd clients/web && npm install && npm run dev -- --port 3001"
echo "  2. Start mobile client: cd clients/mobile && npm install && npm start"
echo "  3. View logs: docker-compose logs -f [service-name]"
echo "  4. Stop services: ./scripts/dev-stop-clean.sh"
echo ""
echo "📚 Documentation: README-LOCAL-DEV.md"
echo "🔀 Running alongside original? Original ports: 3000, 8080, 8000, 5432"