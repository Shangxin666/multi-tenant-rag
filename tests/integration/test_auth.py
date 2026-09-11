from datetime import datetime, timedelta, timezone
import secrets
from uuid import UUID, uuid4

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.config import Settings
from app.core.security import verify_password
from app.modules.tenants.models import Tenant
from app.modules.users.models import User

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def registration(slug: str = "team-one", email: str = "admin@example.com") -> dict[str, str]:
    return {
        "tenant_name": "Team One", "tenant_slug": slug,
        "email": email, "password": secrets.token_urlsafe(24),
    }


async def test_register_login_me(client: AsyncClient, db_engine: AsyncEngine) -> None:
    data = registration(email=" Admin@Example.com ")
    registered = await client.post("/auth/register", json=data)
    assert registered.status_code == 201
    body = registered.json()
    assert body["user"]["role"] == "admin"
    assert body["user"]["tenant_id"] == body["tenant"]["id"]
    assert body["user"]["email"] == "admin@example.com"
    assert "password" not in registered.text

    async with async_sessionmaker(db_engine)() as session:
        user = await session.get(User, UUID(body["user"]["id"]))
        assert user is not None
        assert user.password_hash != data["password"]
        assert user.password_hash.startswith("$argon2id$")
        assert await verify_password(data["password"], user.password_hash)

    login = await client.post("/auth/login", json={"email": data["email"], "password": data["password"]})
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    me = await client.get("/auth/me", headers=headers)
    assert me.status_code == 200 and me.json() == body["user"]
    users = await client.get("/users", headers=headers)
    assert users.status_code == 200 and users.json() == [body["user"]]
    assert "password" not in me.text and "password" not in users.text


async def test_duplicate_email_rolls_back_tenant(client: AsyncClient, db_engine: AsyncEngine) -> None:
    assert (await client.post("/auth/register", json=registration())).status_code == 201
    # A new slug forces Tenant INSERT to succeed before User's email conflict.
    result = await client.post("/auth/register", json=registration("orphan-candidate", " ADMIN@example.com "))
    assert result.status_code == 409
    async with async_sessionmaker(db_engine)() as session:
        assert await session.scalar(select(func.count()).select_from(Tenant)) == 1
        assert await session.scalar(select(func.count()).select_from(User)) == 1
        assert await session.scalar(select(Tenant).where(Tenant.slug == "orphan-candidate")) is None


async def test_duplicate_slug(client: AsyncClient, db_engine: AsyncEngine) -> None:
    assert (await client.post("/auth/register", json=registration())).status_code == 201
    assert (await client.post("/auth/register", json=registration(email="other@example.com"))).status_code == 409
    async with async_sessionmaker(db_engine)() as session:
        assert await session.scalar(select(func.count()).select_from(User)) == 1


async def test_login_failures_are_identical(client: AsyncClient, db_engine: AsyncEngine) -> None:
    data = registration()
    assert (await client.post("/auth/register", json=data)).status_code == 201
    wrong = await client.post("/auth/login", json={"email": data["email"], "password": "incorrect"})
    absent = await client.post("/auth/login", json={"email": "absent@example.com", "password": "incorrect"})
    async with db_engine.begin() as connection:
        await connection.execute(update(User).values(is_active=False))
    inactive = await client.post("/auth/login", json={"email": data["email"], "password": data["password"]})
    assert wrong.status_code == absent.status_code == inactive.status_code == 401
    assert wrong.json() == absent.json() == inactive.json()
    assert wrong.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("case", ["missing", "invalid", "expired", "unknown_user"])
async def test_reject_unauthenticated(client: AsyncClient, database_settings: Settings, case: str) -> None:
    headers = {}
    if case == "invalid":
        headers["Authorization"] = "Bearer invalid"
    elif case in {"expired", "unknown_user"}:
        exp = datetime.now(timezone.utc) + timedelta(minutes=-1 if case == "expired" else 1)
        token = jwt.encode({"sub": str(uuid4()), "exp": exp}, database_settings.jwt_secret.get_secret_value(), algorithm="HS256")
        headers["Authorization"] = "Bearer " + token
    response = await client.get("/auth/me", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_registration_cannot_assign_role(client: AsyncClient) -> None:
    data = registration()
    data["role"] = "admin"
    assert (await client.post("/auth/register", json=data)).status_code == 422
