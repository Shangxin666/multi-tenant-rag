"""Separate text readiness from vector indexing readiness."""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import VECTOR

revision = "0005_add_vector_indexing"
down_revision = "0004_add_document_storage_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("index_status", sa.String(16), nullable=True))
    op.execute("UPDATE documents SET index_status = 'pending'")
    op.alter_column("documents", "index_status", nullable=False, server_default="pending")
    op.add_column("documents", sa.Column("index_error_message", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("embedding_model", sa.String(255), nullable=True))
    op.add_column("documents", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("chunks", sa.Column("embedding", VECTOR(512), nullable=True))
    op.create_check_constraint(op.f("ck_documents_index_status"), "documents", "index_status IN ('pending', 'processing', 'ready', 'failed')")
    op.create_check_constraint(op.f("ck_documents_index_text_ready"), "documents", "index_status NOT IN ('processing', 'ready') OR status = 'ready'")
    op.create_check_constraint(op.f("ck_documents_index_metadata"), "documents", "(index_status = 'ready' AND embedding_model IS NOT NULL AND indexed_at IS NOT NULL AND index_error_message IS NULL) OR (index_status <> 'ready' AND embedding_model IS NULL AND indexed_at IS NULL)")


def downgrade() -> None:
    for name in ("index_metadata", "index_text_ready", "index_status"):
        op.drop_constraint(op.f("ck_documents_" + name), "documents", type_="check")
    op.drop_column("chunks", "embedding")
    for name in ("indexed_at", "embedding_model", "index_error_message", "index_status"):
        op.drop_column("documents", name)
