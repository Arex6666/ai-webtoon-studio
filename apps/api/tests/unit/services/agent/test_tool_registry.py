"""Tests for tool registry."""
from app.services.agent.tool_registry import ToolDefinition, is_visible


async def _dummy(): return None


def test_tool_visible_with_required_context():
    t = ToolDefinition(
        name="t1", description="d", json_schema={}, handler=_dummy,
        requires_context=("project_id", "episode_number"),
    )
    assert is_visible(t, {"project_id": "p1", "episode_number": 3})


def test_tool_invisible_when_required_missing():
    t = ToolDefinition(
        name="t1", description="d", json_schema={}, handler=_dummy,
        requires_context=("project_id",),
    )
    assert not is_visible(t, {})
    assert not is_visible(t, {"project_id": None})


def test_tool_with_no_requirements_always_visible():
    t = ToolDefinition(name="t1", description="d", json_schema={}, handler=_dummy)
    assert is_visible(t, {})
