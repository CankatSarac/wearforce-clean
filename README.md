# WearForce-Clean - Conversational CRM + ERP System

A comprehensive business management system with AI-powered conversational interfaces for multi-platform deployment including web, mobile, and wearable devices.

## 🏗️ Architecture Overview

WearForce-Clean follows a microservices architecture with the following key components:

- **Gateway**: Go-based API gateway with authentication, rate limiting, and routing
- **Core Services**: Python/FastAPI services for CRM, ERP, notifications, and speech processing
- **AI Services**: LangGraph agents, vLLM inference, and RAG pipeline with Qdrant
- **Client Applications**: Multi-platform support for web, mobile, and wearables
- **Infrastructure**: Kubernetes-ready with Docker containers and Terraform IaC

## 📱 Client Applications

### Web Dashboard (React + TypeScript)
- Modern React 18 with TypeScript
- Tailwind CSS with ShadCN/ui components
- TanStack Query for data fetching
- TanStack Table for data management
- Recharts for analytics visualization
- Zustand for state management

### Mobile App (React Native)
- Cross-platform iOS and Android support
- Redux Toolkit for state management
- React Navigation for routing
- Voice recording and speech recognition
- Push notifications with Firebase
- Offline-first architecture

### watchOS App (SwiftUI)
- Native SwiftUI interface
- Speech Framework integration
- HealthKit integration potential
- Apple Watch-optimized UI
- Background audio support

### Wear OS App (Kotlin + Compose)
- Material You design system
- Jetpack Compose for UI
- Voice interaction capabilities
- Health Services integration
- Wear OS 3+ support

## 🚀 Quick Start

### Prerequisites

- Node.js 18+ and npm/pnpm
- Docker and Docker Compose
- Kubernetes cluster (for production)
- Xcode (for iOS/watchOS development)
- Android Studio (for Android/Wear OS development)

### Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/wearforce-clean.git
   cd wearforce-clean
   ```

2. **Setup environment variables**
   ```bash
   # Copy environment templates
   cp clients/web/.env.example clients/web/.env
   cp clients/mobile/.env.example clients/mobile/.env
   
   # Edit the environment files with your configuration
   ```

3. **Install dependencies and start development**
   
   **Web Dashboard:**
   ```bash
   cd clients/web
   npm install
   npm run dev
   ```
   
   **Mobile App:**
   ```bash
   cd clients/mobile
   npm install
   npm run start
   npm run ios    # for iOS
   npm run android # for Android
   ```

4. **Start backend services**
   ```bash
   docker-compose -f infrastructure/docker/development/docker-compose.yml up -d
   ```

## 🛠️ Development Workflow

### Code Quality
- **Linting**: ESLint with TypeScript support
- **Formatting**: Prettier for consistent code style
- **Type Checking**: TypeScript strict mode
- **Testing**: Vitest for web, Jest for mobile
- **Pre-commit Hooks**: Husky + lint-staged

### Testing Strategy
- **Unit Tests**: Component and utility testing
- **Integration Tests**: API and service integration
- **E2E Tests**: Playwright for web, Detox for mobile
- **Visual Testing**: Storybook for component library

### CI/CD Pipeline
- **GitHub Actions**: Automated testing and deployment
- **Quality Gates**: Code coverage and security scanning
- **Multi-platform Builds**: Web, iOS, Android, Wear OS, watchOS
- **Automated Deployment**: Development and production environments

## 📦 Project Structure

```
wearforce-clean/
├── clients/                    # Client applications
│   ├── web/                   # React web dashboard
│   ├── mobile/                # React Native mobile app
│   ├── watchos/               # SwiftUI watchOS app
│   ├── wear-os/               # Kotlin Wear OS app
│   └── shared/                # Shared utilities and types
├── backend/                   # Backend services
│   ├── gateway/               # Go API gateway
│   ├── services/              # Python microservices
│   └── shared/                # Shared backend utilities
├── infrastructure/            # Infrastructure as Code
│   ├── docker/                # Docker configurations
│   ├── kubernetes/            # K8s manifests
│   ├── terraform/             # Cloud infrastructure
│   └── helm/                  # Helm charts
└── docs/                      # Documentation
```

## 🔧 Technology Stack

### Frontend Technologies
- **Web**: React 18, TypeScript, Tailwind CSS, Vite
- **Mobile**: React Native, TypeScript, Redux Toolkit
- **watchOS**: SwiftUI, Swift, Combine
- **Wear OS**: Kotlin, Jetpack Compose, Hilt

### Backend Technologies
- **Gateway**: Go, Gin, gRPC, WebSockets
- **Services**: Python, FastAPI, SQLAlchemy, Celery
- **AI/ML**: LangGraph, vLLM, Qdrant, OpenAI
- **Databases**: PostgreSQL, Redis, Qdrant

### Infrastructure
- **Containerization**: Docker, Kubernetes
- **Cloud**: AWS/GCP/Azure (multi-cloud)
- **Monitoring**: Prometheus, Grafana, Jaeger
- **Security**: Keycloak, OPA, cert-manager

## 🔐 Security

- **Authentication**: Keycloak OpenID Connect
- **Authorization**: Role-based access control (RBAC)
- **API Security**: JWT tokens, rate limiting, CORS
- **Data Protection**: Encryption at rest and in transit
- **Security Scanning**: Trivy, OWASP ZAP, Semgrep

## 📊 Monitoring and Observability

- **Metrics**: Prometheus with custom business metrics
- **Logging**: Structured logging with ELK stack
- **Tracing**: Distributed tracing with Jaeger
- **Alerting**: PagerDuty integration for critical issues
- **Dashboards**: Grafana with custom dashboards

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes following our coding standards
4. Run tests and ensure quality checks pass
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to your branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Development Guidelines
- Follow TypeScript/Swift/Kotlin best practices
- Write comprehensive tests for new features
- Update documentation for API changes
- Ensure accessibility compliance (WCAG 2.1)
- Follow semantic versioning for releases

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: [docs.wearforce-clean.com](https://docs.wearforce-clean.com)
- **Issues**: [GitHub Issues](https://github.com/your-org/wearforce-clean/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/wearforce-clean/discussions)
- **Email**: support@wearforce-clean.com

## 🙏 Acknowledgments

- React and React Native communities
- Apple and Google for developer tools
- Open source contributors and maintainers
- All team members and contributors

---

**Built with ❤️ by the WearForce-Clean Team**