import threading
from uuid import UUID

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.exc import DBAPIError

from app.db.tenant_context import TenantSession, bind_tenant
from app.modules.chunks.models import Chunk
from app.modules.rag.fusion import fuse_rrf
from app.modules.rag.retrieval import retrieve_chunks, retrieve_sparse
from app.modules.rag.reranking import rerank, get_reranker_backend
from app.modules.rag.service import query
from app.modules.rag.schemas import RagQueryRequest
from test_rag import seed, vector, FakeEmbedding, FakeLlm, backends

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
MODEL = "BAAI/bge-small-zh-v1.5"


async def texts(engine, account, contents, **kwargs):
    doc = await seed(engine, account, count=len(contents), index_status="ready",
                     vectors=[vector()] * len(contents), **kwargs)
    async with engine.begin() as conn:
        for i, content in enumerate(contents):
            await conn.execute(update(Chunk).where(Chunk.document_id == doc, Chunk.chunk_index == i).values(content=content))
    return doc


@pytest.mark.parametrize("identifier,near", [("E1001", "E10010"), ("ZX-200", "ZX-200S")])
async def test_identifier_end_to_end(db_engine, app_db_engine, ingestion_accounts, identifier, near):
    account = ingestion_accounts["alpha"]
    doc = await texts(db_engine, account, [f"{near} 故障处理", f"{identifier} 故障处理"])
    factory = async_sessionmaker(app_db_engine, sync_session_class=TenantSession)
    async with factory() as session:
        tenant, kb = UUID(account["tenant_id"]), UUID(account["kb_id"])
        bind_tenant(session, tenant)
        dense = await retrieve_chunks(session, tenant, kb, MODEL, vector(), 30)
        sparse = await retrieve_sparse(session, tenant, kb, MODEL, vector(), identifier, 30)
        await session.rollback()
        assert len(sparse) == 1 and sparse[0].chunk_index == 1
        fused = fuse_rrf([dense, sparse])
        assert fused[0].chunk.chunk_index == 1
        class Fake:
            def score(self, question, passages):
                # Distinguish full identifiers, not substring membership.
                return [10. if passage.split()[0] == question else -10. for passage in passages]
        final = rerank(Fake(), identifier, [f.chunk for f in fused], 2)
        assert final[0].document_id == doc and final[0].chunk_index == 1


@pytest.mark.parametrize("question", ["带薪年假", "TIMEOUT", "ZX-200", "E1001"])
async def test_sparse_scope_and_rls(db_engine, app_db_engine, ingestion_accounts, client, question):
    a, b = ingestion_accounts["alpha"], ingestion_accounts["beta"]
    content = "带薪年假 timeout ZX-200 E1001"
    expected = await texts(db_engine, a, [content])
    await texts(db_engine, b, [content])
    kb = (await client.post("/knowledge-bases", headers=a["headers"], json={"name": "other"})).json()
    await texts(db_engine, {**a, "kb_id": kb["id"]}, [content])
    await texts(db_engine, a, [content], model="other")
    for state in ("failed", "pending", "processing"):
        doc = await texts(db_engine, a, [content])
        async with db_engine.begin() as conn:
            await conn.execute(text("UPDATE documents SET index_status=:state, embedding_model=NULL, indexed_at=NULL WHERE id=:id"), {"state": state, "id": doc})
    doc = await texts(db_engine, a, [content])
    async with db_engine.begin() as conn:
        await conn.execute(text("UPDATE documents SET status='failed', index_status='failed', embedding_model=NULL, indexed_at=NULL WHERE id=:id"), {"id": doc})
    doc = await texts(db_engine, a, [content])
    async with db_engine.begin() as conn:
        await conn.execute(text("UPDATE chunks SET embedding=NULL WHERE document_id=:id"), {"id": doc})
    factory = async_sessionmaker(app_db_engine, sync_session_class=TenantSession)
    async with factory() as session:
        assert await session.scalar(text("SELECT count(*) FROM chunks WHERE search_vector @@ app_private.search_question(:q)"), {"q": question}) == 0
        await session.rollback()
        bind_tenant(session, UUID(a["tenant_id"]))
        rows = await retrieve_sparse(session, UUID(a["tenant_id"]), UUID(a["kb_id"]), MODEL, vector(), question, 30)
        assert {r.document_id for r in rows} == {expected}
        assert await retrieve_sparse(session, UUID(a["tenant_id"]), UUID(b["kb_id"]), MODEL, vector(), question, 30) == []
        tenants = list(await session.scalars(text("SELECT tenant_id FROM chunks WHERE search_vector @@ app_private.search_question(:q)"), {"q": question}))
        assert tenants and set(tenants) == {UUID(a["tenant_id"])}


async def test_sparse_ties_limit_empty(db_engine, app_db_engine, ingestion_accounts):
    a = ingestion_accounts["alpha"]
    await texts(db_engine, a, ["年假 E1001"] * 3)
    async with async_sessionmaker(app_db_engine, sync_session_class=TenantSession)() as session:
        tenant, kb = UUID(a["tenant_id"]), UUID(a["kb_id"])
        bind_tenant(session, tenant)
        rows = await retrieve_sparse(session, tenant, kb, MODEL, vector(), "年假", 2)
        assert len(rows) == 2 and [r.chunk_id for r in rows] == sorted(r.chunk_id for r in rows)
        for q in ("!!!", "ZZ999", "' | ! :* --"):
            assert await retrieve_sparse(session, tenant, kb, MODEL, vector(), q, 30) == []


async def test_runtime_transactions(db_engine, app_db_engine, ingestion_accounts, document_settings):
    a = ingestion_accounts["alpha"]
    await texts(db_engine, a, ["年假十二天"])
    loop_thread = threading.get_ident()
    async with async_sessionmaker(app_db_engine, sync_session_class=TenantSession)() as session:
        bind_tenant(session, UUID(a["tenant_id"]))
        class Embedding(FakeEmbedding):
            def embed_query(self, question):
                assert not session.in_transaction() and threading.get_ident() != loop_thread
                return vector()
        class Reranker:
            def score(self, question, passages):
                assert not session.in_transaction() and threading.get_ident() != loop_thread
                return [1.] * len(passages)
        class Llm(FakeLlm):
            async def generate(self, messages):
                assert not session.in_transaction()
                return await super().generate(messages)
        response = await query(session, UUID(a["tenant_id"]), UUID(a["kb_id"]),
                               RagQueryRequest(question="年假"), document_settings, Embedding(), Llm(), Reranker())
        assert response.sources


@pytest.mark.parametrize("bad", [[], [float("nan")], [float("inf")], ["1"]])
async def test_bad_reranker_safe_503(client, application, ingestion_accounts, db_engine, backends, bad):
    a = ingestion_accounts["alpha"]
    await texts(db_engine, a, ["年假"])
    class Fake:
        def score(self, question, passages): return bad
    application.dependency_overrides[get_reranker_backend] = Fake
    response = await client.post(f"/knowledge-bases/{a['kb_id']}/query", headers=a["headers"], json={"question": "年假"})
    assert response.status_code == 503 and response.json()["detail"] == "Reranking unavailable"
    assert not backends[1].calls


async def test_empty_kb_skips_reranker(client, application, ingestion_accounts, backends):
    class Forbidden:
        def score(self, *args): raise AssertionError("Must not run")
    application.dependency_overrides[get_reranker_backend] = Forbidden
    a = ingestion_accounts["alpha"]
    response = await client.post(f"/knowledge-bases/{a['kb_id']}/query", headers=a["headers"], json={"question": "年假"})
    assert response.status_code == 200 and response.json()["sources"] == []
