import asyncio
import json
import socket
from contextlib import asynccontextmanager
from threading import Event
from uuid import uuid4
import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from app.core.config import Settings
from app.modules.agent.backend import Turn, Call, DeepSeekAgentBackend
from app.modules.agent.graph import Context
from app.modules.agent.runtime import Run, Capacity
from app.modules.agent.streaming import AgentResponse


@asynccontextmanager
async def server(app):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    address = f"http://127.0.0.1:{sock.getsockname()[1]}"
    instance = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", log_level="critical", lifespan="off"))
    task = asyncio.create_task(instance.serve(sockets=[sock]))
    try:
        async with asyncio.timeout(5):
            while not instance.started:
                if task.done(): await task
                await asyncio.sleep(.01)
        yield address
    finally:
        instance.should_exit = True
        await asyncio.wait_for(task, 5)
        sock.close()


async def eventually(predicate):
    async with asyncio.timeout(3):
        while not predicate(): await asyncio.sleep(.01)


def setup(settings, backend, tools=None, **kwargs):
    pool = Capacity()
    assert pool.acquire(1)
    run = Run(10, pool)
    context = Context(run, settings, backend, tools, None)
    response = AgentResponse(context, "人工问题", uuid4(), heartbeat=.05, **kwargs)
    app = FastAPI()
    @app.post("/")
    async def endpoint(): return response
    return app, run, pool, response


@pytest.mark.asyncio
async def test_network_sse_final_order(config_env):
    class Model:
        async def complete(self, *args): return Turn("无工具回答", [])
    app, run, pool, response = setup(Settings(), Model())
    async with server(app) as url, httpx.AsyncClient() as client:
        result = await client.post(url)
    events = [json.loads(line[6:]) for line in result.text.splitlines() if line.startswith("data: ")]
    assert [e["event"] for e in events] == ["agent_start", "answer_delta", "agent_end"]
    assert [e["seq"] for e in events] == [1, 2, 3]
    assert events[1]["data"]["text"] == events[-1]["data"]["answer"]
    assert pool.active == 0


@pytest.mark.asyncio
async def test_disconnect_closes_deepseek_stream(config_env, monkeypatch):
    from pydantic import SecretStr
    from openai import AsyncOpenAI
    from app.modules.agent import backend
    entered, closed = asyncio.Event(), asyncio.Event()
    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            entered.set()
            await asyncio.Event().wait()
            yield b""
        async def aclose(self): closed.set()
    def create(**kwargs):
        return AsyncOpenAI(**kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, headers={"content-type":"text/event-stream"}, stream=Stream()))))
    monkeypatch.setattr(backend, "AsyncOpenAI", create)
    settings = Settings().model_copy(update={"deepseek_api_key": SecretStr("fake-mock-only")})
    app, run, pool, _ = setup(settings, DeepSeekAgentBackend(settings))
    async with server(app) as url, httpx.AsyncClient() as client:
        async with client.stream("POST", url) as response:
            async for line in response.aiter_lines():
                if line.startswith("data:"): break
            await asyncio.wait_for(entered.wait(), 3)
        await eventually(lambda: closed.is_set() and pool.active == 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["lock", "native_cpu"])
async def test_disconnect_local_inference(config_env, monkeypatch, phase):
    from app.modules.rag.reranking import BgeReranker
    entered = asyncio.Event()
    release = Event()
    backend = BgeReranker("fake", "cpu", 1, 512)
    loads = []
    class Native:
        def predict(self, pairs, **kwargs):
            release.wait(5)
            return [1.]
    def load():
        loads.append(1)
        return Native()
    monkeypatch.setattr(backend, "_load", load)
    if phase == "lock": backend._lock.acquire()
    class Model:
        async def complete(self, *args):
            return Turn("", [Call("call1", "search_knowledge_base", '{"query":"q","top_k":1}')])
    app, run, pool, response = setup(Settings(), Model())
    class Tools:
        async def execute(self, *args):
            entered.set()
            await run.cpu(backend.score, "q", ["text"])
            return {"results": []}
    response.context.tools = Tools()
    try:
        async with server(app) as url, httpx.AsyncClient() as client:
            async with client.stream("POST", url) as stream:
                async for line in stream.aiter_lines():
                    if line.startswith("data:"): break
                await asyncio.wait_for(entered.wait(), 3)
                if phase == "native_cpu": await eventually(lambda: bool(loads))
            await eventually(lambda: run.closed)
            if phase == "lock":
                await eventually(lambda: pool.active == 0)
                assert loads == []
            else:
                assert pool.active == 1 and not pool.acquire(1)
                release.set()
                await eventually(lambda: pool.active == 0)
    finally:
        release.set()
        if phase == "lock": backend._lock.release()


@pytest.mark.asyncio
async def test_slow_send_backpressure_cancels(config_env):
    class Model:
        async def complete(self, *args):
            await response.emit("answer_delta", {"text": "test"})
            for _ in range(30): await response.emit("answer_delta", {"text": "test"})
            return Turn("done", [])
    _, run, pool, response = setup(Settings(), Model(), send_timeout=.05)
    blocked = asyncio.Event()
    async def receive():
        await asyncio.Event().wait()
    async def send(message):
        if message["type"] == "http.response.body":
            blocked.set()
            await asyncio.Event().wait()
    with pytest.raises(TimeoutError):
        await response({}, receive, send)
    assert blocked.is_set() and run.closed and pool.active == 0
    assert response.queue.qsize() <= 8


@pytest.mark.asyncio
async def test_deadline_error_and_end(config_env):
    class Model:
        async def complete(self, *args): await asyncio.Event().wait()
    app, run, pool, _ = setup(Settings(), Model())
    from time import monotonic
    run.deadline = monotonic() + .1
    async with server(app) as url, httpx.AsyncClient() as client:
        response = await client.post(url)
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert [e["event"] for e in events] == ["agent_start", "error", "agent_end"]
    assert events[-1]["data"]["status"] == "failed" and pool.active == 0
