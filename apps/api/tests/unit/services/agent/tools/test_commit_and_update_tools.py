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
    # Phase C wiring: orchestrator is sync-await + DB-bound (no Celery), so
    # the tool is now classified "fast" and requires conversation_id so it
    # can build a lean CommitToStudioRequest.
    assert m.tool.expected_duration == "fast"
    assert m.tool.requires_context == ("project_id", "episode_number", "conversation_id")


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
async def test_commit_to_studio_requires_full_context():
    """Without conversation_id the handler returns a clear context error."""
    import app.services.agent.tools.commit_to_studio as m
    out = await m.handle({}, {"project_id": "p", "episode_number": 1}, db=None, tracer=None)
    assert "error" in out
    assert "conversation_id" in out["error"]


@pytest.mark.asyncio
async def test_commit_to_studio_invokes_orchestrator(monkeypatch):
    """With full context, the handler delegates to commit_agent_to_studio."""
    import app.services.agent.tools.commit_to_studio as m
    from app.services.agent_commit import commit_orchestrator as orchestrator_mod

    captured = {}

    async def fake_commit(db, project_id, req):
        captured["project_id"] = project_id
        captured["conversation_id"] = req.conversation_id
        captured["episode_number"] = req.episode_number

        class _Chapter:
            id = "chap-123"

        return orchestrator_mod.CommitResult(
            chapter=_Chapter(),
            status="created",
            character_count=2,
            scene_count=1,
            panel_count=4,
            warnings=["warn"],
            payload_source="conversation",
        )

    monkeypatch.setattr(orchestrator_mod, "commit_agent_to_studio", fake_commit)

    db = MagicMock()
    out = await m.handle(
        {"include_assets": True, "include_script": True, "include_panels": True},
        {"project_id": "proj-1", "episode_number": 2, "conversation_id": "conv-9"},
        db=db, tracer=None,
    )
    assert out["success"] is True
    assert out["chapter_id"] == "chap-123"
    assert out["status"] == "created"
    assert out["character_count"] == 2
    assert out["panel_count"] == 4
    assert out["payload_source"] == "conversation"
    assert captured == {
        "project_id": "proj-1",
        "conversation_id": "conv-9",
        "episode_number": 2,
    }
    db.commit.assert_called()


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
