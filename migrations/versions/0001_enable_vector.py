"""Enable the vector extension without creating business tables."""
from collections.abc import Sequence

from alembic import op

revision: str = "0001_enable_vector"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # Intentionally retain this shared extension and any future dependent data.
    pass
