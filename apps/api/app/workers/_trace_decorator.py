"""Cross-process tracing for Celery tasks — propagates trace_id from caller."""
import asyncio
import functools
from typing import Callable

from app.services.agent.trace import with_tracer, _current_tracer


def trace_task(fn: Callable) -> Callable:
    """Wrap a Celery task so it continues tracing from the dispatcher's parent span.

    Caller passes `_trace_id` and `_parent_span_id` as kwargs:

        celery_app.send_task(
            "name", args=[...],
            kwargs={"_trace_id": tracer.trace_id, "_parent_span_id": current_span_id},
        )

    Worker decorated with @trace_task creates a continuation span named
    `celery_<fn_name>` parented at the caller's span.
    """
    is_async = asyncio.iscoroutinefunction(fn)

    if is_async:
        @functools.wraps(fn)
        async def async_wrapper(*args, _trace_id=None, _parent_span_id=None, **kwargs):
            if _trace_id:
                async with with_tracer(_trace_id) as tracer:
                    if _parent_span_id:
                        tracer._stack.append(_parent_span_id)
                    async with tracer.span(f"celery_{fn.__name__}"):
                        return await fn(*args, **kwargs)
            return await fn(*args, **kwargs)
        return async_wrapper

    @functools.wraps(fn)
    def sync_wrapper(*args, _trace_id=None, _parent_span_id=None, **kwargs):
        if _trace_id:
            # Sync Celery task — run a private event loop just for span emission
            async def _run_with_trace():
                async with with_tracer(_trace_id) as tracer:
                    if _parent_span_id:
                        tracer._stack.append(_parent_span_id)
                    async with tracer.span(f"celery_{fn.__name__}"):
                        return fn(*args, **kwargs)
            return asyncio.run(_run_with_trace())
        return fn(*args, **kwargs)

    return sync_wrapper
