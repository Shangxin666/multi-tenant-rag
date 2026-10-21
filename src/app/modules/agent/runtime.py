import asyncio
from dataclasses import dataclass
from threading import Event
from time import monotonic
from typing import Any, Callable
from uuid import UUID

from app.modules.rag.work import inference_control
from app.modules.agent.schemas import AgentError


@dataclass(frozen=True)
class Scope:
    user_id: UUID
    tenant_id: UUID
    knowledge_base_id: UUID


class Capacity:
    """Event-loop-owned admission; no waiting queue. CPU work retains its slot."""
    def __init__(self) -> None:
        self.active = 0

    def acquire(self, limit: int) -> bool:
        if self.active >= limit:
            return False
        self.active += 1
        return True


capacity = Capacity()


class Run:
    def __init__(self, timeout: float, pool: Capacity) -> None:
        self.deadline = monotonic() + timeout
        self.stop = Event()
        self.pool = pool
        self.jobs: set[asyncio.Task] = set()
        self.model_calls = 0
        self.tool_attempts = 0
        self.closed = False
        self.released = False

    def remaining(self, maximum: float | None = None) -> float:
        value = self.deadline - monotonic()
        if self.stop.is_set() or value <= 0:
            raise AgentError("timeout")
        return min(value, maximum) if maximum is not None else value

    def _finished(self, task: asyncio.Task) -> None:
        self.jobs.discard(task)
        if not task.cancelled():
            task.exception()  # Observe discarded worker exceptions, never print inputs.
        self._release()

    def _release(self) -> None:
        if self.closed and not self.jobs and not self.released:
            self.pool.active -= 1
            self.released = True

    async def cpu(self, function: Callable, *args: Any) -> Any:
        self.remaining()
        token = inference_control.set((self.stop, self.deadline))
        try:
            task = asyncio.create_task(asyncio.to_thread(function, *args))
        finally:
            inference_control.reset(token)
        self.jobs.add(task)
        task.add_done_callback(self._finished)
        # Cancelling the await never pretends the native CPU operation was killed.
        return await asyncio.shield(task)

    def close(self) -> None:
        self.stop.set()
        self.closed = True
        self._release()
