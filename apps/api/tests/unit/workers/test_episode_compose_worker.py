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
         patch("app.workers.episode_compose_worker.subprocess.run", side_effect=fake_subprocess) as sp_mock:

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
