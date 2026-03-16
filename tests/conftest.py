import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from prompt_engineering_proxy.app import create_app
from prompt_engineering_proxy.realtime.publisher import RedisPublisher
from prompt_engineering_proxy.storage.database import Database

import os


# Provide required settings so test modules can be imported without a .env file.
os.environ.setdefault("PREN_PROXY_REDIS_URL", "redis://localhost:6379")


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> str:
    return str(tmp_path / "test.db")


@pytest_asyncio.fixture
async def database(tmp_db_path: str) -> AsyncGenerator[Database]:
    db = Database()
    await db.connect(tmp_db_path)
    await db.init_db()
    yield db
    await db.close()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    with tempfile.TemporaryDirectory() as tmpdir:
        import prompt_engineering_proxy.settings as config_module

        original_path = config_module.settings.DATA_PATH
        config_module.settings.DATA_PATH = Path(tmpdir)

        app = create_app()

        # Manually initialize app state since ASGITransport doesn't run lifespan
        db = Database()
        await db.connect(str(config_module.settings.DATA_PATH / "test.db"))
        await db.init_db()
        app.state.db = db
        app.state.redis = RedisPublisher()  # Not connected — health will report redis=False

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

        await db.close()
        config_module.settings.DATA_PATH = original_path
