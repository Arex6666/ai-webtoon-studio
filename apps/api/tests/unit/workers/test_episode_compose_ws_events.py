"""Verify compose worker emits the expected WS events at each stage (Phase D)."""
from unittest.mock import AsyncMock, MagicMock, patch

from tests.unit.workers._episode_helpers import (
    make_episode_video_job,
    make_compose_job,
    time_offset,
)


def test_compose_emits_events_on_success(tmp_path, monkeypatch):
    monkeypatch.setenv("EPISODE_COMPOSE_TMP_ROOT", str(tmp_path))

    compose_job = make_compose_job("comp-ws", "p1", 1, expected_clip_count=2)
    siblings = [
        make_episode_video_job("c0", "p1", 1, 0, status="succeeded",
                                video_url="images/c0.mp4", finished_at=time_offset(0)),
        make_episode_video_job("c1", "p1", 1, 1, status="succeeded",
                                video_url="images/c1.mp4", finished_at=time_offset(0)),
    ]

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = compose_job
    db.query.return_value.filter.return_value.all.return_value = siblings

    fake_storage = MagicMock()
    fake_storage.download_bytes = AsyncMock(return_value=b"clip")
    fake_storage.upload_bytes = AsyncMock(return_value=None)

    def fake_subprocess(cmd, *args, **kwargs):
        output_path = cmd[-1]
        with open(output_path, "wb") as f:
            f.write(b"ok")
        return MagicMock(returncode=0, stderr=b"", stdout=b"")

    emitted_events = []

    def fake_emit(project_id, episode_number, event_type, data):
        emitted_events.append({"event": event_type, "data": data,
                                "project_id": project_id, "episode_number": episode_number})

    with patch("app.workers.episode_compose_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_compose_worker.get_storage_client", return_value=fake_storage), \
         patch("app.workers.episode_compose_worker.subprocess.run", side_effect=fake_subprocess), \
         patch("app.workers.episode_compose_worker._push_episode_compose_update", side_effect=fake_emit):

        from app.workers.episode_compose_worker import _execute_compose_sync
        _execute_compose_sync("comp-ws")

    event_types = [e["event"] for e in emitted_events]
    assert "episode_compose_progress" in event_types
    assert "episode_compose_done" in event_types
    done_event = next(e for e in emitted_events if e["event"] == "episode_compose_done")
    assert "video_url" in done_event["data"]
    assert done_event["data"]["clip_count"] == 2


def test_compose_emits_failed_event_on_ffmpeg_error(tmp_path, monkeypatch):
    monkeypatch.setenv("EPISODE_COMPOSE_TMP_ROOT", str(tmp_path))

    compose_job = make_compose_job("comp-wsf", "p1", 1, expected_clip_count=1)
    siblings = [
        make_episode_video_job("c0", "p1", 1, 0, status="succeeded",
                                video_url="images/c0.mp4", finished_at=time_offset(0)),
    ]
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = compose_job
    db.query.return_value.filter.return_value.all.return_value = siblings

    fake_storage = MagicMock()
    fake_storage.download_bytes = AsyncMock(return_value=b"clip")

    def fake_subprocess(cmd, *args, **kwargs):
        return MagicMock(returncode=1, stderr=b"boom", stdout=b"")

    emitted = []
    def fake_emit(project_id, episode_number, event_type, data):
        emitted.append((event_type, data))

    with patch("app.workers.episode_compose_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_compose_worker.get_storage_client", return_value=fake_storage), \
         patch("app.workers.episode_compose_worker.subprocess.run", side_effect=fake_subprocess), \
         patch("app.workers.episode_compose_worker._push_episode_compose_update", side_effect=fake_emit):

        from app.workers.episode_compose_worker import _execute_compose_sync
        _execute_compose_sync("comp-wsf")

    failed_events = [e for e in emitted if e[0] == "episode_compose_failed"]
    assert len(failed_events) == 1
    assert failed_events[0][1]["error_code"] == "FFMPEG_FAILED"
