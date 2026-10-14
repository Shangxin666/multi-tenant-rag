from uuid import UUID
import pytest
from sqlalchemy import select, update, event
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.modules.documents import service
from app.modules.documents.models import Document
from app.modules.chunks.models import Chunk
from app.modules.documents.ingestion.types import ChunkDraft
from test_rag import seed, vector

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("fail", [False, True])
async def test_m4_publish_resets_index_atomically(ingestion_accounts, db_engine, fail):
    a = ingestion_accounts["alpha"]
    doc = await seed(db_engine, a, index_status="failed", vectors=[vector()] * 3)
    async with db_engine.begin() as conn:
        await conn.execute(update(Document).where(Document.id == doc).values(status="processing", index_error_message="old error"))
    claimed = service.ProcessingDocument(doc, UUID(a["tenant_id"]), "unused", 1, "a" * 64, "markdown")
    drafts = [ChunkDraft(0, "new text", {})]
    if fail: drafts.append(ChunkDraft(0, "duplicate index", {}))
    async with async_sessionmaker(db_engine)() as session:
        if fail:
            with pytest.raises(Exception): await service.publish(session, claimed, drafts)
            await session.rollback()
        else:
            await service.publish(session, claimed, drafts)
        document = await session.get(Document, doc)
        chunks = list(await session.scalars(select(Chunk).where(Chunk.document_id == doc)))
        if fail:
            assert document.status == "processing" and document.index_status == "failed"
            assert document.index_error_message == "old error" and len(chunks) == 3
            assert all(c.embedding is not None for c in chunks)
        else:
            assert document.status == "ready" and document.index_status == "pending"
            assert document.embedding_model is None and document.indexed_at is None and document.index_error_message is None
            assert len(chunks) == 1 and chunks[0].embedding is None
