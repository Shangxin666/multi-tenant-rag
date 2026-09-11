from collections.abc import AsyncIterator
from pathlib import Path
import os
import re
import subprocess
import sys

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings, get_settings

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def database_settings() -> Settings:
    settings = Settings()
    name = settings.test_database_name
    if (
        settings.app_env != "local"
        or settings.db_host not in {"127.0.0.1", "localhost"}
        or name is None
        or len(name) > 63
        or not re.fullmatch(r"[a-z][a-z0-9_]*_test", name)
        or name == settings.postgres_db
    ):
        pytest.fail("Integration tests require a distinct local TEST_DATABASE_NAME ending in _test")
    target = settings.model_copy(update={"postgres_db": name, "app_env": "test", "db_echo": False})
    env = os.environ.copy()
    env.update({
        "APP_ENV": "test",
        "DB_HOST": target.db_host,
        "DB_PORT": str(target.db_port),
        "POSTGRES_DB": target.postgres_db,
        "POSTGRES_USER": target.postgres_user,
        "POSTGRES_PASSWORD": target.postgres_password.get_secret_value(),
        "JWT_SECRET": target.jwt_secret.get_secret_value(),
        "JWT_ALGORITHM": target.jwt_algorithm,
        "ACCESS_TOKEN_EXPIRE_MINUTES": str(target.access_token_expire_minutes),
        "DB_ECHO": "false",
    })
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )
    if result.returncode:
        # Do not print connection details or environment values.
        pytest.fail("Test database migration failed; prepare the database and check connectivity")
    return target


@pytest_asyncio.fixture
async def db_engine(database_settings: Settings) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(database_settings.database_url)

    async def clean() -> None:
        async with engine.begin() as connection:
            actual = await connection.scalar(text("SELECT current_database()"))
            if actual != database_settings.postgres_db or not actual.endswith("_test"):
                raise RuntimeError("Refusing to clean a non-test database")
            await connection.execute(text("TRUNCATE TABLE users, tenants"))

    try:
        await clean()
        yield engine
    finally:
        try:
            await clean()
        finally:
            await engine.dispose()


@pytest_asyncio.fixture
async def application(db_engine: AsyncEngine, database_settings: Settings) -> AsyncIterator[FastAPI]:
    from app.db.session import get_db
    from app.main import create_app

    app = create_app()
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: database_settings
    try:
        async with app.router.lifespan_context(app):
            yield app
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(application: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        yield client
