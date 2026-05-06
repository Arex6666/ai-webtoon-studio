"""Smoke tests for generate_script / refine_script / analyze_script."""
import sys
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

from app.services.agent.tool_registry import TOOL_REGISTRY


@pytest.fixture(autouse=True)
def clean_registry():
    TOOL_REGISTRY.clear()
    # Clear cached submodules so the next import re-runs registration
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


def test_generate_script_metadata():
    import app.services.agent.tools.generate_script as m
    assert m.tool.name == "generate_script"
    # task_parse runs synchronously in the request — fast, not Celery-dispatched.
    assert m.tool.expected_duration == "fast"
    assert m.tool.read_only is False
    assert m.tool.requires_context == ("project_id", "episode_number")


def test_refine_script_metadata():
    import app.services.agent.tools.refine_script as m
    assert m.tool.name == "refine_script"
    assert m.tool.expected_duration == "fast"


def test_analyze_script_metadata():
    import app.services.agent.tools.analyze_script as m
    assert m.tool.name == "analyze_script"
    assert m.tool.read_only is True


def _fake_parse_result(success: bool = True):
    """Build a fake ParseResult-like object with a script_ir attribute."""
    char_a = SimpleNamespace(name="周昀")
    char_b = SimpleNamespace(name="林知夏")
    scene = SimpleNamespace(name="旧书店")
    beats = [SimpleNamespace(id="beat_01"), SimpleNamespace(id="beat_02")]
    script_ir = SimpleNamespace(characters=[char_a, char_b], scenes=[scene], beats=beats)
    return SimpleNamespace(success=success, script_ir=script_ir, errors=[])


@pytest.mark.asyncio
async def test_generate_script_parses_and_persists():
    """generate_script should call ScriptPipelineService.task_parse and persist
    the raw story onto the chapter row."""
    import app.services.agent.tools.generate_script as m

    fake_pipeline = MagicMock()

    async def _fake_task_parse(text):
        assert text == "once upon a time"
        return _fake_parse_result()

    fake_pipeline.task_parse = _fake_task_parse

    # Fake DB session whose .query().filter().first() returns a chapter mock.
    chapter = MagicMock()
    chapter.script_raw = None
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = chapter

    with patch("app.services.script_pipeline.create_pipeline", return_value=fake_pipeline):
        out = await m.handle(
            {"story": "once upon a time", "panel_count": 5},
            {"project_id": "p1", "episode_number": 1},
            db=db,
            tracer=None,
        )

    assert out["success"] is True
    assert out["beat_count"] == 2
    assert out["characters"] == ["周昀", "林知夏"]
    assert out["scenes"] == ["旧书店"]
    assert out["panel_count"] == 5
    assert out["persisted"] is True
    # Persistence side-effect — script_raw set, commit called.
    assert chapter.script_raw == "once upon a time"
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_generate_script_requires_story():
    import app.services.agent.tools.generate_script as m
    out = await m.handle({}, {"project_id": "p1", "episode_number": 1}, db=None, tracer=None)
    assert "error" in out


@pytest.mark.asyncio
async def test_refine_script_calls_repair_loop():
    """refine_script should record feedback into chapter.layout_json and (when
    a storyboard JSON is present) invoke validate_and_repair_storyboard."""
    import app.services.agent.tools.refine_script as m

    chapter = MagicMock()
    chapter.script_raw = "Once upon a time..."
    chapter.layout_json = {"storyboard": {"panels": []}}

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = chapter

    repaired = {"panels": [{"id": "p1"}]}
    plan = SimpleNamespace(final_status="repaired", attempts_used=2)

    async def _fake_repair(data, script_text, duration_range=(1.5, 8.0), max_attempts=3):
        assert data == {"panels": []}
        assert script_text == "Once upon a time..."
        return True, repaired, plan

    with patch(
        "app.services.brain.repair.repair_loop.validate_and_repair_storyboard",
        side_effect=_fake_repair,
    ):
        out = await m.handle(
            {"feedback": "shorter", "target_section": "panel 2-3"},
            {"project_id": "p1", "episode_number": 1},
            db=db,
            tracer=None,
        )

    assert out["success"] is True
    assert out["feedback_received"] == "shorter"
    assert out["target_section"] == "panel 2-3"
    assert out["repair"]["ran"] is True
    assert out["repair"]["ok"] is True
    assert out["repair"]["final_status"] == "repaired"

    # Layout updated: pending_feedback recorded + storyboard replaced with repaired JSON.
    assert isinstance(chapter.layout_json["pending_feedback"], list)
    assert chapter.layout_json["pending_feedback"][0]["feedback"] == "shorter"
    assert chapter.layout_json["storyboard"] == repaired
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_refine_script_records_feedback_without_storyboard():
    """When no storyboard JSON exists yet, the tool should still record the
    feedback and skip the repair pass."""
    import app.services.agent.tools.refine_script as m

    chapter = MagicMock()
    chapter.script_raw = ""
    chapter.layout_json = {}

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = chapter

    out = await m.handle(
        {"feedback": "tighten pacing"},
        {"project_id": "p1", "episode_number": 1},
        db=db,
        tracer=None,
    )

    assert out["success"] is True
    assert out["repair"]["ran"] is False
    assert chapter.layout_json["pending_feedback"][0]["feedback"] == "tighten pacing"
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_refine_script_missing_chapter():
    import app.services.agent.tools.refine_script as m

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    out = await m.handle(
        {"feedback": "shorter"},
        {"project_id": "p1", "episode_number": 99},
        db=db,
        tracer=None,
    )
    assert "error" in out
    assert "not found" in out["error"]


@pytest.mark.asyncio
async def test_analyze_script_handles_missing_text():
    import app.services.agent.tools.analyze_script as m
    out = await m.handle({}, {"project_id": "p1", "episode_number": 1}, db=None, tracer=None)
    assert out["parsed"] is False
