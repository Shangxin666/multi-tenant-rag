import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_select_one(db_engine: AsyncEngine) -> None:
    async with db_engine.connect() as connection:
        assert await connection.scalar(text("SELECT 1")) == 1
        assert str(await connection.scalar(text("SHOW server_version"))).startswith("17.")
