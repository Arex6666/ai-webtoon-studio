"""
合成导出路由 - 长条漫 Strip PNG 导出
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import uuid
import logging

from app.core.database import get_db
from app.core.storage import storage_client
from app.models.chapter import Chapter
from app.models.panel import Panel
from app.models.render_job import RenderJob, JobType, JobStatus
from app.schemas.chapter_layout import ChapterLayout

router = APIRouter()
logger = logging.getLogger(__name__)


class ComposeRequest(BaseModel):
    chapter_id: str
    output_format: str = "png"  # png/jpg/webp
    strip_width: int = 800
    panel_gap: int = 20
    background_color: str = "#FFFFFF"
    include_typeset: bool = True  # 是否包含嵌字图层


class ComposeResponse(BaseModel):
    job_id: str
    status: str
    message: str


class ExportResult(BaseModel):
    chapter_id: str
    export_url: str
    file_size: int
    panel_count: int
    total_height: int


# Routes
@router.post("/strip", response_model=ComposeResponse)
async def compose_strip(
    request: ComposeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    合成长条漫 Strip
    将章节的所有分镜按顺序拼接成一张长图
    """
    chapter = db.query(Chapter).filter(Chapter.id == request.chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # 检查是否有分镜
    panels = db.query(Panel).filter(
        Panel.chapter_id == request.chapter_id
    ).order_by(Panel.order_index).all()
    
    if not panels:
        raise HTTPException(status_code=400, detail="Chapter has no panels")
    
    # 检查所有分镜是否已渲染
    unrendered = [p for p in panels if p.render_status != "rendered"]
    if unrendered:
        raise HTTPException(
            status_code=400,
            detail=f"{len(unrendered)} panels not rendered yet"
        )
    
    # 创建合成任务
    job = RenderJob(
        chapter_id=chapter.id,
        job_type=JobType.COMPOSE.value,
        status=JobStatus.PENDING.value,
        input_params={
            "chapter_id": request.chapter_id,
            "output_format": request.output_format,
            "strip_width": request.strip_width,
            "panel_gap": request.panel_gap,
            "background_color": request.background_color,
            "include_typeset": request.include_typeset
        }
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # 更新章节状态
    chapter.export_status = "exporting"
    db.commit()
    
    # 启动后台任务
    background_tasks.add_task(
        execute_compose_job,
        job_id=job.id,
        chapter_id=request.chapter_id
    )
    
    return ComposeResponse(
        job_id=job.id,
        status="queued",
        message="Compose job queued"
    )


@router.get("/job/{job_id}")
async def get_compose_status(
    job_id: str,
    db: Session = Depends(get_db)
):
    """获取合成任务状态"""
    job = db.query(RenderJob).filter(RenderJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress,
        "current_step": job.current_step,
        "result": job.output_data,
        "error": job.error_message
    }


@router.get("/chapter/{chapter_id}/download")
async def get_chapter_export(
    chapter_id: str,
    db: Session = Depends(get_db)
):
    """获取章节导出下载链接"""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    if chapter.export_status != "exported" or not chapter.exported_url:
        raise HTTPException(status_code=404, detail="Chapter not exported yet")
    
    # 获取预签名 URL
    url = storage_client.get_url(chapter.exported_url, expires=3600)
    
    return {
        "chapter_id": chapter_id,
        "download_url": url,
        "expires_in": 3600
    }


@router.get("/chapter/{chapter_id}/preview")
async def preview_chapter_layout(
    chapter_id: str,
    db: Session = Depends(get_db)
):
    """
    预览章节布局
    返回所有分镜的缩略图 URL 和布局信息
    """
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    panels = db.query(Panel).filter(
        Panel.chapter_id == chapter_id
    ).order_by(Panel.order_index).all()
    
    layout = chapter.layout_json or {}
    panel_slots = layout.get("panels", [])
    
    preview_panels = []
    for panel in panels:
        # 获取渲染结果
        render_job = db.query(RenderJob).filter(
            RenderJob.panel_id == panel.id,
            RenderJob.status == JobStatus.COMPLETED.value
        ).order_by(RenderJob.completed_at.desc()).first()
        
        thumbnail_url = None
        if render_job and render_job.result_url:
            thumbnail_url = render_job.result_url
        
        # 获取布局信息
        slot_info = next(
            (s for s in panel_slots if s.get("panel_id") == panel.id),
            {"weight": "normal", "height_ratio": 1.0}
        )
        
        preview_panels.append({
            "panel_id": panel.id,
            "order": panel.order_index,
            "thumbnail_url": thumbnail_url,
            "typeset_url": panel.typeset_image_url,
            "weight": slot_info.get("weight", "normal"),
            "height_ratio": slot_info.get("height_ratio", 1.0),
            "render_status": panel.render_status,
            "typeset_status": panel.typeset_status
        })
    
    return {
        "chapter_id": chapter_id,
        "title": chapter.title,
        "export_status": chapter.export_status,
        "reading_flow": layout.get("reading_flow", "vertical"),
        "export_config": layout.get("export_config", {}),
        "panels": preview_panels
    }


# Background Task
async def execute_compose_job(job_id: str, chapter_id: str):
    """
    执行合成任务（后台）
    """
    from app.core.database import SessionLocal
    from app.services.composer import compose_strip_image
    
    db = SessionLocal()
    try:
        job = db.query(RenderJob).filter(RenderJob.id == job_id).first()
        chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
        
        if not job or not chapter:
            return
        
        # 更新状态
        job.status = JobStatus.PROCESSING.value
        job.current_step = "Loading panels"
        job.progress = 5
        db.commit()
        
        params = job.input_params or {}
        
        # 获取所有分镜
        panels = db.query(Panel).filter(
            Panel.chapter_id == chapter_id
        ).order_by(Panel.order_index).all()
        
        # 收集图片路径
        job.current_step = "Collecting images"
        job.progress = 10
        db.commit()
        
        panel_images = []
        for panel in panels:
            # 选择使用嵌字图或渲染图
            if params.get("include_typeset") and panel.typeset_image_url:
                panel_images.append(panel.typeset_image_url)
            else:
                # 获取渲染结果
                render_job = db.query(RenderJob).filter(
                    RenderJob.panel_id == panel.id,
                    RenderJob.job_type == JobType.LAYER_GENERATION.value,
                    RenderJob.status == JobStatus.COMPLETED.value
                ).order_by(RenderJob.completed_at.desc()).first()
                
                if render_job and render_job.output_data:
                    layers = render_job.output_data.get("layers", [])
                    for layer in layers:
                        if layer.get("type") == "full":
                            panel_images.append(layer.get("storage_path"))
                            break
        
        if not panel_images:
            raise Exception("No panel images found")
        
        # 获取布局信息
        layout = chapter.layout_json or {}
        panel_slots = layout.get("panels", [])
        
        # 合成
        job.current_step = "Composing strip"
        job.progress = 30
        db.commit()
        
        strip_data, total_height = await compose_strip_image(
            panel_image_paths=panel_images,
            panel_slots=panel_slots,
            strip_width=params.get("strip_width", 800),
            panel_gap=params.get("panel_gap", 20),
            background_color=params.get("background_color", "#FFFFFF"),
            output_format=params.get("output_format", "png"),
            progress_callback=lambda p: update_job_progress(db, job, 30 + int(p * 0.5))
        )
        
        # 上传
        job.current_step = "Uploading"
        job.progress = 85
        db.commit()
        
        output_format = params.get("output_format", "png")
        filename = f"strip_{chapter_id}_{uuid.uuid4().hex[:8]}.{output_format}"
        folder = f"exports/{chapter_id}"
        
        content_type = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "webp": "image/webp"
        }.get(output_format, "image/png")
        
        path = storage_client.upload_file(
            data=strip_data,
            filename=filename,
            content_type=content_type,
            folder=folder
        )
        
        url = storage_client.get_url(path)
        
        # 更新状态
        job.status = JobStatus.COMPLETED.value
        job.progress = 100
        job.current_step = "Complete"
        job.result_url = url
        job.output_data = {
            "export_path": path,
            "file_size": len(strip_data),
            "panel_count": len(panel_images),
            "total_height": total_height
        }
        
        chapter.export_status = "exported"
        chapter.exported_url = path
        
        from datetime import datetime
        job.completed_at = datetime.utcnow()
        
        db.commit()
        logger.info(f"Compose job completed: {job_id}")
        
    except Exception as e:
        logger.error(f"Compose job failed: {job_id} - {e}")
        if job:
            job.status = JobStatus.FAILED.value
            job.error_message = str(e)
            db.commit()
        if chapter:
            chapter.export_status = "failed"
            db.commit()
    finally:
        db.close()


def update_job_progress(db: Session, job: RenderJob, progress: int):
    """更新任务进度"""
    job.progress = progress
    db.commit()
