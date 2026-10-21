from datetime import datetime
from uuid import UUID, uuid4

from pydantic import JsonValue
from pgvector.sqlalchemy import VECTOR
from sqlalchemy import CheckConstraint, Computed, DateTime, ForeignKeyConstraint, Index, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "document_id"], ["documents.tenant_id", "documents.id"],
            name="fk_chunks_tenant_document", ondelete="CASCADE",
        ),
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_document_index"),
        CheckConstraint("chunk_index >= 0", name="chunk_index"),
        Index("ix_chunks_tenant_id", "tenant_id"),
        Index("ix_chunks_search_vector_gin", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column()
    document_id: Mapped[UUID] = mapped_column()
    chunk_index: Mapped[int] = mapped_column()
    content: Mapped[str] = mapped_column(Text)
    search_vector: Mapped[str] = mapped_column(TSVECTOR, Computed("app_private.search_document(content)", persisted=True))
    embedding: Mapped[list[float] | None] = mapped_column(VECTOR(512))
    chunk_metadata: Mapped[dict[str, JsonValue] | None] = mapped_column(
        "metadata", JSONB(none_as_null=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
