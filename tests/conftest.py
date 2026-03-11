import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from prompt_engineering_proxy.app import create_app
from prompt_engineering_proxy.realtime.publisher import RedisPublisher
from prompt_engineering_proxy.storage.database import Database


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
        import prompt_engineering_proxy.config as config_module

        original_path = config_module.settings.database_path
        config_module.settings.database_path = str(Path(tmpdir) / "test.db")

        app = create_app()

        # Manually initialize app state since ASGITransport doesn't run lifespan
        db = Database()
        await db.connect(config_module.settings.database_path)
        await db.init_db()
        app.state.db = db
        app.state.redis = RedisPublisher()  # Not connected — health will report redis=False

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

        await db.close()
        config_module.settings.database_path = original_path
