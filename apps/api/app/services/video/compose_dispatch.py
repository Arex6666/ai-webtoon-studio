"""Phase D: compose dispatch — decides when to enqueue an episode_video_compose job.

Called from episode_video_worker on the success path of each per-panel clip.
Lives in services/ (not workers/) so it stays unit-testable without Celery.
"""
import logging
import uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError

from app.models import Job
from app.workers.episode_compose_worker import execute_episode_compose

logger = logging.getLogger(__name__)


def _maybe_enqueue_episode_compose(
    db,
    project_id: str,
    episode_number: int,
) -> Optional[str]:
    """Check sibling state; enqueue compose if all clips succeeded.

    Returns new compose job_id on enqueue, None otherwise.
    Strict policy: every sibling clip must be 'succeeded' before compose fires.
    """
    siblings_query = (
        db.query(Job)
        .filter(
            Job.type == "episode_video",
            Job.project_id == project_id,
        )
        .all()
    )
    siblings = [
        j for j in siblings_query
        if (j.inputs_json or {}).get("episode_number") == episode_number
    ]
    if not siblings:
        return None

    if any(j.status != "succeeded" for j in siblings):
        return None

    existing_query = (
        db.query(Job)
        .filter(
            Job.type == "episode_video_compose",
            Job.project_id == project_id,
            Job.status.in_(["queued", "running", "succeeded"]),
        )
        .all()
    )
    existing = [
        j for j in existing_query
        if (j.inputs_json or {}).get("episode_number") == episode_number
    ]
    if existing:
        return None

    compose_job_id = str(uuid.uuid4())
    job = Job(
        id=compose_job_id,
        type="episode_video_compose",
        provider="ffmpeg",
        project_id=project_id,
        status="queued",
        inputs_json={
            "episode_number": episode_number,
            "expected_clip_count": len(siblings),
        },
    )
    try:
        db.add(job)
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.info(
            "[ComposeDispatch] dedup race lost for project=%s ep=%s",
            project_id, episode_number,
        )
        return None

    execute_episode_compose.delay(compose_job_id)
    logger.info(
        "[ComposeDispatch] enqueued compose %s for project=%s ep=%s clips=%d",
        compose_job_id, project_id, episode_number, len(siblings),
    )
    return compose_job_id
