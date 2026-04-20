"""Tests for agent_commit.card_writer."""
import uuid
import pytest


@pytest.fixture
def seeded_conversation(test_client):
    import os; os.environ["ENABLE_AUTH"] = "false"
    from app.core.database import SessionLocal
    from app.models.project import Project
    from app.models.conversation import Conversation
    db = SessionLocal()
    try:
        proj = Project(id=str(uuid.uuid4()), name="CW", description="")
        db.add(proj)
        conv = Conversation(
            id=str(uuid.uuid4()), project_id=proj.id,
            title="test", status="active",
        )
        db.add(conv)
        db.commit()
        return {"conversation_id": conv.id, "project_id": proj.id}
    finally:
        db.close()


class TestUpsertCard:
    def test_creates_new_card_when_absent(self, seeded_conversation):
        from app.core.database import SessionLocal
        from app.models.conversation_message import ConversationMessage
        from app.services.agent_commit.card_writer import upsert_card, build_characters_card

        db = SessionLocal()
        try:
            data = build_characters_card([{"name": "Alice"}])
            msg = upsert_card(db, seeded_conversation["conversation_id"],
                              "characters", data)
            db.commit()
            assert msg.entities_json["card"]["type"] == "characters"
            count = db.query(ConversationMessage).filter(
                ConversationMessage.conversation_id == seeded_conversation["conversation_id"]
            ).count()
            assert count == 1
        finally:
            db.close()

    def test_updates_existing_card_in_place(self, seeded_conversation):
        from app.core.database import SessionLocal
        from app.models.conversation_message import ConversationMessage
        from app.services.agent_commit.card_writer import upsert_card, build_characters_card

        db = SessionLocal()
        try:
            upsert_card(db, seeded_conversation["conversation_id"],
                        "characters", build_characters_card([{"name": "Alice"}]))
            db.commit()
            upsert_card(db, seeded_conversation["conversation_id"],
                        "characters", build_characters_card([{"name": "Bob"}]))
            db.commit()

            msgs = db.query(ConversationMessage).filter(
                ConversationMessage.conversation_id == seeded_conversation["conversation_id"]
            ).all()
            assert len(msgs) == 1  # upsert did NOT duplicate
            assert msgs[0].entities_json["card"]["characters"][0]["name"] == "Bob"
        finally:
            db.close()

    def test_panels_card_discriminates_by_episode(self, seeded_conversation):
        from app.core.database import SessionLocal
        from app.models.conversation_message import ConversationMessage
        from app.services.agent_commit.card_writer import upsert_card, build_panels_card

        db = SessionLocal()
        try:
            upsert_card(db, seeded_conversation["conversation_id"],
                        "panels",
                        build_panels_card([{"id": "p1", "order": 0}]),
                        episode_number=1)
            upsert_card(db, seeded_conversation["conversation_id"],
                        "panels",
                        build_panels_card([{"id": "p2", "order": 0}]),
                        episode_number=2)
            db.commit()

            msgs = db.query(ConversationMessage).filter(
                ConversationMessage.conversation_id == seeded_conversation["conversation_id"]
            ).all()
            assert len(msgs) == 2
            ep_numbers = {m.entities_json["card"]["episode_number"] for m in msgs}
            assert ep_numbers == {1, 2}
        finally:
            db.close()


class TestCardBuilders:
    def test_characters_filters_empty_names(self):
        from app.services.agent_commit.card_writer import build_characters_card
        out = build_characters_card([{"name": "Alice"}, {"name": ""}, {"name": None}, None])
        assert len(out["characters"]) == 1

    def test_scenes_prefers_image_url_over_temp_image_url(self):
        from app.services.agent_commit.card_writer import build_scenes_card
        out = build_scenes_card([{"name": "Rooftop", "image_url": "a", "temp_image_url": "b"}])
        assert out["scenes"][0]["temp_image_url"] == "a"

    def test_panels_defaults_shot_and_camera(self):
        from app.services.agent_commit.card_writer import build_panels_card
        out = build_panels_card([{"id": "p", "order": 0}])
        assert out["panels"][0]["shot_type"] == "MS"
        assert out["panels"][0]["camera_angle"] == "eye-level"

    def test_art_style_all_empty_defaults(self):
        from app.services.agent_commit.card_writer import build_art_style_card
        out = build_art_style_card()
        assert out == {"base_style": "", "color_tone": "", "atmosphere": ""}
