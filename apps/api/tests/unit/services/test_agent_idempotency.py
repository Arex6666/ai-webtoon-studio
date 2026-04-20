"""Tests for agent_commit.idempotency."""
import uuid
import pytest


@pytest.fixture
def seeded(test_client):
    import os; os.environ["ENABLE_AUTH"] = "false"
    from app.core.database import SessionLocal
    from app.models.project import Project
    from app.models.chapter import Chapter

    db = SessionLocal()
    try:
        proj = Project(id=str(uuid.uuid4()), name="I", description="")
        db.add(proj)
        ch1 = Chapter(id=str(uuid.uuid4()), project_id=proj.id, title="ep1",
                      layout_json={"source": {"type": "agent", "conversation_id": "c1", "episode_number": 1}})
        ch2 = Chapter(id=str(uuid.uuid4()), project_id=proj.id, title="ep2",
                      layout_json={"source": {"type": "agent", "conversation_id": "c1", "episode_number": 2}})
        ch_plain = Chapter(id=str(uuid.uuid4()), project_id=proj.id, title="manual",
                           layout_json={})
        db.add_all([ch1, ch2, ch_plain]); db.commit()
        return {"project_id": proj.id, "ch1_id": ch1.id, "ch2_id": ch2.id}
    finally:
        db.close()


def test_finds_matching_chapter(seeded):
    from app.core.database import SessionLocal
    from app.services.agent_commit.idempotency import find_existing_chapter
    db = SessionLocal()
    try:
        ch = find_existing_chapter(db, project_id=seeded["project_id"], conversation_id="c1", episode_number=1)
        assert ch is not None and ch.id == seeded["ch1_id"]
    finally:
        db.close()


def test_returns_none_for_unknown_episode(seeded):
    from app.core.database import SessionLocal
    from app.services.agent_commit.idempotency import find_existing_chapter
    db = SessionLocal()
    try:
        ch = find_existing_chapter(db, project_id=seeded["project_id"], conversation_id="c1", episode_number=99)
        assert ch is None
    finally:
        db.close()


def test_returns_none_for_different_conversation(seeded):
    from app.core.database import SessionLocal
    from app.services.agent_commit.idempotency import find_existing_chapter
    db = SessionLocal()
    try:
        ch = find_existing_chapter(db, project_id=seeded["project_id"], conversation_id="c-other", episode_number=1)
        assert ch is None
    finally:
        db.close()


def test_ignores_chapter_without_source(seeded):
    from app.core.database import SessionLocal
    from app.services.agent_commit.idempotency import find_existing_chapter
    db = SessionLocal()
    try:
        ch = find_existing_chapter(db, project_id=seeded["project_id"], conversation_id="c1", episode_number=1)
        assert ch.id == seeded["ch1_id"]
    finally:
        db.close()
