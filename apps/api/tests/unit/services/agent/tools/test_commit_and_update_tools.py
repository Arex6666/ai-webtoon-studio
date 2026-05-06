"""Smoke tests for commit_to_studio / update_panel_dialogue / update_panel_camera."""
import sys
import pytest
from unittest.mock import MagicMock

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


def test_commit_to_studio_metadata():
    import app.services.agent.tools.commit_to_studio as m
    assert m.tool.name == "commit_to_studio"
    assert m.tool.expected_duration == "slow"
    assert m.tool.requires_context == ("project_id", "episode_number")


def test_update_panel_dialogue_metadata():
    import app.services.agent.tools.update_panel_dialogue as m
    assert m.tool.name == "update_panel_dialogue"
    assert m.tool.expected_duration == "fast"
    assert "dialogue" in m.tool.json_schema["required"]


def test_update_panel_camera_metadata():
    import app.services.agent.tools.update_panel_camera as m
    assert m.tool.name == "update_panel_camera"
    assert m.tool.requires_context == ("project_id", "panel_id")


@pytest.mark.asyncio
async def test_commit_to_studio_returns_dispatched():
    import app.services.agent.tools.commit_to_studio as m
    out = await m.handle({}, {"project_id": "p", "episode_number": 1}, db=None, tracer=None)
    assert "dispatched" in out


@pytest.mark.asyncio
async def test_update_panel_dialogue_requires_db_and_panel():
    import app.services.agent.tools.update_panel_dialogue as m
    # No db → graceful error
    out = await m.handle({"dialogue": "Hi"}, {"project_id": "p"}, db=None, tracer=None)
    assert "error" in out


@pytest.mark.asyncio
async def test_update_panel_camera_requires_at_least_one_arg():
    import app.services.agent.tools.update_panel_camera as m
    db = MagicMock()
    out = await m.handle({}, {"project_id": "p", "panel_id": "x"}, db=db, tracer=None)
    assert "error" in out
