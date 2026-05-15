"""Verify the auto-trigger hook fires (or skips correctly) at clip success."""
from unittest.mock import MagicMock, patch

import pytest


def test_episode_video_success_calls_compose_dispatch():
    """When a clip job succeeds, the dispatch helper is invoked exactly once."""
    fake_job = MagicMock()
    fake_job.id = "v1"
    fake_job.project_id = "p1"
    fake_job.inputs_json = {"episode_number": 1, "image_index": 0}

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = fake_job

    fake_provider = MagicMock()
    fake_result = MagicMock(
        success=True, video_url="x", preview_url="x", duration_sec=5.0,
        provider="doubao", seed=0, cost=0.0,
    )

    with patch("app.workers.episode_video_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_video_worker.get_video_provider", return_value=fake_provider), \
         patch("app.workers.episode_video_worker.run_async", return_value=fake_result), \
         patch("app.workers.episode_video_worker._maybe_enqueue_episode_compose") as dispatch_mock:

        from app.workers.episode_video_worker import generate_episode_video_task
        generate_episode_video_task.run(
            job_id="v1",
            image_url="images/in.png",
            motion_prompt="x",
            duration_sec=3.0,
            provider_name="doubao",
        )

    dispatch_mock.assert_called_once_with(db, "p1", 1)


def test_episode_video_failure_does_not_call_dispatch():
    """On clip failure, dispatch must NOT be called — strict policy."""
    fake_job = MagicMock()
    fake_job.id = "v2"
    fake_job.project_id = "p1"
    fake_job.inputs_json = {"episode_number": 1, "image_index": 0}

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = fake_job

    fake_provider = MagicMock()
    fake_result = MagicMock(success=False, error="boom", error_code="X")

    with patch("app.workers.episode_video_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_video_worker.get_video_provider", return_value=fake_provider), \
         patch("app.workers.episode_video_worker.run_async", return_value=fake_result), \
         patch("app.workers.episode_video_worker._maybe_enqueue_episode_compose") as dispatch_mock:

        from app.workers.episode_video_worker import generate_episode_video_task
        generate_episode_video_task.run(
            job_id="v2",
            image_url="images/in.png",
            motion_prompt="x",
            duration_sec=3.0,
            provider_name="doubao",
        )

    dispatch_mock.assert_not_called()


def test_episode_video_dispatch_error_does_not_fail_clip():
    """If dispatch helper raises, clip status must still be 'succeeded'."""
    fake_job = MagicMock()
    fake_job.id = "v3"
    fake_job.project_id = "p1"
    fake_job.inputs_json = {"episode_number": 1, "image_index": 0}

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = fake_job

    fake_provider = MagicMock()
    fake_result = MagicMock(success=True, video_url="x", preview_url="x",
                             duration_sec=5.0, provider="doubao", seed=0, cost=0.0)

    with patch("app.workers.episode_video_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_video_worker.get_video_provider", return_value=fake_provider), \
         patch("app.workers.episode_video_worker.run_async", return_value=fake_result), \
         patch("app.workers.episode_video_worker._maybe_enqueue_episode_compose",
               side_effect=RuntimeError("dispatch helper crash")):

        from app.workers.episode_video_worker import generate_episode_video_task
        ret = generate_episode_video_task.run(
            job_id="v3",
            image_url="images/in.png",
            motion_prompt="x",
            duration_sec=3.0,
            provider_name="doubao",
        )

    assert ret["success"] is True
    assert fake_job.status == "succeeded"
