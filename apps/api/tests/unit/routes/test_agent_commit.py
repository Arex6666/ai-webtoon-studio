"""Integration tests for POST /api/v1/agent/projects/{pid}/commit-to-studio."""
import uuid
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def seeded(test_client: TestClient):
    import os; os.environ["ENABLE_AUTH"] = "false"
    from app.core.database import SessionLocal
    from app.models.project import Project

    db = SessionLocal()
    try:
        proj = Project(id=str(uuid.uuid4()), name="AC", description="")
        db.add(proj); db.commit()
        return {"project_id": proj.id}
    finally:
        db.close()


@pytest.fixture
def seeded_with_conv(seeded):
    """project + conversation with full set of cards for lean-payload tests."""
    from app.core.database import SessionLocal
    from app.models.conversation import Conversation
    from app.models.conversation_message import ConversationMessage

    db = SessionLocal()
    try:
        conv_id = str(uuid.uuid4())
        # Conversation required fields: project_id, title, status — match Task 8 fixture adaptations
        db.add(Conversation(id=conv_id, project_id=seeded["project_id"], title="test conv", status="active"))
        db.add_all([
            ConversationMessage(
                id=str(uuid.uuid4()), conversation_id=conv_id, role="assistant",
                content="chars", entities_json={"card": {"type": "characters", "characters": [
                    {"name": "Alice", "temp_image_url": "http://t/a.png"},
                    {"name": "Bob", "temp_image_url": "http://t/b.png"},
                ]}}),
            ConversationMessage(
                id=str(uuid.uuid4()), conversation_id=conv_id, role="assistant",
                content="scenes", entities_json={"card": {"type": "scenes", "scenes": [
                    {"name": "Rooftop", "temp_image_url": "http://t/s.png", "time_of_day": "sunset"},
                ]}}),
            ConversationMessage(
                id=str(uuid.uuid4()), conversation_id=conv_id, role="assistant",
                content="panels", entities_json={"card": {"type": "panels", "episode_number": 1, "panels": [
                    {"id": "p1", "order": 0, "scene_name": "Rooftop", "characters": ["Alice"],
                     "scene_description": "wait", "temp_image_url": "http://t/p1.png"},
                    {"id": "p2", "order": 1, "scene_name": "Rooftop", "characters": ["Alice", "Bob"],
                     "scene_description": "meet"},
                ]}}),
        ])
        db.commit()
        return {**seeded, "conversation_id": conv_id}
    finally:
        db.close()


def make_full_body(conversation_id="c1", episode_number=1, with_images=True):
    img = "http://example.com/img.png" if with_images else None
    return {
        "conversation_id": conversation_id,
        "episode_number": episode_number,
        "episode_title": "初遇",
        "outline_summary": "相遇",
        "art_style": {"base_style": "Korean webtoon", "color_tone": "warm", "atmosphere": "romantic"},
        "characters": [
            {"name": "Alice", "temp_image_url": img, "appearance_traits": ["short hair"], "personality_traits": []},
            {"name": "Bob", "temp_image_url": img, "appearance_traits": [], "personality_traits": []},
        ],
        "scenes": [
            {"name": "Rooftop", "temp_image_url": img, "time_of_day": "sunset", "weather": "clear"},
        ],
        "panels": [
            {"id": "ap-1", "order": 0, "scene_name": "Rooftop", "characters": ["Alice"],
             "scene_description": "she waits", "shot_type": "MS", "camera_angle": "eye-level", "temp_image_url": img},
            {"id": "ap-2", "order": 1, "scene_name": "Rooftop", "characters": ["Alice", "Bob"],
             "scene_description": "they meet", "shot_type": "MCU", "camera_angle": "high-angle", "temp_image_url": img},
        ],
    }


class TestCommitToStudioFullPayload:
    def test_creates_chapter_panels_assets(self, test_client, seeded):
        from app.core.database import SessionLocal
        from app.models.chapter import Chapter
        from app.models.panel import Panel
        from app.models.asset import Asset

        with patch("app.services.agent_commit.commit_orchestrator.fetch_and_persist",
                   new=AsyncMock(return_value="key/p.png")), \
             patch("app.services.agent_commit.asset_sync.fetch_and_persist",
                   new=AsyncMock(return_value="key/a.png")):
            resp = test_client.post(
                f"/api/v1/agent/projects/{seeded['project_id']}/commit-to-studio",
                json=make_full_body(),
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "created"
        assert body["created_panels"] == 2
        assert body["created_assets"]["characters"] == 2
        assert body["created_assets"]["scenes"] == 1
        assert body["payload_source"] == "request"

        db = SessionLocal()
        try:
            ch = db.query(Chapter).filter(Chapter.id == body["chapter_id"]).first()
            assert ch.layout_json["source"]["type"] == "agent"
            panels = db.query(Panel).filter(Panel.chapter_id == ch.id).all()
            assert len(panels) == 2 and all(p.preview_url == "key/p.png" for p in panels)
            spec0 = panels[0].spec_json
            assert spec0["characters"][0]["asset_id"]
            assert spec0["scene"].get("anchor_id")
            assets = db.query(Asset).filter(Asset.project_id == seeded["project_id"]).all()
            assert {a.name for a in assets} == {"Alice", "Bob", "Rooftop"}
            for a in assets:
                assert a.data_json["created_via"] == "agent"
        finally:
            db.close()

    def test_idempotent_second_call(self, test_client, seeded):
        from app.core.database import SessionLocal
        from app.models.chapter import Chapter

        with patch("app.services.agent_commit.commit_orchestrator.fetch_and_persist",
                   new=AsyncMock(return_value="k")), \
             patch("app.services.agent_commit.asset_sync.fetch_and_persist",
                   new=AsyncMock(return_value="k")):
            r1 = test_client.post(
                f"/api/v1/agent/projects/{seeded['project_id']}/commit-to-studio", json=make_full_body())
            r2 = test_client.post(
                f"/api/v1/agent/projects/{seeded['project_id']}/commit-to-studio", json=make_full_body())
        assert r1.json()["status"] == "created"
        assert r2.json()["status"] == "already_exists"
        assert r1.json()["chapter_id"] == r2.json()["chapter_id"]

        db = SessionLocal()
        try:
            count = db.query(Chapter).filter(Chapter.project_id == seeded["project_id"]).count()
            assert count == 1
        finally:
            db.close()

    def test_image_download_failure_produces_warning(self, test_client, seeded):
        from app.services.agent_commit.image_fetcher import ImageFetchError

        with patch("app.services.agent_commit.commit_orchestrator.fetch_and_persist",
                   new=AsyncMock(side_effect=ImageFetchError("404"))), \
             patch("app.services.agent_commit.asset_sync.fetch_and_persist",
                   new=AsyncMock(side_effect=ImageFetchError("404"))):
            resp = test_client.post(
                f"/api/v1/agent/projects/{seeded['project_id']}/commit-to-studio",
                json=make_full_body(),
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "created"
        assert len(body["warnings"]) > 0

    def test_project_not_found(self, test_client):
        resp = test_client.post(
            "/api/v1/agent/projects/does-not-exist/commit-to-studio",
            json=make_full_body(),
        )
        assert resp.status_code == 404

    def test_reuses_existing_asset_by_name(self, test_client, seeded):
        from app.core.database import SessionLocal
        from app.models.asset import Asset

        db = SessionLocal()
        existing = Asset(id=str(uuid.uuid4()), project_id=seeded["project_id"],
                         type="character", name="Alice", data_json={"created_via": "studio"})
        db.add(existing); db.commit(); existing_id = existing.id; db.close()

        with patch("app.services.agent_commit.commit_orchestrator.fetch_and_persist",
                   new=AsyncMock(return_value="k")), \
             patch("app.services.agent_commit.asset_sync.fetch_and_persist",
                   new=AsyncMock(return_value="k")):
            resp = test_client.post(
                f"/api/v1/agent/projects/{seeded['project_id']}/commit-to-studio",
                json=make_full_body(),
            )
        assert resp.status_code == 200

        db = SessionLocal()
        try:
            alice_assets = db.query(Asset).filter(
                Asset.project_id == seeded["project_id"],
                Asset.type == "character", Asset.name == "Alice",
            ).all()
            assert len(alice_assets) == 1 and alice_assets[0].id == existing_id
            assert alice_assets[0].data_json["created_via"] == "studio"
        finally:
            db.close()


class TestCommitToStudioLeanPayload:
    def test_lean_payload_populates_from_conversation(self, test_client, seeded_with_conv):
        from app.core.database import SessionLocal
        from app.models.panel import Panel
        from app.models.asset import Asset

        with patch("app.services.agent_commit.commit_orchestrator.fetch_and_persist",
                   new=AsyncMock(return_value="k/p.png")), \
             patch("app.services.agent_commit.asset_sync.fetch_and_persist",
                   new=AsyncMock(return_value="k/a.png")):
            resp = test_client.post(
                f"/api/v1/agent/projects/{seeded_with_conv['project_id']}/commit-to-studio",
                json={
                    "conversation_id": seeded_with_conv["conversation_id"],
                    "episode_number": 1,
                    "episode_title": "初遇",
                },
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "created"
        assert body["created_panels"] == 2
        assert body["created_assets"]["characters"] == 2
        assert body["created_assets"]["scenes"] == 1
        assert body["payload_source"] == "conversation"

        db = SessionLocal()
        try:
            panels = db.query(Panel).filter(Panel.chapter_id == body["chapter_id"]).all()
            assert len(panels) == 2
            assets = db.query(Asset).filter(Asset.project_id == seeded_with_conv["project_id"]).all()
            assert {a.name for a in assets} == {"Alice", "Bob", "Rooftop"}
        finally:
            db.close()
