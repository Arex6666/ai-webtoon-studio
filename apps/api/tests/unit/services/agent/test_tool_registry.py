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


import pytest
from app.services.agent.tool_registry import ToolRegistry, compute_available_tools, TOOL_REGISTRY


def _make(name, **kw):
    return ToolDefinition(
        name=name, description=name, json_schema={}, handler=_dummy, **kw,
    )


@pytest.fixture(autouse=True)
def clean_registry():
    TOOL_REGISTRY.clear()
    yield
    TOOL_REGISTRY.clear()


def test_register_and_retrieve():
    t = _make("alpha")
    TOOL_REGISTRY.register(t)
    assert TOOL_REGISTRY.get("alpha") is t
    assert "alpha" in TOOL_REGISTRY.names()


def test_register_collision_overwrites_with_warning(caplog):
    import logging
    caplog.set_level(logging.WARNING)
    a = _make("dup", source_skill_id="builtin")
    b = _make("dup", source_skill_id="skill:foo")
    TOOL_REGISTRY.register(a)
    TOOL_REGISTRY.register(b)
    assert TOOL_REGISTRY.get("dup") is b
    assert any("Tool name collision" in r.message for r in caplog.records)


def test_compute_available_tools_filters_by_context():
    TOOL_REGISTRY.register(_make("global"))                                          # always visible
    TOOL_REGISTRY.register(_make("episode_only", requires_context=("episode_number",)))
    TOOL_REGISTRY.register(_make("panel_only", requires_context=("panel_id",)))
    out = compute_available_tools({"project_id": "p"})
    assert [t.name for t in out] == ["global"]
    out2 = compute_available_tools({"project_id": "p", "episode_number": 1})
    assert [t.name for t in out2] == ["episode_only", "global"]   # sorted by name


def test_compute_available_tools_respects_allowlist():
    TOOL_REGISTRY.register(_make("a"))
    TOOL_REGISTRY.register(_make("b"))
    TOOL_REGISTRY.register(_make("c"))
    out = compute_available_tools({}, allowlist=["b", "c"])
    assert [t.name for t in out] == ["b", "c"]


def test_deregister_removes_tool():
    TOOL_REGISTRY.register(_make("temp"))
    TOOL_REGISTRY.deregister("temp")
    assert TOOL_REGISTRY.get("temp") is None
