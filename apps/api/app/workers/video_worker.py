"""
视频生成 Worker - 真实 Provider 实现
支持 Tongyi / Doubao / ComfyUI 视频生成
"""
from celery import shared_task
from sqlalchemy.orm import Session
from datetime import datetime
import asyncio
import logging
import time

from app.db.database import SessionLocal
from app.models import Job, Clip, Timeline, Panel
from app.models.layer_pack import LayerPack
from app.api.routes.ws import push_chapter_update
from app.services.video.video_provider_base import (
    VideoGenerationRequest,
    VideoJobStatus,
    get_video_provider,
    list_providers,
)
from app.services.storage import get_object_store

logger = logging.getLogger(__name__)


def push_video_update_sync(chapter_id: str, job_id: str, clip_id: str, status: str, progress: float):
    """同步版本的 WebSocket 推送"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            push_chapter_update(chapter_id, "video_job_progress", {
                "job_id": job_id,
                "clip_id": clip_id,
                "status": status,
                "progress": progress,
            })
        )
        # Unified event
        from app.api.routes.ws import push_unified_job_event
        if status in ("succeeded", "failed"):
            loop.run_until_complete(
                push_unified_job_event(chapter_id, "job_status", job_id, {
                    "status": status,
                    "type": "video",
                })
            )
        else:
            loop.run_until_complete(
                push_unified_job_event(chapter_id, "job_progress", job_id, {
                    "progress": progress,
                    "message": status,
                })
            )
        loop.close()
    except Exception as e:
        logger.warning(f"Failed to push WS update: {e}")


def run_async(coro):
    """在同步上下文中运行异步函数"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(bind=True, name="app.workers.video_worker.execute_video_job")
def execute_video_job(self, job_id: str, clip_id: str):
    """
    执行视频生成任务
    
    根据 clip.provider 选择对应的 Provider 进行生成
    支持: tongyi, doubao, comfyui, mock
    """
    db = SessionLocal()
    
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return {"success": False, "error": "Job not found"}
        
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            return {"success": False, "error": "Clip not found"}
        
        timeline = db.query(Timeline).filter(Timeline.id == clip.timeline_id).first()
        chapter_id = timeline.chapter_id if timeline else "unknown"
        project_id = timeline.project_id if timeline else "unknown"
        
        # 获取 Panel 信息（用于获取起始帧图片）
        panel = db.query(Panel).filter(Panel.id == clip.panel_id).first()
        
        # 更新状态
        job.status = "running"
        job.started_at = datetime.utcnow()
        clip.status = "Running"
        db.commit()
        
        push_video_update_sync(chapter_id, job_id, clip_id, "running", 0)
        
        # Read params from job.inputs_json first, fall back to clip model fields
        params = job.inputs_json or {}

        # Resolve start_frame_url: job params → clip layerpack → clip.start_frame → panel preview
        start_frame_url = params.get("start_frame_url")
        if not start_frame_url and hasattr(clip, 'start_frame_layerpack_id') and clip.start_frame_layerpack_id:
            lp = db.query(LayerPack).filter(LayerPack.id == clip.start_frame_layerpack_id).first()
            if lp:
                start_frame_url = lp.full_url
        if not start_frame_url:
            # Fall back to existing helper which checks clip.start_frame and panel spec
            start_frame_url = get_start_frame_url(panel, clip)

        end_frame_url = params.get("end_frame_url")
        if not end_frame_url:
            end_frame_url = get_end_frame_url(panel, clip) if clip.motion_mode == "dual_keyframe" else None

        if not start_frame_url:
            raise ValueError("No start frame available for video generation")

        # Resolve other params with fallback to clip model fields
        motion_prompt = params.get("motion_prompt") or getattr(clip, 'motion_prompt', '') or ''
        negative_prompt = params.get("negative") or getattr(clip, 'negative', '') or ''
        duration_sec = params.get("duration_sec") or getattr(clip, 'duration_sec', 3.0) or 3.0
        fps = params.get("fps") or getattr(clip, 'fps', 24) or 24
        seed = params.get("seed") or getattr(clip, 'seed', None)
        provider_name = params.get("provider") or job.provider or getattr(clip, 'provider', 'mock') or 'mock'

        # 确定 Provider
        provider = get_video_provider(provider_name)

        logger.info(f"[VideoWorker] Using provider: {provider_name}, available: {list_providers()}")

        # 如果找不到对应 Provider，回退到 Mock
        if provider is None:
            logger.warning(f"[VideoWorker] Provider '{provider_name}' not found, falling back to mock")
            return execute_mock_job(db, job, clip, chapter_id, job_id, clip_id)

        # 准备生成请求
        request = VideoGenerationRequest(
            clip_id=clip_id,
            panel_id=clip.panel_id,
            project_id=project_id,
            chapter_id=chapter_id,
            start_frame_url=start_frame_url,
            end_frame_url=end_frame_url,
            prompt=motion_prompt,
            negative_prompt=negative_prompt,
            duration_sec=duration_sec,
            fps=fps,
            width=1080,
            height=1920,
            seed=seed,
        )
        
        # 进度回调
        def progress_callback(progress: float, message: str):
            job.progress = progress
            clip.progress = progress
            db.commit()
            push_video_update_sync(chapter_id, job_id, clip_id, "running", progress)
        
        # 调用真实 Provider
        logger.info(f"[VideoWorker] Calling {provider_name} provider...")
        result = run_async(provider.generate(
            request=request,
            timeout=300,
            poll_interval=3.0,
            progress_callback=progress_callback,
        ))
        
        if result.success:
            # 如果需要，将视频上传到自己的存储
            video_url = result.video_url
            preview_url = result.preview_url
            
            # 可选：重新上传到自己的 MinIO
            # video_url = upload_to_storage(result.video_url, project_id, chapter_id, clip_id)
            
            outputs = {
                "video_url": video_url,
                "preview_url": preview_url or video_url,
                "frames": result.frames,
                "duration_sec": result.duration_sec,
                "provider": result.provider,
                "seed": result.seed,
            }
            
            job.status = "succeeded"
            job.progress = 1.0
            job.outputs_json = outputs
            job.finished_at = datetime.utcnow()
            job.cost_used = result.cost
            
            clip.status = "Rendered"
            clip.progress = 1.0
            clip.output_json = outputs
            
            db.commit()
            
            push_video_update_sync(chapter_id, job_id, clip_id, "succeeded", 1.0)
            
            logger.info(f"[VideoWorker] Job {job_id} completed with {provider_name}")
            return {"success": True, "outputs": outputs}
        else:
            raise Exception(result.error or "Video generation failed")
        
    except Exception as e:
        logger.error(f"[VideoWorker] Job {job_id} failed: {e}", exc_info=True)
        if job:
            job.status = "failed"
            job.error_json = {"code": "EXECUTION_ERROR", "message": str(e)}
            job.finished_at = datetime.utcnow()
            db.commit()
        if clip:
            clip.status = "Failed"
            db.commit()
        
        push_video_update_sync(chapter_id, job_id, clip_id, "failed", 0)
        return {"success": False, "error": str(e)}
        
    finally:
        db.close()


def execute_mock_job(db, job, clip, chapter_id: str, job_id: str, clip_id: str):
    """Mock 视频生成（用于测试或无 Provider 时）"""
    logger.info(f"[VideoWorker] Running mock job for {clip_id}")
    
    # 模拟生成过程
    steps = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    for progress in steps:
        time.sleep(0.3)
        job.progress = progress
        clip.progress = progress
        db.commit()
        push_video_update_sync(chapter_id, job_id, clip_id, "running", progress)
    
    # 生成 Mock 结果
    outputs = {
        "video_url": f"https://storage.example.com/videos/{clip_id}.mp4",
        "preview_url": f"https://picsum.photos/seed/{clip_id}/512/288",
        "frames": [
            f"https://picsum.photos/seed/{clip_id}-f{i}/512/288"
            for i in range(8)
        ],
        "provider": "mock",
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
    
    logger.info(f"[VideoWorker] Mock job {job_id} completed")
    return {"success": True, "outputs": outputs}


def get_start_frame_url(panel, clip) -> str:
    """获取视频起始帧 URL"""
    # 优先使用 clip 中指定的起始帧
    if hasattr(clip, 'start_frame') and clip.start_frame:
        return clip.start_frame
    
    # 其次使用 panel 的渲染结果
    if panel and panel.spec_json:
        spec = panel.spec_json
        if isinstance(spec, dict):
            render = spec.get("render", {})
            if render.get("preview_url"):
                return render["preview_url"]
    
    # 检查 panel 的 layer pack
    if panel and hasattr(panel, 'active_layer_pack_id'):
        # 这里可以查询 layer pack 获取图片 URL
        pass
    
    return None


def get_end_frame_url(panel, clip) -> str:
    """获取视频结束帧 URL（双关键帧模式）"""
    if hasattr(clip, 'end_frame') and clip.end_frame:
        return clip.end_frame
    return None
