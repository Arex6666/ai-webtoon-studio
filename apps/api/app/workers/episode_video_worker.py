"""
Episode Video Worker - 分集视频生成 Celery 任务
使用豆包视频大模型进行图生视频
"""
from celery import shared_task
from sqlalchemy.orm import Session
from datetime import datetime
import asyncio
import logging
import time

from app.db.database import SessionLocal
from app.models import Job
from app.services.video.video_provider_base import (
    VideoGenerationRequest,
    VideoJobStatus,
    get_video_provider,
)
from app.services.video.compose_dispatch import _maybe_enqueue_episode_compose

logger = logging.getLogger(__name__)


def run_async(coro):
    """在同步上下文中运行异步函数"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(bind=True, name="app.workers.episode_video_worker.generate_episode_video_task")
def generate_episode_video_task(
    self,
    job_id: str,
    image_url: str,
    motion_prompt: str,
    duration_sec: float,
    provider_name: str = "doubao",
):
    """
    分集视频生成任务

    从单张场景图片生成短视频
    """
    db = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return {"success": False, "error": "Job not found"}

        # 更新状态为运行中
        job.status = "running"
        job.started_at = datetime.utcnow()
        job.progress = 0.1
        db.commit()

        logger.info(f"[EpisodeVideoWorker] Starting job {job_id} with provider {provider_name}")

        # 获取 Provider
        provider = get_video_provider(provider_name)

        if provider is None:
            # 尝试注册 doubao provider
            if provider_name == "doubao":
                try:
                    from app.services.video.doubao_video_provider import DoubaoVideoProvider
                    from app.services.video.video_provider_base import register_provider
                    from app.core.config import settings

                    api_key = getattr(settings, 'DOUBAO_VIDEO_API_KEY', None) or settings.DOUBAO_API_KEY
                    if api_key:
                        provider = DoubaoVideoProvider()
                        register_provider("doubao", provider)
                        logger.info("[EpisodeVideoWorker] Registered doubao provider on demand")
                    else:
                        raise ValueError("DOUBAO_API_KEY not configured")
                except Exception as e:
                    logger.error(f"[EpisodeVideoWorker] Failed to register doubao: {e}")
                    raise ValueError(f"Provider '{provider_name}' not available: {e}")
            else:
                raise ValueError(f"Provider '{provider_name}' not found")

        # 从 inputs_json 提取 panel_metadata（如果有），用 prompt compiler 编译
        panel_meta = (job.inputs_json or {}).get("panel_metadata")
        compiled_prompt = motion_prompt
        compiled_negative = ""
        compiled_strength = 0.5

        if panel_meta:
            try:
                from app.services.video.prompt_compiler import compile_video_prompt
                compiled = compile_video_prompt(
                    camera_move=panel_meta.get("camera_move"),
                    shot_type=panel_meta.get("shot_type"),
                    actions=panel_meta.get("actions"),
                    mood=panel_meta.get("mood"),
                    weather=panel_meta.get("weather"),
                    time_of_day=panel_meta.get("time_of_day"),
                    composition_notes=panel_meta.get("composition_notes"),
                    visual_prompt=panel_meta.get("visual_prompt"),
                    lens_hint=panel_meta.get("lens_hint"),
                    duration_sec=duration_sec,
                    original_prompt=motion_prompt,
                )
                compiled_prompt = compiled.motion_prompt
                compiled_negative = compiled.negative_prompt
                compiled_strength = compiled.motion_strength
                logger.info(f"[EpisodeVideoWorker] Compiled prompt for {job_id}: strength={compiled_strength}")
            except Exception as e:
                logger.warning(f"[EpisodeVideoWorker] Prompt compile failed, using original: {e}")
        else:
            # 即使没有结构化数据，也加上默认 negative prompt
            from app.services.video.prompt_compiler import DEFAULT_NEGATIVE_PROMPT
            compiled_negative = DEFAULT_NEGATIVE_PROMPT

        # 构建视频生成请求
        request = VideoGenerationRequest(
            clip_id=job_id,
            panel_id=job_id,
            project_id=job.project_id or "",
            chapter_id="",
            start_frame_url=image_url,
            prompt=compiled_prompt,
            negative_prompt=compiled_negative,
            duration_sec=duration_sec,
            fps=24,
            width=1080,
            height=1920,
            motion_strength=compiled_strength,
        )

        # 进度回调
        def progress_callback(progress: float, message: str):
            job.progress = min(progress, 0.95)
            db.commit()
            logger.debug(f"[EpisodeVideoWorker] Job {job_id} progress: {progress:.0%} - {message}")

        # 调用 Provider 生成视频
        result = run_async(provider.generate(
            request=request,
            timeout=300,
            poll_interval=3.0,
            progress_callback=progress_callback,
        ))

        if result.success:
            outputs = {
                "video_url": result.video_url,
                "preview_url": result.preview_url or result.video_url,
                "duration_sec": result.duration_sec,
                "provider": result.provider,
                "seed": result.seed,
            }

            job.status = "succeeded"
            job.progress = 1.0
            job.outputs_json = outputs
            job.finished_at = datetime.utcnow()
            job.cost_used = result.cost
            db.commit()

            # Phase D: auto-trigger episode compose if all siblings succeeded.
            # Compose dispatch failure must NOT fail the clip job — the clip succeeded.
            try:
                episode_num = (job.inputs_json or {}).get("episode_number")
                if job.project_id and episode_num is not None:
                    _maybe_enqueue_episode_compose(db, job.project_id, episode_num)
            except Exception:
                logger.exception("[EpisodeVideoWorker] compose dispatch check failed")

            logger.info(f"[EpisodeVideoWorker] Job {job_id} completed: {result.video_url}")
            return {"success": True, "outputs": outputs}
        else:
            raise Exception(result.error or "Video generation failed")

    except Exception as e:
        logger.error(f"[EpisodeVideoWorker] Job {job_id} failed: {e}", exc_info=True)

        if job:
            job.status = "failed"
            job.progress = 0.0
            job.error_json = {"code": "GENERATION_ERROR", "message": str(e)}
            job.finished_at = datetime.utcnow()
            db.commit()

        return {"success": False, "error": str(e)}

    finally:
        db.close()
