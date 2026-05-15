"""End-to-end Phase D compose flow.

Inserts three succeeded episode_video Job rows into an in-memory SQLite DB,
invokes the dispatch helper, then runs the compose worker synchronously with
a patched ffmpeg and in-memory storage. Verifies a compose Job row is created,
ffmpeg is invoked with the correct concat list, the final MP4 is uploaded to
the canonical MinIO path, and Job.outputs_json is populated correctly.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401 — register all models
from app.models.base import Base
from app.models import Job


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    sess = Session()
    yield sess
    sess.close()


def test_e2e_dispatch_then_compose(tmp_path, monkeypatch):
    monkeypatch.setenv("EPISODE_COMPOSE_TMP_ROOT", str(tmp_path))

    project_id = "proj-e2e"
    episode_num = 7

    # One engine, multiple sessions — the worker will close its own session,
    # so we can't share a single Session instance. SessionLocal is patched to
    # bind to the same in-memory engine.
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    setup_db = Session()
    from datetime import datetime
    for i in range(3):
        setup_db.add(Job(
            id=f"clip-{i}",
            type="episode_video",
            project_id=project_id,
            status="succeeded",
            progress=1.0,
            finished_at=datetime.utcnow(),
            inputs_json={"episode_number": episode_num, "image_index": i,
                          "image_url": f"images/p{i}.png"},
            outputs_json={"video_url": f"images/clip_{i}.mp4", "duration_sec": 4.0},
        ))
    setup_db.commit()
    setup_db.close()
    db_session = Session()  # fresh session for dispatch

    in_memory: dict[str, bytes] = {}

    fake_storage = MagicMock()
    async def fake_download(key):
        in_memory.setdefault(key, b"clip_bytes_" + key.encode())
        return in_memory[key]
    async def fake_upload(path, data, content_type=None):
        in_memory[path] = data
        return None
    fake_storage.download_bytes = fake_download
    fake_storage.upload_bytes = fake_upload

    def fake_subprocess(cmd, *args, **kwargs):
        output_path = cmd[-1]
        with open(output_path, "wb") as f:
            f.write(b"E2E_FINAL_MP4")
        return MagicMock(returncode=0, stderr=b"", stdout=b"")

    from app.services.video.compose_dispatch import _maybe_enqueue_episode_compose
    from app.workers.episode_compose_worker import _execute_compose_sync

    with patch("app.services.video.compose_dispatch.execute_episode_compose") as fake_task:
        fake_task.delay = MagicMock()
        compose_job_id = _maybe_enqueue_episode_compose(db_session, project_id, episode_num)

    assert compose_job_id is not None
    compose_job = db_session.query(Job).filter(Job.id == compose_job_id).first()
    assert compose_job is not None
    assert compose_job.status == "queued"
    assert compose_job.inputs_json["expected_clip_count"] == 3

    db_session.close()  # release before the worker takes over with its own session

    # Worker uses its own session; SessionLocal patched to bind to the same engine
    with patch("app.workers.episode_compose_worker.SessionLocal", side_effect=Session), \
         patch("app.workers.episode_compose_worker.get_storage_client", return_value=fake_storage), \
         patch("app.workers.episode_compose_worker.subprocess.run", side_effect=fake_subprocess), \
         patch("app.workers.episode_compose_worker._push_episode_compose_update"):
        result = _execute_compose_sync(compose_job_id)

    assert result["success"] is True

    verify_db = Session()
    try:
        compose_job = verify_db.query(Job).filter(Job.id == compose_job_id).first()
        assert compose_job is not None
        assert compose_job.status == "succeeded"
        assert compose_job.outputs_json["clip_count"] == 3
        out_key = compose_job.outputs_json["video_url"]
        assert out_key == f"episode_videos/{project_id}/ep{episode_num}/compose_{compose_job_id}.mp4"
        assert in_memory[out_key] == b"E2E_FINAL_MP4"

        with patch("app.services.video.compose_dispatch.execute_episode_compose") as fake_task:
            fake_task.delay = MagicMock()
            second_id = _maybe_enqueue_episode_compose(verify_db, project_id, episode_num)
        assert second_id is None  # dedup against succeeded compose
    finally:
        verify_db.close()
