# WearForce Services Makefile

.PHONY: help build up down restart logs clean test lint format install dev-setup seed-data migrate

# Colors for output
BOLD := \033[1m
RESET := \033[0m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m

# Default target
help:
	@echo "$(BOLD)WearForce Services Management$(RESET)"
	@echo ""
	@echo "$(BOLD)Development Commands:$(RESET)"
	@echo "  $(GREEN)install$(RESET)      - Install dependencies using Poetry"
	@echo "  $(GREEN)dev-setup$(RESET)    - Set up development environment"
	@echo "  $(GREEN)format$(RESET)       - Format code with black and isort"
	@echo "  $(GREEN)lint$(RESET)         - Run linting checks"
	@echo "  $(GREEN)test$(RESET)         - Run tests"
	@echo "  $(GREEN)test-unit$(RESET)    - Run unit tests only"
	@echo "  $(GREEN)test-integration$(RESET) - Run integration tests only"
	@echo ""
	@echo "$(BOLD)Database Commands:$(RESET)"
	@echo "  $(GREEN)migrate$(RESET)      - Run database migrations"
	@echo "  $(GREEN)migrate-create$(RESET) - Create new migration"
	@echo "  $(GREEN)seed-data$(RESET)    - Seed database with sample data"
	@echo "  $(GREEN)db-reset$(RESET)     - Reset database (drop and recreate)"
	@echo ""
	@echo "$(BOLD)Docker Commands:$(RESET)"
	@echo "  $(GREEN)build$(RESET)        - Build Docker images"
	@echo "  $(GREEN)up$(RESET)           - Start all services"
	@echo "  $(GREEN)up-dev$(RESET)       - Start services in development mode"
	@echo "  $(GREEN)down$(RESET)         - Stop all services"
	@echo "  $(GREEN)restart$(RESET)      - Restart all services"
	@echo "  $(GREEN)logs$(RESET)         - Show logs from all services"
	@echo "  $(GREEN)logs-f$(RESET)       - Follow logs from all services"
	@echo "  $(GREEN)clean$(RESET)        - Clean up Docker resources"
	@echo ""
	@echo "$(BOLD)Service Commands:$(RESET)"
	@echo "  $(GREEN)run-crm$(RESET)      - Run CRM service locally"
	@echo "  $(GREEN)run-erp$(RESET)      - Run ERP service locally"
	@echo "  $(GREEN)run-notification$(RESET) - Run Notification service locally"
	@echo "  $(GREEN)run-graphql$(RESET)  - Run GraphQL gateway locally"
	@echo ""

# Development setup
install:
	@echo "$(YELLOW)Installing dependencies...$(RESET)"
	poetry install

dev-setup: install
	@echo "$(YELLOW)Setting up development environment...$(RESET)"
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(GREEN)Created .env file from template$(RESET)"; \
	fi
	@echo "$(GREEN)Development environment ready!$(RESET)"
	@echo "$(YELLOW)Please update .env with your configuration$(RESET)"

# Code quality
format:
	@echo "$(YELLOW)Formatting code...$(RESET)"
	poetry run black .
	poetry run isort .
	@echo "$(GREEN)Code formatted!$(RESET)"

lint:
	@echo "$(YELLOW)Running linting checks...$(RESET)"
	poetry run black --check .
	poetry run isort --check-only .
	poetry run flake8 .
	poetry run mypy .
	@echo "$(GREEN)Linting passed!$(RESET)"

# Testing
test:
	@echo "$(YELLOW)Running all tests...$(RESET)"
	poetry run pytest -v

test-unit:
	@echo "$(YELLOW)Running unit tests...$(RESET)"
	poetry run pytest tests/unit/ -v

test-integration:
	@echo "$(YELLOW)Running integration tests...$(RESET)"
	poetry run pytest tests/integration/ -v

test-coverage:
	@echo "$(YELLOW)Running tests with coverage...$(RESET)"
	poetry run pytest --cov=. --cov-report=html --cov-report=term

# Database operations
migrate:
	@echo "$(YELLOW)Running database migrations...$(RESET)"
	poetry run python manage_db.py migrate

migrate-create:
	@read -p "Enter migration message: " message; \
	poetry run python manage_db.py create-migration "$$message"

seed-data:
	@echo "$(YELLOW)Seeding database with sample data...$(RESET)"
	poetry run python seed_data.py

db-reset:
	@echo "$(RED)WARNING: This will delete all data!$(RESET)"
	@read -p "Are you sure? (y/N): " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		poetry run python manage_db.py reset; \
		poetry run python manage_db.py migrate; \
		poetry run python seed_data.py; \
		echo "$(GREEN)Database reset complete!$(RESET)"; \
	fi

# Docker operations
build:
	@echo "$(YELLOW)Building Docker images...$(RESET)"
	docker-compose build
	@echo "$(GREEN)Build complete!$(RESET)"

up:
	@echo "$(YELLOW)Starting services...$(RESET)"
	docker-compose up -d
	@echo "$(GREEN)Services started!$(RESET)"
	@echo "$(YELLOW)Services available at:$(RESET)"
	@echo "  GraphQL Gateway: http://localhost:8000"
	@echo "  CRM Service: http://localhost:8001"
	@echo "  ERP Service: http://localhost:8002"
	@echo "  Notification Service: http://localhost:8003"
	@echo "  PgAdmin: http://localhost:5050"
	@echo "  Redis Commander: http://localhost:8081"
	@echo "  RQ Dashboard: http://localhost:9181"

up-dev:
	@echo "$(YELLOW)Starting services in development mode...$(RESET)"
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
	@echo "$(GREEN)Development services started!$(RESET)"
	@echo "  MailHog (Email testing): http://localhost:8025"

down:
	@echo "$(YELLOW)Stopping services...$(RESET)"
	docker-compose down
	@echo "$(GREEN)Services stopped!$(RESET)"

restart:
	@echo "$(YELLOW)Restarting services...$(RESET)"
	docker-compose restart
	@echo "$(GREEN)Services restarted!$(RESET)"

logs:
	docker-compose logs --tail=100

logs-f:
	docker-compose logs -f

clean:
	@echo "$(YELLOW)Cleaning up Docker resources...$(RESET)"
	docker-compose down --volumes --rmi all
	docker system prune -f
	@echo "$(GREEN)Cleanup complete!$(RESET)"

# Individual service runners (for local development)
run-crm:
	@echo "$(YELLOW)Starting CRM service locally...$(RESET)"
	poetry run python -m uvicorn crm.main:app --host 0.0.0.0 --port 8001 --reload

run-erp:
	@echo "$(YELLOW)Starting ERP service locally...$(RESET)"
	poetry run python -m uvicorn erp.main:app --host 0.0.0.0 --port 8002 --reload

run-notification:
	@echo "$(YELLOW)Starting Notification service locally...$(RESET)"
	poetry run python -m uvicorn notification.main:app --host 0.0.0.0 --port 8003 --reload

run-graphql:
	@echo "$(YELLOW)Starting GraphQL gateway locally...$(RESET)"
	poetry run python -m uvicorn graphql.main:app --host 0.0.0.0 --port 8000 --reload

# Status check
status:
	@echo "$(BOLD)Service Status:$(RESET)"
	docker-compose ps

# Health check
health:
	@echo "$(YELLOW)Checking service health...$(RESET)"
	@curl -f http://localhost:8000/health && echo "$(GREEN)GraphQL Gateway: Healthy$(RESET)" || echo "$(RED)GraphQL Gateway: Unhealthy$(RESET)"
	@curl -f http://localhost:8001/health && echo "$(GREEN)CRM Service: Healthy$(RESET)" || echo "$(RED)CRM Service: Unhealthy$(RESET)"
	@curl -f http://localhost:8002/health && echo "$(GREEN)ERP Service: Healthy$(RESET)" || echo "$(RED)ERP Service: Unhealthy$(RESET)"
	@curl -f http://localhost:8003/health && echo "$(GREEN)Notification Service: Healthy$(RESET)" || echo "$(RED)Notification Service: Unhealthy$(RESET)"

# Production deployment helpers
prod-build:
	@echo "$(YELLOW)Building production images...$(RESET)"
	docker-compose -f docker-compose.yml build --no-cache
	@echo "$(GREEN)Production build complete!$(RESET)"

# Backup and restore
backup-db:
	@echo "$(YELLOW)Creating database backup...$(RESET)"
	docker-compose exec postgres pg_dump -U wearforce wearforce > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)Database backup created!$(RESET)"

restore-db:
	@if [ -z "$(FILE)" ]; then \
		echo "$(RED)Usage: make restore-db FILE=backup_file.sql$(RESET)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Restoring database from $(FILE)...$(RESET)"
	docker-compose exec -T postgres psql -U wearforce wearforce < $(FILE)
	@echo "$(GREEN)Database restored!$(RESET)"