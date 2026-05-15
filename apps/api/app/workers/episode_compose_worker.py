"""Phase D: episode_video_compose worker.

Reads sibling episode_video Job rows, downloads succeeded clip MP4s,
stitches them with ffmpeg concat, uploads the result to MinIO, updates
the Job row, and emits compose WebSocket events.
"""
import asyncio
import logging
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List

from celery import shared_task

from app.db.database import SessionLocal
from app.models import Job
from app.core.storage import get_storage_client

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from sync Celery context.

    Always uses a fresh event loop so this works both in production (no
    running loop) and under pytest-asyncio (where the test's loop is already
    running and would reject run_until_complete).
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _resolve_latest_succeeded_clips(db, project_id: str, episode_number: int) -> List[Job]:
    """Return one Job per image_index, picking the latest succeeded by finished_at."""
    all_succeeded = (
        db.query(Job)
        .filter(
            Job.type == "episode_video",
            Job.project_id == project_id,
            Job.status == "succeeded",
        )
        .all()
    )
    matching = [
        j for j in all_succeeded
        if (j.inputs_json or {}).get("episode_number") == episode_number
    ]
    latest_by_index: dict[int, Job] = {}
    for j in matching:
        idx = (j.inputs_json or {}).get("image_index")
        if idx is None:
            continue
        prior = latest_by_index.get(idx)
        if prior is None or (j.finished_at or datetime.min) > (prior.finished_at or datetime.min):
            latest_by_index[idx] = j
    return [latest_by_index[i] for i in sorted(latest_by_index.keys())]


def _execute_compose_sync(job_id: str) -> dict:
    """Body of execute_episode_compose, split out so unit tests can drive it.

    Returns: {"success": bool, "error"?: str}
    """
    db = SessionLocal()
    compose_job = None
    work_dir = None
    try:
        compose_job = db.query(Job).filter(Job.id == job_id).first()
        if compose_job is None:
            return {"success": False, "error": "compose job not found"}

        compose_job.status = "running"
        compose_job.started_at = datetime.utcnow()
        compose_job.progress = 0.0
        db.commit()

        project_id = compose_job.project_id
        episode_number = (compose_job.inputs_json or {}).get("episode_number")
        expected = (compose_job.inputs_json or {}).get("expected_clip_count", 0)

        clips = _resolve_latest_succeeded_clips(db, project_id, episode_number)
        if len(clips) < expected:
            return _fail_job(
                db, compose_job,
                code="MISSING_CLIPS",
                message=f"expected {expected} clips, found {len(clips)}",
            )

        tmp_root = os.environ.get("EPISODE_COMPOSE_TMP_ROOT") or tempfile.gettempdir()
        work_dir = Path(tmp_root) / f"episode-compose-{job_id}"
        work_dir.mkdir(parents=True, exist_ok=True)

        storage = get_storage_client()
        clip_paths: List[Path] = []
        for i, clip in enumerate(clips):
            key = (clip.outputs_json or {}).get("video_url")
            if not key:
                return _fail_job(
                    db, compose_job,
                    code="MISSING_CLIPS",
                    message=f"clip index {i} has no video_url",
                )
            try:
                data = _run_async(storage.download_bytes(key))
            except Exception as e:
                return _fail_job(
                    db, compose_job,
                    code="DOWNLOAD_FAILED",
                    message=f"failed to download clip {i} ({key}): {e!r}",
                )
            if not data:
                return _fail_job(
                    db, compose_job,
                    code="DOWNLOAD_FAILED",
                    message=f"clip {i} returned empty bytes",
                )
            clip_path = work_dir / f"clip_{i:03d}.mp4"
            clip_path.write_bytes(data)
            clip_paths.append(clip_path)

            compose_job.progress = 0.5 * ((i + 1) / len(clips))
            db.commit()

        list_file = work_dir / "concat_list.txt"
        list_file.write_text(
            "\n".join(f"file '{p.name}'" for p in clip_paths),
            encoding="utf-8",
        )

        output_path = work_dir / "output.mp4"
        compose_job.progress = 0.5
        db.commit()

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(output_path),
        ]
        try:
            result = subprocess.run(
                cmd,
                cwd=str(work_dir),
                capture_output=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            return _fail_job(
                db, compose_job,
                code="FFMPEG_FAILED",
                message="ffmpeg timed out after 300s",
            )

        if result.returncode != 0:
            return _fail_job(
                db, compose_job,
                code="FFMPEG_FAILED",
                message=f"ffmpeg exit {result.returncode}",
                ffmpeg_stderr=result.stderr.decode("utf-8", errors="replace")[:4000],
            )

        compose_job.progress = 0.9
        db.commit()

        output_bytes = output_path.read_bytes()
        output_key = f"episode_videos/{project_id}/ep{episode_number}/compose_{job_id}.mp4"
        try:
            _run_async(storage.upload_bytes(
                path=output_key,
                data=output_bytes,
                content_type="video/mp4",
            ))
        except Exception as e:
            return _fail_job(
                db, compose_job,
                code="UPLOAD_FAILED",
                message=f"upload to {output_key} failed: {e!r}",
            )

        compose_job.status = "succeeded"
        compose_job.progress = 1.0
        compose_job.outputs_json = {
            "video_url": output_key,
            "size_bytes": len(output_bytes),
            "clip_count": len(clips),
            "duration_sec": sum(
                (c.outputs_json or {}).get("duration_sec", 0.0) for c in clips
            ),
        }
        compose_job.finished_at = datetime.utcnow()
        db.commit()

        return {"success": True, "video_url": output_key}

    except Exception as e:
        logger.exception("[EpisodeCompose] unexpected error in job %s", job_id)
        if compose_job is not None:
            return _fail_job(db, compose_job, code="UNEXPECTED", message=repr(e))
        return {"success": False, "error": repr(e)}
    finally:
        db.close()
        if work_dir and work_dir.exists():
            try:
                import shutil
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                logger.warning("[EpisodeCompose] cleanup failed for %s", work_dir)


def _fail_job(db, job: Job, code: str, message: str, **extra) -> dict:
    job.status = "failed"
    job.progress = 0.0
    job.error_json = {"code": code, "message": message, **extra}
    job.finished_at = datetime.utcnow()
    db.commit()
    logger.error("[EpisodeCompose] job %s failed: %s — %s", job.id, code, message)
    return {"success": False, "error": message, "code": code}


@shared_task(bind=True, name="app.workers.episode_compose_worker.execute_episode_compose")
def execute_episode_compose(self, job_id: str):
    return _execute_compose_sync(job_id)
