"""
Video generation worker.

This worker executes unified video jobs and normalizes incoming parameters
before dispatching to provider implementations.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

from celery import shared_task

from app.api.routes.ws import push_chapter_update
from app.db.database import SessionLocal
from app.models import Clip, Job, Panel, Timeline
from app.models.layer_pack import LayerPack
from app.services.video.video_provider_base import (
    VideoGenerationRequest,
    get_video_provider,
    list_providers,
)

logger = logging.getLogger(__name__)


VIDEO_PROVIDER_ALIASES = {
    "keling": "doubao",
    "kling": "doubao",
    "deepseek": "doubao",
}

_PROVIDERS_BOOTSTRAPPED = False


def _get_param(params: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in params and params[key] is not None:
            return params[key]
    return default


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def _clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def _normalize_video_provider(provider: Optional[str]) -> str:
    normalized = _as_text(provider).lower()
    if not normalized:
        return "mock"
    return VIDEO_PROVIDER_ALIASES.get(normalized, normalized)


def _extract_resolution(params: Dict[str, Any], default_width: int, default_height: int) -> tuple[int, int]:
    width = _as_int(_get_param(params, "width"), default_width)
    height = _as_int(_get_param(params, "height"), default_height)

    resolution = _get_param(params, "resolution")
    if isinstance(resolution, str):
        normalized = resolution.lower().replace("*", "x")
        left, separator, right = normalized.partition("x")
        if separator:
            width = _as_int(left.strip(), width)
            height = _as_int(right.strip(), height)

    width = _clamp_int(width, 256, 4096)
    height = _clamp_int(height, 256, 4096)
    return width, height


def _layerpack_full_url(db, layerpack_id: Optional[str]) -> Optional[str]:
    if not layerpack_id:
        return None
    layerpack = db.query(LayerPack).filter(LayerPack.id == layerpack_id).first()
    if not layerpack:
        return None
    return _as_text(layerpack.full_url) or None


def _resolve_start_frame_url(db, params: Dict[str, Any], clip: Clip, panel: Optional[Panel]) -> Optional[str]:
    direct_url = _as_text(_get_param(params, "start_frame_url", "startFrameUrl"))
    if direct_url:
        return direct_url

    layerpack_id = _get_param(
        params,
        "start_frame_layerpack_id",
        "startFrameLayerpackId",
        default=getattr(clip, "start_frame_layerpack_id", None),
    )
    layerpack_url = _layerpack_full_url(db, _as_text(layerpack_id) or None)
    if layerpack_url:
        return layerpack_url

    if panel:
        from app.services.storage.panel_preview import resolve_panel_preview_url
        resolved = resolve_panel_preview_url(panel)
        if resolved:
            return resolved

    spec = panel.spec_json if panel else {}
    if isinstance(spec, dict):
        render = spec.get("render", {})
        if isinstance(render, dict):
            preview_url = _as_text(render.get("preview_url"))
            if preview_url:
                return preview_url

    return None


def _resolve_end_frame_url(db, params: Dict[str, Any], clip: Clip) -> Optional[str]:
    direct_url = _as_text(_get_param(params, "end_frame_url", "endFrameUrl"))
    if direct_url:
        return direct_url

    layerpack_id = _get_param(
        params,
        "end_frame_layerpack_id",
        "endFrameLayerpackId",
        default=getattr(clip, "end_frame_layerpack_id", None),
    )
    layerpack_url = _layerpack_full_url(db, _as_text(layerpack_id) or None)
    if layerpack_url:
        return layerpack_url

    return None


def _build_motion_prompt(params: Dict[str, Any], clip: Clip, panel: Optional[Panel]) -> str:
    base_prompt = _as_text(_get_param(params, "motion_prompt", "motionPrompt", "prompt"))
    if not base_prompt:
        base_prompt = _as_text(getattr(clip, "motion_prompt", None))

    spec: Dict[str, Any] = panel.spec_json if panel and isinstance(panel.spec_json, dict) else {}
    scene = spec.get("scene", {}) if isinstance(spec.get("scene", {}), dict) else {}
    shot = spec.get("shot", {}) if isinstance(spec.get("shot", {}), dict) else {}
    composition = spec.get("composition", {}) if isinstance(spec.get("composition", {}), dict) else {}
    look = spec.get("look", {}) if isinstance(spec.get("look", {}), dict) else {}
    camera_motion = spec.get("camera_motion", {}) if isinstance(spec.get("camera_motion", {}), dict) else {}

    action_description = _as_text(spec.get("action_description"))
    panel_summary = _as_text(getattr(panel, "summary", None))

    if not base_prompt:
        base_prompt = action_description or panel_summary or "cinematic motion shot"

    details: list[str] = []

    shot_type = _as_text(
        _get_param(
            params,
            "shot_type",
            "shotType",
            default=shot.get("shotType") or composition.get("shot_size"),
        )
    )
    if shot_type:
        details.append(f"shot type: {shot_type}")

    camera_move = _as_text(
        _get_param(
            params,
            "camera_move",
            "cameraMove",
            default=camera_motion.get("type") or shot.get("cameraMove"),
        )
    )
    if camera_move and camera_move.lower() != "none":
        details.append(f"camera movement: {camera_move}")

    location = _as_text(_get_param(params, "location", default=scene.get("location") or scene.get("name")))
    if location:
        details.append(f"location: {location}")

    time_of_day = _as_text(_get_param(params, "time_of_day", "timeOfDay", default=scene.get("time_of_day")))
    if time_of_day:
        details.append(f"time: {time_of_day}")

    weather = _as_text(_get_param(params, "weather", default=scene.get("weather")))
    if weather:
        details.append(f"weather: {weather}")

    mood = _as_text(_get_param(params, "mood", default=scene.get("mood")))
    if mood:
        details.append(f"mood: {mood}")

    style_hint = _as_text(
        _get_param(
            params,
            "style_hint",
            "styleHint",
            default=look.get("style_preset") or look.get("styleProfileId"),
        )
    )
    if style_hint:
        details.append(f"style: {style_hint}")

    action_hint = _as_text(_get_param(params, "action_description", "actionDescription", default=action_description))
    if action_hint and action_hint.lower() not in base_prompt.lower():
        details.append(f"action: {action_hint}")

    subject_hint = _as_text(_get_param(params, "subject"))
    if subject_hint:
        details.append(f"subject: {subject_hint}")

    if not details:
        return base_prompt

    return f"{base_prompt}. " + "; ".join(details)


def _extract_video_params(db, job: Job, clip: Clip, panel: Optional[Panel]) -> Dict[str, Any]:
    params = job.inputs_json or {}

    motion_mode = _as_text(_get_param(params, "motion_mode", "motionMode", default=getattr(clip, "motion_mode", None)))
    if not motion_mode:
        motion_mode = "single_keyframe"

    duration_sec = _clamp_float(
        _as_float(_get_param(params, "duration_sec", "durationSec", default=getattr(clip, "duration_sec", 3.0)), 3.0),
        0.5,
        12.0,
    )
    fps = _clamp_int(
        _as_int(_get_param(params, "fps", default=getattr(clip, "fps", 24)), 24),
        6,
        60,
    )
    width, height = _extract_resolution(params, default_width=1080, default_height=1920)

    seed_value = _get_param(params, "seed", default=getattr(clip, "seed", None))
    seed = None if seed_value in (None, "") else _as_int(seed_value, 0)
    if seed == 0:
        seed = None

    motion_strength = _clamp_float(
        _as_float(_get_param(params, "motion_strength", "motionStrength"), 0.5),
        0.0,
        1.0,
    )
    prompt_extend = _as_bool(_get_param(params, "prompt_extend", "promptExtend"), True)

    start_frame_url = _resolve_start_frame_url(db, params, clip, panel)
    if not start_frame_url:
        raise ValueError("No start frame available for video generation")

    end_frame_url = _resolve_end_frame_url(db, params, clip)
    if motion_mode != "dual_keyframe":
        end_frame_url = None

    provider_name = _normalize_video_provider(
        _get_param(params, "provider", default=job.provider or getattr(clip, "provider", "mock"))
    )
    model_name = _as_text(_get_param(params, "model", "model_name", "modelName")) or None

    negative_prompt = _as_text(
        _get_param(
            params,
            "negative_prompt",
            "negativePrompt",
            "negative",
            default=getattr(clip, "negative", None),
        )
    )

    motion_prompt = _build_motion_prompt(params, clip, panel)

    camera_move = _as_text(_get_param(params, "camera_move", "cameraMove")) or None
    style_hint = _as_text(_get_param(params, "style_hint", "styleHint")) or None

    return {
        "provider": provider_name,
        "model": model_name,
        "start_frame_url": start_frame_url,
        "end_frame_url": end_frame_url,
        "motion_prompt": motion_prompt,
        "negative_prompt": negative_prompt,
        "motion_mode": motion_mode,
        "duration_sec": duration_sec,
        "fps": fps,
        "width": width,
        "height": height,
        "seed": seed,
        "motion_strength": motion_strength,
        "prompt_extend": prompt_extend,
        "camera_move": camera_move,
        "style_hint": style_hint,
    }


def _ensure_video_providers_registered() -> None:
    global _PROVIDERS_BOOTSTRAPPED
    if _PROVIDERS_BOOTSTRAPPED:
        return

    for module_name in (
        "app.services.video.doubao_video_provider",
        "app.services.video.tongyi_video_provider",
    ):
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            logger.warning("Failed to import video provider module %s: %s", module_name, exc)

    _PROVIDERS_BOOTSTRAPPED = True


def push_video_update_sync(chapter_id: str, job_id: str, clip_id: str, status: str, progress: float):
    """Push websocket updates from sync worker context."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            push_chapter_update(
                chapter_id,
                "video_job_progress",
                {
                    "job_id": job_id,
                    "clip_id": clip_id,
                    "status": status,
                    "progress": progress,
                },
            )
        )

        from app.api.routes.ws import push_unified_job_event

        if status in ("succeeded", "failed"):
            loop.run_until_complete(
                push_unified_job_event(
                    chapter_id,
                    "job_status",
                    job_id,
                    {"status": status, "type": "video"},
                )
            )
        else:
            loop.run_until_complete(
                push_unified_job_event(
                    chapter_id,
                    "job_progress",
                    job_id,
                    {"progress": progress, "message": status},
                )
            )

        loop.close()
    except Exception as exc:
        logger.warning("Failed to push WS update: %s", exc)


def run_async(coro):
    """Run async functions from sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _resolve_timeline_context(db, clip: Clip) -> tuple[str, str]:
    timeline = db.query(Timeline).filter(Timeline.id == clip.timeline_id).first()
    # Bug #3: Timeline has no project_id column; reach it via the chapter relation.
    if timeline:
        chapter = timeline.chapter
        chapter_id = timeline.chapter_id
        project_id = chapter.project_id if chapter else "unknown"
    else:
        chapter_id = "unknown"
        project_id = "unknown"
    return chapter_id, project_id


@shared_task(bind=True, name="app.workers.video_worker.execute_video_job")
def execute_video_job(self, job_id: str, clip_id: str):
    """Execute a video generation job."""
    db = SessionLocal()
    job = None
    clip = None
    chapter_id = "unknown"

    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return {"success": False, "error": "Job not found"}

        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            return {"success": False, "error": "Clip not found"}

        chapter_id, project_id = _resolve_timeline_context(db, clip)
        panel = db.query(Panel).filter(Panel.id == clip.panel_id).first()

        job.status = "running"
        job.started_at = datetime.utcnow()
        clip.status = "Running"
        clip.progress = 0.0
        db.commit()

        push_video_update_sync(chapter_id, job_id, clip_id, "running", 0.0)

        _ensure_video_providers_registered()
        video_params = _extract_video_params(db, job, clip, panel)

        provider_name = video_params["provider"]
        provider = get_video_provider(provider_name)
        logger.info(
            "[VideoWorker] provider=%s available=%s clip=%s",
            provider_name,
            list_providers(),
            clip_id,
        )

        if provider is None:
            logger.warning("[VideoWorker] Provider '%s' not found, falling back to mock", provider_name)
            return execute_mock_job(db, job, clip, chapter_id, job_id, clip_id, video_params)

        request_metadata = {
            "motion_mode": video_params["motion_mode"],
            "resolution": f"{video_params['width']}x{video_params['height']}",
            "prompt_extend": video_params["prompt_extend"],
        }
        if video_params["model"]:
            request_metadata["model"] = video_params["model"]
        if video_params["camera_move"]:
            request_metadata["camera_move"] = video_params["camera_move"]
        if video_params["style_hint"]:
            request_metadata["style_hint"] = video_params["style_hint"]

        request = VideoGenerationRequest(
            clip_id=clip_id,
            panel_id=clip.panel_id,
            project_id=project_id,
            chapter_id=chapter_id,
            start_frame_url=video_params["start_frame_url"],
            end_frame_url=video_params["end_frame_url"],
            prompt=video_params["motion_prompt"],
            negative_prompt=video_params["negative_prompt"],
            duration_sec=video_params["duration_sec"],
            fps=video_params["fps"],
            width=video_params["width"],
            height=video_params["height"],
            seed=video_params["seed"],
            motion_strength=video_params["motion_strength"],
            metadata=request_metadata,
        )

        def progress_callback(progress: float, message: str):
            normalized_progress = _clamp_float(_as_float(progress, 0.0), 0.0, 1.0)
            job.progress = normalized_progress
            clip.progress = normalized_progress
            db.commit()
            push_video_update_sync(chapter_id, job_id, clip_id, "running", normalized_progress)

        logger.info("[VideoWorker] Calling provider %s", provider_name)
        result = run_async(
            provider.generate(
                request=request,
                timeout=420,
                poll_interval=3.0,
                progress_callback=progress_callback,
            )
        )

        if not result.success:
            raise RuntimeError(result.error or "Video generation failed")

        video_url = result.video_url
        if not video_url:
            raise RuntimeError("Provider returned success without video_url")
        preview_url = result.preview_url or video_url

        outputs = {
            "video_url": video_url,
            "preview_url": preview_url,
            "frames": result.frames or [],
            "duration_sec": result.duration_sec or video_params["duration_sec"],
            "provider": result.provider or provider_name,
            "seed": result.seed if result.seed is not None else video_params["seed"],
            "cost": result.cost,
            "generation_time_ms": result.generation_time_ms,
            "input_params": {
                "start_frame_url": video_params["start_frame_url"],
                "end_frame_url": video_params["end_frame_url"],
                "motion_prompt": video_params["motion_prompt"],
                "negative_prompt": video_params["negative_prompt"],
                "motion_mode": video_params["motion_mode"],
                "duration_sec": video_params["duration_sec"],
                "fps": video_params["fps"],
                "width": video_params["width"],
                "height": video_params["height"],
                "seed": video_params["seed"],
                "motion_strength": video_params["motion_strength"],
                "model": video_params["model"],
            },
        }

        job.status = "succeeded"
        job.progress = 1.0
        job.outputs_json = outputs
        job.finished_at = datetime.utcnow()
        job.cost_used = _as_float(result.cost, 0.0)

        clip.status = "Rendered"
        clip.progress = 1.0
        clip.output_json = outputs
        clip.provider = provider_name
        clip.motion_prompt = video_params["motion_prompt"]
        clip.motion_mode = video_params["motion_mode"]
        clip.duration_sec = video_params["duration_sec"]
        clip.fps = video_params["fps"]
        clip.negative = video_params["negative_prompt"]
        if video_params["seed"] is not None:
            clip.seed = _as_int(video_params["seed"], clip.seed or 0)

        db.commit()
        push_video_update_sync(chapter_id, job_id, clip_id, "succeeded", 1.0)

        logger.info("[VideoWorker] Job %s completed with %s", job_id, provider_name)
        return {"success": True, "outputs": outputs}

    except Exception as exc:
        logger.error("[VideoWorker] Job %s failed: %s", job_id, exc, exc_info=True)

        if job:
            job.status = "failed"
            job.error_json = {"code": "EXECUTION_ERROR", "message": str(exc)}
            job.finished_at = datetime.utcnow()
            db.commit()
        if clip:
            clip.status = "Failed"
            db.commit()

        push_video_update_sync(chapter_id, job_id, clip_id, "failed", 0.0)
        return {"success": False, "error": str(exc)}

    finally:
        db.close()


def execute_mock_job(db, job: Job, clip: Clip, chapter_id: str, job_id: str, clip_id: str, video_params: Dict[str, Any]):
    """Fallback mock video generation."""
    logger.info("[VideoWorker] Running mock job for clip=%s", clip_id)

    for progress in (0.1, 0.25, 0.4, 0.55, 0.7, 0.85, 1.0):
        time.sleep(0.25)
        job.progress = progress
        clip.progress = progress
        db.commit()
        push_video_update_sync(chapter_id, job_id, clip_id, "running", progress)

    outputs = {
        "video_url": f"https://storage.example.com/videos/{clip_id}.mp4",
        "preview_url": f"https://picsum.photos/seed/{clip_id}-preview/512/288",
        "frames": [f"https://picsum.photos/seed/{clip_id}-f{i}/512/288" for i in range(8)],
        "duration_sec": video_params["duration_sec"],
        "provider": "mock",
        "input_params": {
            "start_frame_url": video_params.get("start_frame_url"),
            "motion_prompt": video_params.get("motion_prompt"),
            "negative_prompt": video_params.get("negative_prompt"),
            "motion_mode": video_params.get("motion_mode"),
            "fps": video_params.get("fps"),
            "width": video_params.get("width"),
            "height": video_params.get("height"),
        },
    }

    job.status = "succeeded"
    job.progress = 1.0
    job.outputs_json = outputs
    job.finished_at = datetime.utcnow()
    job.cost_used = 0.0

    clip.status = "Rendered"
    clip.progress = 1.0
    clip.output_json = outputs

    db.commit()
    push_video_update_sync(chapter_id, job_id, clip_id, "succeeded", 1.0)
    logger.info("[VideoWorker] Mock job %s completed", job_id)

    return {"success": True, "outputs": outputs}
