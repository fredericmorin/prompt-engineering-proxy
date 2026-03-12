"""Aggregate management API router under /api prefix."""

from fastapi import APIRouter

from prompt_engineering_proxy.api import events, requests

router = APIRouter(prefix="/api")
router.include_router(requests.router)
router.include_router(events.router)
