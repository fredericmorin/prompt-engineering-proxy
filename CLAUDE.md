# CLAUDE.md — Development Guide

This file provides context for AI assistants (and developers) working on the Prompt Engineering Proxy project.

## Project Summary

LLM API proxy with web UI for capturing, inspecting, editing, and replaying LLM requests/responses. See [README.md](README.md) for full architecture and feature details.

## Tech Stack

- **Backend**: Python 3.12+ / FastAPI / httpx / Redis / SQLite (aiosqlite) / SSE
- **Frontend**: Vue.js 3 (Composition API) / TypeScript / Vite / Tailwind CSS v4 / shadcn-vue / Pinia
- **Tooling**: uv (Python), npm (JS), Ruff (lint/format), pytest, ESLint + Prettier, Docker Compose (Redis)

## Commands

### Backend
```bash
# Install dependencies
uv sync

# Run dev server (auto-reload)
uv run uvicorn backend.main:app --reload --port 8000

# Run tests
uv run pytest

# Lint and format
uv run ruff check backend/
uv run ruff format backend/
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
# Start Redis
docker compose up -d

# Stop Redis
docker compose down
```

## Project Structure

```
backend/              # FastAPI application
  main.py             # App factory, lifespan, CORS, mount routers
  config.py           # pydantic-settings based configuration
  proxy/              # Transparent LLM proxy logic
    router.py         # Route registration for /v1/* endpoints
    handler.py        # Core intercept → forward → tee → store logic
    streaming.py      # SSE stream tee (fork to client + Redis)
    protocols/        # Per-protocol parsing (no cross-format conversion)
      base.py         # Abstract protocol handler
      openai_chat.py  # /v1/chat/completions specifics
      openai_responses.py  # /v1/responses specifics
      anthropic.py    # /v1/messages specifics
  storage/            # SQLite persistence layer
    database.py       # Connection management, schema migrations
    models.py         # Pydantic models for DB records
    repository.py     # CRUD operations
  realtime/           # Redis pub/sub → SSE to frontend
    publisher.py      # Publish proxy events to Redis
    subscriber.py     # Subscribe + push SSE to browser clients
    events.py         # Event type definitions
  api/                # Management REST API for web UI
    requests.py       # Request history CRUD + export
    servers.py        # Upstream server config CRUD
    models.py         # Model listing (queries upstream)
    replay.py         # Replay/send edited requests
  tests/              # pytest tests

frontend/src/         # Vue.js 3 SPA
  router/             # Vue Router config
  stores/             # Pinia stores (requests, servers)
  composables/        # Reusable composition functions (useSSE, etc.)
  lib/                # API client, utilities
  components/         # Vue components
    layout/           # App shell (header, sidebar)
    requests/         # Request list, detail, filters, streaming view
    editor/           # Prompt editor, message builder, parameter controls
    common/           # JsonViewer, DiffViewer, StatusBadge, etc.
  pages/              # Route-level page components
```

## Coding Conventions

### Python (Backend)
- **Style**: Ruff for linting and formatting (follows Black defaults, 88 char line width)
- **Type hints**: Use type annotations on all function signatures
- **Async**: All I/O operations must be async (httpx, aiosqlite, Redis)
- **Imports**: Group: stdlib → third-party → local. Use absolute imports from `backend.`
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
- SSE streams must be forwarded with zero-copy semantics where possible
- API keys in stored request headers should be redacted (show first/last 4 chars)
- SQLite WAL mode for concurrent reads during writes
- Frontend must gracefully handle SSE disconnection and reconnection

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PROXY_HOST` | `0.0.0.0` | Bind address |
| `PROXY_PORT` | `8000` | Bind port |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `DATABASE_PATH` | `data/proxy.db` | SQLite database file path |
| `LOG_LEVEL` | `info` | Logging level |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed CORS origins (comma-separated) |
