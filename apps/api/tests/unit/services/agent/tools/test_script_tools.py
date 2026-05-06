"""Smoke tests for generate_script / refine_script / analyze_script."""
import sys
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


def test_generate_script_metadata():
    import app.services.agent.tools.generate_script as m
    assert m.tool.name == "generate_script"
    assert m.tool.expected_duration == "slow"
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


@pytest.mark.asyncio
async def test_generate_script_returns_dispatched_stub():
    import app.services.agent.tools.generate_script as m
    out = await m.handle({"story": "once upon a time"}, {"project_id": "p1", "episode_number": 1}, db=None, tracer=None)
    assert "dispatched" in out
    assert "job_id" in out["dispatched"]


@pytest.mark.asyncio
async def test_refine_script_returns_stub():
    import app.services.agent.tools.refine_script as m
    out = await m.handle({"feedback": "shorter"}, {"project_id": "p1", "episode_number": 1}, db=None, tracer=None)
    assert out["refined"] is False
    assert out["feedback_received"] == "shorter"


@pytest.mark.asyncio
async def test_analyze_script_handles_missing_text():
    import app.services.agent.tools.analyze_script as m
    out = await m.handle({}, {"project_id": "p1", "episode_number": 1}, db=None, tracer=None)
    assert out["parsed"] is False
