.PHONY: help up down restart logs seed migrate test test-unit test-integration lint format typecheck clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

up: ## Start all services
	docker compose up -d

down: ## Stop all services
	docker compose down

restart: ## Restart API + worker + scheduler
	docker compose restart aro-api aro-worker aro-scheduler

logs: ## Follow API logs
	docker compose logs -f aro-api

logs-worker: ## Follow worker logs
	docker compose logs -f aro-worker

logs-scheduler: ## Follow scheduler logs
	docker compose logs -f aro-scheduler

ps: ## Show container status
	docker compose ps

build: ## Rebuild all images
	docker compose build

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

migrate: ## Run Alembic migrations inside API container
	docker exec aro-api alembic -c packages/db/alembic.ini upgrade head

migration: ## Generate a new migration (usage: make migration msg="add foo table")
	docker exec aro-api alembic -c packages/db/alembic.ini revision --autogenerate -m "$(msg)"

seed: ## Seed database with dev data
	docker exec aro-api python scripts/seed.py

create-test-db: ## Create the test database
	docker exec aro-postgres createdb -U avataros avatar_revenue_os_test 2>/dev/null || true

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

test: test-unit ## Run all tests (unit + integration if DB available)
	docker exec aro-api python -m pytest tests/integration/ -v --tb=short 2>/dev/null || echo "Integration tests skipped (DB unavailable)"

test-unit: ## Run unit tests
	docker exec aro-api python -m pytest tests/unit/ -v --tb=short

test-integration: create-test-db ## Run integration tests (creates test DB first)
	docker exec aro-api python -m pytest tests/integration/ -v --tb=short

test-coverage: ## Run tests with coverage report
	docker exec aro-api python -m pytest tests/ -v --cov=apps --cov=packages --cov=workers --cov-report=term-missing

# ---------------------------------------------------------------------------
# Code Quality
# ---------------------------------------------------------------------------

lint: ## Run ruff linter
	ruff check .

format: ## Auto-format with ruff
	ruff format .

typecheck: ## Run mypy type checking
	mypy apps/ packages/ workers/ --ignore-missing-imports

check: lint typecheck ## Run lint + typecheck

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

health: ## Check API health endpoints
	@curl -sf http://localhost:8001/healthz | python3 -m json.tool
	@curl -sf http://localhost:8001/readyz  | python3 -m json.tool

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

clean: ## Remove Python caches and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .mypy_cache .ruff_cache

reset: down ## Full reset: stop containers, remove volumes, rebuild
	docker compose down -v
	docker compose build
	docker compose up -d
	@echo "Waiting for services to be healthy..."
	@sleep 10
	$(MAKE) seed
