# WearForce-Clean Gateway

A production-ready edge gateway service for the WearForce-Clean wearable platform, providing secure API management, real-time communication, and service orchestration.

## Features

### Core Capabilities
- **TLS Termination** with Let's Encrypt automatic certificate management
- **JWT Authentication** with Keycloak integration
- **Bi-directional Audio Streaming** via gRPC for STT/TTS services
- **Real-time WebSocket Communication** for chat and notifications
- **Request Routing** to backend microservices (CRM, ERP, User, etc.)
- **Rate Limiting and Quota Management** with Redis backend

### Observability & Monitoring
- **Structured Logging** with configurable output formats
- **Prometheus Metrics** for monitoring and alerting
- **OpenTelemetry Tracing** for distributed request tracking
- **Health Checks** for service availability monitoring

### Security & Reliability
- **Role-based Access Control** with fine-grained permissions
- **CORS Protection** with configurable policies
- **Request/Response Validation** and sanitization
- **Circuit Breaker Pattern** for service resilience
- **Graceful Shutdown** handling

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Client    │    │  Mobile Client  │    │  WearOS Client  │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────▼─────────────┐
                    │     Load Balancer        │
                    │       (Nginx)           │
                    └─────────────┬─────────────┘
                                 │
                    ┌─────────────▼─────────────┐
                    │    WearForce-Clean Gateway     │
                    │  ┌─────────┬─────────┐   │
                    │  │   HTTP  │  gRPC   │   │
                    │  │ :8080   │ :8081   │   │
                    │  └─────────┴─────────┘   │
                    └─────────────┬─────────────┘
                                 │
     ┌───────────────────────────┼───────────────────────────┐
     │                          │                          │
┌────▼────┐  ┌────▼────┐  ┌────▼────┐  ┌────▼────┐  ┌────▼────┐
│   STT   │  │   TTS   │  │   CRM   │  │   ERP   │  │  User   │
│ Service │  │ Service │  │ Service │  │ Service │  │ Service │
└─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘
```

## Quick Start

### Prerequisites
- Go 1.23+
- Docker and Docker Compose
- Redis (for development)
- Keycloak (for authentication)

### Development Setup

1. **Clone the repository**:
```bash
git clone https://github.com/wearforce-clean/gateway.git
cd gateway
```

2. **Install development tools**:
```bash
make setup
```

3. **Start dependencies**:
```bash
docker-compose up -d redis keycloak postgres
```

4. **Run the gateway**:
```bash
make build
./bin/gateway
```

### Using Docker Compose

1. **Start all services**:
```bash
make docker-up
```

2. **Check service health**:
```bash
make check-health
```

3. **View logs**:
```bash
make docker-logs
```

## Configuration

The gateway uses a hierarchical configuration approach:
1. Default values in `configs/gateway.yaml`
2. Environment variable overrides with `GATEWAY_` prefix
3. Command-line flags (if implemented)

### Key Environment Variables

```bash
# Server Configuration
GATEWAY_SERVER_HTTP_PORT=8080
GATEWAY_SERVER_GRPC_PORT=8081

# TLS Configuration
GATEWAY_TLS_ENABLED=true
GATEWAY_TLS_LETS_ENCRYPT_ENABLED=true
GATEWAY_TLS_LETS_ENCRYPT_DOMAINS=api.wearforce-clean.com
GATEWAY_TLS_LETS_ENCRYPT_EMAIL=admin@wearforce-clean.com

# JWT/Keycloak Configuration
GATEWAY_JWT_KEYCLOAK_BASE_URL=https://auth.wearforce-clean.com
GATEWAY_JWT_KEYCLOAK_REALM=wearforce-clean
GATEWAY_JWT_KEYCLOAK_CLIENT_ID=gateway
GATEWAY_JWT_KEYCLOAK_CLIENT_SECRET=secret

# Redis Configuration
GATEWAY_REDIS_ADDRESS=redis:6379
GATEWAY_REDIS_PASSWORD=secret

# Tracing Configuration
GATEWAY_TRACING_ENABLED=true
GATEWAY_TRACING_EXPORTER_ENDPOINT=http://jaeger:14268/api/traces
```

## API Reference

### HTTP Endpoints

#### Health and Status
- `GET /health` - Service health check
- `GET /ping` - Simple ping endpoint
- `GET /metrics` - Prometheus metrics

#### WebSocket
- `GET /ws` - WebSocket connection for real-time communication

#### Authentication Required APIs
- `GET /api/v1/chat/rooms/{roomId}/messages` - Get chat messages
- `POST /api/v1/chat/rooms/{roomId}/messages` - Send chat message
- `POST /api/v1/audio/stt` - Speech-to-text conversion
- `POST /api/v1/audio/tts` - Text-to-speech conversion

#### Admin APIs (Admin Role Required)
- `GET /api/v1/admin/stats` - System statistics
- `GET /api/v1/admin/users` - User management

#### Service Proxy APIs (Manager/Admin Role Required)
- `ANY /api/v1/proxy/crm/*` - CRM service proxy
- `ANY /api/v1/proxy/erp/*` - ERP service proxy

### gRPC Services

#### AudioStreamingService
- `BiDirectionalStream` - Bi-directional audio streaming
- `SpeechToText` - STT streaming
- `TextToSpeech` - TTS conversion
- `GetAudioConfig` - Get supported audio configurations

#### ChatService
- `JoinChat` - Join a chat room
- `StreamMessages` - Stream chat messages
- `SendMessage` - Send chat message

#### GatewayService
- `HealthCheck` - Health check
- `ForwardRequest` - Forward HTTP requests to backend services

### WebSocket Messages

#### Client to Server
```json
{
  "type": "join_room",
  "room_id": "room123",
  "content": {}
}
```

```json
{
  "type": "chat_message",
  "room_id": "room123",
  "content": {
    "text": "Hello, world!"
  }
}
```

#### Server to Client
```json
{
  "type": "chat_message",
  "room_id": "room123",
  "user_id": "user456",
  "content": {
    "text": "Hello, world!",
    "user_name": "Alice"
  },
  "timestamp": "2023-12-01T12:00:00Z"
}
```

## Development

### Running Tests
```bash
# Run all tests
make test

# Run tests with coverage
make test-coverage

# Run benchmarks
make bench
```

### Code Quality
```bash
# Format code
make fmt

# Run linter
make lint

# Run static analysis
make vet

# Run all quality checks
make all
```

### Hot Reload Development
```bash
make dev
```

## Deployment

### Docker Deployment
```bash
# Build and deploy
make docker-build docker-up

# Health check
curl http://localhost:8080/health
```

### Production Considerations

1. **TLS Configuration**: Use Let's Encrypt in production or provide your own certificates
2. **Database**: Use managed Redis service (AWS ElastiCache, Google Memorystore, etc.)
3. **Monitoring**: Configure Prometheus, Grafana, and Jaeger for observability
4. **Security**: Review CORS settings, rate limits, and authentication configuration
5. **Scaling**: Use container orchestration (Kubernetes) for horizontal scaling

## Monitoring and Observability

### Metrics
The gateway exposes Prometheus metrics on `/metrics`:
- HTTP request counters and histograms
- gRPC method metrics  
- WebSocket connection counts
- Rate limiting metrics
- Custom business metrics

### Tracing
OpenTelemetry traces are exported to configured backend:
- HTTP requests
- gRPC calls
- Database operations
- External service calls

### Logging
Structured JSON logging with configurable levels:
- Request/response logging
- Security events
- Error tracking
- Performance monitoring

## Security

### Authentication
- JWT token validation with Keycloak
- Token caching and key rotation
- Role-based access control

### Authorization
- Method-level role requirements
- Resource-based permissions
- Admin-only endpoints

### Network Security
- TLS 1.2+ enforcement
- CORS protection
- Rate limiting
- Request size limits

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run quality checks: `make ci`
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue on GitHub
- Contact: support@wearforce-clean.com
- Documentation: https://docs.wearforce-clean.com