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
        "APP_DB_PASSWORD": target.app_db_password.get_secret_value(),
        "MIGRATION_DB_PASSWORD": target.migration_db_password.get_secret_value(),
    })
    provision = subprocess.run(
        [sys.executable, "-m", "scripts.prepare_database_roles", "--test"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if provision.returncode:
        pytest.fail("Test database role provisioning failed")
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
            await connection.execute(text("TRUNCATE TABLE chunks, documents, knowledge_bases, users, tenants"))

    try:
        await clean()
        yield engine
    finally:
        try:
            await clean()
        finally:
            await engine.dispose()


@pytest.fixture
def document_settings(database_settings: Settings, tmp_path: Path) -> Settings:
    return database_settings.model_copy(update={"document_storage_root": tmp_path / "documents"})


@pytest_asyncio.fixture
async def app_db_engine(db_engine: AsyncEngine, database_settings: Settings) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(database_settings.application_database_url, hide_parameters=True, pool_size=1, max_overflow=0)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def application(app_db_engine: AsyncEngine, database_settings: Settings, document_settings: Settings) -> AsyncIterator[FastAPI]:
    from app.db.session import get_db
    from app.main import create_app

    from app.db.tenant_context import TenantSession
    app = create_app(document_settings, database_engine=app_db_engine)
    factory = async_sessionmaker(app_db_engine, expire_on_commit=False, sync_session_class=TenantSession)

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: document_settings
    from app.modules.rag.reranking import get_reranker_backend
    class FakeReranker:
        def score(self, question, passages):
            return [0.0] * len(passages)
    app.dependency_overrides[get_reranker_backend] = FakeReranker
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


@pytest_asyncio.fixture
async def ingestion_accounts(client: AsyncClient, db_engine: AsyncEngine) -> dict:
    import secrets
    from uuid import UUID
    from app.core.security import hash_password
    from app.modules.users.models import User

    accounts = {}
    for name in ("alpha", "beta"):
        password = secrets.token_urlsafe(24)
        email = name + "@example.com"
        response = await client.post("/auth/register", json={
            "tenant_name": name, "tenant_slug": name, "email": email, "password": password,
        })
        assert response.status_code == 201
        tenant_id = response.json()["tenant"]["id"]
        login = await client.post("/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        kb = await client.post("/knowledge-bases", headers=headers, json={"name": "Documents"})
        assert kb.status_code == 201
        accounts[name] = {"headers": headers, "tenant_id": tenant_id, "kb_id": kb.json()["id"]}
    password = secrets.token_urlsafe(24)
    encoded = await hash_password(password)
    async with async_sessionmaker(db_engine)() as session:
        async with session.begin():
            session.add(User(tenant_id=UUID(accounts["alpha"]["tenant_id"]), email="member@example.com", password_hash=encoded))
    login = await client.post("/auth/login", json={"email": "member@example.com", "password": password})
    assert login.status_code == 200
    accounts["member"] = {
        **accounts["alpha"], "headers": {"Authorization": "Bearer " + login.json()["access_token"]},
    }
    return accounts
