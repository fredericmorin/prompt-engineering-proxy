# CLAUDE.md — Development Guide

This file provides context for AI assistants (and developers) working on the Prompt Engineering Proxy project.

## Project Summary

LLM API proxy with web UI for capturing, inspecting, editing, and replaying LLM requests/responses. See [README.md](README.md) for full architecture and feature details.

## Tech Stack

- **Backend**: Python 3.12+ / FastAPI / httpx / Redis / SQLite (aiosqlite) / SSE
- **Frontend**: Vue.js 3 (Composition API) / TypeScript / Vite / Tailwind CSS v4 / shadcn-vue / Pinia
- **Type checking**: ty (Python type checker)
- **Tooling**: uv (Python), npm (JS), Ruff (lint/format), ty (type-check), pytest, ESLint (with typescript-eslint) + Prettier
- **Infra**: Docker (production image), Docker Compose (local dev), GitHub Actions (CI/CD), Make (task runner)

## Commands

### Make (preferred)
```bash
make setup      # Install all dependencies (backend + frontend)
make dev        # Start full dev environment via Docker Compose (hot reload)
make debug      # Start Redis + backend (reload) + frontend dev server (no Docker)
make check      # Run all checks: lint + type-check + test
make lint       # Ruff check + ESLint
make typecheck  # ty type checking
make test       # pytest + frontend tests
make format     # Auto-format all code (Ruff + Prettier)
make build      # Build frontend + Docker image
make docker     # Build production Docker image
make clean      # Remove caches, .venv, node_modules, dist
```

### Backend
```bash
# Install dependencies
uv sync

# Run dev server (auto-reload)
uv run uvicorn prompt_engineering_proxy.main:app --reload --port 8000

# Run tests
uv run pytest

# Lint and format
uv run ruff check src/
uv run ruff format src/

# Type check
uv run ty check src/
```

### Frontend
```bash
cd frontend

# Install dependencies
npm install

# Run dev server
npm run dev

# Build for production
npm run build

# Lint
npm run lint

# Format
npm run format
```

### Infrastructure
```bash
# Start full dev environment (Redis + backend + frontend, all hot-reload)
docker compose -f docker-compose.dev.yml up

# Stop dev environment
docker compose -f docker-compose.dev.yml down

# Start Redis only (for use with make debug)
docker compose up -d redis

# Build production Docker image
docker build -t prompt-engineering-proxy .

# Run production image
docker run -p 8000:8000 -e REDIS_URL=redis://host:6379 prompt-engineering-proxy
```

## Project Structure

```
src/prompt_engineering_proxy/  # FastAPI application (Python package)
  main.py             # Entrypoint — imports create_app()
  app.py              # App factory, lifespan (DB/Redis/httpx), CORS, routers
  config.py           # pydantic-settings based configuration
  proxy/              # Transparent LLM proxy logic [Phase 2 ✓]
    router.py         # Route registration for /v1/* endpoints
    handler.py        # Core intercept → forward → tee → store logic
    streaming.py      # SSE tee: forward raw bytes to client + publish chunks to Redis
    protocols/        # Per-protocol parsing (no cross-format conversion)
      base.py         # ProtocolHandler ABC
      openai_chat.py  # /v1/chat/completions — non-streaming + streaming [✓]
      openai_responses.py  # /v1/responses (placeholder)
      anthropic.py    # /v1/messages (placeholder)
  storage/            # SQLite persistence layer [Phase 1 ✓]
    database.py       # Connection management, WAL mode, schema migrations
    models.py         # Pydantic models: Server, ProxyRequest
    repository.py     # CRUD + update operations
  realtime/           # Redis pub/sub → SSE to frontend [Phase 3 ✓]
    publisher.py      # Publish proxy lifecycle + stream chunk events to Redis
    subscriber.py     # RedisSubscriber: subscribes to a channel, yields SSE strings
    events.py         # Event type constants and ProxyEvent model
  api/                # Management REST API for web UI [Phase 3+4 ✓]
    router.py         # Aggregates api/* routers under /api prefix
    requests.py       # GET /api/requests (filtered list), GET/DELETE /api/requests/:id
    events.py         # GET /api/events (lifecycle SSE), GET /api/requests/:id/stream (chunk SSE)
    servers.py        # CRUD /api/servers — upstream server config [Phase 4 ✓]
    models.py         # GET /api/servers/:id/models (loaded status via /api/ps), DELETE unload [Phase 4 ✓]
    send.py           # POST /api/send + POST /api/requests/:id/replay [Phase 4 ✓]; stream=true → background asyncio.create_task + Redis/SSE
tests/                # pytest tests (top-level)

frontend/src/         # Vue.js 3 SPA
  router/             # Vue Router config
  stores/
    requests.ts       # Pinia store: request list, filters, SSE event handler
  composables/
    useSSE.ts         # EventSource wrapper with auto-reconnect and typed event handlers
  lib/
    api.ts            # Typed fetch helpers: listRequests, getRequest, deleteRequest + ProxyEvent types
    utils.ts          # cn() utility
  components/
    layout/           # App shell (AppHeader, AppSidebar, AppLayout)
    common/
      StatusBadge.vue     # Status chip (pending/streaming/complete/error)
      TimingDisplay.vue   # TTFB + total duration display
    requests/
      RequestList.vue         # Scrollable request feed with auto-scroll
      RequestListItem.vue     # Single row: protocol, method, path, model, status, timing
      RequestFilters.vue      # Protocol + model dropdowns
      RequestDetail.vue       # Full detail: headers, body, timing, token counts; conversation thread with per-turn "Fork from here" button
      RequestHeaders.vue      # Key-value header table
      RequestBody.vue         # Pretty-printed JSON body
      StreamingView.vue       # Live token stream via /api/requests/:id/stream SSE
  stores/
    servers.ts        # Pinia store: server list CRUD [Phase 4 ✓]
  pages/
    DashboardPage.vue         # Request list + filters + SSE connection [Phase 3 ✓]
    RequestDetailPage.vue     # Request detail + "Edit in Editor" + "Compare with original" buttons [Phase 3+4 ✓]
    EditorPage.vue            # Prompt editor: server/model/messages/params + send + compare [Phase 4 ✓]; streaming toggle + live StreamingView; fork_at param for conversation branching
    SettingsPage.vue          # Server configuration CRUD [Phase 4 ✓]
    ComparisonPage.vue        # Side-by-side diff of two requests (/compare?a=:id&b=:id) [Phase 4 ✓]
```

## Coding Conventions

### Python (Backend)
- **Style**: Ruff for linting and formatting (follows Black defaults, 88 char line width)
- **Type checking**: ty for static type analysis. All code must pass `ty check` with no errors
- **Type hints**: Use type annotations on all function signatures
- **Async**: All I/O operations must be async (httpx, aiosqlite, Redis)
- **Imports**: Group: stdlib → third-party → local. Use absolute imports from `prompt_engineering_proxy.`
- **Models**: Pydantic v2 models for all data structures. Use `model_validate` / `model_dump`
- **Error handling**: Let FastAPI exception handlers deal with HTTP errors. Use specific exception types
- **Tests**: pytest with async support (pytest-asyncio). Use fixtures for DB and Redis setup
- **No cross-format conversion**: Each protocol handler proxies requests as-is. Never translate between OpenAI and Anthropic formats

### TypeScript (Frontend)
- **Vue style**: `<script setup lang="ts">` with Composition API exclusively
- **State**: Pinia stores for shared state. Local `ref`/`reactive` for component-only state
- **Components**: Single-file components (SFC). Use shadcn-vue primitives as building blocks
- **Naming**: PascalCase for components, camelCase for functions/variables, kebab-case for CSS classes
- **API calls**: Centralized in `lib/api.ts`. Return typed responses
- **SSE**: Use `EventSource` API or `fetch` with `ReadableStream` for streaming

### General
- Commit messages: imperative mood, concise subject line (e.g., "Add request filtering to dashboard")
- No secrets in code — use .env for API keys, never commit .env files
- ULIDs for all entity IDs (sortable, no sequential exposure)
- ISO 8601 for all timestamps
- JSON for all structured data storage in SQLite TEXT columns

## Architecture Notes

### Proxy Flow
1. Client → Proxy: request arrives at `/v1/{path}`
2. Proxy identifies protocol from path, creates DB record (status: pending)
3. Proxy forwards request to configured upstream server using httpx
4. If streaming: tee SSE chunks to (a) client response, (b) Redis pub/sub
5. On completion: assemble full response, update DB record, publish completion event
6. Redis → SSE → Browser: web UI receives real-time updates

### Redis Channels
- `proxy:requests` — lifecycle events (started, completed, error)
- `proxy:stream:{request_id}` — individual SSE chunks for live streaming view

### Key Constraints
- Proxy must not modify request/response payloads (transparent pass-through)
- SSE streams forwarded as raw bytes; events parsed from a side buffer for Redis/storage
- API keys in stored request headers are redacted (first 4 + last 4 chars of token)
- Shared `httpx.AsyncClient` on `app.state.http_client` (connection pooling); tests mock this instance
- SQLite WAL mode for concurrent reads during writes
- Frontend must gracefully handle SSE disconnection and reconnection

## CI/CD

### GitHub Actions — CI (`ci.yml`)
- Triggers: push to any branch, pull requests
- Jobs: backend checks (ruff, ty, pytest) + frontend checks (eslint, prettier, tsc, build)
- Services: Redis container for integration tests
- Must pass before merge

### GitHub Actions — Release (`release.yml`)
- Triggers: push to `main`/`master`, version tags (`v*`)
- Builds multi-stage Docker image
- Pushes to GitHub Container Registry (`ghcr.io`)

### Docker Image
- Multi-stage build: (1) frontend build with Node.js, (2) backend with Python 3.12-slim
- Built frontend is served as static files by the backend
- Only requires external Redis at runtime

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PROXY_HOST` | `0.0.0.0` | Bind address |
| `PROXY_PORT` | `8000` | Bind port |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `DATABASE_PATH` | `data/proxy.db` | SQLite database file path |
| `LOG_LEVEL` | `info` | Logging level |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed CORS origins (comma-separated) |
