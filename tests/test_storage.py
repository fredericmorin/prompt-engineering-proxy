import pytest

from prompt_engineering_proxy.storage.database import Database
from prompt_engineering_proxy.storage.models import ProxyRequest, Server, new_ulid, now_iso
from prompt_engineering_proxy.storage.services import RequestService, ServerService


@pytest.mark.asyncio
async def test_database_creates_tables(database: Database) -> None:
    tables = await database.fetchall("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    table_names = [t["name"] for t in tables]
    assert "servers" in table_names
    assert "proxy_requests" in table_names
    assert "request_tags" in table_names


@pytest.mark.asyncio
async def test_database_wal_mode(database: Database) -> None:
    result = await database.fetchone("PRAGMA journal_mode")
    assert result is not None
    assert result["journal_mode"] == "wal"


@pytest.mark.asyncio
async def test_database_ping(database: Database) -> None:
    assert await database.ping() is True


@pytest.mark.asyncio
async def test_database_ping_when_closed(tmp_db_path: str) -> None:
    db = Database()
    assert await db.ping() is False


@pytest.mark.asyncio
async def test_server_repository_crud(database: Database) -> None:
    repo = ServerService(database)
    server = Server(name="Test Server", base_url="https://api.openai.com", protocol="openai_chat")

    created = await repo.create(server)
    assert created.id == server.id

    fetched = await repo.get(server.id)
    assert fetched is not None
    assert fetched.name == "Test Server"

    all_servers = await repo.list_all()
    assert len(all_servers) == 1

    await repo.delete(server.id)
    assert await repo.get(server.id) is None


@pytest.mark.asyncio
async def test_request_repository_crud(database: Database) -> None:
    repo = RequestService(database)
    req = ProxyRequest(
        protocol="openai_chat",
        method="POST",
        path="/v1/chat/completions",
        request_headers="{}",
        request_body='{"model": "gpt-4"}',
        model="gpt-4",
    )

    created = await repo.create(req)
    assert created.id == req.id

    fetched = await repo.get(req.id)
    assert fetched is not None
    assert fetched.model == "gpt-4"

    recent = await repo.list_recent(limit=10)
    assert len(recent) == 1

    await repo.delete(req.id)
    assert await repo.get(req.id) is None


@pytest.mark.asyncio
async def test_ulid_generation() -> None:
    id1 = new_ulid()
    id2 = new_ulid()
    assert id1 != id2
    assert len(id1) == 26  # ULID standard length


@pytest.mark.asyncio
async def test_now_iso_format() -> None:
    ts = now_iso()
    assert "T" in ts
    assert "+" in ts or "Z" in ts or ts.endswith("+00:00")
