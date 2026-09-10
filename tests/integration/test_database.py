import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_select_one() -> None:
    settings = Settings()
    assert settings.app_env == "local", "Integration tests target a local development database"
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect() as connection:
            assert await connection.scalar(text("SELECT 1")) == 1
    finally:
        await engine.dispose()
