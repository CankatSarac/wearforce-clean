# WearForce Gateway Makefile

.PHONY: help build test clean proto docker-build docker-up docker-down lint fmt vet mod-tidy

# Variables
APP_NAME := gateway
VERSION := $(shell git describe --tags --always --dirty)
BUILD_TIME := $(shell date -u '+%Y-%m-%d_%H:%M:%S')
GIT_COMMIT := $(shell git rev-parse HEAD)

# Build flags
LDFLAGS := -ldflags "-X main.version=$(VERSION) -X main.buildTime=$(BUILD_TIME) -X main.gitCommit=$(GIT_COMMIT)"

# Docker variables
DOCKER_IMAGE := wearforce/gateway
DOCKER_TAG := $(VERSION)

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build the application
	@echo "Building $(APP_NAME)..."
	@go build $(LDFLAGS) -o bin/$(APP_NAME) ./cmd/gateway
	@echo "Build complete: bin/$(APP_NAME)"

build-linux: ## Build for Linux
	@echo "Building $(APP_NAME) for Linux..."
	@CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build $(LDFLAGS) -o bin/$(APP_NAME)-linux ./cmd/gateway
	@echo "Build complete: bin/$(APP_NAME)-linux"

test: ## Run tests
	@echo "Running tests..."
	@go test -v -race ./...

test-coverage: ## Run tests with coverage
	@echo "Running tests with coverage..."
	@go test -v -race -coverprofile=coverage.out ./...
	@go tool cover -html=coverage.out -o coverage.html
	@echo "Coverage report generated: coverage.html"

bench: ## Run benchmarks
	@echo "Running benchmarks..."
	@go test -bench=. -benchmem ./...

clean: ## Clean build artifacts
	@echo "Cleaning..."
	@rm -rf bin/
	@rm -f coverage.out coverage.html
	@go clean

proto: ## Generate protobuf code
	@echo "Generating protobuf code..."
	@protoc --go_out=. --go-grpc_out=. pkg/proto/*.proto
	@echo "Protobuf generation complete"

proto-install: ## Install protobuf tools
	@echo "Installing protobuf tools..."
	@go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
	@go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest

docker-build: ## Build Docker image
	@echo "Building Docker image..."
	@docker build -t $(DOCKER_IMAGE):$(DOCKER_TAG) .
	@docker tag $(DOCKER_IMAGE):$(DOCKER_TAG) $(DOCKER_IMAGE):latest
	@echo "Docker image built: $(DOCKER_IMAGE):$(DOCKER_TAG)"

docker-up: ## Start services with Docker Compose
	@echo "Starting services..."
	@docker-compose up -d
	@echo "Services started. Check status with: docker-compose ps"

docker-down: ## Stop services
	@echo "Stopping services..."
	@docker-compose down
	@echo "Services stopped"

docker-logs: ## Show service logs
	@docker-compose logs -f gateway

docker-shell: ## Get shell in gateway container
	@docker-compose exec gateway sh

lint: ## Run linter
	@echo "Running linter..."
	@golangci-lint run ./...

fmt: ## Format code
	@echo "Formatting code..."
	@go fmt ./...

vet: ## Run go vet
	@echo "Running go vet..."
	@go vet ./...

mod-tidy: ## Tidy Go modules
	@echo "Tidying modules..."
	@go mod tidy

mod-download: ## Download dependencies
	@echo "Downloading dependencies..."
	@go mod download

install-tools: ## Install development tools
	@echo "Installing development tools..."
	@go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
	@go install github.com/air-verse/air@latest
	@make proto-install

dev: ## Run in development mode with hot reload
	@echo "Starting development server with hot reload..."
	@air -c .air.toml

setup: install-tools mod-download ## Setup development environment
	@echo "Development environment setup complete"

# Production deployment targets
deploy-staging: docker-build ## Deploy to staging
	@echo "Deploying to staging..."
	@docker tag $(DOCKER_IMAGE):$(DOCKER_TAG) $(DOCKER_IMAGE):staging
	# Add your staging deployment commands here

deploy-prod: docker-build ## Deploy to production
	@echo "Deploying to production..."
	@docker tag $(DOCKER_IMAGE):$(DOCKER_TAG) $(DOCKER_IMAGE):prod
	# Add your production deployment commands here

# Health checks
check-health: ## Check service health
	@echo "Checking service health..."
	@curl -f http://localhost:8080/health || echo "Service not healthy"

check-metrics: ## Check metrics endpoint
	@echo "Checking metrics..."
	@curl -f http://localhost:9090/metrics || echo "Metrics not available"

# Database migrations (if needed in future)
migrate-up: ## Run database migrations up
	@echo "Running migrations..."
	# Add migration commands here

migrate-down: ## Run database migrations down
	@echo "Reverting migrations..."
	# Add migration rollback commands here

# Security scanning
security-scan: ## Run security scan
	@echo "Running security scan..."
	@gosec ./...

# Generate load test
load-test: ## Run load test
	@echo "Running load test..."
	# Add load testing commands here (e.g., using hey, wrk, or k6)

# Documentation
docs: ## Generate documentation
	@echo "Generating documentation..."
	@godoc -http=:6060
	@echo "Documentation available at http://localhost:6060"

# Release targets
tag-release: ## Tag a new release
	@echo "Current version: $(VERSION)"
	@read -p "Enter new version: " NEW_VERSION && \
	git tag -a $$NEW_VERSION -m "Release $$NEW_VERSION" && \
	git push origin $$NEW_VERSION

release-notes: ## Generate release notes
	@echo "Generating release notes..."
	@git log --pretty=format:"- %s" $(shell git describe --tags --abbrev=0)..HEAD

# Kubernetes targets (for future use)
k8s-deploy: ## Deploy to Kubernetes
	@echo "Deploying to Kubernetes..."
	@kubectl apply -f deployments/k8s/

k8s-delete: ## Delete from Kubernetes
	@echo "Deleting from Kubernetes..."
	@kubectl delete -f deployments/k8s/

# All-in-one targets
all: fmt vet lint test build ## Run all checks and build

ci: mod-tidy fmt vet lint test-coverage build ## CI pipeline

# Default target
.DEFAULT_GOAL := help