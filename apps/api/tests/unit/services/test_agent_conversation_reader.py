"""Tests for agent_commit.conversation_reader."""
import uuid
import pytest

from app.schemas.agent_commit import CommitToStudioRequest


@pytest.fixture
def seeded_conv(test_client):
    import os
    os.environ["ENABLE_AUTH"] = "false"
    from app.core.database import SessionLocal
    from app.models.project import Project
    from app.models.conversation import Conversation
    from app.models.conversation_message import ConversationMessage

    db = SessionLocal()
    try:
        proj_id = str(uuid.uuid4())
        db.add(Project(id=proj_id, name="ConvReader Test", description=""))

        conv_id = str(uuid.uuid4())
        db.add(
            Conversation(
                id=conv_id,
                project_id=proj_id,
                title="test conv",
                status="active",
            )
        )

        msgs = [
            ConversationMessage(
                id=str(uuid.uuid4()),
                conversation_id=conv_id,
                role="assistant",
                content="characters card",
                entities_json={
                    "card": {
                        "type": "characters",
                        "characters": [
                            {"name": "Alice", "visual_prompt": "a girl", "temp_image_url": "http://x/a.png"},
                            {"name": "Bob"},
                        ],
                    }
                },
            ),
            ConversationMessage(
                id=str(uuid.uuid4()),
                conversation_id=conv_id,
                role="assistant",
                content="scenes card",
                entities_json={
                    "card": {
                        "type": "scenes",
                        "scenes": [
                            {"name": "Rooftop", "time_of_day": "sunset"},
                        ],
                    }
                },
            ),
            ConversationMessage(
                id=str(uuid.uuid4()),
                conversation_id=conv_id,
                role="assistant",
                content="panels card",
                entities_json={
                    "card": {
                        "type": "panels",
                        "episode_number": 1,
                        "panels": [
                            {
                                "id": "p1",
                                "order": 0,
                                "scene_name": "Rooftop",
                                "characters": ["Alice"],
                                "scene_description": "wait",
                                "temp_image_url": "http://x/p1.png",
                            },
                            {
                                "id": "p2",
                                "order": 1,
                                "scene_name": "Rooftop",
                                "characters": ["Alice", "Bob"],
                                "scene_description": "meet",
                            },
                        ],
                    }
                },
            ),
            ConversationMessage(
                id=str(uuid.uuid4()),
                conversation_id=conv_id,
                role="assistant",
                content="style card",
                entities_json={
                    "card": {
                        "type": "art_style",
                        "base_style": "Korean webtoon",
                        "color_tone": "warm",
                        "atmosphere": "romantic",
                    }
                },
            ),
        ]
        db.add_all(msgs)
        db.commit()
        return {"conversation_id": conv_id, "project_id": proj_id}
    finally:
        db.close()


def test_enriches_empty_request_from_conversation(seeded_conv):
    from app.core.database import SessionLocal
    from app.services.agent_commit.conversation_reader import enrich_request_from_conversation

    db = SessionLocal()
    try:
        req = CommitToStudioRequest(conversation_id=seeded_conv["conversation_id"], episode_number=1)
        enriched, warnings = enrich_request_from_conversation(db, req)
        assert len(enriched.panels) == 2
        assert enriched.panels[0].scene_name == "Rooftop"
        assert len(enriched.characters) == 2
        assert {c.name for c in enriched.characters} == {"Alice", "Bob"}
        assert len(enriched.scenes) == 1 and enriched.scenes[0].name == "Rooftop"
        assert enriched.art_style.base_style == "Korean webtoon"
        assert warnings == []
    finally:
        db.close()


def test_preserves_request_fields_if_present(seeded_conv):
    from app.core.database import SessionLocal
    from app.services.agent_commit.conversation_reader import enrich_request_from_conversation
    from app.schemas.agent_commit import AgentCharacter

    db = SessionLocal()
    try:
        req = CommitToStudioRequest(
            conversation_id=seeded_conv["conversation_id"],
            episode_number=1,
            characters=[AgentCharacter(name="PreSet")],
        )
        enriched, _ = enrich_request_from_conversation(db, req)
        assert [c.name for c in enriched.characters] == ["PreSet"]
        assert len(enriched.panels) == 2
    finally:
        db.close()


def test_no_cards_returns_empty_request_unchanged(test_client):
    import os
    os.environ["ENABLE_AUTH"] = "false"
    from app.core.database import SessionLocal
    from app.models.project import Project
    from app.models.conversation import Conversation
    from app.services.agent_commit.conversation_reader import enrich_request_from_conversation

    db = SessionLocal()
    try:
        proj_id = str(uuid.uuid4())
        db.add(Project(id=proj_id, name="Empty ConvReader", description=""))
        empty_conv_id = str(uuid.uuid4())
        db.add(
            Conversation(
                id=empty_conv_id,
                project_id=proj_id,
                title="empty conv",
                status="active",
            )
        )
        db.commit()

        req = CommitToStudioRequest(conversation_id=empty_conv_id, episode_number=1)
        enriched, warnings = enrich_request_from_conversation(db, req)
        assert len(enriched.panels) == 0
        assert len(enriched.characters) == 0
        assert warnings == []
    finally:
        db.close()


def test_wrong_episode_number_doesnt_pick_panels(seeded_conv):
    from app.core.database import SessionLocal
    from app.services.agent_commit.conversation_reader import enrich_request_from_conversation

    db = SessionLocal()
    try:
        req = CommitToStudioRequest(conversation_id=seeded_conv["conversation_id"], episode_number=99)
        enriched, _ = enrich_request_from_conversation(db, req)
        assert len(enriched.panels) == 0
        assert len(enriched.characters) == 2
    finally:
        db.close()
