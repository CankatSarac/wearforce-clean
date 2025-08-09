# WearForce-Clean Services - Docker Setup

This document provides comprehensive instructions for running WearForce-Clean services using Docker and Docker Compose.

## Quick Start

1. **Clone and Setup**:
   ```bash
   git clone <repository-url>
   cd services
   cp .env.example .env
   # Edit .env with your configuration
   ```

2. **Start Services**:
   ```bash
   make dev-setup  # Set up environment
   make build      # Build Docker images
   make up         # Start all services
   ```

3. **Access Services**:
   - GraphQL Gateway: http://localhost:8000
   - CRM Service: http://localhost:8001
   - ERP Service: http://localhost:8002
   - Notification Service: http://localhost:8003

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    WearForce-Clean Services                       │
├─────────────────────────────────────────────────────────────┤
│  GraphQL Gateway (8000)                                     │
│  ├── CRM Service (8001)                                     │
│  ├── ERP Service (8002)                                     │
│  └── Notification Service (8003)                           │
├─────────────────────────────────────────────────────────────┤
│  Infrastructure                                             │
│  ├── PostgreSQL (5432) - Multi-database setup              │
│  ├── Redis (6379) - Caching & Background Tasks             │
│  ├── NATS JetStream (4222) - Event Streaming               │
│  └── Background Workers (RQ)                               │
├─────────────────────────────────────────────────────────────┤
│  Development Tools                                          │
│  ├── PgAdmin (5050) - Database Management                  │
│  ├── Redis Commander (8081) - Redis Management            │
│  ├── RQ Dashboard (9181) - Task Queue Monitoring          │
│  └── MailHog (8025) - Email Testing (dev mode)            │
└─────────────────────────────────────────────────────────────┘
```

## Service Structure

### Core Services
- **GraphQL Gateway**: Unified API endpoint that orchestrates calls to underlying services
- **CRM Service**: Customer relationship management with accounts, contacts, deals, and activities
- **ERP Service**: Enterprise resource planning with products, inventory, warehouses, and orders
- **Notification Service**: Multi-channel notifications (email, SMS, push) with template management

### Infrastructure Services
- **PostgreSQL**: Primary database with separate schemas for each service
- **Redis**: Caching layer and background task queue
- **NATS JetStream**: Event streaming and pub/sub messaging
- **Background Workers**: Asynchronous task processing using RQ

## Environment Configuration

### Core Environment Variables

```bash
# Environment
DEBUG=true
ENVIRONMENT=development

# Database
DATABASE_URL=postgresql+asyncpg://wearforce-clean:wearforce-clean_password@localhost:5432/wearforce-clean

# Redis
REDIS_URL=redis://localhost:6379/0

# NATS
NATS_URL=nats://localhost:4222

# JWT
JWT_SECRET_KEY=your-super-secret-jwt-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Services
CRM_SERVICE_URL=http://localhost:8001
ERP_SERVICE_URL=http://localhost:8002
NOTIFICATION_SERVICE_URL=http://localhost:8003
```

### Notification Configuration

```bash
# Email (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# SMS (Twilio)
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_FROM_PHONE=+1234567890

# Push Notifications (Firebase)
FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json
```

## Development Workflow

### Starting Development Environment

```bash
# Set up environment (one-time)
make dev-setup

# Start development services with hot reload
make up-dev

# View logs
make logs-f

# Run tests
make test

# Check service health
make health
```

### Database Operations

```bash
# Run migrations
make migrate

# Create new migration
make migrate-create

# Seed with sample data
make seed-data

# Reset database (WARNING: destroys all data)
make db-reset
```

### Code Quality

```bash
# Format code
make format

# Run linting
make lint

# Run tests with coverage
make test-coverage
```

## Docker Compose Configurations

### Base Configuration (`docker-compose.yml`)
- Production-ready base configuration
- All services with proper networking
- Volume persistence
- Health checks
- Resource constraints

### Development Override (`docker-compose.dev.yml`)
```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```
- Code volume mounting for hot reload
- Development tools (MailHog, etc.)
- Debug settings enabled

### Production Override (`docker-compose.prod.yml`)
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up
```
- Production optimizations
- Resource limits
- Multiple worker replicas
- Monitoring stack (Prometheus, Grafana)
- Nginx reverse proxy

## Service Details

### GraphQL Gateway (Port 8000)
- **Purpose**: Unified API endpoint
- **Features**: Schema stitching, service orchestration
- **Endpoints**: `/graphql`, `/docs`, `/health`

### CRM Service (Port 8001)
- **Purpose**: Customer relationship management
- **Features**: Accounts, contacts, deals, activities, lead scoring
- **Database**: `wearforce-clean_crm`

### ERP Service (Port 8002)
- **Purpose**: Enterprise resource planning
- **Features**: Products, inventory, warehouses, orders, suppliers
- **Database**: `wearforce-clean_erp`

### Notification Service (Port 8003)
- **Purpose**: Multi-channel notifications
- **Features**: Email, SMS, push notifications, templates, webhooks
- **Database**: `wearforce-clean_notification`

## Background Processing

### Task Queues
- **CRM Tasks**: `crm_tasks` (Redis DB 1)
- **ERP Tasks**: `erp_tasks` (Redis DB 2)
- **Notification Tasks**: `notification_tasks` (Redis DB 3)

### Workers
Each service has dedicated workers for background processing:
- Lead scoring calculations
- Inventory updates
- Email sending
- Webhook deliveries
- Report generation

### Monitoring
RQ Dashboard available at http://localhost:9181 for task monitoring.

## Networking

### Internal Network
All services communicate via the `wearforce-clean_network` bridge network:
- Subnet: 172.20.0.0/16
- DNS resolution between services
- Isolated from external networks

### Service Discovery
Services discover each other using Docker DNS:
- `postgres:5432`
- `redis:6379`
- `nats:4222`
- `crm-service:8001`
- etc.

## Data Persistence

### Volumes
- `postgres_data`: PostgreSQL database files
- `redis_data`: Redis persistence
- `nats_data`: NATS JetStream data
- `prometheus_data`: Metrics storage (production)
- `grafana_data`: Dashboard configuration (production)

### Backup and Restore
```bash
# Create backup
make backup-db

# Restore from backup
make restore-db FILE=backup_20240101_120000.sql
```

## Production Deployment

### Prerequisites
1. Docker Swarm or Kubernetes cluster
2. SSL certificates
3. External secrets management
4. Load balancer configuration

### Deployment Steps
```bash
# Build production images
make prod-build

# Deploy to production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Production Features
- SSL termination via Nginx
- Monitoring with Prometheus and Grafana
- Resource limits and health checks
- Multi-replica workers
- Secret management
- Log aggregation

## Monitoring and Observability

### Health Checks
All services expose `/health` endpoints:
```bash
curl http://localhost:8000/health  # GraphQL Gateway
curl http://localhost:8001/health  # CRM Service
curl http://localhost:8002/health  # ERP Service
curl http://localhost:8003/health  # Notification Service
```

### Metrics (Production)
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000

### Logs
```bash
make logs        # View recent logs
make logs-f      # Follow logs
```

## Troubleshooting

### Common Issues

1. **Port Already in Use**:
   ```bash
   make down  # Stop all services
   # Or change ports in docker-compose.yml
   ```

2. **Database Connection Issues**:
   ```bash
   make health  # Check service health
   docker-compose logs postgres  # Check postgres logs
   ```

3. **Build Issues**:
   ```bash
   make clean   # Clean Docker resources
   make build   # Rebuild images
   ```

4. **Permission Issues**:
   ```bash
   sudo chown -R $USER:$USER .  # Fix file permissions
   ```

### Service Dependencies
Services start in dependency order:
1. Infrastructure (PostgreSQL, Redis, NATS)
2. Core services (CRM, ERP, Notification)
3. Gateway (GraphQL)
4. Workers

### Memory and CPU Usage
Monitor resource usage:
```bash
docker stats  # Real-time resource usage
make status   # Service status
```

## Security Considerations

### Development
- Default passwords (change for production)
- Debug mode enabled
- All networks accessible

### Production
- Secret management via Docker secrets
- SSL/TLS encryption
- Network isolation
- Resource limits
- Security scanning

## Performance Tuning

### Database
- Connection pooling configured
- Separate databases per service
- Indexes on frequently queried fields

### Caching
- Redis for session storage
- Application-level caching
- Database query result caching

### Background Tasks
- Async task processing
- Worker scaling based on load
- Task prioritization

## Makefile Commands Reference

| Command | Description |
|---------|-------------|
| `make help` | Show all available commands |
| `make install` | Install dependencies |
| `make dev-setup` | Setup development environment |
| `make build` | Build Docker images |
| `make up` | Start all services |
| `make up-dev` | Start in development mode |
| `make down` | Stop all services |
| `make restart` | Restart services |
| `make logs` | View logs |
| `make logs-f` | Follow logs |
| `make clean` | Clean Docker resources |
| `make health` | Check service health |
| `make status` | Show service status |
| `make test` | Run tests |
| `make format` | Format code |
| `make lint` | Run linting |
| `make migrate` | Run database migrations |
| `make seed-data` | Seed database |
| `make backup-db` | Create database backup |

## Support

For issues and questions:
1. Check this README
2. Review service logs
3. Check health endpoints
4. Review environment configuration
5. Consult service-specific documentation