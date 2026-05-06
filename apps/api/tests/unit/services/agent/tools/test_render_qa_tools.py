"""Smoke tests for render_panels / analyze_quality / suggest_fixes."""
import sys
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
    out = await m.handle({"panel_ids": ["p1", "p2"]}, {"project_id": "x", "episode_number": 1}, db=None, tracer=None)
    assert "dispatched" in out
    assert out["panel_ids"] == ["p1", "p2"]


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
