from app.observability.trace import traced, count
import asyncio
import json
from dataclasses import dataclass
from typing import TypedDict, Callable, Awaitable
from uuid import uuid4
from pydantic import ValidationError
from langgraph.graph import StateGraph, START, END
from langsmith import tracing_context

from app.core.config import Settings
from app.modules.agent.backend import AgentBackend, Call, SYSTEM, parse_arguments
from app.modules.agent.runtime import Run
from app.modules.agent.schemas import AgentError, SearchArgs, DocumentArgs
from app.modules.agent.sources import Sources
from app.modules.agent.tools import ToolBackend


class AgentState(TypedDict):
    messages: list[dict]  # Full evidence only here, never streamed to clients.
    sources: Sources    # Identity/public metadata only; no duplicate full evidence.
    pending_tool_calls: list[Call]  # One pending turn, cleared after execution.
    model_calls: int
    tool_attempts: int
    tool_rounds: int
    reserved_output_tokens: int
    candidate_answer: str
    final: dict | None


@dataclass
class Context:
    run: Run
    settings: Settings
    backend: AgentBackend
    tools: ToolBackend
    emit: Callable[[str, dict], Awaitable[None]]


def build_graph(context: Context):
    async def llm(state: AgentState) -> dict:
        if state["model_calls"] >= 5:
            raise AgentError("budget_exceeded")
        allow = state["tool_attempts"] < 4 and state["tool_rounds"] < 4 and state["model_calls"] < 4
        tokens = 1024 if allow else 2048
        if state["reserved_output_tokens"] + tokens > 8192:
            raise AgentError("budget_exceeded")
        messages = [{"role": "system", "content": SYSTEM}] + state["messages"]
        if len(json.dumps(messages, ensure_ascii=False)) > 24000:
            raise AgentError("budget_exceeded")
        # Reserve before await; provider errors never enable uncounted retry.
        state["model_calls"] += 1
        context.run.model_calls = state["model_calls"]
        count(model_calls=state["model_calls"])
        state["reserved_output_tokens"] += tokens
        timeout = context.run.remaining(context.settings.agent_model_timeout_seconds)
        async with asyncio.timeout(timeout):
            turn = await context.backend.complete(messages, allow, tokens, timeout)
        if len(turn.content) > 12000 or len(turn.calls) > 2 or (turn.calls and not allow):
            raise AgentError("invalid_model_output")
        used_ids = {c["id"] for m in state["messages"] for c in m.get("tool_calls", [])}
        if len({c.id for c in turn.calls}) != len(turn.calls) or any(c.id in used_ids or not c.id for c in turn.calls):
            raise AgentError("invalid_model_output")
        if turn.calls:
            message = {"role": "assistant", "content": turn.content or None, "tool_calls": [
                {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
                for c in turn.calls]}
            return {"messages": state["messages"] + [message], "pending_tool_calls": turn.calls,
                    "model_calls": state["model_calls"], "reserved_output_tokens": state["reserved_output_tokens"]}
        if not turn.content.strip():
            raise AgentError("invalid_model_output")
        return {"candidate_answer": turn.content, "pending_tool_calls": [],
                "model_calls": state["model_calls"], "reserved_output_tokens": state["reserved_output_tokens"]}

    async def tools(state: AgentState) -> dict:
        calls = state["pending_tool_calls"]
        if state["tool_attempts"] + len(calls) > 4:
            raise AgentError("budget_exceeded")
        messages = list(state["messages"])
        for call in calls:
            context.run.remaining()
            state["tool_attempts"] += 1
            context.run.tool_attempts = state["tool_attempts"]
            count(tool_attempts=state["tool_attempts"])
            call_id = uuid4()
            known = call.name in ("search_knowledge_base", "get_document_info")
            if known:
                await context.emit("tool_start", {"call_id": call_id, "tool": call.name})
            code = None
            try:
                if not known:
                    raise AgentError("invalid_tool")
                schema = SearchArgs if call.name == "search_knowledge_base" else DocumentArgs
                try:
                    args = schema.model_validate(parse_arguments(call.arguments))
                except ValidationError:
                    raise AgentError("invalid_arguments") from None
                async with asyncio.timeout(context.run.remaining(context.settings.agent_tool_timeout_seconds)):
                    result = await context.tools.execute(call.name, args, state["sources"])
            except AgentError as exc:
                if exc.code not in ("invalid_tool", "invalid_arguments", "resource_not_found"):
                    raise
                code = exc.code
                count(**{code: 1})
                result = {"results": [], "error_code": code}
            body = json.dumps(result, ensure_ascii=False)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": body})
            if len(json.dumps(messages, ensure_ascii=False)) > 23000:
                raise AgentError("budget_exceeded")
            if known:
                await context.emit("tool_result", {"call_id": call_id, "tool": call.name,
                    "status": "error" if code else "ok" if result["results"] else "empty",
                    "source_ids": [r["source_id"] for r in result["results"]], "error_code": code})
        return {"messages": messages, "pending_tool_calls": [], "tool_attempts": state["tool_attempts"],
                "tool_rounds": state["tool_rounds"] + 1, "sources": state["sources"]}

    @traced("agent.finalize")
    async def finalize(state: AgentState) -> dict:
        answer, sources, reason = state["sources"].finalize(state["candidate_answer"])
        final = {"status": "completed", "finish_reason": reason, "answer": answer,
                 "sources": [s.model_dump(mode="json") for s in sources],
                 "model_calls": state["model_calls"], "tool_attempts": state["tool_attempts"]}
        for start in range(0, len(answer), 512):
            await context.emit("answer_delta", {"text": answer[start:start+512]})
        return {"final": final}

    graph = StateGraph(AgentState)
    graph.add_node("llm", llm)
    graph.add_node("tools", tools)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "llm")
    graph.add_conditional_edges("llm", lambda state: "tools" if state["pending_tool_calls"] else "finalize")
    graph.add_edge("tools", "llm")
    graph.add_edge("finalize", END)
    return graph.compile()


@traced("agent.run", root=True)
async def execute(context: Context, question: str) -> AgentState:
    state = AgentState(messages=[{"role": "user", "content": question}], sources=Sources(),
        pending_tool_calls=[], model_calls=0, tool_attempts=0, tool_rounds=0,
        reserved_output_tokens=0, candidate_answer="", final=None)
    # Explicitly disable external trace upload even if a deployment sets tracing env vars.
    with tracing_context(enabled=False):
        async with asyncio.timeout(context.run.remaining()):
            return await build_graph(context).ainvoke(state, config={"recursion_limit": 16, "callbacks": []})
