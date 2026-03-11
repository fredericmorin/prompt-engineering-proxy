.PHONY: setup setup-backend setup-frontend dev dev-backend dev-frontend dev-redis \
       check lint typecheck test format build docker clean help

# Default target
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ── Setup ────────────────────────────────────────────────────────────────────

setup: setup-backend setup-frontend ## Install all dependencies

setup-backend: ## Install backend dependencies
	uv sync

setup-frontend: ## Install frontend dependencies
	cd frontend && npm install

# ── Development ──────────────────────────────────────────────────────────────

dev: dev-redis ## Start all services for local development
	@echo "Starting backend and frontend..."
	@trap 'kill 0' EXIT; \
		uv run uvicorn prompt_engineering_proxy.main:app --reload --port 8000 & \
		cd frontend && npm run dev & \
		wait

dev-backend: ## Start backend dev server only
	uv run uvicorn prompt_engineering_proxy.main:app --reload --port 8000

dev-frontend: ## Start frontend dev server only
	cd frontend && npm run dev

dev-redis: ## Start Redis via Docker Compose
	docker compose up -d redis

# ── Quality Checks ───────────────────────────────────────────────────────────

check: lint typecheck test ## Run all checks (lint + type-check + test)

lint: ## Run linters (Ruff + ESLint)
	uv run ruff check src/
	uv run ruff format --check src/
	cd frontend && npm run lint

typecheck: ## Run type checkers (ty + tsc)
	uv run ty check src/
	cd frontend && npx vue-tsc --noEmit

test: ## Run tests (pytest + frontend)
	uv run pytest
	cd frontend && npm run test --if-present

# ── Formatting ───────────────────────────────────────────────────────────────

format: ## Auto-format all code
	uv run ruff check --fix src/
	uv run ruff format src/
	cd frontend && npm run format

# ── Build ────────────────────────────────────────────────────────────────────

build: build-frontend docker ## Build frontend and Docker image

build-frontend: ## Build frontend for production
	cd frontend && npm run build

docker: ## Build production Docker image
	docker build -t prompt-engineering-proxy .

# ── Cleanup ──────────────────────────────────────────────────────────────────

clean: ## Remove build artifacts and caches
	rm -rf .venv __pycache__ .pytest_cache .ruff_cache
	rm -rf frontend/node_modules frontend/dist
	rm -rf data/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
