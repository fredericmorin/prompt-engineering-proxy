# Prompt Engineering Proxy

An LLM proxy with an interactive web interface for capturing, inspecting, editing, and replaying LLM API requests and responses. Point your LLM client at this proxy instead of the real API — it transparently forwards traffic while recording everything for analysis and prompt engineering.

## Architecture Overview

```
┌─────────────┐       ┌─────────────────────────────────────────────┐       ┌─────────────┐
│  LLM Client │──────▶│           Prompt Engineering Proxy          │──────▶│  LLM API    │
│  (any SDK)  │◀──────│                                             │◀──────│  (upstream)  │
└─────────────┘       │  ┌────────────┐  ┌───────┐  ┌────────────┐  │       └─────────────┘
                      │  │  FastAPI   │  │ Redis │  │  SQLite    │  │
                      │  │  Proxy +   │  │ Pub/  │  │  Request/  │  │
                      │  │  Mgmt API  │  │ Sub   │  │  Response  │  │
                      │  └────────────┘  └───┬───┘  │  Storage   │  │
                      │                      │      └────────────┘  │
                      └──────────────────────┼──────────────────────┘
                                             │ SSE
                      ┌──────────────────────┴──────────────────────┐
                      │              Vue.js 3 Web UI                │
                      │  Live Dashboard · Request Inspector · Editor│
                      └─────────────────────────────────────────────┘
```

### Request Flow

1. **Client sends request** to the proxy (e.g., `POST /v1/chat/completions`)
2. **Proxy intercepts**: logs request headers + body to SQLite, assigns a unique request ID
3. **Proxy forwards** the request as-is to the configured upstream LLM API
4. **Upstream responds**:
   - **Non-streaming**: Proxy captures full response, stores it, publishes event to Redis, returns to client
   - **Streaming (SSE)**: Proxy tees the SSE stream — each chunk is forwarded to the client in real-time AND buffered/published to Redis for live UI updates. Full response is assembled and stored in SQLite on stream completion
5. **Redis pub/sub** pushes real-time events (new request, streaming chunks, completion) to connected web UI clients via SSE
6. **Web UI** displays live traffic and allows inspection/editing/replay

### Key Design Decisions

- **Pass-through proxy**: Each API protocol is forwarded natively — no format conversion between OpenAI and Anthropic formats
- **Redis pub/sub** for fan-out of real-time events to multiple browser tabs/clients
- **SQLite** for durable storage — simple, zero-config, good for single-node deployment
- **SSE (not WebSocket)** from backend to frontend — simpler, unidirectional (server→client) which is all we need for live updates
- **Tee streaming**: SSE streams are forked — one copy goes to the original client, one copy goes to Redis/storage

## Features

### Proxy Core
- [ ] Transparent LLM API proxy — clients point to this instead of the real API
- [ ] Configurable upstream server targets (multiple LLM providers)
- [ ] Pass-through authentication (forward client-provided API keys to upstream)
- [ ] Full request/response capture and storage
- [ ] Request/response header capture
- [ ] Unique request ID assignment and tracking
- [ ] Error response capture and logging
- [ ] Request timing and latency measurement
- [ ] Configurable request timeout handling

### Multi-Protocol Support
- [ ] OpenAI Chat Completions API (`POST /v1/chat/completions`)
  - Bearer token auth forwarding
  - `messages[]` format with roles (system, user, assistant, tool)
  - Tool/function calling pass-through
  - Response format: `choices[].message`
- [ ] OpenAI Responses API (`POST /v1/responses`)
  - Bearer token auth forwarding
  - `input` + `instructions` format
  - Built-in tool support (web_search, file_search, code_interpreter, functions)
  - Response format: `output[]` items
  - Semantic streaming events (`response.created`, `response.output.text.delta`, etc.)
- [ ] Anthropic Messages API (`POST /v1/messages`)
  - `x-api-key` header auth forwarding
  - `messages[]` + separate `system` prompt
  - `max_tokens` required field handling
  - Content blocks response format (`content[].type`)
  - Thinking blocks support
  - Named streaming events (`message_start`, `content_block_delta`, etc.)
- [ ] Model listing endpoints
  - `GET /v1/models` (OpenAI)
  - `GET /v1/models` (Anthropic — if available)

### Streaming (SSE)
- [ ] Transparent SSE stream forwarding to clients
- [ ] Real-time stream tee — fork to client + Redis simultaneously
- [ ] Per-protocol SSE event parsing and reassembly
  - OpenAI Chat: `data: {json}\n\n` chunks, `data: [DONE]` terminator
  - OpenAI Responses: `event: {type}\ndata: {json}\n\n` semantic events
  - Anthropic: `event: {type}\ndata: {json}\n\n` named events with `ping` keep-alive
- [ ] Full response reconstruction from stream chunks for storage
- [ ] Stream interruption / error handling
- [ ] Backpressure handling for slow clients

### Live Dashboard (Web UI)
- [ ] Real-time request/response feed via SSE from backend
- [ ] Live streaming response display — see tokens arrive as they stream
- [ ] Request list with status indicators (pending, streaming, complete, error)
- [ ] Auto-scroll with pause-on-hover
- [ ] Request filtering by:
  - API protocol type (OpenAI Chat / OpenAI Responses / Anthropic)
  - Model name
  - Status (success, error, streaming)
  - Time range
  - Text search in request/response content
- [ ] Request detail view:
  - Full request headers and body (syntax highlighted JSON)
  - Full response headers and body
  - Timing breakdown (latency, time-to-first-token, total stream duration)
  - Token usage display (prompt tokens, completion tokens, total)
- [ ] Collapsible message thread view for conversation requests

### Prompt Engineering Interface
- [ ] Server/provider selection (dropdown of configured upstream targets)
- [ ] Model selection with live model list query from upstream
- [ ] Compose new LLM request from scratch
  - Protocol-aware form (adapts fields to selected API type)
  - System prompt editor
  - Message/conversation builder with role selection
  - Parameter controls (temperature, max_tokens, top_p, stop sequences, etc.)
  - Tool/function definition editor (JSON)
- [ ] Clone and edit from captured request
  - Select any previously captured request as starting point
  - Modify any field (messages, parameters, model, system prompt)
  - Side-by-side diff view: original vs. edited request
- [ ] Send edited request through the proxy
- [ ] Response comparison
  - View original and new response side-by-side
  - Visual diff highlighting for text content differences
- [ ] Conversation forking — branch from any point in a multi-turn conversation
- [ ] Request templates — save commonly used request configurations

### Configuration & Management
- [ ] Server configuration UI
  - Add/edit/remove upstream LLM server targets
  - Per-server: base URL, default API key (optional), protocol type, display name
- [ ] Settings persisted to SQLite
- [ ] Environment variable overrides for server config
- [ ] CORS configuration for web UI
- [ ] Proxy port configuration

### Data Management
- [ ] Request/response history browser with pagination
- [ ] Bulk delete old requests
- [ ] Export requests as cURL commands
- [ ] Export request/response as JSON
- [ ] Import request JSON for replay
- [ ] Storage size indicator

## Tech Stack

### Backend
| Technology | Purpose |
|---|---|
| **Python 3.12+** | Runtime |
| **FastAPI** | HTTP framework — proxy endpoints + management API |
| **uvicorn** | ASGI server |
| **httpx** | Async HTTP client for upstream LLM requests (streaming support) |
| **sse-starlette** | SSE response support for pushing events to web UI |
| **Redis** | Pub/sub for real-time event fan-out to web UI clients |
| **SQLite** (via **aiosqlite**) | Persistent storage for request/response history and configuration |
| **Pydantic** | Request/response validation and serialization |
| **python-ulid** | Sortable unique IDs for requests |

### Frontend
| Technology | Purpose |
|---|---|
| **Vue.js 3** | UI framework (Composition API + `<script setup>`) |
| **Vite** | Build tool and dev server |
| **Tailwind CSS v4** | Utility-first styling |
| **shadcn-vue** | UI component library |
| **Vue Router** | Client-side routing |
| **Pinia** | State management |
| **EventSource / fetch** | SSE client for live updates from backend |
| **CodeMirror 6** or **Monaco** | JSON/text editor for request editing |

### Dev & Tooling
| Technology | Purpose |
|---|---|
| **uv** | Python package manager and virtual environment |
| **Ruff** | Python linter and formatter |
| **ty** | Python type checker (from the Ruff/Astral toolchain) |
| **pytest** | Python test framework |
| **ESLint + Prettier** | Frontend linting and formatting |
| **Docker** | Production container image |
| **Docker Compose** | Local dev environment (Redis + app) |
| **Make** | Task runner — setup, dev, check, build shortcuts |
| **GitHub Actions** | CI (lint/type-check/test) + CD (Docker image build/push) |

## Project Structure

```
prompt-engineering-proxy/
├── README.md
├── CLAUDE.md
├── LICENSE
├── Makefile                        # Task runner (setup, dev, check, build)
├── Dockerfile                      # Multi-stage production image
├── docker-compose.yml              # Local dev (Redis + app)
├── pyproject.toml                  # Python project config (uv)
├── .env.example                    # Environment variable template
│
├── .github/
│   └── workflows/
│       ├── ci.yml                  # Lint, type-check, test on every PR/push
│       └── release.yml             # Build + push Docker image on main/tags
│
├── src/
│   └── prompt_engineering_proxy/    # Python package (backend)
│       ├── __init__.py
│       ├── main.py                  # FastAPI app factory, lifespan, CORS
│       ├── config.py                # Settings via pydantic-settings
│       │
│       ├── proxy/
│       │   ├── __init__.py
│       │   ├── router.py            # Proxy route registration (catch-all for /v1/*)
│       │   ├── handler.py           # Core proxy logic: intercept, forward, tee
│       │   ├── streaming.py         # SSE stream tee: fork to client + Redis
│       │   └── protocols/
│       │       ├── __init__.py
│       │       ├── base.py          # Base protocol handler interface
│       │       ├── openai_chat.py   # OpenAI Chat Completions specifics
│       │       ├── openai_responses.py # OpenAI Responses API specifics
│       │       └── anthropic.py     # Anthropic Messages API specifics
│       │
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── database.py          # SQLite connection, migrations, helpers
│       │   ├── models.py            # Pydantic models for DB records
│       │   └── repository.py        # CRUD operations for requests/responses
│       │
│       ├── realtime/
│       │   ├── __init__.py
│       │   ├── publisher.py         # Redis publish events
│       │   ├── subscriber.py        # Redis subscribe + SSE push to frontend
│       │   └── events.py            # Event type definitions
│       │
│       └── api/
│           ├── __init__.py
│           ├── router.py            # Management API route aggregation
│           ├── requests.py          # GET/DELETE captured requests
│           ├── servers.py           # CRUD upstream server configuration
│           ├── models.py            # GET available models from upstream
│           └── replay.py            # POST replay/send edited requests
│
├── tests/                           # pytest tests
│   ├── conftest.py
│   ├── test_proxy.py
│   ├── test_streaming.py
│   ├── test_storage.py
│   └── test_api.py
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── index.html
│   │
│   └── src/
│       ├── main.ts
│       ├── App.vue
│       ├── router/
│       │   └── index.ts
│       ├── stores/
│       │   ├── requests.ts          # Request list + live updates
│       │   └── servers.ts           # Server configuration
│       ├── composables/
│       │   ├── useSSE.ts            # SSE connection to backend
│       │   └── useRequestDetail.ts
│       ├── lib/
│       │   ├── api.ts               # HTTP client for management API
│       │   └── utils.ts
│       ├── components/
│       │   ├── layout/
│       │   │   ├── AppHeader.vue
│       │   │   ├── AppSidebar.vue
│       │   │   └── AppLayout.vue
│       │   ├── requests/
│       │   │   ├── RequestList.vue
│       │   │   ├── RequestListItem.vue
│       │   │   ├── RequestDetail.vue
│       │   │   ├── RequestHeaders.vue
│       │   │   ├── RequestBody.vue
│       │   │   ├── ResponseBody.vue
│       │   │   ├── StreamingView.vue
│       │   │   └── RequestFilters.vue
│       │   ├── editor/
│       │   │   ├── PromptEditor.vue
│       │   │   ├── MessageBuilder.vue
│       │   │   ├── ParameterControls.vue
│       │   │   ├── ServerSelector.vue
│       │   │   ├── ModelSelector.vue
│       │   │   └── JsonEditor.vue
│       │   └── common/
│       │       ├── JsonViewer.vue
│       │       ├── DiffViewer.vue
│       │       ├── StatusBadge.vue
│       │       └── TimingDisplay.vue
│       └── pages/
│           ├── DashboardPage.vue     # Live request feed
│           ├── RequestDetailPage.vue # Single request inspection
│           ├── EditorPage.vue        # Prompt engineering / compose
│           └── SettingsPage.vue      # Server configuration
```

## Database Schema

### `servers` — Upstream LLM server configuration
| Column | Type | Description |
|---|---|---|
| `id` | TEXT PK | ULID |
| `name` | TEXT | Display name |
| `base_url` | TEXT | Upstream base URL (e.g., `https://api.openai.com`) |
| `protocol` | TEXT | `openai_chat`, `openai_responses`, `anthropic` |
| `api_key` | TEXT NULL | Default API key (optional, client key takes precedence) |
| `is_default` | BOOLEAN | Default server for new requests |
| `created_at` | TEXT | ISO 8601 timestamp |

### `proxy_requests` — Captured request/response pairs
| Column | Type | Description |
|---|---|---|
| `id` | TEXT PK | ULID (sortable by time) |
| `server_id` | TEXT FK | References `servers.id` |
| `protocol` | TEXT | Protocol type used |
| `method` | TEXT | HTTP method |
| `path` | TEXT | Request path (e.g., `/v1/chat/completions`) |
| `request_headers` | TEXT | JSON — request headers (API keys redacted) |
| `request_body` | TEXT | JSON — full request body |
| `response_status` | INTEGER | HTTP status code |
| `response_headers` | TEXT | JSON — response headers |
| `response_body` | TEXT | JSON — full response body (assembled from stream if SSE) |
| `is_streaming` | BOOLEAN | Whether SSE streaming was used |
| `model` | TEXT | Model name extracted from request |
| `duration_ms` | INTEGER | Total request duration |
| `ttfb_ms` | INTEGER NULL | Time to first byte/token (streaming) |
| `prompt_tokens` | INTEGER NULL | Token usage from response |
| `completion_tokens` | INTEGER NULL | Token usage from response |
| `error` | TEXT NULL | Error message if request failed |
| `parent_id` | TEXT NULL FK | References `proxy_requests.id` — links replayed/forked requests to original |
| `created_at` | TEXT | ISO 8601 timestamp |

### `request_tags` — Optional tags/labels for organizing requests
| Column | Type | Description |
|---|---|---|
| `request_id` | TEXT FK | References `proxy_requests.id` |
| `tag` | TEXT | Tag string |
| PRIMARY KEY | | (`request_id`, `tag`) |

## API Endpoints

### Proxy Endpoints (transparent pass-through)
| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/chat/completions` | Proxy → OpenAI Chat Completions upstream |
| `POST` | `/v1/responses` | Proxy → OpenAI Responses upstream |
| `POST` | `/v1/messages` | Proxy → Anthropic Messages upstream |
| `GET` | `/v1/models` | Proxy → upstream model listing |

### Management API (`/api/`)
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/requests` | List captured requests (paginated, filterable) |
| `GET` | `/api/requests/:id` | Get single request detail |
| `DELETE` | `/api/requests/:id` | Delete a captured request |
| `DELETE` | `/api/requests` | Bulk delete (with filters) |
| `GET` | `/api/requests/:id/export` | Export as JSON or cURL |
| `POST` | `/api/requests/:id/replay` | Replay request (optionally with edits) |
| `POST` | `/api/send` | Send a new request (from editor) |
| `GET` | `/api/servers` | List configured servers |
| `POST` | `/api/servers` | Add a server |
| `PUT` | `/api/servers/:id` | Update a server |
| `DELETE` | `/api/servers/:id` | Delete a server |
| `GET` | `/api/servers/:id/models` | Query models from upstream server |
| `GET` | `/api/events` | SSE stream — real-time events for web UI |

### Redis Pub/Sub Channels
| Channel | Events |
|---|---|
| `proxy:requests` | `request.started`, `request.completed`, `request.error` |
| `proxy:stream:{request_id}` | `chunk` — individual SSE chunks for live streaming view |

## Development Phases

### Phase 1 — Foundation
- Project scaffolding (pyproject.toml, Vite, Docker Compose)
- FastAPI app with health check
- SQLite database initialization and migrations
- Redis connection
- Basic Vue.js app with router and layout

### Phase 2 — Proxy Core
- Implement transparent proxy for OpenAI Chat Completions (non-streaming)
- Request/response capture and SQLite storage
- Add streaming (SSE) proxy with tee to Redis
- Extend to OpenAI Responses protocol
- Extend to Anthropic Messages protocol

### Phase 3 — Live Dashboard
- SSE endpoint for frontend real-time events
- Request list page with live updates
- Request detail page (headers, body, timing)
- Live streaming response view
- Filtering and search

### Phase 4 — Prompt Engineering
- Server configuration CRUD (UI + API)
- Model listing from upstream
- Request editor — compose from scratch
- Clone from captured request and edit
- Send edited request and view response
- Side-by-side response comparison / diff

### Phase 5 — Polish
- Export (JSON, cURL)
- Conversation threading / fork view
- Request tagging
- Bulk operations
- Error handling edge cases
- Responsive UI refinements

## Getting Started

### Prerequisites
- Python 3.12+
- Node.js 20+
- Redis 7+
- uv (Python package manager)

### Quick Start (with Make)
```bash
git clone https://github.com/fredericmorin/prompt-engineering-proxy.git
cd prompt-engineering-proxy

make setup    # Install all dependencies (backend + frontend)
make dev      # Start Redis, backend (auto-reload), and frontend dev server
```

### Manual Setup
```bash
# Start Redis
docker compose up -d

# Backend
uv sync
uv run uvicorn prompt_engineering_proxy.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

### Make Targets
```bash
make setup      # Install backend + frontend dependencies
make dev        # Start all services for local development
make check      # Run all checks: lint, type-check, test (backend + frontend)
make lint       # Ruff lint + ESLint
make typecheck  # ty (Python) type checking
make test       # pytest + frontend tests
make format     # Auto-format all code (Ruff + Prettier)
make build      # Build frontend + Docker image
make docker     # Build production Docker image
make clean      # Remove build artifacts, caches, .venv
```

### Docker (Production)
```bash
# Build
docker build -t prompt-engineering-proxy .

# Run (with external Redis)
docker run -p 8000:8000 -e REDIS_URL=redis://host:6379 prompt-engineering-proxy

# Or use docker compose for everything
docker compose --profile prod up
```

### Configuration
```bash
# .env
PROXY_PORT=8000
REDIS_URL=redis://localhost:6379
DATABASE_PATH=data/proxy.db
```

### Usage
Point your LLM client at the proxy:
```python
import openai

client = openai.OpenAI(
    base_url="http://localhost:8000/v1",  # proxy instead of api.openai.com
    api_key="sk-..."                       # your real API key, forwarded upstream
)
```

Then open `http://localhost:5173` to see live traffic and use the prompt engineering tools.

## CI/CD

### GitHub Actions — CI (`ci.yml`)
Runs on every push and pull request:
1. **Backend checks**: Ruff lint, Ruff format check, ty type-check, pytest
2. **Frontend checks**: ESLint, Prettier format check, TypeScript type-check, build
3. **Matrix**: Python 3.12+ × Node 20+
4. **Services**: Redis (via `services` container) for integration tests

### GitHub Actions — Release (`release.yml`)
Runs on every push to `main`/`master` and on version tags (`v*`):
1. Build multi-stage Docker image
2. Push to GitHub Container Registry (`ghcr.io`)
3. Tag as `latest` on main, version tag on releases (e.g., `v1.0.0`)

## Docker

The production Docker image uses a multi-stage build:
1. **Stage 1 — Frontend build**: Node.js, `npm ci`, `npm run build` → static assets
2. **Stage 2 — Backend**: Python 3.12-slim, `uv sync --frozen`, copy built frontend into static serving directory
3. **Runtime**: uvicorn serves both the API and static frontend assets

The image is self-contained — only requires an external Redis instance.

## License

GPLv3 — see [LICENSE](LICENSE).
