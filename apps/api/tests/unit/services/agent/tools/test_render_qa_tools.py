"""Smoke tests for render_panels / analyze_quality / suggest_fixes."""
import sys
from unittest.mock import patch, MagicMock
import pytest

from app.services.agent.tool_registry import TOOL_REGISTRY


@pytest.fixture(autouse=True)
def clean_registry():
    TOOL_REGISTRY.clear()
    for mod in list(sys.modules):
        if mod.startswith("app.services.agent.tools"):
            sys.modules.pop(mod, None)
    yield
    TOOL_REGISTRY.clear()
    # Also evict modules on teardown so the next test (e.g. the 16-tool forcing
    # test) re-runs the package __init__ and re-registers tools.
    for mod in list(sys.modules):
        if mod.startswith("app.services.agent.tools"):
            sys.modules.pop(mod, None)


def test_render_panels_metadata():
    import app.services.agent.tools.render_panels as m
    assert m.tool.name == "render_panels"
    assert m.tool.expected_duration == "slow"
    assert m.tool.read_only is False
    assert m.tool.requires_context == ("project_id", "episode_number")
    schema = m.tool.json_schema
    assert "panel_ids" in schema["required"]


def test_analyze_quality_metadata():
    import app.services.agent.tools.analyze_quality as m
    assert m.tool.name == "analyze_quality"
    assert m.tool.read_only is True
    assert m.tool.requires_context == ("project_id", "panel_id")


def test_suggest_fixes_metadata():
    import app.services.agent.tools.suggest_fixes as m
    assert m.tool.name == "suggest_fixes"
    assert m.tool.read_only is True
    assert m.tool.requires_context == ("project_id", "panel_id")


@pytest.mark.asyncio
async def test_render_panels_returns_dispatched():
    import app.services.agent.tools.render_panels as m

    # Mock the Celery dispatch so the test never actually queues a task.
    fake_send = MagicMock(return_value=MagicMock(id="celery-task-id"))
    with patch.object(m.celery_app, "send_task", fake_send):
        out = await m.handle(
            {"panel_ids": ["p1", "p2"]},
            {"project_id": "x", "episode_number": 1},
            db=None,
            tracer=None,
        )

    assert "dispatched" in out
    assert out["panel_ids"] == ["p1", "p2"]
    # Dispatch should have been invoked once per panel.
    assert fake_send.call_count == 2

    # Each call must target the canonical image-render task name discovered
    # at scout time. We accept either the legacy positional shape or the
    # explicit kwarg shape — whichever the implementation uses.
    expected_task_name = m.IMAGE_RENDER_TASK
    assert expected_task_name == "app.workers.image_worker.execute_image_job"

    for call in fake_send.call_args_list:
        # First positional arg is the task name in celery_app.send_task(name, ...)
        task_name = call.args[0] if call.args else call.kwargs.get("name")
        assert task_name == expected_task_name
        # Args should carry [job_id, panel_id]
        send_args = call.kwargs.get("args") or (call.args[1] if len(call.args) > 1 else None)
        assert send_args is not None
        assert len(send_args) == 2
        # Queue should be "image"
        assert call.kwargs.get("queue") == "image"


@pytest.mark.asyncio
async def test_render_panels_rejects_empty_panel_ids():
    import app.services.agent.tools.render_panels as m
    out = await m.handle(
        {"panel_ids": []},
        {"project_id": "x", "episode_number": 1},
        db=None,
        tracer=None,
    )
    assert "error" in out


@pytest.mark.asyncio
async def test_render_panels_passes_trace_ids_to_celery():
    import app.services.agent.tools.render_panels as m

    class _StubTracer:
        trace_id = "trace-xyz"
        current_span_id = "span-abc"

    fake_send = MagicMock(return_value=MagicMock(id="celery-task-id"))
    with patch.object(m.celery_app, "send_task", fake_send):
        await m.handle(
            {"panel_ids": ["p1"]},
            {"project_id": "x", "episode_number": 1},
            db=None,
            tracer=_StubTracer(),
        )

    assert fake_send.call_count == 1
    kwargs_passed = fake_send.call_args.kwargs.get("kwargs") or {}
    assert kwargs_passed.get("_trace_id") == "trace-xyz"
    assert kwargs_passed.get("_parent_span_id") == "span-abc"


@pytest.mark.asyncio
async def test_analyze_quality_requires_panel_id():
    import app.services.agent.tools.analyze_quality as m
    out = await m.handle({}, {"project_id": "x"}, db=None, tracer=None)
    assert "error" in out


@pytest.mark.asyncio
async def test_suggest_fixes_requires_panel_id():
    import app.services.agent.tools.suggest_fixes as m
    out = await m.handle({}, {"project_id": "x"}, db=None, tracer=None)
    assert "error" in out
