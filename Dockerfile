# Stage 1: Build frontend
FROM node:24-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Build the Python virtual environment
FROM python:3.14-slim AS python-builder
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock README.md ./
COPY src/ src/
RUN uv sync --no-dev --compile-bytecode

# Stage 3: Minimal runtime image
FROM python:3.14-slim
# Install curl for HEALTHCHECK
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python environment (includes installed sharetree package)
COPY --from=python-builder /app/.venv /app/.venv
# Source tree (needed for editable install path references and alembic.ini resolution)
COPY --from=python-builder /app/src /app/src
# Built frontend assets
COPY --from=frontend-builder /app/static/ static/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PREN_PROXY_DATA_PATH=/data \
    PREN_PROXY_SHARE_ROOT=/files

VOLUME ["/data", "/files"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "prompt_engineering_proxy.main:app", "--host", "0.0.0.0", "--port", "8000"]
