from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.modules.tenants.models import Tenant
from app.modules.knowledge_bases.models import KnowledgeBase
from app.modules.documents.models import Document
from app.modules.chunks.models import Chunk

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def graph(db_engine: AsyncEngine) -> dict[str, UUID]:
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        async with session.begin():
            a = Tenant(name="A", slug="a")
            b = Tenant(name="B", slug="b")
            session.add_all([a, b])
            await session.flush()
            ka = KnowledgeBase(tenant_id=a.id, name="KB")
            kb = KnowledgeBase(tenant_id=b.id, name="KB")
            session.add_all([ka, kb])
            await session.flush()
            da = Document(tenant_id=a.id, knowledge_base_id=ka.id, filename="a.pdf", source_type="pdf")
            db = Document(tenant_id=b.id, knowledge_base_id=kb.id, filename="b.md", source_type="markdown")
            session.add_all([da, db])
            await session.flush()
            ca = Chunk(tenant_id=a.id, document_id=da.id, chunk_index=0, content="A", chunk_metadata={"page": 1})
            cb = Chunk(tenant_id=b.id, document_id=db.id, chunk_index=0, content="B")
            session.add_all([ca, cb])
            await session.flush()
        return {"a": a.id, "b": b.id, "ka": ka.id, "kb": kb.id, "da": da.id, "db": db.id, "ca": ca.id, "cb": cb.id}


async def test_valid_graph_and_defaults(db_engine: AsyncEngine, graph: dict[str, UUID]) -> None:
    async with async_sessionmaker(db_engine)() as session:
        document = await session.get(Document, graph["da"])
        assert document is not None and document.status == "pending"
        assert document.created_at.tzinfo is not None and document.updated_at.tzinfo is not None
        chunk = await session.get(Chunk, graph["ca"])
        assert chunk is not None and chunk.chunk_metadata == {"page": 1}
        other = await session.get(Chunk, graph["cb"])
        assert other is not None and other.chunk_index == chunk.chunk_index
        assert other.chunk_metadata is None


@pytest.mark.parametrize(
    ("case", "constraint"),
    [
        ("document_wrong_tenant", "fk_documents_tenant_knowledge_base"),
        ("chunk_wrong_tenant", "fk_chunks_tenant_document"),
        ("document_update_tenant", "fk_documents_tenant_knowledge_base"),
        ("chunk_update_tenant", "fk_chunks_tenant_document"),
        ("source_type", "ck_documents_source_type"),
        ("status", "ck_documents_status"),
        ("negative_index", "ck_chunks_chunk_index"),
        ("duplicate_index", "uq_chunks_document_index"),
    ],
)
async def test_database_rejects_invalid_rows(
    db_engine: AsyncEngine, graph: dict[str, UUID], case: str, constraint: str,
) -> None:
    if case == "document_wrong_tenant":
        statement = insert(Document).values(
            tenant_id=graph["a"], knowledge_base_id=graph["kb"],
            filename="wrong.pdf", source_type="pdf",
        )
    elif case == "chunk_wrong_tenant":
        statement = insert(Chunk).values(
            tenant_id=graph["a"], document_id=graph["db"], chunk_index=1, content="Wrong",
        )
    elif case == "document_update_tenant":
        # Use a childless Document so the outgoing composite FK is the failing constraint.
        async with db_engine.begin() as connection:
            await connection.execute(delete(Chunk).where(Chunk.document_id == graph["da"]))
        statement = update(Document).where(Document.id == graph["da"]).values(tenant_id=graph["b"])
    elif case == "chunk_update_tenant":
        statement = update(Chunk).where(Chunk.id == graph["ca"]).values(tenant_id=graph["b"])
    elif case == "source_type":
        statement = update(Document).where(Document.id == graph["da"]).values(source_type="txt")
    elif case == "status":
        statement = update(Document).where(Document.id == graph["da"]).values(status="unknown")
    else:
        statement = insert(Chunk).values(
            tenant_id=graph["a"], document_id=graph["da"],
            chunk_index=-1 if case == "negative_index" else 0, content="Invalid",
        )
    # The context rolls back before we inspect the error or open another transaction.
    with pytest.raises(IntegrityError) as error:
        async with db_engine.begin() as connection:
            await connection.execute(statement)
    assert getattr(error.value.orig.__cause__, "constraint_name", None) == constraint
    async with db_engine.connect() as connection:
        assert await connection.scalar(text("SELECT 1")) == 1


async def test_document_delete_cascades_only_its_chunks(db_engine: AsyncEngine, graph: dict[str, UUID]) -> None:
    async with db_engine.begin() as connection:
        await connection.execute(delete(Document).where(Document.id == graph["da"]))
    async with async_sessionmaker(db_engine)() as session:
        assert await session.get(Chunk, graph["ca"]) is None
        assert await session.get(Chunk, graph["cb"]) is not None
        assert await session.get(Document, graph["db"]) is not None


@pytest.mark.parametrize("target", ["knowledge_base", "tenant"])
async def test_parent_delete_restricted(db_engine: AsyncEngine, graph: dict[str, UUID], target: str) -> None:
    statement = (
        delete(KnowledgeBase).where(KnowledgeBase.id == graph["ka"])
        if target == "knowledge_base"
        else delete(Tenant).where(Tenant.id == graph["a"])
    )
    with pytest.raises(IntegrityError) as error:
        async with db_engine.begin() as connection:
            await connection.execute(statement)
    expected = "fk_documents_tenant_knowledge_base" if target == "knowledge_base" else "fk_knowledge_bases_tenant"
    assert getattr(error.value.orig.__cause__, "constraint_name", None) == expected
    async with async_sessionmaker(db_engine)() as session:
        assert await session.get(Tenant, graph["a"]) is not None
        assert await session.get(KnowledgeBase, graph["ka"]) is not None
        assert await session.get(Document, graph["da"]) is not None
