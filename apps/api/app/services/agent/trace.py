"""Tracing skeleton — structured JSON span emission with OTel-compatible attribute names.

Spans emit as logging records to logger 'webtoon.trace'. JSON formatting handled by
TraceJsonFormatter (see app.core.logging — Task 2.2). No OTel SDK dependency in v1.
"""
import json
import time
import uuid
import logging
import functools
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Optional

_current_tracer: ContextVar[Optional["Tracer"]] = ContextVar("tracer", default=None)
_log = logging.getLogger("webtoon.trace")


class Tracer:
    """One Tracer instance per chat call (per /v1/agent/chat invocation).

    span() context manager records start/end timestamps, parent linkage,
    attributes, and emits a structured log record on exit.
    """

    def __init__(self, trace_id: str, conversation_id: Optional[str] = None):
        self.trace_id = trace_id
        self.conversation_id = conversation_id
        self._stack: list[str] = []

    @asynccontextmanager
    async def span(self, name: str, **attrs):
        span_id = uuid.uuid4().hex
        parent_id = self._stack[-1] if self._stack else None
        start_mono = time.monotonic()
        record = {
            "trace_id": self.trace_id,
            "span_id": span_id,
            "parent_span_id": parent_id,
            "name": name,
            "ts_start": time.time(),
            "conversation_id": self.conversation_id,
            "attributes": dict(attrs),
        }
        self._stack.append(span_id)
        status = "ok"
        error = None
        try:
            yield record["attributes"]   # caller can append attrs in-place inside the `with`
        except Exception as e:
            status = "error"
            error = repr(e)
            raise
        finally:
            self._stack.pop()
            record["ts_end"] = time.time()
            record["duration_ms"] = (time.monotonic() - start_mono) * 1000
            record["status"] = status
            record["error"] = error
            _log.info("span", extra={"_trace_record": record})

    @property
    def current_span_id(self) -> Optional[str]:
        return self._stack[-1] if self._stack else None


def get_tracer() -> Tracer:
    """Return the active tracer; raises if none."""
    t = _current_tracer.get()
    if t is None:
        raise RuntimeError("No active tracer; wrap call site in `async with with_tracer(...)`")
    return t


@asynccontextmanager
async def with_tracer(trace_id: Optional[str] = None, conversation_id: Optional[str] = None):
    """Context manager that installs a Tracer into the current asyncio context.

    If trace_id is None, generates one. Yields the Tracer instance.
    """
    tracer = Tracer(trace_id or uuid.uuid4().hex, conversation_id)
    token = _current_tracer.set(tracer)
    try:
        yield tracer
    finally:
        _current_tracer.reset(token)
