"""Shared fixtures for episode_compose unit tests (Phase D).

Provides factories for Job rows in canonical states so each test can describe
its scenario in one or two lines.
"""
from datetime import datetime, timedelta
from typing import Optional

from app.models import Job


def make_episode_video_job(
    job_id: str,
    project_id: str,
    episode_number: int,
    image_index: int,
    status: str = "succeeded",
    video_url: Optional[str] = "images/clip.mp4",
    finished_at: Optional[datetime] = None,
) -> Job:
    """Build an episode_video Job row in any lifecycle state."""
    return Job(
        id=job_id,
        type="episode_video",
        project_id=project_id,
        status=status,
        progress=1.0 if status == "succeeded" else 0.0,
        finished_at=finished_at or (datetime.utcnow() if status == "succeeded" else None),
        inputs_json={
            "episode_number": episode_number,
            "image_index": image_index,
            "image_url": f"images/panel_{image_index}.png",
        },
        outputs_json=(
            {"video_url": video_url, "duration_sec": 5.0}
            if status == "succeeded" and video_url else None
        ),
    )


def make_compose_job(
    job_id: str,
    project_id: str,
    episode_number: int,
    status: str = "queued",
    expected_clip_count: int = 3,
) -> Job:
    return Job(
        id=job_id,
        type="episode_video_compose",
        project_id=project_id,
        provider="ffmpeg",
        status=status,
        inputs_json={
            "episode_number": episode_number,
            "expected_clip_count": expected_clip_count,
        },
    )


def time_offset(seconds: int) -> datetime:
    """Helper to build distinct finished_at values for ordering tests."""
    return datetime.utcnow() + timedelta(seconds=seconds)
