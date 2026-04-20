"""
Image generation worker.

This worker handles image jobs from the unified jobs API and supports
multiple providers with a normalized parameter interface.
"""

from celery import shared_task
from datetime import datetime
import asyncio
import logging
import time
import uuid
from typing import Any, Dict, Optional

from app.api.routes.ws import push_job_update
from app.core.config import settings
from app.db.database import SessionLocal
from app.models import Job, LayerPack, Panel

logger = logging.getLogger(__name__)


IMAGE_PROVIDER_ALIASES = {
    "comfyui_svd": "comfyui",
    "kling": "doubao",
    "keling": "doubao",
    "deepseek": "doubao",
}


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


def _normalize_image_provider(provider: Optional[str]) -> str:
    normalized = (provider or "").strip().lower()
    if not normalized:
        return "comfyui" if settings.COMFYUI_URL else "mock"
    return IMAGE_PROVIDER_ALIASES.get(normalized, normalized)


def _extract_resolution(params: Dict[str, Any], default_width: int, default_height: int) -> tuple[int, int]:
    width = _as_int(_get_param(params, "width"), default_width)
    height = _as_int(_get_param(params, "height"), default_height)

    resolution = _get_param(params, "resolution")
    if isinstance(resolution, str) and "x" in resolution:
        left, _, right = resolution.lower().partition("x")
        width = _as_int(left.strip(), width)
        height = _as_int(right.strip(), height)

    width = max(256, width)
    height = max(256, height)
    return width, height


def _build_prompt_from_spec(spec: Dict[str, Any]) -> str:
    """Build a fallback prompt from panel spec fields."""
    parts = []

    scene = spec.get("scene", {})
    if scene.get("location_description"):
        parts.append(scene["location_description"])
    if scene.get("time_of_day"):
        parts.append(scene["time_of_day"])

    if spec.get("action_description"):
        parts.append(spec["action_description"])

    for char in spec.get("characters", []):
        if isinstance(char, str):
            parts.append(char)
        elif isinstance(char, dict) and char.get("emotion"):
            parts.append(f"{char.get('character_id', 'character')} with {char['emotion']} expression")

    camera = spec.get("camera", {})
    if camera.get("shot_type"):
        parts.append(f"{camera['shot_type']} shot")

    look = spec.get("look", {})
    if look.get("style_preset"):
        parts.append(f"{look['style_preset']} style")

    prompt = ", ".join(parts) if parts else "masterpiece, best quality, detailed illustration"
    return f"webtoon style, {prompt}"


def _extract_image_params(job: Job, panel: Panel) -> Dict[str, Any]:
    params = job.inputs_json or {}
    spec = panel.spec_json or {}

    base_prompt = spec.get("prompt_override") or _build_prompt_from_spec(spec)
    positive_prompt = _get_param(params, "positive_prompt", "prompt_override", "prompt", default=base_prompt)

    style_hint = _get_param(params, "style_hint", default="")
    if style_hint:
        positive_prompt = f"{style_hint}, {positive_prompt}"

    negative_prompt = _get_param(
        params,
        "negative_prompt",
        "negativePrompt",
        "negative",
        default=spec.get("negative_prompt", ""),
    )

    width, height = _extract_resolution(params, default_width=1080, default_height=1920)

    return {
        "provider": _normalize_image_provider(_get_param(params, "provider", default=job.provider)),
        "positive_prompt": positive_prompt,
        "negative_prompt": negative_prompt,
        "width": width,
        "height": height,
        "seed": _get_param(params, "seed"),
        "steps": _as_int(_get_param(params, "steps"), 20),
        "sampler": _get_param(params, "sampler", default="euler"),
        "scheduler": _get_param(params, "scheduler", default="normal"),
        "guidance_scale": _as_float(_get_param(params, "guidance_scale"), 2.5),
        "reference_image_url": _get_param(params, "reference_image_url", "referenceImageUrl"),
    }


def get_event_loop():
    """Get or create an event loop for sync Celery workers."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


def push_update_sync(chapter_id: str, job_id: str, panel_id: str, status: str, progress: float, current_step: str = None):
    """Push job updates to websocket channels from sync worker context."""
    try:
        loop = get_event_loop()
        loop.run_until_complete(
            push_job_update(chapter_id, job_id, panel_id, status, progress, current_step)
        )

        from app.api.routes.ws import push_unified_job_event
        if status in ("succeeded", "failed"):
            loop.run_until_complete(
                push_unified_job_event(chapter_id, "job_status", job_id, {
                    "status": status,
                    "type": "image",
                })
            )
        else:
            loop.run_until_complete(
                push_unified_job_event(chapter_id, "job_progress", job_id, {
                    "progress": progress,
                    "message": current_step,
                })
            )
    except Exception as e:
        logger.warning(f"Failed to push WS update: {e}")


@shared_task(bind=True, name="app.workers.image_worker.execute_image_job")
def execute_image_job(self, job_id: str, panel_id: str):
    """Execute an image generation job."""
    db = SessionLocal()
    job = None
    panel = None
    chapter_id = "unknown"

    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return {"success": False, "error": "Job not found"}

        panel = db.query(Panel).filter(Panel.id == panel_id).first()
        if not panel:
            logger.error(f"Panel {panel_id} not found")
            return {"success": False, "error": "Panel not found"}

        chapter_id = panel.chapter_id
        project_id = panel.chapter.project_id if panel.chapter else "unknown"

        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()

        push_update_sync(chapter_id, job_id, panel_id, "running", 0, "initializing")

        image_params = _extract_image_params(job, panel)
        provider = image_params["provider"]
        logger.info(
            "[ImageWorker] provider=%s panel=%s size=%sx%s steps=%s seed=%s",
            provider,
            panel_id,
            image_params["width"],
            image_params["height"],
            image_params["steps"],
            image_params["seed"],
        )

        if provider == "comfyui":
            if not settings.COMFYUI_URL:
                logger.warning("[ImageWorker] COMFYUI_URL not configured, falling back to mock")
                outputs = _execute_mock(
                    chapter_id=chapter_id,
                    job_id=job_id,
                    panel_id=panel_id,
                    push_update_sync=push_update_sync,
                    width=image_params["width"],
                    height=image_params["height"],
                )
            else:
                outputs = _execute_with_comfyui(
                    job=job,
                    panel=panel,
                    project_id=project_id,
                    chapter_id=chapter_id,
                    positive_prompt=image_params["positive_prompt"],
                    negative_prompt=image_params["negative_prompt"],
                    width=image_params["width"],
                    height=image_params["height"],
                    seed=image_params["seed"],
                    steps=image_params["steps"],
                    sampler=image_params["sampler"],
                    scheduler=image_params["scheduler"],
                    progress_callback=lambda p: push_update_sync(chapter_id, job_id, panel_id, "running", p, "generating"),
                )
        elif provider == "doubao":
            outputs = _execute_with_doubao(
                panel_id=panel_id,
                positive_prompt=image_params["positive_prompt"],
                negative_prompt=image_params["negative_prompt"],
                width=image_params["width"],
                height=image_params["height"],
                seed=image_params["seed"],
                guidance_scale=image_params["guidance_scale"],
                reference_image_url=image_params["reference_image_url"],
                progress_callback=lambda p: push_update_sync(chapter_id, job_id, panel_id, "running", p, "generating"),
            )
        elif provider == "tongyi":
            outputs = _execute_with_tongyi(
                panel_id=panel_id,
                positive_prompt=image_params["positive_prompt"],
                negative_prompt=image_params["negative_prompt"],
                width=image_params["width"],
                height=image_params["height"],
                seed=image_params["seed"],
                progress_callback=lambda p: push_update_sync(chapter_id, job_id, panel_id, "running", p, "generating"),
            )
        else:
            logger.warning("[ImageWorker] Unknown provider '%s', falling back to mock", provider)
            outputs = _execute_mock(
                chapter_id=chapter_id,
                job_id=job_id,
                panel_id=panel_id,
                push_update_sync=push_update_sync,
                width=image_params["width"],
                height=image_params["height"],
            )

        outputs.setdefault("provider", provider)
        outputs.setdefault("width", image_params["width"])
        outputs.setdefault("height", image_params["height"])

        job.status = "succeeded"
        job.progress = 1.0
        job.outputs_json = outputs
        job.finished_at = datetime.utcnow()
        job.cost_used = _as_float(outputs.get("cost"), 3.0)
        db.commit()

        layerpack = LayerPack(
            id=outputs.get("layerpack_id", str(uuid.uuid4())),
            panel_id=panel_id,
            attempt=job.attempt,
            status="completed",
            manifest_url=outputs.get("manifest_url"),
            full_url=outputs.get("full_url"),
            generation_params=job.inputs_json,
        )
        db.add(layerpack)

        panel.render_status = "rendered"
        panel.preview_url = outputs.get("full_url")
        panel.active_layer_pack_id = layerpack.id
        db.commit()

        push_update_sync(chapter_id, job_id, panel_id, "succeeded", 1.0, "completed")

        logger.info(f"Image job {job_id} completed successfully")
        return {"success": True, "outputs": outputs}

    except Exception as e:
        logger.error(f"Image job {job_id} failed: {e}", exc_info=True)

        if job:
            job.status = "failed"
            job.error_json = {"code": "EXECUTION_ERROR", "message": str(e)}
            job.finished_at = datetime.utcnow()
            db.commit()

        if panel:
            push_update_sync(chapter_id, job_id, panel_id, "failed", 0, None)

        return {"success": False, "error": str(e)}

    finally:
        db.close()


def _execute_with_comfyui(
    job: Job,
    panel: Panel,
    project_id: str,
    chapter_id: str,
    positive_prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    seed: Optional[int],
    steps: int,
    sampler: str,
    scheduler: str,
    progress_callback,
) -> Dict[str, Any]:
    from app.services.layer_factory.comfyui_adapter import get_comfyui_adapter

    adapter = get_comfyui_adapter()
    loop = get_event_loop()

    result = loop.run_until_complete(
        adapter.generate(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            project_id=project_id,
            chapter_id=chapter_id,
            panel_id=panel.id,
            attempt=job.attempt,
            width=width,
            height=height,
            seed=seed,
            steps=steps,
            progress_callback=progress_callback,
        )
    )

    result.setdefault("provider", "comfyui")
    return result


def _execute_with_doubao(
    panel_id: str,
    positive_prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    seed: Optional[int],
    guidance_scale: float,
    reference_image_url: Optional[str],
    progress_callback,
) -> Dict[str, Any]:
    from app.services.layer_factory.doubao_image_provider import DoubaoImageRequest, get_doubao_image_provider

    provider = get_doubao_image_provider()
    if not provider:
        raise RuntimeError("Doubao image provider is not configured")

    request = DoubaoImageRequest(
        prompt=positive_prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        seed=seed,
        reference_image_url=reference_image_url,
        guidance_scale=guidance_scale,
    )

    loop = get_event_loop()
    result = loop.run_until_complete(
        provider.generate(
            request,
            progress_callback=lambda p, _msg: progress_callback(min(max(p, 0.0), 1.0)) if progress_callback else None,
        )
    )

    if not result.success:
        raise RuntimeError(result.error or "Doubao image generation failed")

    return {
        "layerpack_id": f"lp-{int(time.time())}-{uuid.uuid4().hex[:6]}",
        "manifest_url": None,
        "full_url": result.image_url,
        "seed": result.seed,
        "provider": "doubao",
        "cost": result.cost,
        "generation_time_ms": result.generation_time_ms,
    }


def _execute_with_tongyi(
    panel_id: str,
    positive_prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    seed: Optional[int],
    progress_callback,
) -> Dict[str, Any]:
    from app.services.layer_factory.tongyi_image_provider import TongyiImageRequest, get_tongyi_image_provider

    provider = get_tongyi_image_provider()
    if not provider:
        raise RuntimeError("Tongyi image provider is not configured")

    request = TongyiImageRequest(
        prompt=positive_prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        seed=seed,
    )

    loop = get_event_loop()
    result = loop.run_until_complete(
        provider.generate(
            request,
            progress_callback=lambda p, _msg: progress_callback(min(max(p, 0.0), 1.0)) if progress_callback else None,
        )
    )

    if not result.success:
        raise RuntimeError(result.error or "Tongyi image generation failed")

    return {
        "layerpack_id": f"lp-{int(time.time())}-{uuid.uuid4().hex[:6]}",
        "manifest_url": None,
        "full_url": result.image_url,
        "seed": seed,
        "provider": "tongyi",
        "cost": 0.1,
        "generation_time_ms": int(result.generation_time * 1000),
    }


def _execute_mock(
    chapter_id: str,
    job_id: str,
    panel_id: str,
    push_update_sync,
    width: int,
    height: int,
) -> Dict[str, Any]:
    """Mock execution for local development."""
    steps = [
        (0.1, "loading_model"),
        (0.3, "encoding_prompt"),
        (0.5, "generating_image"),
        (0.7, "post_processing"),
        (0.9, "saving_output"),
        (1.0, "completed"),
    ]

    for progress, step in steps:
        time.sleep(1)
        push_update_sync(chapter_id, job_id, panel_id, "running", progress, step)

    layerpack_id = f"lp-{int(time.time())}-{uuid.uuid4().hex[:6]}"
    return {
        "layerpack_id": layerpack_id,
        "manifest_url": f"https://storage.example.com/layerpacks/{panel_id}/{layerpack_id}/manifest.json",
        "full_url": f"https://picsum.photos/seed/{panel_id}/{width}/{height}",
        "provider": "mock",
        "cost": 0.0,
    }
