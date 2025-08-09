# Wear Force - Conversational CRM + ERP System
## Complete Folder Structure

```
wear-force/
├── README.md                           # Project overview and setup instructions
├── docker-compose.yml                  # Local development environment
├── docker-compose.prod.yml             # Production-like local environment
├── .env.example                        # Environment variables template
├── .gitignore                          # Git ignore patterns
├── Makefile                            # Common development tasks
│
├── backend/                            # Backend services and APIs
│   ├── gateway/                        # Go edge gateway service
│   │   ├── cmd/
│   │   │   └── server/
│   │   │       └── main.go            # Gateway entry point
│   │   ├── internal/
│   │   │   ├── auth/                  # Authentication middleware
│   │   │   ├── config/                # Configuration management
│   │   │   ├── handlers/              # HTTP handlers
│   │   │   ├── middleware/            # Custom middleware
│   │   │   ├── proxy/                 # Service proxy logic
│   │   │   └── websocket/             # WebSocket handling
│   │   ├── pkg/
│   │   │   ├── logger/                # Structured logging
│   │   │   └── metrics/               # Metrics collection
│   │   ├── configs/
│   │   │   ├── gateway.yaml           # Gateway configuration
│   │   │   └── routes.yaml            # Route definitions
│   │   ├── Dockerfile
│   │   ├── go.mod
│   │   ├── go.sum
│   │   └── .air.toml                  # Hot reload config
│   │
│   ├── services/                      # Microservices
│   │   ├── crm/                      # Customer Relationship Management
│   │   │   ├── app/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── main.py           # FastAPI application
│   │   │   │   ├── api/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── v1/           # API version 1
│   │   │   │   │   │   ├── __init__.py
│   │   │   │   │   │   ├── customers.py
│   │   │   │   │   │   ├── contacts.py
│   │   │   │   │   │   ├── leads.py
│   │   │   │   │   │   ├── opportunities.py
│   │   │   │   │   │   └── activities.py
│   │   │   │   │   └── deps.py       # Dependencies
│   │   │   │   ├── core/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── config.py     # Settings management
│   │   │   │   │   ├── security.py   # Security utilities
│   │   │   │   │   └── events.py     # Event handling
│   │   │   │   ├── models/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── customer.py   # SQLAlchemy models
│   │   │   │   │   ├── contact.py
│   │   │   │   │   ├── lead.py
│   │   │   │   │   ├── opportunity.py
│   │   │   │   │   └── activity.py
│   │   │   │   ├── schemas/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── customer.py   # Pydantic schemas
│   │   │   │   │   ├── contact.py
│   │   │   │   │   ├── lead.py
│   │   │   │   │   ├── opportunity.py
│   │   │   │   │   └── common.py
│   │   │   │   ├── services/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── customer.py   # Business logic
│   │   │   │   │   ├── lead.py
│   │   │   │   │   └── analytics.py
│   │   │   │   └── utils/
│   │   │   │       ├── __init__.py
│   │   │   │       ├── database.py   # Database utilities
│   │   │   │       └── messaging.py  # Message queue
│   │   │   ├── tests/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── conftest.py       # Pytest configuration
│   │   │   │   ├── test_api/
│   │   │   │   ├── test_services/
│   │   │   │   └── test_models/
│   │   │   ├── migrations/           # Alembic migrations
│   │   │   │   ├── versions/
│   │   │   │   ├── env.py
│   │   │   │   └── script.py.mako
│   │   │   ├── Dockerfile
│   │   │   ├── requirements.txt
│   │   │   ├── requirements-dev.txt
│   │   │   └── alembic.ini
│   │   │
│   │   ├── erp/                      # Enterprise Resource Planning
│   │   │   ├── app/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── main.py
│   │   │   │   ├── api/
│   │   │   │   │   └── v1/
│   │   │   │   │       ├── inventory.py
│   │   │   │   │       ├── orders.py
│   │   │   │   │       ├── suppliers.py
│   │   │   │   │       ├── products.py
│   │   │   │   │       └── reports.py
│   │   │   │   ├── models/
│   │   │   │   │   ├── inventory.py
│   │   │   │   │   ├── order.py
│   │   │   │   │   ├── supplier.py
│   │   │   │   │   └── product.py
│   │   │   │   ├── services/
│   │   │   │   │   ├── inventory.py
│   │   │   │   │   ├── order.py
│   │   │   │   │   └── analytics.py
│   │   │   │   └── [similar structure to CRM]
│   │   │   ├── tests/
│   │   │   ├── migrations/
│   │   │   ├── Dockerfile
│   │   │   └── requirements.txt
│   │   │
│   │   ├── notifications/            # Notification service
│   │   │   ├── app/
│   │   │   │   ├── main.py
│   │   │   │   ├── api/
│   │   │   │   │   └── v1/
│   │   │   │   │       ├── push.py
│   │   │   │   │       ├── email.py
│   │   │   │   │       ├── sms.py
│   │   │   │   │       └── webhook.py
│   │   │   │   ├── services/
│   │   │   │   │   ├── push_service.py
│   │   │   │   │   ├── email_service.py
│   │   │   │   │   └── template_service.py
│   │   │   │   └── templates/        # Email/SMS templates
│   │   │   ├── tests/
│   │   │   ├── Dockerfile
│   │   │   └── requirements.txt
│   │   │
│   │   ├── stt/                     # Speech-to-Text service
│   │   │   ├── app/
│   │   │   │   ├── main.py
│   │   │   │   ├── api/
│   │   │   │   │   └── v1/
│   │   │   │   │       ├── transcribe.py
│   │   │   │   │       └── streaming.py
│   │   │   │   ├── models/
│   │   │   │   │   └── whisper/     # Whisper model files
│   │   │   │   └── services/
│   │   │   │       ├── transcription.py
│   │   │   │       └── audio_processing.py
│   │   │   ├── tests/
│   │   │   ├── Dockerfile
│   │   │   └── requirements.txt
│   │   │
│   │   └── tts/                     # Text-to-Speech service
│   │       ├── app/
│   │       │   ├── main.py
│   │       │   ├── api/
│   │       │   │   └── v1/
│   │       │   │       ├── synthesize.py
│   │       │   │       └── voices.py
│   │       │   ├── models/
│   │       │   │   └── voice_models/
│   │       │   └── services/
│   │       │       ├── synthesis.py
│   │       │       └── voice_cloning.py
│   │       ├── tests/
│   │       ├── Dockerfile
│   │       └── requirements.txt
│   │
│   ├── ai/                          # AI/ML Components
│   │   ├── agent-router/            # LangGraph agent router
│   │   │   ├── app/
│   │   │   │   ├── main.py
│   │   │   │   ├── agents/
│   │   │   │   │   ├── crm_agent.py
│   │   │   │   │   ├── erp_agent.py
│   │   │   │   │   ├── search_agent.py
│   │   │   │   │   └── routing_agent.py
│   │   │   │   ├── graphs/
│   │   │   │   │   ├── conversation_graph.py
│   │   │   │   │   └── workflow_graph.py
│   │   │   │   ├── tools/
│   │   │   │   │   ├── crm_tools.py
│   │   │   │   │   ├── erp_tools.py
│   │   │   │   │   └── search_tools.py
│   │   │   │   └── utils/
│   │   │   │       ├── prompts.py
│   │   │   │       └── memory.py
│   │   │   ├── tests/
│   │   │   ├── Dockerfile
│   │   │   └── requirements.txt
│   │   │
│   │   ├── vllm-inference/          # vLLM inference server
│   │   │   ├── app/
│   │   │   │   ├── main.py
│   │   │   │   ├── api/
│   │   │   │   │   └── v1/
│   │   │   │   │       ├── completions.py
│   │   │   │   │       └── chat.py
│   │   │   │   ├── models/
│   │   │   │   │   └── model_registry.py
│   │   │   │   └── services/
│   │   │   │       ├── inference.py
│   │   │   │       └── model_loader.py
│   │   │   ├── configs/
│   │   │   │   └── model_configs/
│   │   │   ├── Dockerfile
│   │   │   └── requirements.txt
│   │   │
│   │   └── rag-pipeline/            # RAG with Qdrant
│   │       ├── app/
│   │       │   ├── main.py
│   │       │   ├── api/
│   │       │   │   └── v1/
│   │       │   │       ├── search.py
│   │       │   │       ├── index.py
│   │       │   │       └── knowledge.py
│   │       │   ├── services/
│   │       │   │   ├── embedding.py
│   │       │   │   ├── retrieval.py
│   │       │   │   ├── indexing.py
│   │       │   │   └── reranking.py
│   │       │   ├── models/
│   │       │   │   ├── embeddings/
│   │       │   │   └── reranker/
│   │       │   └── utils/
│   │       │       ├── chunking.py
│   │       │       └── preprocessing.py
│   │       ├── tests/
│   │       ├── Dockerfile
│   │       └── requirements.txt
│   │
│   └── shared/                      # Shared libraries and utilities
│       ├── python/
│       │   ├── wear_force_common/
│       │   │   ├── __init__.py
│       │   │   ├── auth/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── jwt.py
│       │   │   │   └── keycloak.py
│       │   │   ├── database/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── base.py
│       │   │   │   └── session.py
│       │   │   ├── messaging/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── rabbitmq.py
│       │   │   │   └── redis.py
│       │   │   ├── monitoring/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── metrics.py
│       │   │   │   └── tracing.py
│       │   │   └── utils/
│       │   │       ├── __init__.py
│       │   │       └── datetime.py
│       │   ├── setup.py
│       │   └── requirements.txt
│       │
│       └── go/
│           ├── pkg/
│           │   ├── auth/
│           │   │   ├── jwt.go
│           │   │   └── keycloak.go
│           │   ├── config/
│           │   │   └── config.go
│           │   ├── logger/
│           │   │   └── logger.go
│           │   └── metrics/
│           │       └── prometheus.go
│           ├── go.mod
│           └── go.sum
│
├── clients/                         # Client applications
│   ├── watchos/                    # Apple Watch app
│   │   ├── WearForce.xcodeproj/
│   │   ├── WearForce/
│   │   │   ├── ContentView.swift
│   │   │   ├── WearForceApp.swift
│   │   │   ├── Views/
│   │   │   │   ├── ConversationView.swift
│   │   │   │   ├── CRMView.swift
│   │   │   │   └── ERPView.swift
│   │   │   ├── Services/
│   │   │   │   ├── APIService.swift
│   │   │   │   ├── AudioService.swift
│   │   │   │   └── WebSocketService.swift
│   │   │   └── Models/
│   │   │       ├── Customer.swift
│   │   │       └── Order.swift
│   │   └── WearForce WatchKit Extension/
│   │
│   ├── wear-os/                    # Wear OS app
│   │   ├── app/
│   │   │   ├── build.gradle
│   │   │   ├── src/
│   │   │   │   ├── main/
│   │   │   │   │   ├── java/com/wearforce/
│   │   │   │   │   │   ├── MainActivity.kt
│   │   │   │   │   │   ├── ui/
│   │   │   │   │   │   │   ├── ConversationActivity.kt
│   │   │   │   │   │   │   └── DashboardActivity.kt
│   │   │   │   │   │   ├── services/
│   │   │   │   │   │   │   ├── ApiService.kt
│   │   │   │   │   │   │   └── AudioService.kt
│   │   │   │   │   │   └── models/
│   │   │   │   │   │       ├── Customer.kt
│   │   │   │   │   │       └── Order.kt
│   │   │   │   │   └── res/
│   │   │   │   │       ├── layout/
│   │   │   │   │       └── values/
│   │   │   │   └── androidTest/
│   │   │   └── proguard-rules.pro
│   │   ├── gradle/
│   │   ├── build.gradle
│   │   └── settings.gradle
│   │
│   ├── mobile/                     # React Native mobile app
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── metro.config.js
│   │   ├── babel.config.js
│   │   ├── src/
│   │   │   ├── App.tsx
│   │   │   ├── screens/
│   │   │   │   ├── DashboardScreen.tsx
│   │   │   │   ├── CRMScreen.tsx
│   │   │   │   ├── ERPScreen.tsx
│   │   │   │   └── ConversationScreen.tsx
│   │   │   ├── components/
│   │   │   │   ├── common/
│   │   │   │   ├── crm/
│   │   │   │   └── erp/
│   │   │   ├── services/
│   │   │   │   ├── api.ts
│   │   │   │   ├── auth.ts
│   │   │   │   └── websocket.ts
│   │   │   ├── hooks/
│   │   │   │   ├── useAuth.ts
│   │   │   │   └── useWebSocket.ts
│   │   │   ├── types/
│   │   │   │   ├── api.ts
│   │   │   │   └── models.ts
│   │   │   └── utils/
│   │   │       ├── storage.ts
│   │   │       └── constants.ts
│   │   ├── android/
│   │   ├── ios/
│   │   └── __tests__/
│   │
│   └── web/                        # React web dashboard
│       ├── package.json
│       ├── tsconfig.json
│       ├── vite.config.ts
│       ├── index.html
│       ├── public/
│       ├── src/
│       │   ├── main.tsx
│       │   ├── App.tsx
│       │   ├── pages/
│       │   │   ├── Dashboard.tsx
│       │   │   ├── CRM/
│       │   │   │   ├── Customers.tsx
│       │   │   │   ├── Leads.tsx
│       │   │   │   └── Opportunities.tsx
│       │   │   └── ERP/
│       │   │       ├── Inventory.tsx
│       │   │       ├── Orders.tsx
│       │   │       └── Suppliers.tsx
│       │   ├── components/
│       │   │   ├── ui/              # Shadcn/ui components
│       │   │   ├── layout/
│       │   │   ├── charts/
│       │   │   └── forms/
│       │   ├── hooks/
│       │   ├── services/
│       │   ├── types/
│       │   ├── utils/
│       │   └── styles/
│       │       └── globals.css
│       └── dist/
│
├── infrastructure/                  # Infrastructure as Code
│   ├── docker/                     # Docker configurations
│   │   ├── development/
│   │   │   ├── docker-compose.yml
│   │   │   └── .env.dev
│   │   ├── production/
│   │   │   ├── docker-compose.yml
│   │   │   └── .env.prod
│   │   └── dockerfiles/
│   │       ├── python-base.dockerfile
│   │       └── go-base.dockerfile
│   │
│   ├── kubernetes/                 # K8s manifests
│   │   ├── base/                   # Kustomize base
│   │   │   ├── gateway/
│   │   │   │   ├── deployment.yaml
│   │   │   │   ├── service.yaml
│   │   │   │   ├── configmap.yaml
│   │   │   │   └── kustomization.yaml
│   │   │   ├── services/
│   │   │   │   ├── crm/
│   │   │   │   ├── erp/
│   │   │   │   ├── notifications/
│   │   │   │   ├── stt/
│   │   │   │   └── tts/
│   │   │   ├── ai/
│   │   │   │   ├── agent-router/
│   │   │   │   ├── vllm-inference/
│   │   │   │   └── rag-pipeline/
│   │   │   ├── databases/
│   │   │   │   ├── postgresql/
│   │   │   │   ├── redis/
│   │   │   │   ├── rabbitmq/
│   │   │   │   └── qdrant/
│   │   │   └── security/
│   │   │       ├── keycloak/
│   │   │       └── opa/
│   │   ├── overlays/
│   │   │   ├── development/
│   │   │   │   ├── kustomization.yaml
│   │   │   │   └── patches/
│   │   │   ├── staging/
│   │   │   │   ├── kustomization.yaml
│   │   │   │   └── patches/
│   │   │   └── production/
│   │   │       ├── kustomization.yaml
│   │   │       ├── patches/
│   │   │       └── secrets/
│   │   └── operators/
│   │       ├── prometheus/
│   │       ├── grafana/
│   │       └── istio/
│   │
│   ├── terraform/                  # Terraform for cloud resources
│   │   ├── modules/
│   │   │   ├── vpc/
│   │   │   ├── eks/
│   │   │   ├── rds/
│   │   │   └── s3/
│   │   ├── environments/
│   │   │   ├── dev/
│   │   │   ├── staging/
│   │   │   └── prod/
│   │   └── globals/
│   │       ├── main.tf
│   │       ├── variables.tf
│   │       └── outputs.tf
│   │
│   └── helm/                       # Helm charts
│       ├── wear-force/
│       │   ├── Chart.yaml
│       │   ├── values.yaml
│       │   ├── templates/
│       │   └── charts/
│       └── dependencies/
│           ├── postgresql/
│           ├── redis/
│           └── rabbitmq/
│
├── security/                       # Security configurations
│   ├── keycloak/
│   │   ├── realm-config/
│   │   │   ├── wear-force-realm.json
│   │   │   ├── client-configs/
│   │   │   └── user-federation/
│   │   ├── themes/
│   │   │   └── wear-force/
│   │   └── extensions/
│   │
│   ├── opa/                       # Open Policy Agent
│   │   ├── policies/
│   │   │   ├── crm.rego
│   │   │   ├── erp.rego
│   │   │   └── common.rego
│   │   ├── data/
│   │   │   ├── roles.json
│   │   │   └── permissions.json
│   │   └── tests/
│   │       ├── crm_test.rego
│   │       └── erp_test.rego
│   │
│   ├── certificates/              # SSL certificates
│   │   ├── ca/
│   │   ├── server/
│   │   └── client/
│   │
│   └── audit/                     # Audit logging
│       ├── policies/
│       ├── schemas/
│       └── processors/
│
├── monitoring/                     # Observability stack
│   ├── prometheus/
│   │   ├── prometheus.yml
│   │   ├── rules/
│   │   │   ├── alerts.yml
│   │   │   └── recording.yml
│   │   └── targets/
│   │
│   ├── grafana/
│   │   ├── dashboards/
│   │   │   ├── application.json
│   │   │   ├── infrastructure.json
│   │   │   └── business.json
│   │   ├── datasources/
│   │   └── provisioning/
│   │
│   ├── jaeger/
│   │   ├── jaeger-config.yaml
│   │   └── sampling-strategies.json
│   │
│   ├── elasticsearch/
│   │   ├── elasticsearch.yml
│   │   ├── index-templates/
│   │   └── ilm-policies/
│   │
│   └── kibana/
│       ├── kibana.yml
│       ├── dashboards/
│       └── index-patterns/
│
├── database/                       # Database schemas and migrations
│   ├── postgresql/
│   │   ├── schemas/
│   │   │   ├── crm/
│   │   │   │   ├── 001_initial.sql
│   │   │   │   ├── 002_customers.sql
│   │   │   │   └── 003_leads.sql
│   │   │   ├── erp/
│   │   │   │   ├── 001_initial.sql
│   │   │   │   ├── 002_products.sql
│   │   │   │   └── 003_inventory.sql
│   │   │   └── shared/
│   │   │       ├── 001_users.sql
│   │   │       └── 002_audit.sql
│   │   ├── seeds/
│   │   │   ├── dev_data.sql
│   │   │   └── test_data.sql
│   │   └── functions/
│   │       ├── audit_triggers.sql
│   │       └── reporting_functions.sql
│   │
│   ├── redis/
│   │   ├── redis.conf
│   │   └── lua-scripts/
│   │       ├── rate_limiting.lua
│   │       └── session_cleanup.lua
│   │
│   └── qdrant/
│       ├── collections/
│       │   ├── documents.json
│       │   └── conversations.json
│       └── snapshots/
│
├── api/                           # API specifications
│   ├── openapi/
│   │   ├── gateway.yaml
│   │   ├── crm-v1.yaml
│   │   ├── erp-v1.yaml
│   │   ├── notifications-v1.yaml
│   │   ├── stt-v1.yaml
│   │   ├── tts-v1.yaml
│   │   └── ai-services-v1.yaml
│   │
│   ├── asyncapi/
│   │   ├── events.yaml
│   │   └── websocket.yaml
│   │
│   ├── graphql/
│   │   ├── schema.graphql
│   │   └── resolvers/
│   │
│   └── postman/
│       ├── collections/
│       └── environments/
│
├── docs/                          # Documentation
│   ├── architecture/
│   │   ├── system-design.md
│   │   ├── service-boundaries.md
│   │   ├── data-flow.md
│   │   └── security-model.md
│   ├── deployment/
│   │   ├── local-development.md
│   │   ├── kubernetes-deployment.md
│   │   └── production-setup.md
│   ├── api/
│   │   ├── authentication.md
│   │   ├── rate-limiting.md
│   │   └── error-handling.md
│   └── client/
│       ├── mobile-sdk.md
│       ├── web-integration.md
│       └── wearable-development.md
│
├── scripts/                       # Development and deployment scripts
│   ├── dev/
│   │   ├── setup-local.sh
│   │   ├── reset-db.sh
│   │   ├── generate-certs.sh
│   │   └── seed-data.sh
│   ├── build/
│   │   ├── build-all.sh
│   │   ├── push-images.sh
│   │   └── generate-manifests.sh
│   ├── deploy/
│   │   ├── deploy-dev.sh
│   │   ├── deploy-staging.sh
│   │   └── deploy-prod.sh
│   └── maintenance/
│       ├── backup-db.sh
│       ├── cleanup-logs.sh
│       └── health-check.sh
│
├── tests/                         # Integration and E2E tests
│   ├── integration/
│   │   ├── api/
│   │   │   ├── crm_integration_test.py
│   │   │   └── erp_integration_test.py
│   │   ├── services/
│   │   │   ├── stt_integration_test.py
│   │   │   └── ai_integration_test.py
│   │   └── workflows/
│   │       ├── customer_journey_test.py
│   │       └── order_processing_test.py
│   ├── e2e/
│   │   ├── web/
│   │   │   ├── playwright.config.ts
│   │   │   └── tests/
│   │   ├── mobile/
│   │   │   ├── appium/
│   │   │   └── detox/
│   │   └── api/
│   │       ├── postman/
│   │       └── k6/
│   ├── load/
│   │   ├── k6/
│   │   │   ├── load-test.js
│   │   │   └── spike-test.js
│   │   └── artillery/
│   │       └── artillery.yml
│   ├── security/
│   │   ├── owasp-zap/
│   │   ├── nuclei/
│   │   └── bandit/
│   └── fixtures/
│       ├── data/
│       ├── mocks/
│       └── stubs/
│
├── ci/                           # CI/CD configuration
│   ├── github-actions/           # GitHub Actions workflows
│   │   ├── .github/
│   │   │   └── workflows/
│   │   │       ├── ci.yml
│   │   │       ├── cd-dev.yml
│   │   │       ├── cd-staging.yml
│   │   │       ├── cd-prod.yml
│   │   │       ├── security-scan.yml
│   │   │       └── dependency-update.yml
│   │   └── actions/              # Custom actions
│   │       ├── setup-env/
│   │       └── deploy-k8s/
│   │
│   ├── gitlab-ci/               # GitLab CI configuration
│   │   ├── .gitlab-ci.yml
│   │   ├── stages/
│   │   └── templates/
│   │
│   ├── jenkins/                 # Jenkins pipeline
│   │   ├── Jenkinsfile
│   │   ├── shared-library/
│   │   └── jobs/
│   │
│   └── configs/                 # CI/CD configurations
│       ├── sonarqube.properties
│       ├── hadolint.yaml
│       └── trivy.yaml
│
├── tools/                        # Development tools
│   ├── code-generation/
│   │   ├── openapi-generator/
│   │   ├── protobuf/
│   │   └── graphql-codegen/
│   ├── migration/
│   │   ├── data-migration/
│   │   └── schema-migration/
│   ├── testing/
│   │   ├── test-data-generator/
│   │   └── mock-servers/
│   └── utilities/
│       ├── log-parser/
│       ├── config-validator/
│       └── health-checker/
│
├── .github/                      # GitHub specific files
│   ├── ISSUE_TEMPLATE/
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── workflows/               # Symlink to ci/github-actions/.github/workflows/
│   └── dependabot.yml
│
└── .vscode/                      # VS Code configuration
    ├── settings.json
    ├── launch.json
    ├── tasks.json
    ├── extensions.json
    └── snippets/
```

## Key Architecture Decisions

### 1. Service Boundaries
- **Gateway**: Single entry point for all client requests, handles routing, authentication, and rate limiting
- **CRM Service**: Manages customer relationships, leads, opportunities, and activities
- **ERP Service**: Handles inventory, orders, suppliers, and products
- **Notifications**: Centralized notification service for push, email, and SMS
- **STT/TTS**: Dedicated services for speech processing
- **AI Services**: Separate services for agent routing, inference, and RAG

### 2. Data Architecture
- **PostgreSQL**: Primary database for transactional data (CRM, ERP)
- **Redis**: Caching, session storage, and pub/sub messaging
- **RabbitMQ**: Asynchronous message processing between services
- **Qdrant**: Vector database for RAG and semantic search

### 3. Security Model
- **Keycloak**: Identity and access management
- **OPA**: Fine-grained authorization policies
- **JWT**: Token-based authentication
- **Audit Logging**: Comprehensive audit trail for compliance

### 4. Client Support
- **Multi-platform**: Native watchOS, Wear OS, React Native mobile, and React web
- **Consistent APIs**: OpenAPI specifications ensure consistent client integration
- **Real-time**: WebSocket support for real-time updates

### 5. Deployment Strategy
- **Docker**: Containerized services for consistency
- **Kubernetes**: Orchestration with Kustomize for environment management
- **Helm**: Package management for complex deployments
- **Terraform**: Infrastructure as code for cloud resources

### 6. Observability
- **Metrics**: Prometheus and Grafana
- **Tracing**: Jaeger for distributed tracing
- **Logging**: ELK stack (Elasticsearch, Logstash, Kibana)
- **Alerting**: Prometheus Alertmanager

This structure supports:
- **Horizontal scaling**: Each service can scale independently
- **Fault isolation**: Service failures don't cascade
- **Technology diversity**: Right tool for each job
- **Developer productivity**: Clear boundaries and shared utilities
- **Compliance**: Comprehensive audit and security controls
- **Multi-client support**: Unified backend for all client platforms