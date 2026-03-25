"""
图像生成 Worker (使用 ComfyUI)
"""
from celery import shared_task
from sqlalchemy.orm import Session
from datetime import datetime
import asyncio
import logging
import uuid
import time

from app.db.database import SessionLocal
from app.models import Job, Panel, LayerPack
from app.api.routes.ws import push_job_update
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_event_loop():
    """获取或创建事件循环"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


def push_update_sync(chapter_id: str, job_id: str, panel_id: str, status: str, progress: float, current_step: str = None):
    """同步版本的 WebSocket 推送"""
    try:
        loop = get_event_loop()
        loop.run_until_complete(
            push_job_update(chapter_id, job_id, panel_id, status, progress, current_step)
        )
        # Unified event
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
    """
    执行图像生成任务
    
    如果配置了 COMFYUI_URL，使用真实 ComfyUI
    否则使用 Mock 实现
    """
    db = SessionLocal()
    
    try:
        # 获取 Job
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return {"success": False, "error": "Job not found"}
        
        # 获取 Panel
        panel = db.query(Panel).filter(Panel.id == panel_id).first()
        if not panel:
            logger.error(f"Panel {panel_id} not found")
            return {"success": False, "error": "Panel not found"}
        
        chapter_id = panel.chapter_id
        project_id = panel.chapter.project_id if panel.chapter else "unknown"
        
        # 更新状态为 running
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()
        
        push_update_sync(chapter_id, job_id, panel_id, "running", 0, "initializing")
        
        # 获取生成参数
        spec = panel.spec_json or {}
        positive_prompt = spec.get("prompt_override") or _build_prompt_from_spec(spec)
        negative_prompt = spec.get("negative_prompt", "")
        
        # 判断使用真实 ComfyUI 还是 Mock
        if settings.COMFYUI_URL:
            outputs = _execute_with_comfyui(
                job=job,
                panel=panel,
                project_id=project_id,
                chapter_id=chapter_id,
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt,
                progress_callback=lambda p: push_update_sync(chapter_id, job_id, panel_id, "running", p, "generating")
            )
        else:
            outputs = _execute_mock(
                job=job,
                panel=panel,
                chapter_id=chapter_id,
                job_id=job_id,
                panel_id=panel_id,
                push_update_sync=push_update_sync
            )
        
        # 更新 Job
        job.status = "succeeded"
        job.progress = 1.0
        job.outputs_json = outputs
        job.finished_at = datetime.utcnow()
        job.cost_used = 3.0
        db.commit()
        
        # 创建 LayerPack 记录
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
        
        # 更新 Panel
        panel.render_status = "rendered"
        panel.preview_url = outputs.get("full_url")
        panel.active_layer_pack_id = layerpack.id
        db.commit()
        
        push_update_sync(chapter_id, job_id, panel_id, "succeeded", 1.0, "completed")
        
        logger.info(f"Image job {job_id} completed successfully")
        return {"success": True, "outputs": outputs}
        
    except Exception as e:
        logger.error(f"Image job {job_id} failed: {e}")
        
        if job:
            job.status = "failed"
            job.error_json = {"code": "EXECUTION_ERROR", "message": str(e)}
            job.finished_at = datetime.utcnow()
            db.commit()
        
        push_update_sync(chapter_id, job_id, panel_id, "failed", 0, None)
        
        return {"success": False, "error": str(e)}
        
    finally:
        db.close()


def _build_prompt_from_spec(spec: dict) -> str:
    """从 PanelSpec 构建提示词"""
    parts = []
    
    # 场景
    scene = spec.get("scene", {})
    if scene.get("location_description"):
        parts.append(scene["location_description"])
    if scene.get("time_of_day"):
        parts.append(scene["time_of_day"])
    
    # 动作描述
    if spec.get("action_description"):
        parts.append(spec["action_description"])
    
    # 角色
    characters = spec.get("characters", [])
    for char in characters:
        if char.get("emotion"):
            parts.append(f"{char.get('character_id', 'character')} with {char['emotion']} expression")
    
    # 镜头
    camera = spec.get("camera", {})
    if camera.get("shot_type"):
        parts.append(f"{camera['shot_type']} shot")
    
    # 风格
    look = spec.get("look", {})
    if look.get("style_preset"):
        parts.append(f"{look['style_preset']} style")
    
    prompt = ", ".join(parts) if parts else "masterpiece, best quality, detailed illustration"
    return f"webtoon style, {prompt}"


def _execute_with_comfyui(
    job: Job,
    panel: Panel,
    project_id: str,
    chapter_id: str,
    positive_prompt: str,
    negative_prompt: str,
    progress_callback: callable,
) -> dict:
    """使用真实 ComfyUI 执行"""
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
            width=1080,
            height=1920,
            progress_callback=progress_callback,
        )
    )
    
    return result


def _execute_mock(
    job: Job,
    panel: Panel,
    chapter_id: str,
    job_id: str,
    panel_id: str,
    push_update_sync: callable,
) -> dict:
    """Mock 执行（开发测试用）"""
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
        job.progress = progress
        push_update_sync(chapter_id, job_id, panel_id, "running", progress, step)
    
    layerpack_id = f"lp-{int(time.time())}-{uuid.uuid4().hex[:6]}"
    
    return {
        "layerpack_id": layerpack_id,
        "manifest_url": f"https://storage.example.com/layerpacks/{panel_id}/{layerpack_id}/manifest.json",
        "full_url": f"https://picsum.photos/seed/{panel_id}/1080/1920",
    }
