import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings


@pytest.mark.integration
def test_upgrade_head_and_vector() -> None:
    settings = Settings()
    assert settings.app_env == "local", "Migration tests upgrade the local development database"
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    command.upgrade(config, "head")
    head = ScriptDirectory.from_config(config).get_current_head()

    async def verify() -> None:
        engine = create_async_engine(settings.database_url)
        try:
            async with engine.connect() as connection:
                assert await connection.scalar(text("SELECT version_num FROM alembic_version")) == head
                assert await connection.scalar(
                    text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
                ) == "vector"
        finally:
            await engine.dispose()

    asyncio.run(verify())
