"""Aggregate management API router under /api prefix."""

from fastapi import APIRouter

from prompt_engineering_proxy.api import events, models, requests, send, servers

router = APIRouter(prefix="/api")
router.include_router(requests.router)
router.include_router(events.router)
router.include_router(servers.router)
router.include_router(models.router)
router.include_router(send.router)
