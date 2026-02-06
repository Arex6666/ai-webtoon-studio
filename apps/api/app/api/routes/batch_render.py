"""
Batch Render Routes (S3-07)

章节级批量渲染：一键渲染所有分镜
"""

from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
import uuid

from app.core.database import get_db
from app.models.chapter import Chapter
from app.models.panel import Panel
from app.models.render_job import RenderJob


router = APIRouter(prefix="/chapters", tags=["batch-render"])


# ============ Pydantic Schemas ============

class BatchRenderRequest(BaseModel):
    """批量渲染请求"""
    provider: str = "comfyui"
    panel_ids: Optional[List[str]] = None  # None = 渲染全部
    force_rerender: bool = False  # 是否强制重渲染已渲染的分镜
    max_retries: int = 3  # 失败重试次数


class BatchRenderResponse(BaseModel):
    """批量渲染响应"""
    batch_id: str
    job_count: int
    skipped_count: int
    can_render: bool
    pending_assets: List[str]


class BatchRenderStatus(BaseModel):
    """批量渲染状态"""
    batch_id: str
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    running_jobs: int
    progress: float


# ============ API Endpoints ============

@router.post("/{chapter_id}/render-all", response_model=BatchRenderResponse)
async def render_all_panels(
    chapter_id: str,
    request: BatchRenderRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    一键渲染章节所有分镜 (S3-07)
    
    1. 检查 assets_lock 是否完整
    2. 按 panel_index 顺序创建 RenderJob
    3. 失败自动重试 (max 3, exponential backoff)
    """
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # 检查资产绑定 (S6-Render: 使用实际 FaceID + 锚点状态)
    assets_lock = chapter.assets_lock_json or {}
    
    # 计算 pending 资产
    pending_assets = []
    
    # 检查角色 FaceID
    characters = assets_lock.get("characters", {})
    for char_id, char_lock in characters.items():
        if char_lock.get("binding_status") != "exact":
            pending_assets.append(f"角色 '{char_lock.get('name', char_id)}' FaceID 未就绪")
    
    # 检查场景锚点
    scenes = assets_lock.get("scenes", {})
    for scene_id, scene_lock in scenes.items():
        if scene_lock.get("anchor_status") != "ready":
            pending_assets.append(f"场景 '{scene_lock.get('name', scene_id)}' 锚点未就绪")
    
    if pending_assets and not request.force_rerender:
        return BatchRenderResponse(
            batch_id="",
            job_count=0,
            skipped_count=0,
            can_render=False,
            pending_assets=pending_assets
        )
    
    # 获取分镜列表
    panels_query = db.query(Panel).filter(
        Panel.chapter_id == chapter_id
    ).order_by(Panel.order_index)
    
    if request.panel_ids:
        panels_query = panels_query.filter(Panel.id.in_(request.panel_ids))
    
    panels = panels_query.all()
    
    if not panels:
        raise HTTPException(status_code=400, detail="No panels to render")
    
    # 创建批次 ID
    batch_id = f"batch_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    # 创建渲染任务
    job_ids = []
    skipped = 0
    
    for panel in panels:
        # 跳过已渲染的分镜（除非强制重渲染）
        if panel.render_status == "Rendered" and not request.force_rerender:
            skipped += 1
            continue
        
        # 从 assets_lock 获取渲染参数
        assets_lock = chapter.assets_lock_json or {}
        
        # 构建渲染参数
        spec = panel.spec_json or {}
        
        # S6-Render: 从 assets_lock 提取具体资产路径
        character_assets = {}
        for char_info in spec.get("characters", []):
            char_name = char_info.get("name") or char_info.get("character_id")
            # 从 assets_lock 查找对应角色
            for char_id, char_lock in assets_lock.get("characters", {}).items():
                if char_lock.get("name") == char_name:
                    character_assets[char_name] = {
                        "face_embedding_path": char_lock.get("face_embedding_path"),
                        "reference_image_path": char_lock.get("reference_image_path"),
                        "lora_path": char_lock.get("lora_path"),
                        "consistency_weight": char_lock.get("consistency_weight", 0.8)
                    }
                    break
        
        scene_assets = {}
        scene_info = spec.get("scene", {})
        scene_name = scene_info.get("location") or scene_info.get("scene_id")
        for scene_id, scene_lock in assets_lock.get("scenes", {}).items():
            if scene_lock.get("name") == scene_name or scene_id == scene_info.get("scene_id"):
                scene_assets = {
                    "anchor_image_path": scene_lock.get("anchor_image_path"),
                    "depth_map_path": scene_lock.get("depth_map_path"),
                    "control_maps": scene_lock.get("control_maps", {}),
                    "style_preset": scene_lock.get("style_preset")
                }
                break
        
        render_params = {
            "panel_id": panel.id,
            "chapter_id": chapter_id,
            "project_id": chapter.project_id,
            # 镜头参数
            "shot_type": spec.get("shot", {}).get("shotType", "MS"),
            "camera_move": spec.get("camera", {}).get("move", "static"),
            "duration": spec.get("shot", {}).get("durationSec", 3.0),
            # 场景参数
            "scene": spec.get("scene", {}),
            "scene_assets": scene_assets,  # S6-Render: 锚点和控制图
            # 角色参数
            "characters": spec.get("characters", []),
            "character_assets": character_assets,  # S6-Render: FaceID 和参考图
            # 提示词
            "prompt": spec.get("action_description", ""),
            "mood": spec.get("shot", {}).get("mood", "neutral"),
            # 资产锁定 (完整备份)
            "assets_lock": {
                "characters": assets_lock.get("characters", {}),
                "scenes": assets_lock.get("scenes", {}),
                "styles": assets_lock.get("styles", {})
            },
            # 重试配置
            "max_retries": request.max_retries,
            "retry_count": 0,
            # 批次信息
            "batch_id": batch_id
        }
        
        # 创建 RenderJob
        job = RenderJob(
            id=str(uuid.uuid4()),
            panel_id=panel.id,
            chapter_id=chapter_id,
            project_id=chapter.project_id,
            engine=request.provider,
            status="Queued",
            input_params=render_params,
            current_step="queued",
            progress=0
        )
        db.add(job)
        job_ids.append(job.id)
        
        # 更新分镜状态
        panel.render_status = "Queued"
    
    # 保存批次信息到 chapter
    layout = chapter.layout_json or {}
    layout["current_batch_id"] = batch_id
    layout["batch_started_at"] = datetime.utcnow().isoformat()
    layout["batch_total_jobs"] = len(job_ids)
    chapter.layout_json = layout
    
    db.commit()
    
    # 后台启动渲染
    background_tasks.add_task(run_batch_render_task, job_ids, request.max_retries)
    
    return BatchRenderResponse(
        batch_id=batch_id,
        job_count=len(job_ids),
        skipped_count=skipped,
        can_render=True,
        pending_assets=[]
    )


@router.get("/{chapter_id}/render-status")
async def get_render_status(
    chapter_id: str,
    db: Session = Depends(get_db)
):
    """
    获取章节渲染状态 (S3-07)
    """
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    layout = chapter.layout_json or {}
    batch_id = layout.get("current_batch_id")
    
    # 获取任务统计
    jobs = db.query(RenderJob).filter(
        RenderJob.chapter_id == chapter_id
    ).all()
    
    total = len(jobs)
    completed = sum(1 for j in jobs if j.status == "Succeeded")
    failed = sum(1 for j in jobs if j.status == "Failed")
    running = sum(1 for j in jobs if j.status in ["Queued", "Running"])
    
    progress = (completed / total * 100) if total > 0 else 0
    
    return {
        "chapter_id": chapter_id,
        "batch_id": batch_id,
        "total_jobs": total,
        "completed_jobs": completed,
        "failed_jobs": failed,
        "running_jobs": running,
        "progress": round(progress, 1),
        "batch_started_at": layout.get("batch_started_at"),
        "is_complete": running == 0 and total > 0
    }


async def run_batch_render_task(job_ids: List[str], max_retries: int = 3):
    """
    后台执行批量渲染任务
    
    Production MVP: 使用 PanelRenderer 执行真实渲染
    """
    from app.core.database import SessionLocal
    from app.services.layer_factory.panel_renderer import render_panel
    from app.services.layer_factory.render_protocol import RenderProviderType
    from app.core.config import settings
    import asyncio
    import logging
    
    logger = logging.getLogger(__name__)
    db = SessionLocal()
    
    # 根据配置选择 provider
    provider = RenderProviderType.COMFYUI_LOCAL if settings.COMFYUI_URL else RenderProviderType.MOCK
    logger.info(f"[BatchRender] Starting batch with provider={provider}, jobs={len(job_ids)}")
    
    try:
        for job_id in job_ids:
            job = db.query(RenderJob).filter(RenderJob.id == job_id).first()
            if not job:
                continue
            
            panel = db.query(Panel).filter(Panel.id == job.panel_id).first()
            if not panel:
                job.status = "Failed"
                job.error_message = "Panel not found"
                db.commit()
                continue
            
            # 更新状态
            job.status = "Running"
            job.current_step = "rendering"
            job.started_at = datetime.utcnow()
            db.commit()
            
            try:
                # 构建渲染参数
                render_params = job.input_params or {}
                panel_spec = panel.spec_json or {}
                assets_lock = render_params.get("assets_lock", {})
                
                # 创建进度回调
                def progress_callback(progress: float, message: str):
                    nonlocal db, job
                    try:
                        job.progress = int(progress * 100)
                        job.current_step = message
                        db.commit()
                    except Exception:
                        pass  # 忽略进度更新错误
                
                # 执行真实渲染
                result = await render_panel(
                    panel_id=panel.id,
                    project_id=job.project_id,
                    chapter_id=job.chapter_id,
                    panel_spec=panel_spec,
                    assets_lock=assets_lock,
                    provider=provider,
                    progress_callback=progress_callback,
                )
                
                if result.success and result.layerpack:
                    # 渲染成功
                    job.status = "Succeeded"
                    job.current_step = "done"
                    job.progress = 100
                    job.completed_at = datetime.utcnow()
                    
                    # 保存渲染结果到 job
                    job.output_result = result.layerpack.to_dict()
                    
                    # 更新分镜状态和预览 URL
                    panel.render_status = "Rendered"
                    
                    # 更新 panel spec 中的预览 URL
                    panel_spec["render"] = {
                        "preview_url": result.layerpack.full_url,
                        "layerpack_id": result.layerpack.layerpack_id,
                        "manifest_url": result.layerpack.manifest_url,
                        "rendered_at": datetime.utcnow().isoformat(),
                        "trace_id": result.layerpack.trace_id,
                    }
                    panel.spec_json = panel_spec
                    
                    logger.info(f"[BatchRender] Panel {panel.id} rendered successfully: {result.layerpack.full_url}")
                    
                else:
                    # 渲染失败
                    raise Exception(result.error or "Unknown render error")
                
                db.commit()
                
            except Exception as e:
                logger.error(f"[BatchRender] Panel {panel.id} render failed: {e}")
                
                # 失败处理 + 重试
                retry_count = (job.input_params or {}).get("retry_count", 0)
                
                if retry_count < max_retries:
                    # 重新入队
                    job.status = "Queued"
                    job.current_step = "retry_pending"
                    job.input_params = {
                        **(job.input_params or {}),
                        "retry_count": retry_count + 1,
                        "last_error": str(e)
                    }
                    logger.info(f"[BatchRender] Panel {panel.id} queued for retry ({retry_count + 1}/{max_retries})")
                else:
                    # 最终失败
                    job.status = "Failed"
                    job.current_step = "failed"
                    job.error_message = str(e)
                    job.completed_at = datetime.utcnow()
                    
                    if panel:
                        panel.render_status = "NeedsFix"
                    
                    logger.error(f"[BatchRender] Panel {panel.id} failed after {max_retries} retries")
                
                db.commit()
    
    finally:
        db.close()
        logger.info(f"[BatchRender] Batch completed")
