"""Create an explicitly named local test database without touching existing data."""
import asyncio
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings


def test_database_settings(settings: Settings) -> Settings:
    name = settings.test_database_name
    if (
        settings.app_env != "local"
        or settings.db_host not in {"127.0.0.1", "localhost"}
        or name is None
        or len(name) > 63
        or not re.fullmatch(r"[a-z][a-z0-9_]*_test", name)
        or name == settings.postgres_db
    ):
        raise ValueError("Set a distinct local TEST_DATABASE_NAME ending in _test")
    return settings.model_copy(update={"postgres_db": name, "app_env": "test", "db_echo": False})


async def prepare() -> None:
    original = Settings()
    target = test_database_settings(original)
    engine = create_async_engine(original.database_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            exists = await connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": target.postgres_db},
            )
            if not exists:
                quoted = connection.dialect.identifier_preparer.quote(target.postgres_db)
                await connection.execute(text(f"CREATE DATABASE {quoted}"))
                print("Created dedicated test database")
            else:
                print("Dedicated test database already exists; preserved")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(prepare())
