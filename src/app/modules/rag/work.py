"""Optional cooperative cancellation at model locks; ordinary RAG is unchanged."""
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Event, Lock
from time import monotonic
from collections.abc import Iterator

inference_control: ContextVar[tuple[Event, float] | None] = ContextVar("inference_control", default=None)


@contextmanager
def inference_lock(lock: Lock) -> Iterator[None]:
    control = inference_control.get()
    if control is None:
        with lock:
            yield
        return
    stop, deadline = control
    while not stop.is_set() and monotonic() < deadline:
        if lock.acquire(timeout=0.05):
            try:
                if stop.is_set() or monotonic() >= deadline:
                    raise TimeoutError("Inference cancelled")
                yield
            finally:
                lock.release()
            return
    raise TimeoutError("Inference cancelled")
