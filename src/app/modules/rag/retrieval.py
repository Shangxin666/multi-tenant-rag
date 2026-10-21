from app.observability.trace import traced
from dataclasses import dataclass
from uuid import UUID
from typing import Any

from sqlalchemy import select, Select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chunks.models import Chunk
from app.modules.documents.models import Document


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: UUID
    document_id: UUID
    filename: str
    chunk_index: int
    content: str
    metadata: dict[str, Any] | None
    distance: float


def scoped_query(tenant_id: UUID, knowledge_base_id: UUID, model: str) -> Select:
    return select(Chunk.id).join(Document, (Document.id == Chunk.document_id) &
                                 (Document.tenant_id == Chunk.tenant_id)).where(
        Chunk.tenant_id == tenant_id, Document.tenant_id == tenant_id,
        Document.knowledge_base_id == knowledge_base_id,
        Document.status == "ready", Document.index_status == "ready",
        Document.embedding_model == model, Chunk.embedding.is_not(None),
    )


async def has_chunks(session: AsyncSession, tenant_id: UUID, kb_id: UUID, model: str) -> bool:
    return await session.scalar(scoped_query(tenant_id, kb_id, model).limit(1)) is not None


@traced("dense_search")
async def retrieve_chunks(session: AsyncSession, tenant_id: UUID, kb_id: UUID,
                          model: str, vector: list[float], top_k: int) -> list[RetrievedChunk]:
    distance = Chunk.embedding.cosine_distance(vector).label("distance")
    statement = scoped_query(tenant_id, kb_id, model).with_only_columns(
        Chunk.id, Chunk.document_id, Document.filename, Chunk.chunk_index,
        Chunk.content, Chunk.chunk_metadata, distance,
    ).order_by(distance.asc(), Chunk.id.asc()).limit(top_k)
    return [RetrievedChunk(*row) for row in (await session.execute(statement)).all()]


@traced("sparse_search")
async def retrieve_sparse(session: AsyncSession, tenant_id: UUID, kb_id: UUID,
                          model: str, vector: list[float], question: str,
                          top_k: int) -> list[RetrievedChunk]:
    query = func.app_private.search_question(question)
    rank = func.ts_rank(Chunk.search_vector, query)
    distance = Chunk.embedding.cosine_distance(vector).label("distance")
    statement = scoped_query(tenant_id, kb_id, model).with_only_columns(
        Chunk.id, Chunk.document_id, Document.filename, Chunk.chunk_index,
        Chunk.content, Chunk.chunk_metadata, distance,
    ).where(Chunk.search_vector.bool_op("@@")(query)).order_by(rank.desc(), Chunk.id.asc()).limit(top_k)
    return [RetrievedChunk(*row) for row in (await session.execute(statement)).all()]
