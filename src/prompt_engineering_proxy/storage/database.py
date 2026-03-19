import logging
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS servers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    protocol TEXT NOT NULL,
    api_key TEXT,
    proxy_slug TEXT,
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
    client_ip TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS request_tags (
    request_id TEXT NOT NULL REFERENCES proxy_requests(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    PRIMARY KEY (request_id, tag)
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);
"""


class Database:
    SCHEMA_VERSION = 2  # Bump this when adding new migrations

    def __init__(self) -> None:
        self._conn: aiosqlite.Connection | None = None

    async def connect(self, path: str) -> None:
        db_path = Path(path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = await aiosqlite.connect(str(db_path))
        self._conn.row_factory = aiosqlite.Row

        # Enable WAL mode for concurrent reads during writes
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")

        logger.info("Connected to SQLite database at %s", path)

    async def init_db(self) -> None:
        if not self._conn:
            raise RuntimeError("Database not connected")
        await self._conn.executescript(SCHEMA_SQL)
        await self._migrate(self._conn)
        await self._conn.commit()
        logger.info("Database schema initialized")

    @staticmethod
    async def _migrate(conn: aiosqlite.Connection) -> None:
        """Apply incremental schema migrations using a version counter."""
        # Ensure the schema_version table exists (handles pre-versioning databases)
        await conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")

        row = await (await conn.execute("SELECT version FROM schema_version")).fetchone()
        if row is None:
            # First run — insert starting version 0 so migrations run from the beginning
            await conn.execute("INSERT INTO schema_version (version) VALUES (0)")
            current = 0
        else:
            current = row[0]

        # Migration 1: add proxy_slug column to servers
        if current < 1:
            cols = {r[1] for r in await (await conn.execute("PRAGMA table_info(servers)")).fetchall()}
            if "proxy_slug" not in cols:
                await conn.execute("ALTER TABLE servers ADD COLUMN proxy_slug TEXT")
                logger.info("Migration 1: added proxy_slug column to servers")

        # Migration 2: add client_ip column to proxy_requests
        if current < 2:
            cols = {r[1] for r in await (await conn.execute("PRAGMA table_info(proxy_requests)")).fetchall()}
            if "client_ip" not in cols:
                await conn.execute("ALTER TABLE proxy_requests ADD COLUMN client_ip TEXT")
                logger.info("Migration 2: added client_ip column to proxy_requests")

        # Update stored version
        if current < Database.SCHEMA_VERSION:
            await conn.execute("UPDATE schema_version SET version = ?", (Database.SCHEMA_VERSION,))
            logger.info("Schema version updated: %d → %d", current, Database.SCHEMA_VERSION)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("Database connection closed")

    async def execute(self, sql: str, params: tuple[Any, ...] = ()) -> aiosqlite.Cursor:
        if not self._conn:
            raise RuntimeError("Database not connected")
        return await self._conn.execute(sql, params)

    async def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        cursor = await self.execute(sql, params)
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        cursor = await self.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def commit(self) -> None:
        if self._conn:
            await self._conn.commit()

    async def ping(self) -> bool:
        try:
            if not self._conn:
                return False
            await self._conn.execute("SELECT 1")
            return True
        except Exception:
            return False
