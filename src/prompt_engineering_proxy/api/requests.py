"""Management API — request CRUD endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from prompt_engineering_proxy.storage.database import Database
from prompt_engineering_proxy.storage.repository import RequestRepository

router = APIRouter()


def _get_repo(request: Request) -> RequestRepository:
    db: Database = request.app.state.db
    return RequestRepository(db)


@router.get("/requests")
async def list_requests(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    protocol: str | None = None,
    model: str | None = None,
) -> JSONResponse:
    """Return a lightweight list of captured requests (body fields excluded)."""
    repo = _get_repo(request)
    rows: list[dict[str, Any]] = await repo.list_filtered(
        limit=limit,
        offset=offset,
        protocol=protocol or None,
        model=model or None,
    )
    return JSONResponse(content=rows)


@router.get("/requests/{request_id}")
async def get_request(request: Request, request_id: str) -> JSONResponse:
    """Return the full record including request/response headers and bodies."""
    repo = _get_repo(request)
    row = await repo.get(request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return JSONResponse(content=dict(row))


@router.delete("/requests/{request_id}", status_code=204)
async def delete_request(request: Request, request_id: str) -> Response:
    repo = _get_repo(request)
    row = await repo.get(request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Request not found")
    await repo.delete(request_id)
    return Response(status_code=204)
