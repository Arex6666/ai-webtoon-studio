"""
Export API Routes
Production MVP: Strip PNG and future video export

Endpoints:
- POST /api/v1/export/strip - Export chapter as vertical strip PNG
- GET /api/v1/export/strip/{export_id} - Get export status/download
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
import logging

from app.core.database import get_db
from app.models.chapter import Chapter
from app.models.panel import Panel
from app.services.export.strip_composer import get_strip_composer
from app.services.storage import get_object_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["导出"])


# ============ Request/Response Models ============

class ExportStripRequest(BaseModel):
    """Strip 导出请求"""
    chapter_id: str
    panel_ids: Optional[List[str]] = None  # None = all rendered panels
    output_width: int = 1080
    gap: int = 0  # pixel gap between panels
    background_color: str = "#FFFFFF"
    format: str = "png"  # png | webp | jpg
    direct_download: bool = False  # True = return bytes, False = upload and return URL


class ExportStripResponse(BaseModel):
    """Strip 导出响应"""
    success: bool
    export_id: str
    download_url: Optional[str] = None
    file_size: Optional[int] = None
    panel_count: int = 0
    error: Optional[str] = None


class ExportJobStatus(BaseModel):
    """导出任务状态"""
    export_id: str
    status: str  # pending | processing | completed | failed
    progress: float = 0
    download_url: Optional[str] = None
    error: Optional[str] = None


# ============ In-memory export job tracking ============
# In production, this should be a database or Redis
_export_jobs = {}


# ============ API Endpoints ============

@router.post("/strip", response_model=ExportStripResponse)
async def export_strip(
    request: ExportStripRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    导出章节为长条漫 PNG
    
    1. 获取章节已渲染的分镜
    2. 按顺序下载图片
    3. 合成长条漫
    4. 返回下载 URL 或直接下载
    """
    chapter = db.query(Chapter).filter(Chapter.id == request.chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # 获取分镜
    panels_query = db.query(Panel).filter(
        Panel.chapter_id == request.chapter_id,
        Panel.render_status == "Rendered"
    ).order_by(Panel.order_index)
    
    if request.panel_ids:
        panels_query = panels_query.filter(Panel.id.in_(request.panel_ids))
    
    panels = panels_query.all()
    
    if not panels:
        return ExportStripResponse(
            success=False,
            export_id="",
            panel_count=0,
            error="没有已渲染的分镜可供导出"
        )
    
    # 收集预览 URL
    image_urls = []
    for panel in panels:
        spec = panel.spec_json or {}
        preview_url = spec.get("render", {}).get("preview_url")
        if preview_url:
            image_urls.append(preview_url)
    
    if not image_urls:
        return ExportStripResponse(
            success=False,
            export_id="",
            panel_count=len(panels),
            error="分镜没有预览图片可供导出"
        )
    
    export_id = f"export-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    
    logger.info(f"[Export] Starting strip export {export_id} with {len(image_urls)} panels")
    
    try:
        # 解析背景色
        bg_hex = request.background_color.lstrip("#")
        bg_color = tuple(int(bg_hex[i:i+2], 16) for i in (0, 2, 4))
        
        # 合成长条漫
        composer = get_strip_composer(gap=request.gap)
        composer.bg_color = bg_color
        
        strip_bytes = await composer.compose_from_urls(
            image_urls=image_urls,
            output_width=request.output_width
        )
        
        # 直接下载或上传到存储
        if request.direct_download:
            # 返回响应会在另一个端点中处理
            _export_jobs[export_id] = {
                "status": "completed",
                "data": strip_bytes,
                "panel_count": len(image_urls)
            }
            
            return ExportStripResponse(
                success=True,
                export_id=export_id,
                download_url=f"/api/v1/export/strip/{export_id}/download",
                file_size=len(strip_bytes),
                panel_count=len(image_urls)
            )
        else:
            # 上传到存储
            storage = get_object_store()
            storage_key = f"exports/{chapter.project_id}/{export_id}/strip.png"
            
            try:
                download_url = await storage.upload_file(
                    file_content=strip_bytes,
                    key=storage_key,
                    content_type="image/png"
                )
            except Exception as storage_error:
                logger.warning(f"[Export] Storage error: {storage_error}")
                # Fallback to memory storage
                _export_jobs[export_id] = {
                    "status": "completed",
                    "data": strip_bytes,
                    "panel_count": len(image_urls)
                }
                download_url = f"/api/v1/export/strip/{export_id}/download"
            
            return ExportStripResponse(
                success=True,
                export_id=export_id,
                download_url=download_url,
                file_size=len(strip_bytes),
                panel_count=len(image_urls)
            )
            
    except Exception as e:
        logger.error(f"[Export] Error: {e}")
        return ExportStripResponse(
            success=False,
            export_id=export_id,
            panel_count=len(image_urls),
            error=str(e)
        )


@router.get("/strip/{export_id}/download")
async def download_strip(export_id: str):
    """
    下载导出的长条漫 PNG
    """
    job = _export_jobs.get(export_id)
    if not job or job.get("status") != "completed":
        raise HTTPException(status_code=404, detail="Export not found or not ready")
    
    data = job.get("data")
    if not data:
        raise HTTPException(status_code=404, detail="Export data not available")
    
    return Response(
        content=data,
        media_type="image/png",
        headers={
            "Content-Disposition": f"attachment; filename=strip-{export_id}.png"
        }
    )


@router.get("/strip/{export_id}/status", response_model=ExportJobStatus)
async def get_export_status(export_id: str):
    """
    获取导出任务状态
    """
    job = _export_jobs.get(export_id)
    if not job:
        return ExportJobStatus(
            export_id=export_id,
            status="not_found"
        )
    
    return ExportJobStatus(
        export_id=export_id,
        status=job.get("status", "pending"),
        progress=1.0 if job.get("status") == "completed" else 0,
        download_url=f"/api/v1/export/strip/{export_id}/download" if job.get("data") else None
    )


@router.post("/strip/preview")
async def preview_strip(
    request: ExportStripRequest,
    db: Session = Depends(get_db)
):
    """
    预览导出配置 - 返回元信息而不实际导出
    """
    chapter = db.query(Chapter).filter(Chapter.id == request.chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    panels = db.query(Panel).filter(
        Panel.chapter_id == request.chapter_id,
        Panel.render_status == "Rendered"
    ).order_by(Panel.order_index).all()
    
    rendered_count = len(panels)
    image_urls = []
    
    for panel in panels:
        spec = panel.spec_json or {}
        preview_url = spec.get("render", {}).get("preview_url")
        if preview_url:
            image_urls.append({
                "panel_id": panel.id,
                "index": panel.order_index,
                "preview_url": preview_url
            })
    
    # 估算输出尺寸 (假设 16:9 每格)
    estimated_height = len(image_urls) * int(request.output_width * 1.78)
    
    return {
        "chapter_id": request.chapter_id,
        "total_panels": db.query(Panel).filter(Panel.chapter_id == request.chapter_id).count(),
        "rendered_panels": rendered_count,
        "exportable_panels": len(image_urls),
        "panels": image_urls,
        "estimated_output": {
            "width": request.output_width,
            "height": estimated_height,
            "format": request.format
        }
    }
