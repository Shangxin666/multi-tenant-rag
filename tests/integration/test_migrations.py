import pytest
from sqlalchemy import Connection, inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_upgrade_head_and_vector(db_engine: AsyncEngine) -> None:
    async with db_engine.connect() as connection:
        assert await connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002_create_tenants_and_users"
        assert await connection.scalar(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        ) == "vector"

        def inspect_schema(sync_connection: Connection) -> None:
            inspector = inspect(sync_connection)
            assert {"tenants", "users", "alembic_version"} <= set(inspector.get_table_names())
            assert {tuple(c["column_names"]) for c in inspector.get_unique_constraints("users")} == {("email",)}
            assert {tuple(c["column_names"]) for c in inspector.get_unique_constraints("tenants")} == {("slug",)}
            foreign_key = inspector.get_foreign_keys("users")[0]
            assert foreign_key["referred_table"] == "tenants"
            assert foreign_key["options"]["ondelete"] == "RESTRICT"
            checks = inspector.get_check_constraints("users")
            assert len(checks) == 1 and checks[0]["name"] == "ck_users_role"
            assert "admin" in checks[0]["sqltext"] and "member" in checks[0]["sqltext"]
            assert any(i["column_names"] == ["tenant_id"] for i in inspector.get_indexes("users"))

        await connection.run_sync(inspect_schema)
