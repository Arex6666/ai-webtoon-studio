"""Unit tests for the Phase D compose API endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


@pytest.fixture
def fake_db():
    db = MagicMock()
    return db


def test_get_compose_job_status_succeeded(client, fake_db):
    from app.models import Job
    job = MagicMock(spec=Job)
    job.id = "comp-1"
    job.status = "succeeded"
    job.progress = 1.0
    job.outputs_json = {"video_url": "episode_videos/p1/ep1/compose_comp-1.mp4",
                         "clip_count": 3, "duration_sec": 15.0}
    job.error_json = None
    fake_db.query.return_value.filter.return_value.first.return_value = job

    from app.db.database import get_db
    from app.main import app
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        resp = client.get("/api/v1/agent/episode/compose-jobs/comp-1")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == "comp-1"
    assert body["status"] == "succeeded"
    assert body["video_url"].endswith("compose_comp-1.mp4")
    assert body["clip_count"] == 3


def test_get_compose_job_status_404(client, fake_db):
    fake_db.query.return_value.filter.return_value.first.return_value = None

    from app.db.database import get_db
    from app.main import app
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        resp = client.get("/api/v1/agent/episode/compose-jobs/nope")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


def test_retry_endpoint_requires_all_clips_succeeded(client, fake_db):
    """If any sibling clip is not 'succeeded', 409."""
    from tests.unit.workers._episode_helpers import make_episode_video_job

    siblings = [
        make_episode_video_job("c0", "p1", 1, 0, status="succeeded"),
        make_episode_video_job("c1", "p1", 1, 1, status="failed"),
    ]
    fake_db.query.return_value.filter.return_value.all.return_value = siblings

    from app.db.database import get_db
    from app.main import app
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        resp = client.post("/api/v1/agent/episode/1/compose-video/retry", json={"project_id": "p1"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 409


def test_retry_endpoint_creates_new_compose_bypassing_dedup(client, fake_db):
    """All clips succeeded + a prior succeeded compose exists → retry STILL creates a new one."""
    from tests.unit.workers._episode_helpers import make_episode_video_job, make_compose_job

    siblings = [make_episode_video_job("c0", "p1", 1, 0, status="succeeded")]
    fake_db.query.return_value.filter.return_value.all.return_value = siblings
    fake_db.add = MagicMock()
    fake_db.commit = MagicMock()

    from app.db.database import get_db
    from app.main import app
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        with patch("app.workers.episode_compose_worker.execute_episode_compose") as fake_task:
            fake_task.delay = MagicMock()
            resp = client.post("/api/v1/agent/episode/1/compose-video/retry", json={"project_id": "p1"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert "job_id" in body
    assert body["status"] == "queued"
    fake_db.add.assert_called_once()
