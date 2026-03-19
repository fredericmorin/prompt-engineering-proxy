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


@pytest.mark.asyncio
async def test_schema_version_table_exists(database: Database):
    """After init_db, a schema_version table should exist with the current version."""
    row = await database.fetchone("SELECT version FROM schema_version")
    assert row is not None
    assert isinstance(row["version"], int)
    assert row["version"] >= 1


@pytest.mark.asyncio
async def test_migrations_idempotent(database: Database):
    """Running init_db twice should not fail or change the version."""
    row_before = await database.fetchone("SELECT version FROM schema_version")
    await database.init_db()  # second init
    row_after = await database.fetchone("SELECT version FROM schema_version")
    assert row_before == row_after


@pytest.mark.asyncio
async def test_migrate_from_pre_version_database(tmp_db_path: str):
    """A database created without schema_version should be migrated correctly."""
    db = Database()
    await db.connect(tmp_db_path)
    # Simulate a pre-versioning database: create tables without schema_version
    assert db._conn is not None
    await db._conn.executescript("""
        CREATE TABLE IF NOT EXISTS servers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            base_url TEXT NOT NULL,
            protocol TEXT NOT NULL,
            api_key TEXT,
            is_default BOOLEAN NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS proxy_requests (
            id TEXT PRIMARY KEY,
            server_id TEXT REFERENCES servers(id),
            protocol TEXT NOT NULL,
            method TEXT NOT NULL,
            path TEXT NOT NULL,
            request_headers TEXT NOT NULL,
            request_body TEXT NOT NULL,
            response_status INTEGER,
            response_headers TEXT,
            response_body TEXT,
            is_streaming BOOLEAN NOT NULL DEFAULT 0,
            model TEXT,
            duration_ms INTEGER,
            ttfb_ms INTEGER,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            error TEXT,
            parent_id TEXT REFERENCES proxy_requests(id),
            created_at TEXT NOT NULL
        );
    """)
    await db._conn.commit()

    # Now run init_db which should detect missing columns and add them
    await db.init_db()

    # Verify version was set
    row = await db.fetchone("SELECT version FROM schema_version")
    assert row is not None
    assert row["version"] == Database.SCHEMA_VERSION

    # Verify columns were added
    cols = {r["name"] for r in await db.fetchall("PRAGMA table_info(servers)")}
    assert "proxy_slug" in cols

    cols = {r["name"] for r in await db.fetchall("PRAGMA table_info(proxy_requests)")}
    assert "client_ip" in cols

    await db.close()
