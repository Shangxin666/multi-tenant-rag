import asyncio
import json
from uuid import uuid4
import pytest
from app.core.config import Settings
from app.modules.agent.backend import Turn, Call, parse_arguments
from app.modules.agent.graph import Context, execute
from app.modules.agent.runtime import Capacity, Run
from app.modules.agent.sources import Sources
from app.modules.agent.schemas import AgentError
from app.modules.rag.retrieval import RetrievedChunk


class FakeModel:
    def __init__(self, turns): self.turns, self.messages = list(turns), []
    async def complete(self, messages, allow_tools, max_tokens, timeout):
        self.messages.append(messages)
        assert timeout > 0
        return self.turns.pop(0)


class FakeTools:
    def __init__(self): self.calls = []
    async def execute(self, name, args, sources):
        self.calls.append((name, args))
        row = RetrievedChunk(uuid4(), uuid4(), "人工.md", 0, "员工年假十二天", None, .1)
        return {"results": [sources.chunk(row)]}


def search(i=1, **kwargs):
    return Turn("", [Call(str(i), "search_knowledge_base", json.dumps({"query": "年假", "top_k": 5, **kwargs}))])


async def run_graph(config_env, turns, tools=None):
    pool = Capacity()
    assert pool.acquire(1)
    run = Run(5, pool)
    events = []
    async def emit(event, data): events.append((event, data))
    context = Context(run, Settings(), FakeModel(turns), tools or FakeTools(), emit)
    try:
        result = await execute(context, "年假？")
        return result, events, context
    finally:
        run.close()
        assert pool.active == 0


@pytest.mark.asyncio
async def test_real_langgraph_search_answer(config_env):
    result, events, context = await run_graph(config_env, [search(), Turn("十二天 [S1]", [])])
    assert result["final"]["answer"] == "十二天 [S1]"
    assert result["model_calls"] == 2 and not result["pending_tool_calls"]
    assert [event for event, _ in events] == ["tool_start", "tool_result", "answer_delta"]
    assert len(result["sources"].items) == 1
    assert sum("员工年假十二天" in str(m) for m in result["messages"]) == 1


@pytest.mark.asyncio
async def test_multiple_tools_and_recovery(config_env):
    turns = [Turn("", [Call("bad", "not_allowed", "{}")]), search(2, tenant_id="evil"),
             search(3), Turn("有证据 [S1]", [])]
    result, events, context = await run_graph(config_env, turns)
    assert result["tool_attempts"] == 3 and len(context.tools.calls) == 1
    assert any(data.get("error_code") == "invalid_arguments" for _, data in events)
    assert all("evil" not in str(data) for _, data in events)


@pytest.mark.asyncio
async def test_direct_no_evidence_is_controlled(config_env):
    result, _, context = await run_graph(config_env, [Turn("编造的知识库事实", [])])
    assert result["final"]["finish_reason"] == "no_evidence"
    assert "编造" not in result["final"]["answer"] and not context.tools.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", ["十二天", "十二天 [S999]", "十二天 S1"])
async def test_invalid_citations_never_emit_answer(config_env, answer):
    with pytest.raises(AgentError, match="invalid_citation"):
        await run_graph(config_env, [search(), Turn(answer, [])])


@pytest.mark.asyncio
async def test_tool_budget_and_duplicate_call_ids(config_env):
    with pytest.raises(AgentError, match="invalid_model_output"):
        await run_graph(config_env, [search(i) for i in range(5)])
    with pytest.raises(AgentError, match="invalid_model_output"):
        await run_graph(config_env, [search(), search()])


@pytest.mark.parametrize("raw", ['{"x":1,"x":2}', '[]', '{', '{"x":NaN}', 'x'*4097])
def test_bad_json(raw):
    with pytest.raises(AgentError): parse_arguments(raw)


def test_sources_dedup_budget_and_status_only():
    sources = Sources()
    row = RetrievedChunk(uuid4(), uuid4(), "test.md", 0, "内容", None, .2)
    assert sources.chunk(row)["source_id"] == "S1"
    assert sources.chunk(row) == {"source_id": "S1", "already_provided": True}
    large = RetrievedChunk(uuid4(), uuid4(), "large", 1, "x"*12000, None, .3)
    assert sources.chunk(large) is None and len(sources.items) == 1
    info = Sources()
    info.add("document", "doc", {"document_id": uuid4(), "filename": "file", "snippet": '{"status":"ready"}'}, {"status": "ready"})
    answer, _, reason = info.finalize("这份文档证明员工年假一百天 [S1]")
    assert reason == "document_info" and "一百天" not in answer and "ready" in answer
