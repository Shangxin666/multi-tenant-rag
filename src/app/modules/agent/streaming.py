import asyncio
from uuid import uuid4
from pydantic import TypeAdapter
from starlette.responses import Response
from app.modules.agent.schemas import AgentEvent, AgentError
from app.modules.agent.graph import Context, execute

EVENTS = TypeAdapter(AgentEvent)


class AgentResponse(Response):
    media_type = "text/event-stream"

    def __init__(self, context: Context, question: str, kb_id, *, heartbeat: float = 15, send_timeout: float = 5) -> None:
        super().__init__(content=None, media_type=self.media_type,
                         headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
        self.raw_headers = [(k, v) for k, v in self.raw_headers if k != b"content-length"]
        self.context, self.question, self.kb_id = context, question, kb_id
        self.heartbeat, self.send_timeout = heartbeat, send_timeout
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=8)
        self.seq = 0
        self.run_id = uuid4()
        context.emit = self.emit

    async def emit(self, event: str, data: dict) -> None:
        self.seq += 1
        model = EVENTS.validate_python(dict(event=event, v=1, run_id=self.run_id, seq=self.seq, data=data))
        encoded = f"id: {self.run_id}:{self.seq}\nevent: {event}\ndata: {model.model_dump_json()}\n\n".encode()
        await asyncio.wait_for(self.queue.put(encoded), self.send_timeout)

    async def produce(self) -> None:
        try:
            await self.emit("agent_start", {"knowledge_base_id": self.kb_id})
            state = await execute(self.context, self.question)
            await self.emit("agent_end", state["final"])
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            code = exc.code if isinstance(exc, AgentError) else "timeout" if isinstance(exc, TimeoutError) else "unavailable"
            await self.emit("error", {"code": code, "message": "Agent execution could not complete",
                                      "retryable": code in ("timeout", "unavailable")})
            await self.emit("agent_end", {"status": "failed", "finish_reason": "error", "answer": None,
                "sources": [], "model_calls": self.context.run.model_calls, "tool_attempts": self.context.run.tool_attempts})
        finally:
            # A disconnected/slow client cancels this producer, so no unbounded sentinel wait.
            if not self.queue.full():
                self.queue.put_nowait(None)

    async def __call__(self, scope, receive, send) -> None:
        tasks = []
        async def disconnect() -> None:
            while (await receive())["type"] != "http.disconnect":
                pass
        async def drain(producer: asyncio.Task) -> None:
            while not producer.done() or not self.queue.empty():
                try:
                    data = await asyncio.wait_for(self.queue.get(), self.heartbeat)
                except TimeoutError:
                    data = b": heartbeat\n\n"
                if data is None:
                    break
                await asyncio.wait_for(send({"type": "http.response.body", "body": data, "more_body": True}), self.send_timeout)
            await producer  # Observe errors if queue backpressure prevented error delivery.
            await send({"type": "http.response.body", "body": b"", "more_body": False})
        try:
            await asyncio.wait_for(send({"type": "http.response.start", "status": 200, "headers": self.raw_headers}), self.send_timeout)
            producer = asyncio.create_task(self.produce())
            writer = asyncio.create_task(drain(producer))
            watcher = asyncio.create_task(disconnect())
            tasks = [producer, writer, watcher]
            done, _ = await asyncio.wait([writer, watcher], return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        finally:
            self.context.run.stop.set()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self.context.run.close()
