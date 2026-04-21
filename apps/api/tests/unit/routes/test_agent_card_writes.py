"""Integration tests: agent generate-panels / script endpoints write cards."""
import uuid
import pytest
from unittest.mock import AsyncMock, patch


@pytest.fixture(autouse=True)
def _auth_off(monkeypatch):
    monkeypatch.setenv("ENABLE_AUTH", "false")


@pytest.fixture
def seeded_conv(test_client):
    from app.core.database import SessionLocal
    from app.models.project import Project
    from app.models.conversation import Conversation
    db = SessionLocal()
    try:
        proj = Project(id=str(uuid.uuid4()), name="CW2", description="")
        db.add(proj)
        conv = Conversation(id=str(uuid.uuid4()), project_id=proj.id,
                            title="t", status="active")
        db.add(conv)
        db.commit()
        return {"project_id": proj.id, "conversation_id": conv.id}
    finally:
        db.close()


def test_generate_panels_writes_panels_card(test_client, seeded_conv):
    import app.api.routes.agent as agent_mod
    from app.core.database import SessionLocal
    from app.models.conversation_message import ConversationMessage

    fake_doubao = AsyncMock()
    fake_doubao.generate = AsyncMock(return_value=type("R", (), {
        "success": True, "image_url": "http://doubao/img.png", "error": None,
    })())

    body = {
        "project_id": seeded_conv["project_id"],
        "conversation_id": seeded_conv["conversation_id"],
        "art_style": {"base_style": "", "color_tone": "", "atmosphere": ""},
        "characters": [],
        "scenes": [],
        "panels": [
            {"id": "p-1", "order": 0, "scene_name": "Rooftop",
             "characters": ["Alice"], "scene_description": "w", "composition": ""},
        ],
    }

    with patch.object(agent_mod, "get_doubao_image_provider", return_value=fake_doubao), \
         patch("app.services.agent_commit.image_fetcher.fetch_and_persist",
               new=AsyncMock(return_value="minio-key-1")):
        resp = test_client.post("/api/v1/agent/episode/2/generate-panels", json=body)

    assert resp.status_code == 200

    db = SessionLocal()
    try:
        msgs = db.query(ConversationMessage).filter(
            ConversationMessage.conversation_id == seeded_conv["conversation_id"]
        ).all()
        card_msgs = [m for m in msgs
                     if (m.entities_json or {}).get("card", {}).get("type") == "panels"]
        assert len(card_msgs) == 1
        card = card_msgs[0].entities_json["card"]
        assert card["episode_number"] == 2
        assert card["panels"][0]["id"] == "p-1"
        assert card["panels"][0]["temp_image_url"] == "minio-key-1"
    finally:
        db.close()


def test_generate_panels_updates_existing_card_in_place(test_client, seeded_conv):
    """Calling generate-panels twice for same episode → only 1 card remains."""
    import app.api.routes.agent as agent_mod
    from app.core.database import SessionLocal
    from app.models.conversation_message import ConversationMessage

    fake_doubao = AsyncMock()
    fake_doubao.generate = AsyncMock(return_value=type("R", (), {
        "success": True, "image_url": "http://doubao/img.png", "error": None,
    })())

    body = {
        "project_id": seeded_conv["project_id"],
        "conversation_id": seeded_conv["conversation_id"],
        "art_style": {"base_style": "", "color_tone": "", "atmosphere": ""},
        "characters": [], "scenes": [],
        "panels": [{"id": "p-1", "order": 0, "scene_name": "x",
                    "characters": [], "scene_description": "", "composition": ""}],
    }

    with patch.object(agent_mod, "get_doubao_image_provider", return_value=fake_doubao), \
         patch("app.services.agent_commit.image_fetcher.fetch_and_persist",
               new=AsyncMock(return_value="k")):
        test_client.post("/api/v1/agent/episode/1/generate-panels", json=body)
        test_client.post("/api/v1/agent/episode/1/generate-panels", json=body)

    db = SessionLocal()
    try:
        card_msgs = db.query(ConversationMessage).filter(
            ConversationMessage.conversation_id == seeded_conv["conversation_id"]
        ).all()
        card_msgs = [m for m in card_msgs
                     if (m.entities_json or {}).get("card", {}).get("type") == "panels"]
        assert len(card_msgs) == 1
    finally:
        db.close()
