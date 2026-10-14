"""Explicit real-model/real-HTTP acceptance, never collected by pytest.

Uses the configured dedicated test database and temporary storage. Deletes only
the tenants created by this run. No fake embedding or LLM is injected.
"""
import asyncio
import argparse
import json
import secrets
import socket
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

import httpx
import uvicorn
from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.main import create_app
from app.modules.chunks.models import Chunk
from app.modules.documents.models import Document
from app.modules.knowledge_bases.models import KnowledgeBase
from app.modules.users.models import User
from app.modules.tenants.models import Tenant
from app.core.security import hash_password
from app.modules.rag.embedding import get_embedding_backend
from app.modules.rag.retrieval import retrieve_chunks
from app.modules.rag.generation import DeepSeekBackend, SYSTEM_PROMPT, get_llm_backend
from app.modules.rag.context import build_context
from scripts.prepare_test_database import test_database_settings


async def verify(skip_llm: bool = False) -> None:
    settings = test_database_settings(Settings())
    assert settings.llm_base_url.rstrip("/") == "https://api.deepseek.com", "Unapproved LLM endpoint"
    if not skip_llm:
        assert settings.deepseek_api_key and settings.deepseek_api_key.get_secret_value().strip(), "DEEPSEEK_API_KEY is not configured"
    if skip_llm:
        settings = settings.model_copy(update={"deepseek_api_key": None})
    engine = create_async_engine(settings.database_url, hide_parameters=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    tenants = []
    with TemporaryDirectory(prefix="m5-http-") as directory:
        settings = settings.model_copy(update={"document_storage_root": Path(directory)})
        app = create_app(settings)
        async def db():
            async with factory() as session:
                yield session
        app.dependency_overrides[get_db] = db
        app.dependency_overrides[get_settings] = lambda: settings
        approved_text = "正式员工每年享有十二天带薪年假。年假申请需提前三个工作日提交。"
        question = "正式员工每年有几天带薪年假？"
        expected_context = "[S1]\n" + json.dumps({
            "document": "中文验收.md", "page": None, "title": None, "content": approved_text,
        }, ensure_ascii=False)
        llm_calls = []
        real_backend = DeepSeekBackend(settings)
        class AuditedRealBackend:
            async def generate(self, messages: list[dict[str, str]]) -> str:
                assert messages == [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps({"Question": question, "Context": expected_context}, ensure_ascii=False)},
                ], "Unapproved outgoing content"
                llm_calls.append(1)
                return await real_backend.generate(messages)
        app.dependency_overrides[get_llm_backend] = lambda: AuditedRealBackend()
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        task = asyncio.create_task(server.serve(sockets=[sock]))
        try:
            for _ in range(100):
                if server.started: break
                await asyncio.sleep(0.05)
            assert server.started
            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=600) as client:
                accounts = []
                for _ in range(2):
                    tag, password = secrets.token_hex(8), secrets.token_urlsafe(24)
                    email = tag + "@example.com"
                    result = await client.post("/auth/register", json={"tenant_name": tag, "tenant_slug": tag, "email": email, "password": password})
                    assert result.status_code == 201
                    tenant = UUID(result.json()["tenant"]["id"])
                    tenants.append(tenant)
                    login = await client.post("/auth/login", json={"email": email, "password": password})
                    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
                    kb = await client.post("/knowledge-bases", headers=headers, json={"name": "M5 acceptance"})
                    accounts.append((tenant, headers, UUID(kb.json()["id"])))
                tenant, headers, kb = accounts[0]
                _, other_headers, other_kb = accounts[1]
                uploaded = await client.post(f"/knowledge-bases/{kb}/documents", headers=headers,
                    files={"file": ("中文验收.md", approved_text.encode("utf-8"))})
                assert uploaded.status_code == 201
                data = uploaded.json()
                assert data["status"] == "ready" and data["index_status"] == "pending"
                doc = UUID(data["id"])
                print("PASS real HTTP upload: text ready / index pending", flush=True)
                indexed = await client.post(f"/documents/{doc}/index", headers=headers)
                assert indexed.status_code == 200 and indexed.json()["index_status"] == "ready", "Real indexing failed"
                async with factory() as session:
                    rows = (await session.execute(select(Chunk.embedding, func.vector_dims(Chunk.embedding)).where(Chunk.document_id == doc))).all()
                    assert rows and all(v is not None and dim == 512 for v, dim in rows)
                    document = await session.get(Document, doc)
                    assert document.embedding_model == settings.embedding_model
                print("PASS real BGE indexing and PostgreSQL VECTOR(512)", flush=True)
                vector = await asyncio.to_thread(get_embedding_backend(settings).embed_query, question)
                async with factory() as session:
                    hits = await retrieve_chunks(session, tenant, kb, settings.embedding_model, vector, 5)
                    assert hits and hits[0].document_id == doc and "十二天" in hits[0].content
                    actual_context = build_context(hits, settings.max_rag_context_chars)
                    assert actual_context.text == expected_context
                print("PASS real BGE query and exact pgvector retrieval", flush=True)
                member_password = secrets.token_urlsafe(24)
                member_email = secrets.token_hex(8) + "@example.com"
                encoded = await hash_password(member_password)
                async with factory() as session:
                    async with session.begin():
                        session.add(User(tenant_id=tenant, email=member_email, password_hash=encoded, role="member"))
                login = await client.post("/auth/login", json={"email": member_email, "password": member_password})
                member_headers = {"Authorization": "Bearer " + login.json()["access_token"]}
                assert (await client.post(f"/documents/{doc}/index", headers=member_headers)).status_code == 403
                assert (await client.post(f"/documents/{doc}/index", headers=other_headers)).status_code == 404
                assert (await client.post(f"/knowledge-bases/{kb}/query", headers=other_headers, json={"question": question})).status_code == 404
                empty = await client.post(f"/knowledge-bases/{other_kb}/query", headers=other_headers, json={"question": question})
                assert empty.status_code == 200 and empty.json()["sources"] == []
                assert empty.json()["answer"] == "当前知识库中没有足够的信息回答该问题"
                assert llm_calls == [], "Empty/cross-tenant query must not invoke LLM"
                print("PASS real HTTP member index 403, tenant isolation, empty KB no-answer", flush=True)
                if skip_llm or not settings.deepseek_api_key or not settings.deepseek_api_key.get_secret_value().strip():
                    print("NOT VERIFIED: real DeepSeek answer and member query; LLM disabled or key not configured", flush=True)
                else:
                    for role, identity in (("admin", headers), ("member", member_headers)):
                        answer = await client.post(f"/knowledge-bases/{kb}/query", headers=identity, json={"question": question})
                        assert answer.status_code == 200, "Real provider query failed"
                        body = answer.json()
                        assert body["sources"] and all(s["document_id"] == str(doc) for s in body["sources"])
                        assert "[S1]" in body["answer"] and any(v in body["answer"] for v in ("十二", "12"))
                        assert "带薪年假" in body["answer"]
                        assert body["sources"] == [s.model_dump(mode="json") for s in actual_context.sources]
                        print(json.dumps({"role": role, "answer": body["answer"], "sources": body["sources"]}, ensure_ascii=False), flush=True)
                    assert len(llm_calls) == 2
                    print("PASS real DeepSeek admin/member answer and sources", flush=True)
        finally:
            server.should_exit = True
            await task
            sock.close()
            async with engine.begin() as connection:
                for model in (Chunk, Document, KnowledgeBase, User):
                    await connection.execute(delete(model).where(model.tenant_id.in_(tenants)))
                await connection.execute(delete(Tenant).where(Tenant.id.in_(tenants)))
            await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-llm", action="store_true", help="Never send document content to an external LLM")
    asyncio.run(verify(skip_llm=parser.parse_args().skip_llm))
