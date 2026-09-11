import secrets
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import update, delete
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.security import hash_password
from app.modules.users.models import User

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_tenant_isolation_and_latest_permissions(client: AsyncClient, db_engine: AsyncEngine) -> None:
    accounts = []
    for slug in ("alpha", "beta"):
        password = secrets.token_urlsafe(24)
        email = slug + "@example.com"
        registered = await client.post("/auth/register", json={
            "tenant_name": slug, "tenant_slug": slug, "email": email, "password": password,
        })
        assert registered.status_code == 201
        login = await client.post("/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200
        accounts.append((registered.json(), {"Authorization": "Bearer " + login.json()["access_token"]}))
    alpha, alpha_headers = accounts[0]
    beta, beta_headers = accounts[1]

    member_password = secrets.token_urlsafe(24)
    async with async_sessionmaker(db_engine, expire_on_commit=False)() as session:
        async with session.begin():
            member = User(
                tenant_id=UUID(alpha["tenant"]["id"]), email="member@example.com",
                password_hash=await hash_password(member_password),
            )
            session.add(member)
        member_id = str(member.id)
    login = await client.post("/auth/login", json={"email": "member@example.com", "password": member_password})
    assert login.status_code == 200
    member_headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    assert (await client.get("/auth/me", headers=member_headers)).status_code == 200
    assert (await client.get("/users", headers=member_headers)).status_code == 403

    for headers, expected in (
        (alpha_headers, {alpha["user"]["id"], member_id}),
        (beta_headers, {beta["user"]["id"]}),
    ):
        listed = await client.get("/users", headers=headers)
        assert listed.status_code == 200
        assert {u["id"] for u in listed.json()} == expected
        assert "password" not in listed.text

    injected = await client.get("/users", headers=alpha_headers, params={"tenant_id": beta["tenant"]["id"]})
    assert {u["tenant_id"] for u in injected.json()} == {alpha["tenant"]["id"]}
    assert len((await client.get("/users?limit=1", headers=alpha_headers)).json()) == 1

    async with db_engine.begin() as connection:
        await connection.execute(update(User).where(User.id == UUID(alpha["user"]["id"])).values(role="member"))
    assert (await client.get("/users", headers=alpha_headers)).status_code == 403
    async with db_engine.begin() as connection:
        await connection.execute(update(User).where(User.id == UUID(alpha["user"]["id"])).values(is_active=False))
    assert (await client.get("/auth/me", headers=alpha_headers)).status_code == 401
    async with db_engine.begin() as connection:
        await connection.execute(delete(User).where(User.id == UUID(beta["user"]["id"])))
    assert (await client.get("/auth/me", headers=beta_headers)).status_code == 401
