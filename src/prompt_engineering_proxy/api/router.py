"""Aggregate management API router under /api prefix."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from prompt_engineering_proxy.api import events, models, requests, send, servers
from prompt_engineering_proxy.realtime.publisher import RedisPublisher
from prompt_engineering_proxy.storage.database import Database

router = APIRouter(prefix="/api")
router.include_router(requests.router)
router.include_router(events.router)
router.include_router(servers.router)
router.include_router(models.router)
router.include_router(send.router)


@router.get("/health")
async def health(request: Request) -> JSONResponse:
    db: Database = request.app.state.db
    publisher: RedisPublisher = request.app.state.redis

    db_ok = await db.ping()
    redis_ok = await publisher.ping()

    status = "ok" if db_ok else "degraded"
    status_code = 200 if db_ok else 503

    return JSONResponse(
        content={"status": status, "database": db_ok, "redis": redis_ok},
        status_code=status_code,
    )


@router.get("")
@router.get("/{full_path:path}")
async def api_fallback(full_path: str = "") -> JSONResponse:
    return JSONResponse(
        content={"status": "api endpoint not found"},
        status_code=404,
    )
