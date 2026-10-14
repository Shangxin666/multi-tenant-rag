import asyncio
import threading
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update, event, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.chunks.models import Chunk
from app.modules.documents.models import Document
from app.modules.documents import indexing
from app.modules.rag.embedding import get_embedding_backend
from app.modules.rag.generation import get_llm_backend, GenerationError
from app.modules.rag.retrieval import retrieve_chunks
from app.modules.rag.service import NO_ANSWER

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def vector(axis=0, sign=1.0):
    result = [0.0] * 512
    result[axis] = sign
    return result


class FakeEmbedding:
    def __init__(self):
        self.calls = []
    def embed_passages(self, texts):
        self.calls.append(list(texts))
        return [vector() for _ in texts]
    def embed_query(self, question):
        self.calls.append(question)
        return vector()


class FakeLlm:
    def __init__(self): self.calls = []
    async def generate(self, messages):
        self.calls.append(messages)
        return "根据资料回答 [S1]"


@pytest.fixture
def backends(application):
    embedding, llm = FakeEmbedding(), FakeLlm()
    application.dependency_overrides[get_embedding_backend] = lambda: embedding
    application.dependency_overrides[get_llm_backend] = lambda: llm
    return embedding, llm


async def seed(engine, account, count=3, text_status="ready", index_status="pending", model="BAAI/bge-small-zh-v1.5", vectors=None):
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        async with session.begin():
            document = Document(tenant_id=UUID(account["tenant_id"]), knowledge_base_id=UUID(account["kb_id"]),
                filename="guide.md", source_type="markdown", status=text_status, index_status=index_status,
                embedding_model=model if index_status == "ready" else None,
                indexed_at=datetime.now(timezone.utc) if index_status == "ready" else None)
            session.add(document)
            await session.flush()
            for i in range(count):
                session.add(Chunk(tenant_id=document.tenant_id, document_id=document.id, chunk_index=i,
                    content=f"指南第{i}节", chunk_metadata={"page": i + 1, "private": "not-public"},
                    embedding=vectors[i] if vectors is not None else None))
        return document.id


async def stored_vectors(engine, document_id):
    async with async_sessionmaker(engine)() as session:
        values = list(await session.scalars(select(Chunk.embedding).where(Chunk.document_id == document_id).order_by(Chunk.chunk_index)))
        return [list(v) if v is not None else None for v in values]


async def test_index_and_query(client, ingestion_accounts, db_engine, backends):
    a = ingestion_accounts["alpha"]
    document_id = await seed(db_engine, a)
    result = await client.post(f"/documents/{document_id}/index", headers=a["headers"])
    assert result.status_code == 200 and result.json()["index_status"] == "ready"
    assert result.json()["status"] == "ready" and result.json()["indexed_at"]
    assert await stored_vectors(db_engine, document_id) == [vector()] * 3
    for role in ("alpha", "member"):
        response = await client.post(f"/knowledge-bases/{a['kb_id']}/query", headers=ingestion_accounts[role]["headers"], json={"question": " 指南是什么？ "})
        assert response.status_code == 200
        body = response.json()
        assert body["answer"] and len(body["sources"]) == 3
        assert set(body["sources"][0]) == {"source_id", "document_id", "filename", "chunk_index", "page", "title", "distance", "snippet"}
        assert "private" not in response.text and "embedding" not in response.text


@pytest.mark.parametrize("state", ["pending", "failed", "processing", "ready", "text_pending", "text_failed"])
async def test_index_states(client, ingestion_accounts, db_engine, backends, state):
    a = ingestion_accounts["alpha"]
    doc = await seed(db_engine, a, text_status=state[5:] if state.startswith("text_") else "ready",
                     index_status="pending" if state.startswith("text_") else state)
    response = await client.post(f"/documents/{doc}/index", headers=a["headers"])
    assert response.status_code == (200 if state in ("pending", "failed") else 409)


async def test_permissions(client, ingestion_accounts, db_engine, backends):
    a, b, m = [ingestion_accounts[k] for k in ("alpha", "beta", "member")]
    doc = await seed(db_engine, a)
    for headers, code in ((m["headers"], 403), (b["headers"], 404), ({}, 401)):
        assert (await client.post(f"/documents/{doc}/index", headers=headers)).status_code == code
    assert (await client.post(f"/knowledge-bases/{a['kb_id']}/query", headers=b["headers"], json={"question": "q"})).status_code == 404


@pytest.mark.parametrize("case", ["exception", "dimension", "count", "nan", "inf", "zero", "norm", "no_chunks"])
async def test_embedding_failure(client, ingestion_accounts, db_engine, backends, monkeypatch, case):
    a = ingestion_accounts["alpha"]
    doc = await seed(db_engine, a, count=0 if case == "no_chunks" else 3)
    def broken(texts):
        if case == "exception": raise RuntimeError("sensitive backend message")
        if case == "count": return []
        if case == "dimension": return [[1]] * len(texts)
        v = vector()
        v[0] = {"nan": float("nan"), "inf": float("inf"), "zero": 0.0, "norm": 2.0}.get(case, 1)
        return [v] * len(texts)
    monkeypatch.setattr(backends[0], "embed_passages", broken)
    response = await client.post(f"/documents/{doc}/index", headers=a["headers"])
    assert response.status_code == 200 and response.json()["index_status"] == "failed"
    assert response.json()["status"] == "ready" and "sensitive" not in response.text
    assert all(v is None for v in await stored_vectors(db_engine, doc))


async def test_concurrent_claim(client, ingestion_accounts, db_engine, backends, monkeypatch):
    a = ingestion_accounts["alpha"]
    doc = await seed(db_engine, a)
    entered, release = threading.Event(), threading.Event()
    calls = []
    def blocked(texts):
        calls.append(1)
        entered.set()
        assert release.wait(10)
        return [vector()] * len(texts)
    monkeypatch.setattr(backends[0], "embed_passages", blocked)
    first = asyncio.create_task(client.post(f"/documents/{doc}/index", headers=a["headers"]))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        other = await client.post(f"/documents/{doc}/index", headers=a["headers"])
        assert other.status_code == 409
    finally:
        release.set()
        result = await first
    assert result.json()["index_status"] == "ready" and len(calls) == 1


@pytest.mark.parametrize("mode", ["batch", "commit"])
async def test_publish_rollback(client, ingestion_accounts, db_engine, backends, monkeypatch, mode):
    a = ingestion_accounts["alpha"]
    old = [vector(1)] * 101
    doc = await seed(db_engine, a, count=101, index_status="failed", vectors=old)
    original = indexing.write_batch
    calls = []
    async def batch(*args):
        calls.append(1)
        if len(calls) == 2: raise RuntimeError("simulated write failure")
        await original(*args)
    def fail_commit(connection):
        state = connection.scalar(text("SELECT index_status FROM documents WHERE id=:id"), {"id": doc})
        if state == "ready" and not calls:
            calls.append(1)
            raise RuntimeError("simulated commit failure")
    if mode == "batch": monkeypatch.setattr(indexing, "write_batch", batch)
    else: event.listen(db_engine.sync_engine, "commit", fail_commit)
    try:
        response = await client.post(f"/documents/{doc}/index", headers=a["headers"])
    finally:
        if mode == "commit": event.remove(db_engine.sync_engine, "commit", fail_commit)
    assert response.status_code == 200 and response.json()["index_status"] == "failed"
    assert await stored_vectors(db_engine, doc) == old


@pytest.mark.parametrize("field", ["content", "chunk_index", "id", "count"])
async def test_snapshot_changes_rejected(client, ingestion_accounts, db_engine, backends, monkeypatch, field):
    a = ingestion_accounts["alpha"]
    doc = await seed(db_engine, a)
    original = indexing.publish
    async def changed(session, *args):
        assert not session.in_transaction()
        async with db_engine.begin() as conn:
            chunk_id = await conn.scalar(select(Chunk.id).where(Chunk.document_id == doc, Chunk.chunk_index == 0))
            if field == "count": await conn.execute(Chunk.__table__.delete().where(Chunk.id == chunk_id))
            else:
                values = {"content": "changed"} if field == "content" else ({"chunk_index": 99} if field == "chunk_index" else {"id": uuid4()})
                await conn.execute(update(Chunk).where(Chunk.id == chunk_id).values(**values))
        await original(session, *args)
    monkeypatch.setattr(indexing, "publish", changed)
    response = await client.post(f"/documents/{doc}/index", headers=a["headers"])
    assert response.json()["index_status"] == "failed"
    assert all(v is None for v in await stored_vectors(db_engine, doc))


async def test_retrieval_filters_and_distance(client, ingestion_accounts, db_engine, backends):
    a, b = ingestion_accounts["alpha"], ingestion_accounts["beta"]
    doc = await seed(db_engine, a, index_status="ready", vectors=[vector(0, -1), vector(1), vector()])
    await seed(db_engine, b, index_status="ready", vectors=[vector()] * 3)
    kb = (await client.post("/knowledge-bases", headers=a["headers"], json={"name": "other"})).json()
    await seed(db_engine, {**a, "kb_id": kb["id"]}, index_status="ready", vectors=[vector()] * 3)
    await seed(db_engine, a, index_status="ready", model="other-model", vectors=[vector()] * 3)
    await seed(db_engine, a, text_status="failed", vectors=[vector()] * 3)
    await seed(db_engine, a, index_status="failed", vectors=[vector()] * 3)
    await seed(db_engine, a, index_status="ready", vectors=[None] * 3)
    async with async_sessionmaker(db_engine)() as session:
        rows = await retrieve_chunks(session, UUID(a["tenant_id"]), UUID(a["kb_id"]), "BAAI/bge-small-zh-v1.5", vector(), 10)
        assert [r.distance for r in rows] == pytest.approx([0, 1, 2])
        assert {r.document_id for r in rows} == {doc}
        assert len(await retrieve_chunks(session, UUID(a["tenant_id"]), UUID(a["kb_id"]), "BAAI/bge-small-zh-v1.5", vector(), 1)) == 1
    equal = await seed(db_engine, a, index_status="ready", vectors=[vector()] * 3)
    async with async_sessionmaker(db_engine)() as session:
        rows = await retrieve_chunks(session, UUID(a["tenant_id"]), UUID(a["kb_id"]), "BAAI/bge-small-zh-v1.5", vector(), 10)
        tied = [r.chunk_id for r in rows if r.distance == 0]
        assert tied == sorted(tied)


@pytest.mark.parametrize("body", [{"question": " "}, {"question": "x" * 2001}, {"question": "q", "top_k": 0}, {"question": "q", "top_k": 11}, {"question": "q", "tenant_id": "bad"}], ids=["blank", "long", "zero-k", "large-k", "extra"])
async def test_query_validation(client, ingestion_accounts, backends, body):
    a = ingestion_accounts["alpha"]
    assert (await client.post(f"/knowledge-bases/{a['kb_id']}/query", headers=a["headers"], json=body)).status_code == 422


async def test_no_result_skips_backends(client, ingestion_accounts, backends):
    a = ingestion_accounts["alpha"]
    response = await client.post(f"/knowledge-bases/{a['kb_id']}/query", headers=a["headers"], json={"question": "q"})
    assert response.status_code == 200 and response.json() == {"answer": NO_ANSWER, "sources": []}
    assert not backends[0].calls and not backends[1].calls


@pytest.mark.parametrize("mode", ["source", "502", "503", "embedding"])
async def test_query_errors(client, ingestion_accounts, db_engine, backends, monkeypatch, mode):
    a = ingestion_accounts["alpha"]
    await seed(db_engine, a, index_status="ready", vectors=[vector()] * 3)
    async def fail(messages):
        if mode == "source": return "Answer [S999]"
        raise GenerationError(int(mode))
    if mode == "embedding":
        monkeypatch.setattr(backends[0], "embed_query", lambda q: [float("nan")] * 512)
    else: monkeypatch.setattr(backends[1], "generate", fail)
    response = await client.post(f"/knowledge-bases/{a['kb_id']}/query", headers=a["headers"], json={"question": "q"})
    assert response.status_code == (503 if mode in ("503", "embedding") else 502)
    assert "指南" not in response.text and "S999" not in response.text


async def test_inference_has_no_database_transaction(ingestion_accounts, db_engine, document_settings):
    from app.modules.rag.service import query
    from app.modules.rag.schemas import RagQueryRequest
    a = ingestion_accounts["alpha"]
    doc = await seed(db_engine, a)
    tenant, kb = UUID(a["tenant_id"]), UUID(a["kb_id"])
    async with async_sessionmaker(db_engine)() as session:
        class Embedding(FakeEmbedding):
            def embed_passages(self, texts):
                assert not session.in_transaction()
                return super().embed_passages(texts)
            def embed_query(self, question):
                assert not session.in_transaction()
                return super().embed_query(question)
        class Llm(FakeLlm):
            async def generate(self, messages):
                assert not session.in_transaction()
                return await super().generate(messages)
        embedding = Embedding()
        await indexing.claim(session, doc, tenant)
        result = await indexing.process(session, doc, tenant, embedding, document_settings)
        assert result.index_status == "ready"
        await session.rollback()
        response = await query(session, tenant, kb, RagQueryRequest(question="q"), document_settings, embedding, Llm())
        assert response.sources


async def test_commit_ack_failure_does_not_overwrite_ready(client, ingestion_accounts, db_engine, backends, monkeypatch):
    a = ingestion_accounts["alpha"]
    doc = await seed(db_engine, a)
    original = indexing.publish
    async def committed_then_error(*args):
        await original(*args)
        raise RuntimeError("Lost acknowledgement after successful commit")
    monkeypatch.setattr(indexing, "publish", committed_then_error)
    response = await client.post(f"/documents/{doc}/index", headers=a["headers"])
    assert response.status_code == 200 and response.json()["index_status"] == "ready"
    assert await stored_vectors(db_engine, doc) == [vector()] * 3
