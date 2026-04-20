"""Tests for agent_commit.asset_sync — DB-backed, mocks image fetcher."""
import uuid
import pytest
from unittest.mock import AsyncMock, patch

from app.schemas.agent_commit import AgentCharacter, AgentScene


@pytest.fixture
def project_in_db(test_client):
    import os; os.environ["ENABLE_AUTH"] = "false"
    from app.core.database import SessionLocal
    from app.models.project import Project
    db = SessionLocal()
    try:
        proj = Project(id=str(uuid.uuid4()), name="AST", description="")
        db.add(proj); db.commit()
        return proj.id
    finally:
        db.close()


class TestSyncCharacter:
    @pytest.mark.asyncio
    async def test_creates_new_character(self, project_in_db):
        from app.core.database import SessionLocal
        from app.services.agent_commit.asset_sync import sync_character
        from app.models.asset import Asset

        db = SessionLocal()
        try:
            with patch("app.services.agent_commit.asset_sync.fetch_and_persist",
                       new=AsyncMock(return_value="key/x.png")):
                char = AgentCharacter(name="Alice", temp_image_url="http://x.png")
                asset_id, warnings = await sync_character(db, project_in_db, char, source_conversation_id="conv-1")
                db.commit()
            assert warnings == []
            asset = db.query(Asset).filter(Asset.id == asset_id).first()
            assert asset is not None and asset.name == "Alice" and asset.type == "character"
            assert asset.thumbnail_url == "key/x.png"
            assert asset.data_json["created_via"] == "agent"
            assert asset.data_json["source_conversation_id"] == "conv-1"
        finally:
            db.close()

    @pytest.mark.asyncio
    async def test_reuses_existing_character(self, project_in_db):
        from app.core.database import SessionLocal
        from app.services.agent_commit.asset_sync import sync_character
        from app.models.asset import Asset

        db = SessionLocal()
        existing = Asset(id=str(uuid.uuid4()), project_id=project_in_db, type="character",
                         name="Bob", data_json={"created_via": "studio"})
        db.add(existing); db.commit(); existing_id = existing.id; db.close()

        db2 = SessionLocal()
        try:
            char = AgentCharacter(name="Bob")
            asset_id, warnings = await sync_character(db2, project_in_db, char, source_conversation_id="conv-2")
            assert asset_id == existing_id
            assert warnings == []
            asset = db2.query(Asset).filter(Asset.id == existing_id).first()
            assert asset.data_json["created_via"] == "studio"
        finally:
            db2.close()

    @pytest.mark.asyncio
    async def test_image_fetch_failure_becomes_warning(self, project_in_db):
        from app.core.database import SessionLocal
        from app.services.agent_commit.asset_sync import sync_character
        from app.services.agent_commit.image_fetcher import ImageFetchError
        from app.models.asset import Asset

        db = SessionLocal()
        try:
            with patch("app.services.agent_commit.asset_sync.fetch_and_persist",
                       new=AsyncMock(side_effect=ImageFetchError("404"))):
                char = AgentCharacter(name="Eve", temp_image_url="http://dead.png")
                asset_id, warnings = await sync_character(db, project_in_db, char, source_conversation_id="c")
                db.commit()
            assert len(warnings) == 1 and "Eve" in warnings[0]
            asset = db.query(Asset).filter(Asset.id == asset_id).first()
            assert asset.thumbnail_url is None
        finally:
            db.close()


class TestSyncScene:
    @pytest.mark.asyncio
    async def test_creates_new_scene(self, project_in_db):
        from app.core.database import SessionLocal
        from app.services.agent_commit.asset_sync import sync_scene
        from app.models.asset import Asset

        db = SessionLocal()
        try:
            with patch("app.services.agent_commit.asset_sync.fetch_and_persist",
                       new=AsyncMock(return_value="key/s.png")):
                scene = AgentScene(name="Rooftop", temp_image_url="http://s.png", time_of_day="sunset")
                asset_id, warnings = await sync_scene(db, project_in_db, scene, source_conversation_id="c-1")
                db.commit()
            asset = db.query(Asset).filter(Asset.id == asset_id).first()
            assert asset is not None and asset.type == "scene"
            assert asset.data_json["time_of_day"] == "sunset"
        finally:
            db.close()
