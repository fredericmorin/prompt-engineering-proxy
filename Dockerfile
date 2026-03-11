# Stage 1: Build frontend
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Backend + serve built frontend
FROM python:3.12-slim AS runtime

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

# Copy backend source
COPY src/ ./src/

# Copy built frontend assets
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Create data directory for SQLite
RUN mkdir -p /app/data

ENV PROXY_HOST=0.0.0.0
ENV PROXY_PORT=8000
ENV DATABASE_PATH=/app/data/proxy.db

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "prompt_engineering_proxy.main:app", "--host", "0.0.0.0", "--port", "8000"]
