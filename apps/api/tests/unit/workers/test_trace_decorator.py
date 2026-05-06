"""Test @trace_task cross-process trace propagation."""
import logging

import pytest

from app.workers._trace_decorator import trace_task


@pytest.fixture
def trace_caplog(caplog):
    """Attach caplog's handler directly to webtoon.trace (which has propagate=False
    after configure_trace_logger runs in main.py)."""
    logger = logging.getLogger("webtoon.trace")
    logger.addHandler(caplog.handler)
    prev_level = logger.level
    logger.setLevel(logging.INFO)
    yield caplog
    logger.removeHandler(caplog.handler)
    logger.setLevel(prev_level)


def test_trace_task_passthrough_when_no_trace_id():
    @trace_task
    def add(a, b):
        return a + b
    assert add(2, 3) == 5


def test_trace_task_creates_continuation_span(trace_caplog):
    caplog = trace_caplog

    @trace_task
    def work(x):
        return x * 2

    result = work(5, _trace_id="t-parent", _parent_span_id="span-parent")
    assert result == 10
    # span emitted under name celery_work, parented at span-parent
    records = [r for r in caplog.records if r.name == "webtoon.trace"]
    assert len(records) == 1
    rec = records[0]._trace_record
    assert rec["name"] == "celery_work"
    assert rec["parent_span_id"] == "span-parent"
    assert rec["trace_id"] == "t-parent"


@pytest.mark.asyncio
async def test_trace_task_works_on_async_function():
    @trace_task
    async def afetch(url):
        return f"got {url}"
    assert await afetch("/x") == "got /x"
    # With trace
    out = await afetch("/y", _trace_id="t1", _parent_span_id="ps1")
    assert out == "got /y"
