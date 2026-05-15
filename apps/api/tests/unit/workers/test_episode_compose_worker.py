"""Unit tests for episode_compose_worker (Phase D)."""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.unit.workers._episode_helpers import (
    make_episode_video_job,
    make_compose_job,
    time_offset,
)


def test_compose_happy_path_three_clips(tmp_path, monkeypatch):
    """3 succeeded clips → download → ffmpeg concat → upload → status=succeeded."""
    monkeypatch.setenv("EPISODE_COMPOSE_TMP_ROOT", str(tmp_path))

    project_id = "p1"
    ep_num = 1
    compose_job = make_compose_job("comp-1", project_id, ep_num, status="queued", expected_clip_count=3)
    siblings = [
        make_episode_video_job("c0", project_id, ep_num, 0, status="succeeded",
                                video_url="images/c0.mp4", finished_at=time_offset(0)),
        make_episode_video_job("c1", project_id, ep_num, 1, status="succeeded",
                                video_url="images/c1.mp4", finished_at=time_offset(1)),
        make_episode_video_job("c2", project_id, ep_num, 2, status="succeeded",
                                video_url="images/c2.mp4", finished_at=time_offset(2)),
    ]

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = compose_job
    db.query.return_value.filter.return_value.all.return_value = siblings

    fake_storage = MagicMock()
    fake_storage.download_bytes = AsyncMock(side_effect=[b"clip0", b"clip1", b"clip2"])
    fake_storage.upload_bytes = AsyncMock(return_value=None)

    def fake_subprocess(cmd, *args, **kwargs):
        output_path = cmd[-1]
        with open(output_path, "wb") as f:
            f.write(b"fake_output_mp4_bytes")
        return MagicMock(returncode=0, stderr=b"", stdout=b"")

    with patch("app.workers.episode_compose_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_compose_worker.get_storage_client", return_value=fake_storage), \
         patch("app.workers.episode_compose_worker.subprocess.run", side_effect=fake_subprocess) as sp_mock, \
         patch("app.workers.episode_compose_worker._push_episode_compose_update"):

        from app.workers.episode_compose_worker import _execute_compose_sync
        result = _execute_compose_sync("comp-1")

    assert result["success"] is True
    assert compose_job.status == "succeeded"
    assert compose_job.outputs_json["clip_count"] == 3
    assert compose_job.outputs_json["video_url"].startswith(f"episode_videos/{project_id}/ep{ep_num}/compose_")

    invoked_cmd = sp_mock.call_args.args[0]
    assert invoked_cmd[0] == "ffmpeg"
    assert "-f" in invoked_cmd and "concat" in invoked_cmd
    assert "-safe" in invoked_cmd
    assert "-c" in invoked_cmd and "copy" in invoked_cmd

    assert fake_storage.download_bytes.await_count == 3
    fake_storage.upload_bytes.assert_awaited_once()


def test_compose_resolves_latest_succeeded_per_image_index(tmp_path, monkeypatch):
    """Two succeeded clips at index 0 → the latest finished_at wins."""
    monkeypatch.setenv("EPISODE_COMPOSE_TMP_ROOT", str(tmp_path))

    project_id = "p1"
    compose_job = make_compose_job("comp-x", project_id, 1, status="queued", expected_clip_count=2)

    siblings = [
        make_episode_video_job("old0", project_id, 1, 0, status="succeeded",
                                video_url="images/old0.mp4", finished_at=time_offset(0)),
        make_episode_video_job("new0", project_id, 1, 0, status="succeeded",
                                video_url="images/new0.mp4", finished_at=time_offset(60)),
        make_episode_video_job("a1", project_id, 1, 1, status="succeeded",
                                video_url="images/a1.mp4", finished_at=time_offset(10)),
    ]

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = compose_job
    db.query.return_value.filter.return_value.all.return_value = siblings

    downloaded_keys = []

    fake_storage = MagicMock()
    async def fake_download(key):
        downloaded_keys.append(key)
        return b"clip-bytes"
    fake_storage.download_bytes = fake_download
    fake_storage.upload_bytes = AsyncMock(return_value=None)

    def fake_subprocess(cmd, *args, **kwargs):
        output_path = cmd[-1]
        with open(output_path, "wb") as f:
            f.write(b"ok")
        return MagicMock(returncode=0, stderr=b"", stdout=b"")

    with patch("app.workers.episode_compose_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_compose_worker.get_storage_client", return_value=fake_storage), \
         patch("app.workers.episode_compose_worker.subprocess.run", side_effect=fake_subprocess), \
         patch("app.workers.episode_compose_worker._push_episode_compose_update"):

        from app.workers.episode_compose_worker import _execute_compose_sync
        result = _execute_compose_sync("comp-x")

    assert result["success"] is True
    assert downloaded_keys == ["images/new0.mp4", "images/a1.mp4"]


def test_compose_missing_clips_fails(tmp_path, monkeypatch):
    """expected_clip_count = 3 but only 2 succeeded clips found → MISSING_CLIPS."""
    monkeypatch.setenv("EPISODE_COMPOSE_TMP_ROOT", str(tmp_path))

    compose_job = make_compose_job("comp-m", "p1", 1, expected_clip_count=3)
    siblings = [
        make_episode_video_job("c0", "p1", 1, 0, status="succeeded", finished_at=time_offset(0)),
        make_episode_video_job("c1", "p1", 1, 1, status="succeeded", finished_at=time_offset(0)),
    ]

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = compose_job
    db.query.return_value.filter.return_value.all.return_value = siblings

    with patch("app.workers.episode_compose_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_compose_worker.get_storage_client"), \
         patch("app.workers.episode_compose_worker.subprocess.run"), \
         patch("app.workers.episode_compose_worker._push_episode_compose_update"):
        from app.workers.episode_compose_worker import _execute_compose_sync
        result = _execute_compose_sync("comp-m")

    assert result["success"] is False
    assert result["code"] == "MISSING_CLIPS"
    assert compose_job.status == "failed"
    assert compose_job.error_json["code"] == "MISSING_CLIPS"


def test_compose_download_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("EPISODE_COMPOSE_TMP_ROOT", str(tmp_path))

    compose_job = make_compose_job("comp-d", "p1", 1, expected_clip_count=1)
    siblings = [
        make_episode_video_job("c0", "p1", 1, 0, status="succeeded",
                                video_url="images/c0.mp4", finished_at=time_offset(0)),
    ]

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = compose_job
    db.query.return_value.filter.return_value.all.return_value = siblings

    fake_storage = MagicMock()
    fake_storage.download_bytes = AsyncMock(side_effect=RuntimeError("network down"))

    with patch("app.workers.episode_compose_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_compose_worker.get_storage_client", return_value=fake_storage), \
         patch("app.workers.episode_compose_worker._push_episode_compose_update"):
        from app.workers.episode_compose_worker import _execute_compose_sync
        result = _execute_compose_sync("comp-d")

    assert result["success"] is False
    assert result["code"] == "DOWNLOAD_FAILED"


def test_compose_ffmpeg_failure_captures_stderr(tmp_path, monkeypatch):
    monkeypatch.setenv("EPISODE_COMPOSE_TMP_ROOT", str(tmp_path))

    compose_job = make_compose_job("comp-f", "p1", 1, expected_clip_count=1)
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
        return MagicMock(returncode=1, stderr=b"ffmpeg: codec mismatch", stdout=b"")

    with patch("app.workers.episode_compose_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_compose_worker.get_storage_client", return_value=fake_storage), \
         patch("app.workers.episode_compose_worker.subprocess.run", side_effect=fake_subprocess), \
         patch("app.workers.episode_compose_worker._push_episode_compose_update"):
        from app.workers.episode_compose_worker import _execute_compose_sync
        result = _execute_compose_sync("comp-f")

    assert result["success"] is False
    assert result["code"] == "FFMPEG_FAILED"
    assert "codec mismatch" in compose_job.error_json["ffmpeg_stderr"]


def test_compose_upload_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("EPISODE_COMPOSE_TMP_ROOT", str(tmp_path))

    compose_job = make_compose_job("comp-u", "p1", 1, expected_clip_count=1)
    siblings = [
        make_episode_video_job("c0", "p1", 1, 0, status="succeeded",
                                video_url="images/c0.mp4", finished_at=time_offset(0)),
    ]
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = compose_job
    db.query.return_value.filter.return_value.all.return_value = siblings

    fake_storage = MagicMock()
    fake_storage.download_bytes = AsyncMock(return_value=b"clip")
    fake_storage.upload_bytes = AsyncMock(side_effect=RuntimeError("S3 down"))

    def fake_subprocess(cmd, *args, **kwargs):
        output_path = cmd[-1]
        with open(output_path, "wb") as f:
            f.write(b"out")
        return MagicMock(returncode=0, stderr=b"", stdout=b"")

    with patch("app.workers.episode_compose_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_compose_worker.get_storage_client", return_value=fake_storage), \
         patch("app.workers.episode_compose_worker.subprocess.run", side_effect=fake_subprocess), \
         patch("app.workers.episode_compose_worker._push_episode_compose_update"):
        from app.workers.episode_compose_worker import _execute_compose_sync
        result = _execute_compose_sync("comp-u")

    assert result["success"] is False
    assert result["code"] == "UPLOAD_FAILED"


def test_compose_concat_list_contents(tmp_path, monkeypatch):
    """Verify the concat list file written before ffmpeg lists clips in image_index order."""
    monkeypatch.setenv("EPISODE_COMPOSE_TMP_ROOT", str(tmp_path))

    compose_job = make_compose_job("comp-cl", "p1", 1, expected_clip_count=3)
    siblings = [
        make_episode_video_job("c2", "p1", 1, 2, status="succeeded",
                                video_url="images/c2.mp4", finished_at=time_offset(0)),
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

    list_contents = {}
    def fake_subprocess(cmd, *args, **kwargs):
        i_idx = cmd.index("-i")
        list_file = cmd[i_idx + 1]
        with open(list_file, "r", encoding="utf-8") as f:
            list_contents["text"] = f.read()
        output_path = cmd[-1]
        with open(output_path, "wb") as f:
            f.write(b"ok")
        return MagicMock(returncode=0, stderr=b"", stdout=b"")

    with patch("app.workers.episode_compose_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_compose_worker.get_storage_client", return_value=fake_storage), \
         patch("app.workers.episode_compose_worker.subprocess.run", side_effect=fake_subprocess), \
         patch("app.workers.episode_compose_worker._push_episode_compose_update"):
        from app.workers.episode_compose_worker import _execute_compose_sync
        result = _execute_compose_sync("comp-cl")

    assert result["success"] is True
    text = list_contents["text"]
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    assert lines == ["file 'clip_000.mp4'", "file 'clip_001.mp4'", "file 'clip_002.mp4'"]
