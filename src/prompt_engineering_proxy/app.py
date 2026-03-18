import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from prompt_engineering_proxy.api.router import router as api_router
from prompt_engineering_proxy.settings import settings
from prompt_engineering_proxy.proxy.router import router as proxy_router
from prompt_engineering_proxy.realtime.publisher import RedisPublisher
from prompt_engineering_proxy.storage.database import Database

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Startup
    logging.basicConfig(level=settings.LOG_LEVEL.upper())
    logger.info("Starting Prompt Engineering Proxy")

    # Initialize database
    db = Database()
    await db.connect(str(settings.DATA_PATH / "proxy.db"))
    await db.init_db()
    app.state.db = db

    # Connect to Redis
    publisher = RedisPublisher()
    try:
        await publisher.connect(settings.REDIS_URL)
        app.state.redis = publisher
        logger.info("Connected to Redis at %s", settings.REDIS_URL)
    except Exception:
        logger.warning("Redis not available at %s — real-time features disabled", settings.REDIS_URL)
        app.state.redis = publisher  # Store even if not connected; health check reports status

    # Shared async HTTP client for upstream requests (connection pooling)
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0),
        follow_redirects=True,
    )
    app.state.http_client = http_client

    # Registry of active streaming cancel events keyed by request_id
    app.state.stream_cancel_events: dict[str, asyncio.Event] = {}

    # In-memory chunk buffers for streaming requests (replay missed chunks on late subscribe)
    app.state.stream_chunk_buffers: dict[str, list[str]] = {}

    logger.info("Prompt Engineering Proxy ready")

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

    # Proxy routes (/{server_slug}/*)
    app.include_router(proxy_router)

    # Management API (/api/*)
    app.include_router(api_router)

    # Serve built frontend static files if the directory exists
    if STATIC_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="static-assets")

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str) -> FileResponse:
            """Serve index.html for SPA client-side routing."""
            file_path = STATIC_DIR / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(STATIC_DIR / "index.html")

    return app
