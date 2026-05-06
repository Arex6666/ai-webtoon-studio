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


def test_generate_panels_metadata():
    import app.services.agent.tools.generate_panels as m
    assert m.tool.name == "generate_panels"
    assert m.tool.expected_duration == "slow"
    assert m.tool.requires_context == ("project_id", "episode_number")


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
async def test_generate_panels_returns_dispatched():
    import app.services.agent.tools.generate_panels as m
    out = await m.handle({}, {"project_id": "p", "episode_number": 1}, db=None, tracer=None)
    assert "dispatched" in out
    assert "job_id" in out["dispatched"]


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
