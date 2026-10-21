"""Real HTTP + real models, exclusively artificial annual-leave evidence.

Do not run concurrently with pytest. Never sends real business documents.
"""
import asyncio
import json
import secrets
import socket
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from uuid import UUID
import httpx
import uvicorn
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.db.tenant_context import TenantSession
from app.main import create_app
from app.modules.agent.backend import DeepSeekAgentBackend, SYSTEM, get_agent_backend
from app.modules.agent.tools import get_agent_session_factory
from app.modules.chunks.models import Chunk
from app.modules.documents.models import Document
from app.modules.knowledge_bases.models import KnowledgeBase
from app.modules.users.models import User
from app.modules.tenants.models import Tenant
from scripts.prepare_test_database import test_database_settings

TEXT = "正式员工每年享有十二天带薪年假。年假申请需提前三个工作日提交。"
QUESTION = "正式员工每年有几天带薪年假？"


async def verify() -> None:
    settings = test_database_settings(Settings())
    if settings.llm_base_url.rstrip("/") != "https://api.deepseek.com":
        raise RuntimeError("Unapproved LLM endpoint")
    if not settings.deepseek_api_key or not settings.deepseek_api_key.get_secret_value().strip():
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")
    admin = create_async_engine(settings.database_url, hide_parameters=True)
    runtime = create_async_engine(settings.application_database_url, hide_parameters=True)
    factory = async_sessionmaker(runtime, expire_on_commit=False, sync_session_class=TenantSession)
    tenant = None
    document = None
    calls = []
    with TemporaryDirectory(prefix="m8-http-") as directory:
        settings = settings.model_copy(update={"document_storage_root": Path(directory)})
        real = DeepSeekAgentBackend(settings)
        class Audited:
            async def complete(self, messages, *args):
                assert messages[0] == {"role": "system", "content": SYSTEM}
                assert messages[1] == {"role": "user", "content": QUESTION}
                for message in messages[2:]:
                    assert message["role"] in ("assistant", "tool")
                    if message["role"] == "tool":
                        for block in json.loads(message["content"]).get("results", []):
                            evidence = block.get("evidence")
                            if evidence:
                                assert evidence.get("document_id", evidence.get("id")) == str(document)
                                if block["kind"] == "chunk": assert evidence["content"] == TEXT
                serialized = json.dumps(messages, ensure_ascii=False)
                for value in (settings.deepseek_api_key, settings.jwt_secret, settings.postgres_password,
                              settings.app_db_password, settings.migration_db_password):
                    if value: assert value.get_secret_value() not in serialized
                turn = await real.complete(messages, *args)
                calls.append({"tools": [call.name for call in turn.calls]})
                return turn
        app = create_app(settings, database_engine=runtime)
        async def db():
            async with factory() as session: yield session
        app.dependency_overrides[get_db] = db
        app.dependency_overrides[get_settings] = lambda: settings
        app.dependency_overrides[get_agent_session_factory] = lambda: factory
        app.dependency_overrides[get_agent_backend] = Audited
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
        task = asyncio.create_task(server.serve(sockets=[sock]))
        try:
            async with asyncio.timeout(10):
                while not server.started:
                    if task.done(): await task
                    await asyncio.sleep(.05)
            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{sock.getsockname()[1]}", timeout=180) as client:
                tag, password = secrets.token_hex(8), secrets.token_urlsafe(24)
                email = tag + "@example.com"
                result = await client.post("/auth/register", json={"tenant_name": tag, "tenant_slug": tag, "email": email, "password": password})
                result.raise_for_status()
                tenant = UUID(result.json()["tenant"]["id"])
                login = await client.post("/auth/login", json={"email": email, "password": password})
                login.raise_for_status()
                headers = {"Authorization": "Bearer " + login.json()["access_token"]}
                kb = await client.post("/knowledge-bases", headers=headers, json={"name": "M8 artificial acceptance"})
                kb.raise_for_status()
                kb_id = kb.json()["id"]
                uploaded = await client.post(f"/knowledge-bases/{kb_id}/documents", headers=headers,
                    files={"file": ("人工验收.md", TEXT.encode())})
                uploaded.raise_for_status()
                document = UUID(uploaded.json()["id"])
                indexed = await client.post(f"/documents/{document}/index", headers=headers)
                assert indexed.json()["index_status"] == "ready"
                started = perf_counter()
                received = []
                async with client.stream("POST", f"/knowledge-bases/{kb_id}/agent/stream", headers=headers,
                                         json={"question": QUESTION}) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            received.append({"elapsed_seconds": perf_counter()-started, **json.loads(line[6:])})
                final = received[-1]["data"]
                report = {"real_deepseek": True, "provider_calls": calls, "events": received,
                          "total_seconds": perf_counter()-started}
                output = Path(".data/verification/m8.json")
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                assert final["status"] == "completed", "Agent did not complete; see safe local report"
                assert any("search_knowledge_base" in call["tools"] for call in calls)
                assert ("12" in final["answer"] or "十二" in final["answer"]) and "年假" in final["answer"]
                assert final["sources"] and all(s["document_id"] == str(document) for s in final["sources"])
                print(json.dumps({"answer": final["answer"], "sources": final["sources"],
                    "model_calls": len(calls), "elapsed_seconds": report["total_seconds"]}, ensure_ascii=False))
        finally:
            server.should_exit = True
            await task
            sock.close()
            if tenant:
                async with admin.begin() as conn:
                    for model in (Chunk, Document, KnowledgeBase, User):
                        await conn.execute(delete(model).where(model.tenant_id == tenant))
                    await conn.execute(delete(Tenant).where(Tenant.id == tenant))
            await admin.dispose()
            await runtime.dispose()


if __name__ == "__main__":
    asyncio.run(verify())
