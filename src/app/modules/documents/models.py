from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKeyConstraint, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SourceType = Literal["pdf", "markdown", "html"]
DocumentStatus = Literal["pending", "processing", "ready", "failed"]


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_documents_tenant_id"),
        UniqueConstraint("storage_key", name="uq_documents_storage_key"),
        CheckConstraint(
            "(storage_key IS NULL AND file_size_bytes IS NULL AND content_sha256 IS NULL) OR "
            "(storage_key IS NOT NULL AND file_size_bytes IS NOT NULL AND content_sha256 IS NOT NULL)",
            name="storage_fields",
        ),
        CheckConstraint("file_size_bytes > 0", name="file_size"),
        CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="sha256"),
        ForeignKeyConstraint(
            ["tenant_id", "knowledge_base_id"], ["knowledge_bases.tenant_id", "knowledge_bases.id"],
            name="fk_documents_tenant_knowledge_base", ondelete="RESTRICT",
        ),
        CheckConstraint("source_type IN ('pdf', 'markdown', 'html')", name="source_type"),
        CheckConstraint("status IN ('pending', 'processing', 'ready', 'failed')", name="status"),
        Index("ix_documents_tenant_knowledge_base", "tenant_id", "knowledge_base_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column()
    knowledge_base_id: Mapped[UUID] = mapped_column()
    filename: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[SourceType] = mapped_column(String(16))
    status: Mapped[DocumentStatus] = mapped_column(
        String(16), default="pending", server_default="pending"
    )
    storage_key: Mapped[str | None] = mapped_column(String(255))
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    content_sha256: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
