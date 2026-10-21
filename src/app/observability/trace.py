"""Only fixed names, numeric counters and enumerated errors cross this boundary.

No arguments, return values, exception messages or identities are captured.
Evaluation can capture traces explicitly without enabling production logging.
"""
import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from time import monotonic
from uuid import uuid4
from typing import Any, Callable

NAMES = frozenset({'rag.query', 'retrieval', 'query_embedding', 'dense_search', 'sparse_search',
    'rrf', 'rerank', 'context', 'llm', 'citation_validation', 'agent.stream', 'agent.run',
    'tool', 'agent.finalize'})
ERRORS = frozenset({'invalid_tool', 'invalid_arguments', 'resource_not_found', 'budget_exceeded',
    'timeout', 'unavailable', 'invalid_model_output', 'invalid_citation', 'forbidden', 'cancelled', 'internal'})
COUNTERS = frozenset({'candidates', 'sources', 'context_chars', 'model_calls', 'tool_attempts',
    'invalid_arguments', 'invalid_tool', 'first_event_ms', 'answer_ready_ms', 'cpu_jobs_at_disconnect'})
active: ContextVar['Trace | None'] = ContextVar('safe_trace', default=None)
current_span: ContextVar[dict | None] = ContextVar('safe_span', default=None)
_sink: Callable[[dict], None] | None = None


def configure(path: Path | None) -> None:
    global _sink
    logger = logging.getLogger('app.safe_trace')
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    logger.propagate = False
    _sink = None
    if path is not None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=2, encoding='utf-8')
            handler.setFormatter(logging.Formatter('%(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            _sink = lambda record: logger.info(json.dumps(record, ensure_ascii=True))
        except Exception:
            pass  # Observation must not prevent application startup.


class Trace:
    def __init__(self) -> None:
        self.id = str(uuid4())
        self.started = monotonic()
        self.spans: list[dict] = []
        self.closed = False
        self.dropped = 0

    def summary(self) -> dict:
        calls = [s for s in self.spans if s['name'] == 'llm']
        known = [s['usage'] for s in calls if s.get('usage') is not None]
        return {'version': 1, 'trace_id': self.id, 'duration_ms': (monotonic()-self.started)*1000,
                'spans': self.spans, 'dropped_spans': self.dropped,
                'usage': {'calls': len(calls), 'reported_calls': len(known),
                          'complete': len(known) == len(calls),
                          'prompt_tokens': sum(u['prompt_tokens'] for u in known),
                          'completion_tokens': sum(u['completion_tokens'] for u in known),
                          'total_tokens': sum(u['total_tokens'] for u in known)}}


@contextmanager
def capture():
    trace = Trace()
    token = active.set(trace)
    parent = current_span.set(None)
    try:
        yield trace
    finally:
        trace.closed = True
        current_span.reset(parent)
        active.reset(token)


@contextmanager
def span(name: str):
    trace = active.get()
    if trace is None or trace.closed or name not in NAMES:
        yield
        return
    if len(trace.spans) >= 128:
        trace.dropped += 1
        yield
        return
    parent = current_span.get()
    row = {'span_id': str(uuid4()), 'parent_span_id': parent['span_id'] if parent else None,
           'name': name, 'start_ms': (monotonic()-trace.started)*1000, 'status': 'ok', 'usage': None}
    trace.spans.append(row)
    token = current_span.set(row)
    started = monotonic()
    try:
        yield
    except BaseException as exc:
        row['status'] = 'cancelled' if isinstance(exc, asyncio.CancelledError) else 'error'
        code = 'cancelled' if isinstance(exc, asyncio.CancelledError) else 'timeout' if isinstance(exc, TimeoutError) else getattr(exc, 'code', 'internal')
        row['error_code'] = code if isinstance(code, str) and code in ERRORS else 'internal'
        raise
    finally:
        row['duration_ms'] = (monotonic()-started)*1000
        current_span.reset(token)


def count(**values: int | float) -> None:
    trace, row = active.get(), current_span.get()
    if trace is None or trace.closed or row is None:
        return
    import math
    for key, value in values.items():
        if key in COUNTERS and type(value) in (int, float) and math.isfinite(value) and value >= 0:
            row[key] = value


def usage(value: Any) -> None:
    trace, row = active.get(), current_span.get()
    if trace is None or trace.closed or row is None or value is None:
        return
    fields = {name: getattr(value, name, None) for name in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
    if all(type(v) is int and v >= 0 for v in fields.values()) and fields['total_tokens'] == fields['prompt_tokens'] + fields['completion_tokens']:
        row['usage'] = fields  # Last cumulative report replaces, never adds duplicate usage chunks.


def traced(name: str, *, root: bool = False):
    def decorate(fn):
        if asyncio.iscoroutinefunction(fn):
            @wraps(fn)
            async def call(*args, **kwargs):
                if root and active.get() is None and _sink is not None:
                    with capture() as trace:
                        try:
                            with span(name):
                                return await fn(*args, **kwargs)
                        finally:
                            try:
                                _sink(trace.summary())
                            except Exception:
                                pass
                with span(name):
                    return await fn(*args, **kwargs)
        else:
            @wraps(fn)
            def call(*args, **kwargs):
                with span(name):
                    return fn(*args, **kwargs)
        return call
    return decorate
