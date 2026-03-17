"""Tests for the transparent proxy: non-streaming and streaming chat completions."""

import json
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from prompt_engineering_proxy.app import create_app
from prompt_engineering_proxy.proxy.protocols.openai_chat import OpenAIChatHandler
from prompt_engineering_proxy.realtime.publisher import RedisPublisher
from prompt_engineering_proxy.storage.database import Database
from prompt_engineering_proxy.storage.models import Server
from prompt_engineering_proxy.storage.services import RequestService, ServerService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app_client(tmp_path: Any) -> AsyncGenerator[tuple[AsyncClient, Database, FastAPI]]:
    """AsyncClient wired to a test app with an in-memory DB and a mock http client."""
    import prompt_engineering_proxy.settings as config_module

    original_path = config_module.settings.DATA_PATH
    config_module.settings.DATA_PATH = tmp_path

    app = create_app()

    db = Database()
    await db.connect(str(tmp_path / "test.db"))
    await db.init_db()
    app.state.db = db
    app.state.redis = RedisPublisher()  # not connected — OK for tests

    # Use a mock http_client so tests can control upstream responses
    mock_http = MagicMock(spec=httpx.AsyncClient)
    mock_http.request = AsyncMock()
    mock_http.send = AsyncMock()
    mock_http.build_request = MagicMock()
    app.state.http_client = mock_http

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, db, app

    await db.close()
    config_module.settings.DATA_PATH = original_path


async def _add_test_server(db: Database) -> Server:
    repo = ServerService(db)
    server = Server(
        name="test-openai",
        base_url="https://api.openai.com",
        protocol="openai_chat",
        is_default=True,
    )
    await repo.create(server)
    return server


# ---------------------------------------------------------------------------
# Protocol handler unit tests
# ---------------------------------------------------------------------------


def test_openai_chat_extract_model() -> None:
    handler = OpenAIChatHandler()
    assert handler.extract_model({"model": "gpt-4o"}) == "gpt-4o"
    assert handler.extract_model({}) is None


def test_openai_chat_extract_usage() -> None:
    handler = OpenAIChatHandler()
    body: dict[str, object] = {"usage": {"prompt_tokens": 10, "completion_tokens": 20}}
    assert handler.extract_usage(body) == (10, 20)
    assert handler.extract_usage({}) == (None, None)


def test_openai_chat_assemble_streaming_response() -> None:
    handler = OpenAIChatHandler()
    chunks: list[dict[str, object]] = [
        {"id": "c1", "model": "gpt-4o", "choices": [{"delta": {"role": "assistant"}, "finish_reason": None}]},
        {"id": "c1", "model": "gpt-4o", "choices": [{"delta": {"content": "Hello"}, "finish_reason": None}]},
        {"id": "c1", "model": "gpt-4o", "choices": [{"delta": {"content": " world"}, "finish_reason": "stop"}]},
    ]
    result = handler.assemble_streaming_response(chunks)
    assert result["id"] == "c1"
    choices = result["choices"]
    assert isinstance(choices, list)
    assert choices[0]["message"]["content"] == "Hello world"  # type: ignore[index]
    assert choices[0]["finish_reason"] == "stop"  # type: ignore[index]


def test_openai_chat_assemble_empty() -> None:
    handler = OpenAIChatHandler()
    assert handler.assemble_streaming_response([]) == {}


# ---------------------------------------------------------------------------
# Non-streaming proxy tests
# ---------------------------------------------------------------------------


FAKE_CHAT_RESPONSE = {
    "id": "chatcmpl-test",
    "object": "chat.completion",
    "model": "gpt-4o",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hi!"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
}


@pytest.mark.asyncio
async def test_non_streaming_proxy_success(
    app_client: tuple[AsyncClient, Database, FastAPI],
) -> None:
    client, db, app = app_client
    await _add_test_server(db)

    app.state.http_client.request = AsyncMock(return_value=httpx.Response(200, json=FAKE_CHAT_RESPONSE))

    response = await client.post(
        "/test-openai/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
        headers={"Authorization": "Bearer sk-test1234567890abcdef"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "chatcmpl-test"


@pytest.mark.asyncio
async def test_non_streaming_proxy_stores_request(
    app_client: tuple[AsyncClient, Database, FastAPI],
) -> None:
    client, db, app = app_client
    await _add_test_server(db)

    app.state.http_client.request = AsyncMock(return_value=httpx.Response(200, json=FAKE_CHAT_RESPONSE))

    await client.post(
        "/test-openai/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello"}]},
        headers={"Authorization": "Bearer sk-test1234567890abcdef"},
    )

    repo = RequestService(db)
    requests = await repo.list_recent(limit=1)
    assert len(requests) == 1
    req = requests[0]
    assert req.protocol == "openai_chat"
    assert req.model == "gpt-4o"
    assert req.response_status == 200
    assert req.prompt_tokens == 5
    assert req.completion_tokens == 3
    assert req.is_streaming is False


@pytest.mark.asyncio
async def test_non_streaming_proxy_redacts_api_key(
    app_client: tuple[AsyncClient, Database, FastAPI],
) -> None:
    client, db, app = app_client
    await _add_test_server(db)

    app.state.http_client.request = AsyncMock(return_value=httpx.Response(200, json=FAKE_CHAT_RESPONSE))

    await client.post(
        "/test-openai/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
        headers={"Authorization": "Bearer sk-verysecretkey0000"},
    )

    repo = RequestService(db)
    requests = await repo.list_recent(limit=1)
    stored_headers = json.loads(requests[0].request_headers)
    auth = stored_headers.get("authorization", "")
    # Full key must NOT be stored
    assert "verysecretkey" not in auth
    # Format: Bearer xxxx...xxxx
    assert "Bearer" in auth
    assert "..." in auth


@pytest.mark.asyncio
async def test_non_streaming_proxy_unknown_slug_returns_404(
    app_client: tuple[AsyncClient, Database, FastAPI],
) -> None:
    client, _, _app = app_client
    # No server configured

    response = await client.post(
        "/no-such-server/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_non_streaming_proxy_upstream_error_returns_502(
    app_client: tuple[AsyncClient, Database, FastAPI],
) -> None:
    client, db, app = app_client
    await _add_test_server(db)

    fake_req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    app.state.http_client.request = AsyncMock(side_effect=httpx.ConnectError("connection refused", request=fake_req))

    response = await client.post(
        "/test-openai/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
    )

    assert response.status_code == 502

    repo = RequestService(db)
    requests = await repo.list_recent(limit=1)
    assert requests[0].error is not None


# ---------------------------------------------------------------------------
# Streaming proxy tests
# ---------------------------------------------------------------------------


STREAM_CHUNKS = [
    '{"id":"s1","model":"gpt-4o","choices":[{"delta":{"role":"assistant"},"finish_reason":null}]}',
    '{"id":"s1","model":"gpt-4o","choices":[{"delta":{"content":"Hi"},"finish_reason":null}]}',
    '{"id":"s1","model":"gpt-4o","choices":[{"delta":{"content":"!"},"finish_reason":"stop"}]}',
    "[DONE]",
]


def _make_mock_streaming_response() -> MagicMock:
    """Return a mock httpx.Response that streams SSE chunks."""
    chunks = [(f"data: {line}\n\n").encode() for line in STREAM_CHUNKS]

    async def fake_aiter_bytes() -> AsyncGenerator[bytes, None]:
        for chunk in chunks:
            yield chunk

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.headers = httpx.Headers({"content-type": "text/event-stream"})
    mock_resp.aiter_bytes = fake_aiter_bytes
    mock_resp.aclose = AsyncMock()
    return mock_resp


@pytest.mark.asyncio
async def test_streaming_proxy_returns_sse(
    app_client: tuple[AsyncClient, Database, FastAPI],
) -> None:
    client, db, app = app_client
    await _add_test_server(db)

    mock_resp = _make_mock_streaming_response()
    fake_req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    app.state.http_client.build_request = MagicMock(return_value=fake_req)
    app.state.http_client.send = AsyncMock(return_value=mock_resp)

    response = await client.post(
        "/test-openai/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}], "stream": True},
        headers={"Authorization": "Bearer sk-test1234567890abcdef"},
    )

    assert response.status_code == 200
    assert "data:" in response.text


@pytest.mark.asyncio
async def test_streaming_proxy_stores_assembled_response(
    app_client: tuple[AsyncClient, Database, FastAPI],
) -> None:
    client, db, app = app_client
    await _add_test_server(db)

    mock_resp = _make_mock_streaming_response()
    fake_req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    app.state.http_client.build_request = MagicMock(return_value=fake_req)
    app.state.http_client.send = AsyncMock(return_value=mock_resp)

    await client.post(
        "/test-openai/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}], "stream": True},
    )

    repo = RequestService(db)
    requests = await repo.list_recent(limit=1)
    assert len(requests) == 1
    req = requests[0]
    assert req.is_streaming is True
    assert req.response_status == 200

    # Assembled content should be stored
    assert req.response_body is not None
    body = json.loads(req.response_body)
    choices = body.get("choices", [])
    assert len(choices) == 1
    assert choices[0]["message"]["content"] == "Hi!"


# ---------------------------------------------------------------------------
# Prefixed proxy route tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prefixed_route_routes_to_correct_server(
    app_client: tuple[AsyncClient, Database, FastAPI],
) -> None:
    """POST /{server-slug}/v1/chat/completions routes to the server matching the slug."""
    client, db, app = app_client
    server = await _add_test_server(db)  # name="test-openai" → slug="test-openai"

    app.state.http_client.request = AsyncMock(return_value=httpx.Response(200, json=FAKE_CHAT_RESPONSE))

    response = await client.post(
        "/test-openai/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
        headers={"Authorization": "Bearer sk-test1234567890abcdef"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == "chatcmpl-test"

    # Check stored record has correct server_id and clean path
    repo = RequestService(db)
    requests = await repo.list_recent(limit=1)
    assert requests[0].server_id == server.id
    assert requests[0].path == "/v1/chat/completions"


@pytest.mark.asyncio
async def test_prefixed_route_unknown_slug_returns_404(
    app_client: tuple[AsyncClient, Database, FastAPI],
) -> None:
    client, db, _app = app_client
    await _add_test_server(db)

    response = await client.post(
        "/nonexistent-server/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_prefixed_route_unsupported_path_is_passthroughed(
    app_client: tuple[AsyncClient, Database, FastAPI],
) -> None:
    """Unknown POST paths are forwarded to upstream without recording (passthrough)."""
    client, db, app = app_client
    await _add_test_server(db)

    app.state.http_client.request = AsyncMock(return_value=httpx.Response(200, json={"ok": True}))

    response = await client.post(
        "/test-openai/v1/embeddings",
        json={"model": "text-embedding-3-small", "input": "hello"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}

    # Passthrough requests must NOT be stored in the database
    from prompt_engineering_proxy.storage.services import RequestService

    repo = RequestService(db)
    requests = await repo.list_recent(limit=10)
    assert len(requests) == 0
