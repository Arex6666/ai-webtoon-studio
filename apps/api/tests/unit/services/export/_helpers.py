"""Shared fixtures for export bundle unit tests (Phase E)."""
from datetime import datetime, timedelta
from typing import Optional

from app.models import Chapter, Job, Panel, LayerPack


def make_chapter(
    chapter_id: str = "ch-1",
    project_id: str = "p-1",
    title: str = "Test Chapter",
    order_index: int = 1,
) -> Chapter:
    return Chapter(
        id=chapter_id,
        project_id=project_id,
        title=title,
        order_index=order_index,
        layout_json={},
        status="storyboarded",
    )


def make_compose_job(
    job_id: str,
    project_id: str,
    episode_number: int,
    status: str = "succeeded",
    video_url: Optional[str] = "episode_videos/p-1/ep1/compose_x.mp4",
    duration_sec: float = 12.0,
    clip_count: int = 3,
    size_bytes: int = 4096,
    finished_at: Optional[datetime] = None,
) -> Job:
    return Job(
        id=job_id,
        type="episode_video_compose",
        project_id=project_id,
        provider="ffmpeg",
        status=status,
        progress=1.0 if status == "succeeded" else 0.0,
        finished_at=finished_at or (datetime.utcnow() if status == "succeeded" else None),
        inputs_json={"episode_number": episode_number, "expected_clip_count": clip_count},
        outputs_json=(
            {
                "video_url": video_url,
                "duration_sec": duration_sec,
                "clip_count": clip_count,
                "size_bytes": size_bytes,
            } if status == "succeeded" and video_url else None
        ),
    )


def time_offset(seconds: int) -> datetime:
    return datetime.utcnow() + timedelta(seconds=seconds)
