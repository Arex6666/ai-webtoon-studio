"""Smoke tests for generate_panels / regenerate_asset_image / create_character / create_scene."""
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
    # Also evict modules on teardown so the next test (e.g. the 16-tool forcing
    # test) re-runs the package __init__ and re-registers tools.
    for mod in list(sys.modules):
        if mod.startswith("app.services.agent.tools"):
            sys.modules.pop(mod, None)


def test_generate_panels_metadata():
    import app.services.agent.tools.generate_panels as m
    assert m.tool.name == "generate_panels"
    assert m.tool.expected_duration == "slow"
    # Phase C: now requires conversation_id (cards live there).
    assert m.tool.requires_context == (
        "project_id", "episode_number", "conversation_id",
    )


def test_regenerate_asset_image_metadata():
    import app.services.agent.tools.regenerate_asset_image as m
    assert m.tool.name == "regenerate_asset_image"
    assert m.tool.requires_context == ("project_id", "asset_id")
    assert m.tool.expected_duration == "slow"


def test_create_character_metadata():
    import app.services.agent.tools.create_character as m
    assert m.tool.name == "create_character"
    assert m.tool.requires_context == ("project_id",)
    schema = m.tool.json_schema
    assert "name" in schema["required"]
    assert "appearance" in schema["required"]


def test_create_scene_metadata():
    import app.services.agent.tools.create_scene as m
    assert m.tool.name == "create_scene"
    assert m.tool.requires_context == ("project_id",)


@pytest.mark.asyncio
async def test_generate_panels_requires_full_context():
    import app.services.agent.tools.generate_panels as m
    out = await m.handle(
        {},
        {"project_id": "p", "episode_number": 1},  # no conversation_id
        db=None, tracer=None,
    )
    assert "error" in out
    assert "conversation_id" in out["error"]


@pytest.mark.asyncio
async def test_generate_panels_invokes_helper(monkeypatch):
    """With full context, delegates to generate_panels_for_episode."""
    from unittest.mock import MagicMock
    import app.services.agent.tools.generate_panels as m
    from app.services.agent_commit import panel_generation as pg_mod

    captured = {}

    async def fake_helper(*, db, project_id, episode_number, conversation_id, force_regenerate):
        captured.update({
            "project_id": project_id,
            "episode_number": episode_number,
            "conversation_id": conversation_id,
            "force_regenerate": force_regenerate,
        })
        return {
            "panel_count": 2,
            "success_count": 1,
            "panels": [
                {"id": "p1", "image_url": "k1", "status": "success", "error": None},
                {"id": "p2", "image_url": None, "status": "failed", "error": "boom"},
            ],
            "warnings": [],
        }

    monkeypatch.setattr(pg_mod, "generate_panels_for_episode", fake_helper)

    db = MagicMock()
    out = await m.handle(
        {"force_regenerate": True},
        {"project_id": "proj", "episode_number": 3, "conversation_id": "conv"},
        db=db, tracer=None,
    )
    assert out["success"] is True
    assert out["panel_count"] == 2
    assert out["success_count"] == 1
    assert len(out["panels"]) == 2
    assert captured == {
        "project_id": "proj",
        "episode_number": 3,
        "conversation_id": "conv",
        "force_regenerate": True,
    }


@pytest.mark.asyncio
async def test_create_character_passes_through_name():
    import app.services.agent.tools.create_character as m
    out = await m.handle(
        {"name": "Aria", "description": "warrior", "appearance": "tall, blue hair"},
        {"project_id": "p"},
        db=None, tracer=None,
    )
    assert out["name"] == "Aria"
    assert "dispatched" in out


@pytest.mark.asyncio
async def test_regenerate_asset_image_uses_context_asset_id():
    import app.services.agent.tools.regenerate_asset_image as m
    out = await m.handle({}, {"project_id": "p", "asset_id": "a-123"}, db=None, tracer=None)
    assert out["asset_id"] == "a-123"
    assert "dispatched" in out
