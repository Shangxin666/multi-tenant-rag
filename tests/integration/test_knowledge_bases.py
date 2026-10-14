from collections.abc import AsyncIterator
from datetime import datetime, timezone
import secrets
from uuid import UUID, uuid4
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.security import hash_password
from app.modules.knowledge_bases.models import KnowledgeBase
from app.modules.users.models import User

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
PUBLIC_FIELDS = {"id", "tenant_id", "name", "description", "created_at", "updated_at"}


@pytest_asyncio.fixture
async def accounts(client: AsyncClient, db_engine: AsyncEngine) -> dict[str, dict[str, str]]:
    result = {}
    tenant_id = None
    for team in ("alpha", "beta"):
        password = secrets.token_urlsafe(24)
        email = team + "@example.com"
        registration = await client.post("/auth/register", json={
            "tenant_name": team, "tenant_slug": team, "email": email, "password": password,
        })
        assert registration.status_code == 201
        if team == "alpha":
            tenant_id = UUID(registration.json()["tenant"]["id"])
        login = await client.post("/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200
        result[team] = {"Authorization": "Bearer " + login.json()["access_token"]}
    password = secrets.token_urlsafe(24)
    encoded = await hash_password(password)
    async with async_sessionmaker(db_engine)() as session:
        async with session.begin():
            session.add(User(
                tenant_id=tenant_id, email="member@example.com", password_hash=encoded,
            ))
    login = await client.post("/auth/login", json={"email": "member@example.com", "password": password})
    assert login.status_code == 200
    result["member"] = {"Authorization": "Bearer " + login.json()["access_token"]}
    return result


async def test_create_read_permissions_and_isolation(client: AsyncClient, accounts: dict) -> None:
    first = await client.post("/knowledge-bases", headers=accounts["alpha"], json={"name": " Support "})
    assert first.status_code == 201
    resource = first.json()
    assert set(resource) == PUBLIC_FIELDS
    assert resource["name"] == "Support"
    assert datetime.fromisoformat(resource["created_at"]).tzinfo is not None
    assert datetime.fromisoformat(resource["updated_at"]).tzinfo is not None

    duplicate = await client.post("/knowledge-bases", headers=accounts["alpha"], json={"name": "Support"})
    assert duplicate.status_code == 409
    # A conflict must not poison later requests; case remains significant.
    assert (await client.post("/knowledge-bases", headers=accounts["alpha"], json={"name": "support"})).status_code == 201
    second = await client.post("/knowledge-bases", headers=accounts["beta"], json={"name": "Support"})
    assert second.status_code == 201

    assert (await client.post("/knowledge-bases", headers=accounts["member"], json={"name": "Denied"})).status_code == 403
    for role in ("alpha", "member"):
        listed = await client.get("/knowledge-bases", headers=accounts[role], params={"tenant_id": second.json()["tenant_id"]})
        assert listed.status_code == 200
        assert len(listed.json()) == 2
        assert {r["tenant_id"] for r in listed.json()} == {resource["tenant_id"]}
        assert all(set(r) == PUBLIC_FIELDS for r in listed.json())
        detail = await client.get("/knowledge-bases/" + resource["id"], headers=accounts[role])
        assert detail.status_code == 200 and detail.json() == resource
        foreign = await client.get("/knowledge-bases/" + second.json()["id"], headers=accounts[role])
        absent = await client.get("/knowledge-bases/" + str(uuid4()), headers=accounts[role])
        assert foreign.status_code == absent.status_code == 404
        assert foreign.json() == absent.json()


@pytest.mark.parametrize("field", ["tenant_id", "id", "created_at", "updated_at"])
async def test_reject_server_owned_fields(client: AsyncClient, accounts: dict, field: str) -> None:
    response = await client.post("/knowledge-bases", headers=accounts["alpha"], json={"name": "Rejected", field: str(uuid4())})
    assert response.status_code == 422


async def test_pagination_stable_for_equal_timestamps(client: AsyncClient, accounts: dict, db_engine: AsyncEngine) -> None:
    ids = []
    for name in ("one", "two", "three"):
        response = await client.post("/knowledge-bases", headers=accounts["alpha"], json={"name": name})
        assert response.status_code == 201
        ids.append(response.json()["id"])
    async with db_engine.begin() as connection:
        await connection.execute(update(KnowledgeBase).values(created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
    response = await client.get("/knowledge-bases?limit=1&offset=1", headers=accounts["alpha"])
    assert response.status_code == 200
    assert [r["id"] for r in response.json()] == [sorted(ids)[1]]
    for query in ("limit=0", "limit=101", "offset=-1"):
        assert (await client.get("/knowledge-bases?" + query, headers=accounts["alpha"])).status_code == 422


async def test_no_token(client: AsyncClient) -> None:
    assert (await client.get("/knowledge-bases")).status_code == 401
    assert (await client.get("/knowledge-bases/" + str(uuid4()))).status_code == 401
    assert (await client.post("/knowledge-bases", json={"name": "No auth"})).status_code == 401


async def test_commit_failure_rolls_back(
    application: FastAPI, accounts: dict, db_engine: AsyncEngine,
    app_db_engine: AsyncEngine,
) -> None:
    from app.db.session import get_db

    from app.db.tenant_context import TenantSession
    factory = async_sessionmaker(app_db_engine, expire_on_commit=False, sync_session_class=TenantSession)
    sessions = []

    async def failing_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            session.commit = AsyncMock(side_effect=RuntimeError("Simulated commit failure"))
            session.rollback = AsyncMock(wraps=session.rollback)
            sessions.append(session)
            yield session

    previous = application.dependency_overrides[get_db]
    application.dependency_overrides[get_db] = failing_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=application, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            response = await client.post("/knowledge-bases", headers=accounts["alpha"], json={"name": "Never committed"})
        assert response.status_code == 500
        assert len(sessions) == 1
        sessions[0].commit.assert_awaited_once()
        # Authentication releases its read transaction; failed commit rolls back again.
        assert sessions[0].rollback.await_count == 2
        async with async_sessionmaker(db_engine)() as session:
            assert await session.scalar(select(KnowledgeBase).where(KnowledgeBase.name == "Never committed")) is None
    finally:
        application.dependency_overrides[get_db] = previous
