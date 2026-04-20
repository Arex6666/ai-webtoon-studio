"""Integration tests for GET /api/v1/assets/{asset_id}/usage."""
import uuid
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def seeded_usage(test_client: TestClient):
    import os
    os.environ["ENABLE_AUTH"] = "false"

    from app.core.database import SessionLocal
    from app.models.project import Project
    from app.models.chapter import Chapter
    from app.models.panel import Panel
    from app.models.asset import Asset

    db = SessionLocal()
    try:
        proj = Project(id=str(uuid.uuid4()), name="UP", description="")
        db.add(proj)
        ch = Chapter(
            id=str(uuid.uuid4()),
            project_id=proj.id,
            title="Ep1",
            script_raw="",
        )
        db.add(ch)
        asset = Asset(
            id=str(uuid.uuid4()),
            project_id=proj.id,
            type="character",
            name="Hero",
            data_json={},
        )
        db.add(asset)

        used_panel = Panel(
            id=str(uuid.uuid4()),
            chapter_id=ch.id,
            order_index=0,
            spec_json={"characters": [{"name": "Hero", "asset_id": asset.id}]},
        )
        unused_panel = Panel(
            id=str(uuid.uuid4()),
            chapter_id=ch.id,
            order_index=1,
            spec_json={"characters": [{"name": "Other"}]},
        )
        db.add_all([used_panel, unused_panel])
        db.commit()
        return {
            "asset_id": asset.id,
            "used_panel_id": used_panel.id,
            "unused_panel_id": unused_panel.id,
            "chapter_id": ch.id,
        }
    finally:
        db.close()


class TestAssetUsage:
    def test_returns_referring_panels(self, test_client, seeded_usage):
        resp = test_client.get(f"/api/v1/assets/{seeded_usage['asset_id']}/usage")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] == 1
        assert body["references"][0]["panel_id"] == seeded_usage["used_panel_id"]
        assert body["references"][0]["chapter_id"] == seeded_usage["chapter_id"]

    def test_asset_not_found(self, test_client):
        resp = test_client.get("/api/v1/assets/does-not-exist/usage")
        assert resp.status_code == 404

    def test_no_references(self, test_client):
        import uuid as _u
        from app.core.database import SessionLocal
        from app.models.project import Project
        from app.models.asset import Asset

        db = SessionLocal()
        try:
            proj = Project(id=str(_u.uuid4()), name="X", description="")
            db.add(proj)
            orphan = Asset(
                id=str(_u.uuid4()),
                project_id=proj.id,
                type="character",
                name="Orphan",
                data_json={},
            )
            db.add(orphan)
            db.commit()
            asset_id = orphan.id
        finally:
            db.close()

        resp = test_client.get(f"/api/v1/assets/{asset_id}/usage")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_count"] == 0
        assert body["references"] == []
