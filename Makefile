
# Default target
.PHONY: help
all: format

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ── Setup ────────────────────────────────────────────────────────────────────

.venv/deps: .venv/bin/uv pyproject.toml uv.lock
	@echo "Installing dependencies..."
	.venv/bin/uv sync --all-extras
	@touch .venv/deps

.venv/bin/uv: .venv/bin/python
	.venv/bin/pip install uv

.venv/bin/python:
	python3 -m venv --prompt venv .venv

frontend/node_modules: frontend/package.json frontend/package-lock.json
	cd frontend && npm install
	@touch frontend/node_modules

.PHONY: setup
setup: .venv/deps frontend/node_modules ## Start all services locally (no Docker)

# ── Development ──────────────────────────────────────────────────────────────

.PHONY: dev
dev: ## Start full dev environment via Docker Compose (hot reload)
	docker compose -f docker-compose.dev.yml up

.PHONY: debug
debug: .venv/deps frontend/node_modules ## Start all services locally (no Docker)
	@echo "Starting backend (port 8000) and frontend (port 5173)..."
	@trap 'kill 0' EXIT; \
		cd frontend && npm run dev & \
		FRONTEND_URL=http://localhost:5173 uv run uvicorn prompt_engineering_proxy.main:app --reload --port 8000 & \
		wait

.PHONY: dev-backend
dev-backend: .venv/deps ## Start backend dev server only
	uv run uvicorn prompt_engineering_proxy.main:app --reload --port 8000

.PHONY: dev-frontend
dev-frontend: frontend/node_modules ## Start frontend dev server only
	cd frontend && npm run dev

# ── Quality Checks ───────────────────────────────────────────────────────────

.PHONY: check
check: check-backend check-frontend ## Run all checks (lint + type-check + test)

.PHONY: check-backend
check-backend: .venv/deps ## Run backend checks (lint + type-check + test)
	uv run ruff check
	uv run ruff format --check
	uv run ty check
	uv run pytest

.PHONY: check-frontend
check-frontend: frontend/node_modules ## Run frontend checks (lint + type-check + test)
	cd frontend && npx eslint src/
	cd frontend && npx prettier --check "src/**/*.{ts,vue,css}"
	cd frontend && npx vue-tsc --noEmit
	cd frontend && npm run test --if-present

# ── Formatting ───────────────────────────────────────────────────────────────

# Default target
.PHONY: format
format: .venv/deps frontend/node_modules ## Auto-format all code
	uv run ruff check --fix src/
	uv run ruff format src/
	cd frontend && npx eslint --fix src/
	cd frontend && npx prettier --write "src/**/*.{ts,vue,css}"

# ── Build ────────────────────────────────────────────────────────────────────

.PHONY: docker
docker: ## Build production Docker image
	docker build -t prompt-engineering-proxy .

# ── Cleanup ──────────────────────────────────────────────────────────────────

.PHONY: clean
clean: ## Remove build artifacts and caches
	rm -rf .venv __pycache__ .pytest_cache .ruff_cache
	rm -rf frontend/node_modules frontend/dist
	rm -rf data/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
