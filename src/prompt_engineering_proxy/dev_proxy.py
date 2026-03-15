"""Reverse proxy to forward frontend requests to the Vite dev server.

In development, Python serves as the single entry point (port 8000).
API/proxy routes are handled directly; everything else is forwarded to Vite.
"""

import asyncio
import logging
from urllib.parse import urljoin, urlparse

import httpx
import websockets
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from starlette.responses import StreamingResponse

logger = logging.getLogger(__name__)


def create_dev_proxy_router(frontend_url: str) -> APIRouter:
    """Create a router that proxies unmatched requests to the Vite dev server."""
    router = APIRouter()

    parsed = urlparse(frontend_url)
    ws_url = f"ws://{parsed.hostname}:{parsed.port}"

    @router.websocket("/{path:path}")
    async def proxy_websocket(websocket: WebSocket, path: str) -> None:
        """Proxy WebSocket connections (Vite HMR) to the dev server."""
        target = f"{ws_url}/{path}"
        await websocket.accept()

        try:
            async with websockets.connect(target) as ws_client:

                async def client_to_server() -> None:
                    try:
                        async for message in websocket.iter_text():
                            await ws_client.send(message)
                    except WebSocketDisconnect:
                        await ws_client.close()

                async def server_to_client() -> None:
                    try:
                        async for message in ws_client:
                            if isinstance(message, str):
                                await websocket.send_text(message)
                            else:
                                await websocket.send_bytes(message)
                    except websockets.exceptions.ConnectionClosed:
                        pass

                await asyncio.gather(client_to_server(), server_to_client())
        except Exception:
            logger.debug("WebSocket proxy closed for /%s", path)
        finally:
            try:
                await websocket.close()
            except Exception:
                pass

    @router.api_route("/{path:path}", methods=["GET", "HEAD", "POST", "PUT", "DELETE", "PATCH"])
    async def proxy_http(request: Request, path: str) -> StreamingResponse:
        """Proxy HTTP requests to the Vite dev server."""
        target_url = urljoin(frontend_url + "/", path)

        # Forward query string
        if request.url.query:
            target_url = f"{target_url}?{request.url.query}"

        # Build headers, dropping hop-by-hop headers
        headers = dict(request.headers)
        for hop_header in ("host", "connection", "keep-alive", "transfer-encoding"):
            headers.pop(hop_header, None)

        client: httpx.AsyncClient = request.app.state.http_client
        body = await request.body()

        upstream = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body if body else None,
        )

        # Forward response, streaming the body
        response_headers = dict(upstream.headers)
        for hop_header in ("content-encoding", "content-length", "transfer-encoding", "connection"):
            response_headers.pop(hop_header, None)

        return StreamingResponse(
            content=upstream.aiter_bytes(),
            status_code=upstream.status_code,
            headers=response_headers,
        )

    return router
