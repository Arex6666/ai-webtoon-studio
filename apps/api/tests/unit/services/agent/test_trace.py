"""Unit tests for app.services.agent.trace."""
import logging

import pytest

from app.services.agent.trace import Tracer, with_tracer, get_tracer


@pytest.fixture
def trace_caplog(caplog):
    """Attach caplog's handler directly to webtoon.trace logger.

    Needed because configure_trace_logger() (run at app.main import time) sets
    propagate=False on this logger, which prevents caplog's default root-logger
    capture from seeing trace records.
    """
    logger = logging.getLogger("webtoon.trace")
    logger.addHandler(caplog.handler)
    prev_level = logger.level
    logger.setLevel(logging.INFO)
    yield caplog
    logger.removeHandler(caplog.handler)
    logger.setLevel(prev_level)


@pytest.mark.asyncio
async def test_with_tracer_installs_and_clears_tracer():
    with pytest.raises(RuntimeError):
        get_tracer()
    async with with_tracer("test-trace-id") as tracer:
        assert get_tracer() is tracer
        assert tracer.trace_id == "test-trace-id"
    with pytest.raises(RuntimeError):
        get_tracer()


@pytest.mark.asyncio
async def test_span_records_parent_child_relationship(trace_caplog):
    caplog = trace_caplog
    async with with_tracer("t1", conversation_id="c1") as tracer:
        async with tracer.span("parent", color="red"):
            assert tracer.current_span_id is not None
            parent_id = tracer.current_span_id
            async with tracer.span("child"):
                child_id = tracer.current_span_id
                assert child_id != parent_id
    # Two records emitted
    records = [r for r in caplog.records if r.name == "webtoon.trace"]
    assert len(records) == 2
    child = records[0]._trace_record
    parent = records[1]._trace_record
    assert child["name"] == "child"
    assert child["parent_span_id"] == parent["span_id"]
    assert parent["parent_span_id"] is None
    assert parent["attributes"]["color"] == "red"


@pytest.mark.asyncio
async def test_span_records_error_on_exception(trace_caplog):
    caplog = trace_caplog
    async with with_tracer("t2") as tracer:
        with pytest.raises(ValueError):
            async with tracer.span("doomed"):
                raise ValueError("boom")
    record = caplog.records[0]._trace_record
    assert record["status"] == "error"
    assert "boom" in record["error"]
