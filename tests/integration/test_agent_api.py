import asyncio
import json
from uuid import UUID
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.db.tenant_context import TenantSession
from app.modules.users.models import User
from app.modules.agent.backend import Turn, Call, get_agent_backend
from app.modules.agent.runtime import capacity, Run, Scope
from app.modules.agent.tools import ReadTools
from app.modules.agent.sources import Sources
from app.modules.agent.schemas import DocumentArgs, SearchArgs, AgentError
from test_rag import seed, vector, backends

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


class Model:
    def __init__(self, document=None): self.calls = 0; self.document = document
    async def complete(self, messages, *args):
        self.calls += 1
        if self.calls == 1:
            name, params = ("get_document_info", {"document_id": str(self.document)}) if self.document else ("search_knowledge_base", {"query": "指南", "top_k": 5})
            return Turn("", [Call("id1", name, json.dumps(params))])
        return Turn("根据证据 [S1]", [])


@pytest.mark.parametrize("role", ["alpha", "member"])
async def test_agent_search_and_schema(client, application, ingestion_accounts, db_engine, backends, role):
    account = ingestion_accounts[role]
    await seed(db_engine, account, index_status="ready", vectors=[vector()] * 3)
    application.dependency_overrides[get_agent_backend] = Model
    response = await client.post(f"/knowledge-bases/{account['kb_id']}/agent/stream", headers=account["headers"], json={"question": "指南"})
    assert response.status_code == 200 and "text/event-stream" in response.headers["content-type"]
    result = events(response)
    assert [e["event"] for e in result] == ["agent_start", "tool_start", "tool_result", "answer_delta", "agent_end"]
    assert result[-1]["data"]["sources"][0]["kind"] == "chunk"
    assert all(secret not in response.text for secret in ("storage_key", "password_hash", "Authorization", "reasoning_content", "private"))
    assert capacity.active == 0


async def test_preflight_scope_auth_validation_and_capacity(client, application, ingestion_accounts):
    a, b = ingestion_accounts["alpha"], ingestion_accounts["beta"]
    application.dependency_overrides[get_agent_backend] = Model
    url = f"/knowledge-bases/{a['kb_id']}/agent/stream"
    assert (await client.post(url, json={"question": "q"})).status_code == 401
    assert (await client.post(url, headers=b["headers"], json={"question": "q"})).status_code == 404
    assert (await client.post(url, headers=a["headers"], json={"question": "q", "tenant_id": b["tenant_id"]})).status_code == 422
    old = capacity.active
    capacity.active = 100
    try:
        assert (await client.post(url, headers=a["headers"], json={"question": "q"})).status_code == 429
    finally:
        capacity.active = old


async def test_search_tool_excludes_other_tenant_and_kb(client, application, ingestion_accounts, db_engine, backends):
    a, b = ingestion_accounts["alpha"], ingestion_accounts["beta"]
    own = await seed(db_engine, a, index_status="ready", vectors=[vector()] * 3)
    await seed(db_engine, b, index_status="ready", vectors=[vector()] * 3)
    other_kb = (await client.post("/knowledge-bases", headers=a["headers"], json={"name": "Other search KB"})).json()
    await seed(db_engine, {**a, "kb_id": other_kb["id"]}, index_status="ready", vectors=[vector()] * 3)
    application.dependency_overrides[get_agent_backend] = Model
    response = await client.post(f"/knowledge-bases/{a['kb_id']}/agent/stream", headers=a["headers"], json={"question": "指南"})
    result = events(response)
    assert result[-1]["data"]["status"] == "completed"
    assert {s["document_id"] for s in result[-1]["data"]["sources"]} == {str(own)}
    # Inspect every admitted tool source, not only the final answer's citation subset.
    assert next(e for e in result if e["event"] == "tool_result")["data"]["source_ids"] == ["S1", "S2", "S3"]


async def test_document_tool_scope_and_status_evidence(client, application, ingestion_accounts, db_engine, app_db_engine, document_settings, backends):
    a, b = ingestion_accounts["alpha"], ingestion_accounts["beta"]
    own = await seed(db_engine, a)
    foreign = await seed(db_engine, b)
    other_kb = (await client.post("/knowledge-bases", headers=a["headers"], json={"name": "Other"})).json()
    other = await seed(db_engine, {**a, "kb_id": other_kb["id"]})
    async with async_sessionmaker(db_engine)() as session:
        user = await session.scalar(select(User.id).where(User.tenant_id == UUID(a["tenant_id"]), User.role == "admin"))
    run = Run(5, capacity)
    factory = async_sessionmaker(app_db_engine, sync_session_class=TenantSession)
    tools = ReadTools(Scope(user, UUID(a["tenant_id"]), UUID(a["kb_id"])), factory, document_settings,
                      backends[0], None, run, 5)
    for document in (foreign, other):
        with pytest.raises(AgentError, match="resource_not_found"):
            await tools.execute("get_document_info", DocumentArgs(document_id=document), Sources())
    application.dependency_overrides[get_agent_backend] = lambda: Model(own)
    response = await client.post(f"/knowledge-bases/{a['kb_id']}/agent/stream", headers=a["headers"], json={"question": "文档状态"})
    end = events(response)[-1]["data"]
    assert end["finish_reason"] == "document_info"
    assert end["sources"][0]["kind"] == "document" and "pending" in end["answer"]


async def test_disconnect_during_real_database_query(app_db_engine):
    from fastapi import FastAPI
    import httpx
    # Network helper is deliberately shared with unit transport tests, not production.
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("agent_network_helpers", Path(__file__).parents[1]/"unit"/"test_agent_streaming.py")
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    from app.core.config import Settings
    entered, closed = asyncio.Event(), asyncio.Event()
    app, run, pool, response = helpers.setup(Settings(), Model())
    class Tools:
        async def execute(self, *args):
            try:
                async with async_sessionmaker(app_db_engine, sync_session_class=TenantSession)() as session:
                    # Real asyncpg cancellation while a transaction is active.
                    entered.set()
                    await session.execute(text("SELECT pg_sleep(10)"))
            finally:
                closed.set()
            return {"results": []}
    response.context.tools = Tools()
    async with helpers.server(app) as url, httpx.AsyncClient() as client:
        async with client.stream("POST", url) as stream:
            async for line in stream.aiter_lines():
                if line.startswith("data:"): break
            await asyncio.wait_for(entered.wait(), 3)
            await asyncio.sleep(.1)
        await helpers.eventually(lambda: closed.is_set() and pool.active == 0)
    async with app_db_engine.connect() as conn:
        assert await conn.scalar(text("SELECT 1")) == 1
        assert await conn.scalar(text("SELECT NULLIF(current_setting('app.tenant_id',true),'')")) is None
