.PHONY: setup setup-backend setup-frontend dev debug dev-backend dev-frontend dev-redis \
       check check-backend check-frontend lint typecheck test format build docker clean help

# Default target
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ── Setup ────────────────────────────────────────────────────────────────────

setup: setup-backend setup-frontend ## Install all dependencies

setup-backend: .venv ## Install backend dependencies
	uv sync

setup-frontend: frontend/node_modules ## Install frontend dependencies
	cd frontend && npm install

.venv: .venv/bin/uv pyproject.toml uv.lock
	@echo "Installing dependencies..."
	.venv/bin/uv sync --all-extras
	@touch .venv

.venv/bin/uv: .venv/bin/python
	.venv/bin/pip install uv

.venv/bin/python:
	python3 -m venv --prompt venv .venv

frontend/node_modules: frontend/package.json frontend/package-lock.json
	cd frontend && npm install
	@touch frontend/node_modules

# ── Development ──────────────────────────────────────────────────────────────

dev: ## Start full dev environment via Docker Compose (hot reload)
	docker compose -f docker-compose.dev.yml up

debug: .venv frontend/node_modules dev-redis ## Start all services locally (no Docker)
	@echo "Starting backend and frontend..."
	@trap 'kill 0' EXIT; \
		uv run uvicorn prompt_engineering_proxy.main:app --reload --port 8000 & \
		cd frontend && npm run dev & \
		wait

dev-backend: .venv ## Start backend dev server only
	uv run uvicorn prompt_engineering_proxy.main:app --reload --port 8000

dev-frontend: frontend/node_modules ## Start frontend dev server only
	cd frontend && npm run dev

dev-redis: ## Start Redis via Docker Compose
	docker compose up -d redis

# ── Quality Checks ───────────────────────────────────────────────────────────

check: check-backend check-frontend ## Run all checks (lint + type-check + test)

check-backend: .venv ## Run backend checks (lint + type-check + test)
	uv run ruff check
	uv run ruff format --check
	uv run ty check
	uv run pytest

check-frontend: frontend/node_modules ## Run frontend checks (lint + type-check + test)
	cd frontend && npm run lint
	cd frontend && npx prettier --check "src/**/*.{ts,vue,css}"
	cd frontend && npx vue-tsc --noEmit
	cd frontend && npm run test --if-present

# ── Formatting ───────────────────────────────────────────────────────────────

format: .venv frontend/node_modules ## Auto-format all code
	uv run ruff check --fix src/
	uv run ruff format src/
	cd frontend && npm run format

# ── Build ────────────────────────────────────────────────────────────────────

build: build-frontend docker ## Build frontend and Docker image

build-frontend: frontend/node_modules ## Build frontend for production
	cd frontend && npm run build

docker: ## Build production Docker image
	docker build -t prompt-engineering-proxy .

# ── Cleanup ──────────────────────────────────────────────────────────────────

clean: ## Remove build artifacts and caches
	rm -rf .venv __pycache__ .pytest_cache .ruff_cache
	rm -rf frontend/node_modules frontend/dist
	rm -rf data/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
