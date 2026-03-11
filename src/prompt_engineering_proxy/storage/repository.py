from typing import Any

from prompt_engineering_proxy.storage.database import Database
from prompt_engineering_proxy.storage.models import ProxyRequest, Server


class ServerRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def create(self, server: Server) -> Server:
        await self.db.execute(
            """INSERT INTO servers (id, name, base_url, protocol, api_key, is_default, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                server.id,
                server.name,
                server.base_url,
                server.protocol,
                server.api_key,
                server.is_default,
                server.created_at,
            ),
        )
        await self.db.commit()
        return server

    async def get(self, server_id: str) -> dict[str, Any] | None:
        return await self.db.fetchone("SELECT * FROM servers WHERE id = ?", (server_id,))

    async def list_all(self) -> list[dict[str, Any]]:
        return await self.db.fetchall("SELECT * FROM servers ORDER BY created_at DESC")

    async def delete(self, server_id: str) -> None:
        await self.db.execute("DELETE FROM servers WHERE id = ?", (server_id,))
        await self.db.commit()


class RequestRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def create(self, request: ProxyRequest) -> ProxyRequest:
        await self.db.execute(
            """INSERT INTO proxy_requests
               (id, server_id, protocol, method, path, request_headers, request_body,
                response_status, response_headers, response_body, is_streaming, model,
                duration_ms, ttfb_ms, prompt_tokens, completion_tokens, error, parent_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                request.id,
                request.server_id,
                request.protocol,
                request.method,
                request.path,
                request.request_headers,
                request.request_body,
                request.response_status,
                request.response_headers,
                request.response_body,
                request.is_streaming,
                request.model,
                request.duration_ms,
                request.ttfb_ms,
                request.prompt_tokens,
                request.completion_tokens,
                request.error,
                request.parent_id,
                request.created_at,
            ),
        )
        await self.db.commit()
        return request

    async def get(self, request_id: str) -> dict[str, Any] | None:
        return await self.db.fetchone("SELECT * FROM proxy_requests WHERE id = ?", (request_id,))

    async def list_recent(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        return await self.db.fetchall(
            "SELECT * FROM proxy_requests ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )

    async def delete(self, request_id: str) -> None:
        await self.db.execute("DELETE FROM proxy_requests WHERE id = ?", (request_id,))
        await self.db.commit()
