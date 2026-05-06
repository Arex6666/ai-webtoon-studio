"""Smoke tests for query_assets / query_episodes / query_panels."""
import sys
import pytest
from unittest.mock import MagicMock

from app.services.agent.tool_registry import TOOL_REGISTRY


@pytest.fixture(autouse=True)
def clean_registry():
    TOOL_REGISTRY.clear()
    yield
    TOOL_REGISTRY.clear()
    # Also evict modules on teardown so the next test (e.g. the 16-tool forcing
    # test) re-runs the package __init__ and re-registers tools.
    for mod in list(sys.modules):
        if mod.startswith("app.services.agent.tools"):
            sys.modules.pop(mod, None)


def test_query_assets_metadata():
    import importlib
    import app.services.agent.tools.query_assets as m
    importlib.reload(m)
    assert m.tool.name == "query_assets"
    assert m.tool.read_only is True
    assert m.tool.requires_context == ("project_id",)
    assert m.tool.expected_duration == "fast"


def test_query_episodes_metadata():
    import importlib
    import app.services.agent.tools.query_episodes as m
    importlib.reload(m)
    assert m.tool.name == "query_episodes"
    assert m.tool.read_only is True


def test_query_panels_metadata():
    import importlib
    import app.services.agent.tools.query_panels as m
    importlib.reload(m)
    assert m.tool.name == "query_panels"
    assert m.tool.read_only is True


@pytest.mark.asyncio
async def test_query_assets_handler_returns_count_and_list():
    import importlib
    import app.services.agent.tools.query_assets as m
    importlib.reload(m)
    # NOTE: `name` is a reserved kwarg on MagicMock (sets the mock's repr name),
    # so set it as an attribute after construction.
    fake_asset = MagicMock(id="a1", description="d")
    fake_asset.name = "hero"
    type(fake_asset).type = MagicMock(value="character")
    q = MagicMock()
    q.filter.return_value = q
    q.limit.return_value.all.return_value = [fake_asset]
    db = MagicMock()
    db.query.return_value = q

    out = await m.handle({}, {"project_id": "p1"}, db, tracer=None)
    assert out["count"] == 1
    assert out["assets"][0]["name"] == "hero"


@pytest.mark.asyncio
async def test_query_panels_handler_requires_episode_number():
    import importlib
    import app.services.agent.tools.query_panels as m
    importlib.reload(m)
    db = MagicMock()
    out = await m.handle({}, {"project_id": "p1"}, db, tracer=None)
    assert "error" in out
    assert "episode_number" in out["error"]


def test_tools_package_init_registers_three_query_tools():
    """Loading the tools package should register all 3 query tools."""
    import importlib
    import sys
    # Drop cached submodules so reloading the package re-executes each
    # tool module's `TOOL_REGISTRY.register(tool)` call.
    for mod_name in [
        "app.services.agent.tools",
        "app.services.agent.tools.query_assets",
        "app.services.agent.tools.query_episodes",
        "app.services.agent.tools.query_panels",
    ]:
        sys.modules.pop(mod_name, None)
    import app.services.agent.tools as pkg  # noqa: F401
    names = TOOL_REGISTRY.names()
    assert "query_assets" in names
    assert "query_episodes" in names
    assert "query_panels" in names
