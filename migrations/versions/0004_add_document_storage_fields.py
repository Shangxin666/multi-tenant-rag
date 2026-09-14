"""Add nullable original-file storage fields, preserving existing Documents."""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "0004_add_document_storage_fields"
down_revision: str = "0003_create_knowledge_models"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("storage_key", sa.String(255), nullable=True))
    op.add_column("documents", sa.Column("file_size_bytes", sa.BigInteger(), nullable=True))
    op.add_column("documents", sa.Column("content_sha256", sa.String(64), nullable=True))
    op.create_unique_constraint("uq_documents_storage_key", "documents", ["storage_key"])
    op.create_check_constraint(op.f("ck_documents_storage_fields"), "documents",
        "(storage_key IS NULL AND file_size_bytes IS NULL AND content_sha256 IS NULL) OR "
        "(storage_key IS NOT NULL AND file_size_bytes IS NOT NULL AND content_sha256 IS NOT NULL)")
    op.create_check_constraint(op.f("ck_documents_file_size"), "documents", "file_size_bytes > 0")
    op.create_check_constraint(op.f("ck_documents_sha256"), "documents", "content_sha256 ~ '^[0-9a-f]{64}$'")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_documents_sha256"), "documents", type_="check")
    op.drop_constraint(op.f("ck_documents_file_size"), "documents", type_="check")
    op.drop_constraint(op.f("ck_documents_storage_fields"), "documents", type_="check")
    op.drop_constraint("uq_documents_storage_key", "documents", type_="unique")
    op.drop_column("documents", "content_sha256")
    op.drop_column("documents", "file_size_bytes")
    op.drop_column("documents", "storage_key")
