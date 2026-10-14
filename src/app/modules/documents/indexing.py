from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.modules.chunks.models import Chunk
from app.modules.documents.models import Document
from app.modules.documents.schemas import DocumentPublic
from app.modules.documents.service import get_public, unavailable
from app.modules.documents.ingestion.errors import log_failure
from app.modules.rag.embedding import EmbeddingBackend, EmbeddingError, validate_vectors


@dataclass(frozen=True)
class ChunkSnapshot:
    id: UUID
    chunk_index: int
    content: str


async def snapshot(session: AsyncSession, document_id: UUID, tenant_id: UUID) -> list[ChunkSnapshot]:
    rows = (await session.execute(select(Chunk.id, Chunk.chunk_index, Chunk.content).where(
        Chunk.document_id == document_id, Chunk.tenant_id == tenant_id,
    ).order_by(Chunk.chunk_index, Chunk.id))).all()
    return [ChunkSnapshot(*row) for row in rows]


async def claim(session: AsyncSession, document_id: UUID, tenant_id: UUID) -> None:
    async with session.begin():
        claimed = await session.scalar(update(Document).where(
            Document.id == document_id, Document.tenant_id == tenant_id,
            Document.status == "ready", Document.index_status.in_(["pending", "failed"]),
        ).values(index_status="processing", index_error_message=None,
                 embedding_model=None, indexed_at=None).returning(Document.id))
        if claimed is None:
            raise HTTPException(409, "Document cannot be indexed in its current state")


async def write_batch(session: AsyncSession, document_id: UUID, tenant_id: UUID,
                      rows: list[ChunkSnapshot], vectors: list[list[float]]) -> None:
    for row, vector in zip(rows, vectors, strict=True):
        await session.execute(update(Chunk).where(
            Chunk.id == row.id, Chunk.document_id == document_id, Chunk.tenant_id == tenant_id,
        ).values(embedding=vector))


async def publish(session: AsyncSession, document_id: UUID, tenant_id: UUID,
                  rows: list[ChunkSnapshot], vectors: list[list[float]], model: str) -> None:
    async with session.begin():
        document = await session.scalar(select(Document).where(
            Document.id == document_id, Document.tenant_id == tenant_id,
        ).with_for_update())
        if document is None or document.status != "ready" or document.index_status != "processing":
            raise EmbeddingError("Indexing state changed")
        current = await snapshot(session, document_id, tenant_id)
        if not rows or current != rows:
            raise EmbeddingError("Document chunks changed")
        for start in range(0, len(rows), 100):
            await write_batch(session, document_id, tenant_id, rows[start:start + 100], vectors[start:start + 100])
        document.index_status = "ready"
        document.index_error_message = None
        document.embedding_model = model
        document.indexed_at = func.now()


async def process(session: AsyncSession, document_id: UUID, tenant_id: UUID,
                  backend: EmbeddingBackend, settings: Settings) -> DocumentPublic:
    try:
        async with session.begin():
            rows = await snapshot(session, document_id, tenant_id)
        if not rows:
            raise EmbeddingError("No document chunks")
        vectors = await run_in_threadpool(backend.embed_passages, [row.content for row in rows])
        vectors = await run_in_threadpool(validate_vectors, vectors, len(rows))
        await publish(session, document_id, tenant_id, rows, vectors, settings.embedding_model)
    except Exception as exc:
        log_failure("Document indexing", exc)
        try:
            await session.rollback()
            async with session.begin():
                await session.execute(update(Document).where(
                    Document.id == document_id, Document.tenant_id == tenant_id,
                    Document.index_status == "processing",
                ).values(index_status="failed", index_error_message="Document indexing failed",
                         embedding_model=None, indexed_at=None))
        except Exception as status_error:
            log_failure("Record indexing failure", status_error)
            await session.rollback()
            raise unavailable(document_id) from None
    try:
        return await get_public(session, document_id, tenant_id)
    except Exception as exc:
        log_failure("Read indexing result", exc)
        await session.rollback()
        raise unavailable(document_id) from None
