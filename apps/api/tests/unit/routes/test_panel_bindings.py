"""Integration tests for PATCH /api/v1/panels/{panel_id}/bindings."""
import uuid
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def seeded(test_client: TestClient):
    """Seed one project, chapter, panel, and one character + one scene asset."""
    import os
    os.environ["ENABLE_AUTH"] = "false"

    from app.main import app
    from app.core.database import SessionLocal
    from app.models.project import Project
    from app.models.chapter import Chapter
    from app.models.panel import Panel
    from app.models.asset import Asset

    db = SessionLocal()
    try:
        proj = Project(id=str(uuid.uuid4()), name="T", description="")
        db.add(proj)
        ch = Chapter(
            id=str(uuid.uuid4()),
            project_id=proj.id,
            title="ch1",
            script_raw="hi",
        )
        db.add(ch)
        panel = Panel(
            id=str(uuid.uuid4()),
            chapter_id=ch.id,
            order_index=0,
            spec_json={"characters": [{"name": "Alice"}], "scene": {"location": "rooftop"}},
            render_status="draft",
        )
        db.add(panel)
        char_asset = Asset(
            id=str(uuid.uuid4()),
            project_id=proj.id,
            type="character",
            name="Alice",
            data_json={},
        )
        scene_asset = Asset(
            id=str(uuid.uuid4()),
            project_id=proj.id,
            type="scene",
            name="Rooftop",
            data_json={},
        )
        db.add_all([char_asset, scene_asset])
        db.commit()
        return {
            "project_id": proj.id,
            "chapter_id": ch.id,
            "panel_id": panel.id,
            "char_asset_id": char_asset.id,
            "scene_asset_id": scene_asset.id,
        }
    finally:
        db.close()


class TestPatchPanelBindings:
    def test_bind_character_happy_path(self, test_client, seeded):
        resp = test_client.patch(
            f"/api/v1/panels/{seeded['panel_id']}/bindings",
            json={"slot": "character", "slot_index": 0, "asset_id": seeded["char_asset_id"]},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["chapter_bindings_updated"] is True
        assert body["spec_json"]["characters"][0]["asset_id"] == seeded["char_asset_id"]

    def test_bind_scene_anchor(self, test_client, seeded):
        resp = test_client.patch(
            f"/api/v1/panels/{seeded['panel_id']}/bindings",
            json={"slot": "scene", "slot_index": 0, "asset_id": seeded["scene_asset_id"]},
        )
        assert resp.status_code == 200
        assert resp.json()["spec_json"]["scene"]["anchor_id"] == seeded["scene_asset_id"]

    def test_clear_binding(self, test_client, seeded):
        test_client.patch(
            f"/api/v1/panels/{seeded['panel_id']}/bindings",
            json={"slot": "character", "slot_index": 0, "asset_id": seeded["char_asset_id"]},
        )
        resp = test_client.patch(
            f"/api/v1/panels/{seeded['panel_id']}/bindings",
            json={"slot": "character", "slot_index": 0, "asset_id": None},
        )
        assert resp.status_code == 200
        assert "asset_id" not in resp.json()["spec_json"]["characters"][0]

    def test_panel_not_found(self, test_client):
        resp = test_client.patch(
            "/api/v1/panels/bogus/bindings",
            json={"slot": "character", "slot_index": 0, "asset_id": "x"},
        )
        assert resp.status_code == 404

    def test_asset_type_mismatch(self, test_client, seeded):
        # Bind a scene asset into a character slot → 400
        resp = test_client.patch(
            f"/api/v1/panels/{seeded['panel_id']}/bindings",
            json={"slot": "character", "slot_index": 0, "asset_id": seeded["scene_asset_id"]},
        )
        assert resp.status_code == 400

    def test_asset_not_found(self, test_client, seeded):
        resp = test_client.patch(
            f"/api/v1/panels/{seeded['panel_id']}/bindings",
            json={"slot": "character", "slot_index": 0, "asset_id": "does-not-exist"},
        )
        assert resp.status_code == 404

    def test_rendering_returns_409(self, test_client, seeded):
        from app.core.database import SessionLocal
        from app.models.panel import Panel

        db = SessionLocal()
        try:
            p = db.query(Panel).filter(Panel.id == seeded["panel_id"]).first()
            p.render_status = "running"
            db.commit()
        finally:
            db.close()

        resp = test_client.patch(
            f"/api/v1/panels/{seeded['panel_id']}/bindings",
            json={"slot": "character", "slot_index": 0, "asset_id": seeded["char_asset_id"]},
        )
        assert resp.status_code == 409

    def test_chapter_bindings_aggregate_refreshed(self, test_client, seeded):
        from app.core.database import SessionLocal
        from app.models.bindings import ChapterBindings

        test_client.patch(
            f"/api/v1/panels/{seeded['panel_id']}/bindings",
            json={"slot": "character", "slot_index": 0, "asset_id": seeded["char_asset_id"]},
        )
        test_client.patch(
            f"/api/v1/panels/{seeded['panel_id']}/bindings",
            json={"slot": "scene", "slot_index": 0, "asset_id": seeded["scene_asset_id"]},
        )

        db = SessionLocal()
        try:
            cb = db.query(ChapterBindings).filter(
                ChapterBindings.chapter_id == seeded["chapter_id"]
            ).first()
            assert cb is not None
            assert seeded["char_asset_id"] in (cb.identity_asset_ids or [])
            assert seeded["scene_asset_id"] in (cb.scene_asset_ids or [])
        finally:
            db.close()
