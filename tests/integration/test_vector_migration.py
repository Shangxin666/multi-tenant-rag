from uuid import UUID, uuid4
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from test_document_storage_migration import migrate, legacy_row

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_0004_history_upgrades(db_engine, database_settings):
    try:
        await migrate(database_settings, "downgrade", "0004_add_document_storage_fields")
        for status in ("pending", "processing", "ready", "failed"):
            doc = await legacy_row(db_engine)
            async with db_engine.begin() as conn:
                await conn.execute(text("UPDATE documents SET status=:status WHERE id=:id"), {"status": status, "id": doc})
                await conn.execute(text("INSERT INTO chunks (id, tenant_id, document_id, chunk_index, content) SELECT :chunk, tenant_id, id, 0, 'legacy' FROM documents WHERE id=:doc"), {"chunk": uuid4(), "doc": doc})
    finally:
        await migrate(database_settings, "upgrade", "head")
    async with db_engine.connect() as conn:
        assert await conn.scalar(text("SELECT count(*) FROM documents WHERE index_status='pending' AND indexed_at IS NULL AND embedding_model IS NULL")) == 4
        assert await conn.scalar(text("SELECT count(*) FROM chunks WHERE embedding IS NULL")) == 4
        assert await conn.scalar(text("SELECT format_type(atttypid, atttypmod) FROM pg_attribute WHERE attrelid='chunks'::regclass AND attname='embedding'")) == "vector(512)"
        assert await conn.scalar(text("SELECT count(*) FROM pg_indexes WHERE tablename='chunks' AND (indexdef ILIKE '% USING hnsw %' OR indexdef ILIKE '% USING ivfflat %')")) == 0
    await migrate(database_settings, "check")


@pytest.mark.parametrize("assignment", [
    "index_status='invalid'",
    "index_status='processing'",
    "status='ready', index_status='ready'",
    "embedding_model='unpublished'",
])
async def test_index_checks(db_engine, assignment):
    doc = await legacy_row(db_engine)
    with pytest.raises(IntegrityError):
        async with db_engine.begin() as conn:
            await conn.execute(text("UPDATE documents SET " + assignment + " WHERE id=:id"), {"id": doc})
