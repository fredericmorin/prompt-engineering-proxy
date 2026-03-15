import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from prompt_engineering_proxy.api.router import router as api_router
from prompt_engineering_proxy.config import settings
from prompt_engineering_proxy.dev_proxy import create_dev_proxy_router
from prompt_engineering_proxy.proxy.router import router as proxy_router
from prompt_engineering_proxy.realtime.publisher import RedisPublisher
from prompt_engineering_proxy.storage.database import Database

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Startup
    logging.basicConfig(level=settings.log_level.upper())
    logger.info("Starting Prompt Engineering Proxy")

    # Initialize database
    db = Database()
    await db.connect(settings.database_path)
    await db.init_db()
    app.state.db = db

    # Connect to Redis
    publisher = RedisPublisher()
    try:
        await publisher.connect(settings.redis_url)
        app.state.redis = publisher
        logger.info("Connected to Redis at %s", settings.redis_url)
    except Exception:
        logger.warning("Redis not available at %s — real-time features disabled", settings.redis_url)
        app.state.redis = publisher  # Store even if not connected; health check reports status

    # Shared async HTTP client for upstream requests (connection pooling)
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0),
        follow_redirects=True,
    )
    app.state.http_client = http_client

    yield

    # Shutdown
    await http_client.aclose()
    await publisher.close()
    await db.close()
    logger.info("Prompt Engineering Proxy stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="Prompt Engineering Proxy", version="0.1.0", lifespan=lifespan)

    # CORS
    app.add_middleware(
        CORSMiddleware,  # type: ignore[arg-type]
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Proxy routes (/v1/*)
    app.include_router(proxy_router)

    # Management API (/api/*)
    app.include_router(api_router)

    @app.get("/health")
    async def health() -> JSONResponse:
        db: Database = app.state.db
        publisher: RedisPublisher = app.state.redis

        db_ok = await db.ping()
        redis_ok = await publisher.ping()

        status = "ok" if db_ok else "degraded"
        status_code = 200 if db_ok else 503

        return JSONResponse(
            content={"status": status, "database": db_ok, "redis": redis_ok},
            status_code=status_code,
        )

    # In dev mode, reverse-proxy frontend requests to the Vite dev server.
    # In production, serve built frontend static files from disk.
    if settings.frontend_url:
        logger.info("Dev proxy enabled → forwarding frontend requests to %s", settings.frontend_url)
        app.include_router(create_dev_proxy_router(settings.frontend_url))
    elif STATIC_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="static-assets")

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str) -> FileResponse:
            """Serve index.html for SPA client-side routing."""
            file_path = STATIC_DIR / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(STATIC_DIR / "index.html")

    return app
