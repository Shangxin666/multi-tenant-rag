import asyncio
import os
import secrets
import sys
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def migrate(settings: Settings, *arguments: str) -> None:
    env = os.environ.copy()
    env.update({
        "APP_ENV": "test", "POSTGRES_DB": settings.postgres_db,
        "DB_HOST": settings.db_host, "DB_PORT": str(settings.db_port),
        "POSTGRES_USER": settings.postgres_user,
        "POSTGRES_PASSWORD": settings.postgres_password.get_secret_value(),
        "JWT_SECRET": settings.jwt_secret.get_secret_value(),
    })
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "alembic", *arguments, env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    await process.communicate()
    assert process.returncode == 0, "Test database migration failed"


async def legacy_row(engine: AsyncEngine) -> str:
    tenant, kb, document = [uuid4() for _ in range(3)]
    async with engine.begin() as connection:
        await connection.execute(text("INSERT INTO tenants (id, name, slug) VALUES (:id, 'Legacy', :slug)"),
            {"id": tenant, "slug": "legacy-" + secrets.token_hex(8)})
        await connection.execute(text("INSERT INTO knowledge_bases (id, tenant_id, name) VALUES (:id, :tenant, 'Legacy')"),
            {"id": kb, "tenant": tenant})
        await connection.execute(text(
            "INSERT INTO documents (id, tenant_id, knowledge_base_id, filename, source_type) "
            "VALUES (:id, :tenant, :kb, 'legacy.md', 'markdown')"
        ), {"id": document, "tenant": tenant, "kb": kb})
    return str(document)


async def test_upgrade_with_existing_document(db_engine: AsyncEngine, database_settings: Settings) -> None:
    # Only the explicit test database is used; restore head even on failure.
    try:
        await migrate(database_settings, "downgrade", "0003_create_knowledge_models")
        document_id = await legacy_row(db_engine)
    finally:
        await migrate(database_settings, "upgrade", "head")
    async with db_engine.connect() as connection:
        row = (await connection.execute(text(
            "SELECT storage_key, file_size_bytes, content_sha256 FROM documents WHERE id = :id"
        ), {"id": document_id})).one()
        assert tuple(row) == (None, None, None)


@pytest.mark.parametrize("case", ["partial", "negative_size", "bad_hash"])
async def test_storage_checks(db_engine: AsyncEngine, case: str) -> None:
    document_id = await legacy_row(db_engine)
    fields = {"key": uuid4().hex + "/" + uuid4().hex, "size": 1, "hash": "a" * 64, "id": document_id}
    if case == "partial":
        fields["hash"] = None
    elif case == "negative_size":
        fields["size"] = -1
    else:
        fields["hash"] = "invalid"
    with pytest.raises(IntegrityError):
        async with db_engine.begin() as connection:
            await connection.execute(text(
                "UPDATE documents SET storage_key=:key, file_size_bytes=:size, content_sha256=:hash WHERE id=:id"
            ), fields)
