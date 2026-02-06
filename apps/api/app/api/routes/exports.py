"""
Exports API - 导出管理
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.models import Export, Chapter

router = APIRouter(prefix="/exports", tags=["exports"])


# ============ Schemas ============

class ExportCreate(BaseModel):
    chapter_id: str
    type: str = Field(default="strip_png")  # strip_png/micro_mp4/full_video
    settings_json: dict = Field(default_factory=dict)


class ExportResponse(BaseModel):
    id: str
    chapter_id: str
    type: str
    state: str
    settings_json: dict
    output_uri: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


# ============ Routes ============

@router.get("", response_model=List[ExportResponse])
async def list_exports(
    chapter_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """获取导出列表"""
    query = db.query(Export)
    if chapter_id:
        query = query.filter(Export.chapter_id == chapter_id)
    exports = query.offset(skip).limit(limit).all()
    return [_to_response(e) for e in exports]


@router.post("", response_model=ExportResponse)
async def create_export(
    data: ExportCreate,
    db: Session = Depends(get_db)
):
    """创建导出任务"""
    # 验证章节存在
    chapter = db.query(Chapter).filter(Chapter.id == data.chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    # 创建 Export 记录
    export = Export(
        chapter_id=data.chapter_id,
        type=data.type,
        settings_json=data.settings_json,
        state="queued"
    )
    db.add(export)
    db.commit()
    db.refresh(export)

    # 创建关联的 Job
    job_type = "export_job"
    if data.type == "bundle":
        job_type = "EXPORT_BUNDLE"
    
    job = Job(
        type=job_type,
        chapter_id=data.chapter_id,
        status="queued",
        inputs_json={
            "export_id": export.id,
            "export_type": data.type,
            "settings": data.settings_json
        },
        provider="local"
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 触发 Celery 任务
    if data.type == "bundle":
        from app.workers.bundle_worker import export_bundle_task
        export_bundle_task.delay(job.id, data.chapter_id, export.id)
    else:
        # 保留旧逻辑 (TODO: 迁移到统一 worker)
        from app.workers.export_worker import execute_export_job
        execute_export_job.delay(job.id, data.chapter_id)

    return _to_response(export)


@router.get("/{export_id}", response_model=ExportResponse)
async def get_export(
    export_id: str,
    db: Session = Depends(get_db)
):
    """获取导出详情"""
    export = db.query(Export).filter(Export.id == export_id).first()
    if not export:
        raise HTTPException(status_code=404, detail="Export not found")
    return _to_response(export)


@router.delete("/{export_id}")
async def cancel_export(
    export_id: str,
    db: Session = Depends(get_db)
):
    """取消导出"""
    export = db.query(Export).filter(Export.id == export_id).first()
    if not export:
        raise HTTPException(status_code=404, detail="Export not found")

    if export.state in ["succeeded", "failed"]:
        raise HTTPException(status_code=400, detail="Cannot cancel completed export")

    export.state = "cancelled"
    db.commit()
    return {"status": "ok", "message": "Export cancelled"}


@router.get("/{export_id}/manifest")
async def get_export_manifest(
    export_id: str,
    db: Session = Depends(get_db)
):
    """获取导出的 Manifest (用于预览)"""
    export = db.query(Export).filter(Export.id == export_id).first()
    if not export:
        raise HTTPException(status_code=404, detail="Export not found")
        
    settings = export.settings_json or {}
    manifest_url = settings.get("manifest_url")
    
    if not manifest_url:
        raise HTTPException(status_code=404, detail="Manifest not available")
        
    # 如果是本地 Mock 环境，可能需要直接读取文件或代理请求
    # 这里假设前端能直接访问 MinIO/S3 链接，或者通过反向代理
    
    # 暂时返回 URL
    return {"manifest_url": manifest_url}


def _to_response(export: Export) -> dict:
    return {
        "id": export.id,
        "chapter_id": export.chapter_id,
        "type": export.type,
        "state": export.state,
        "settings_json": export.settings_json or {},
        "output_uri": export.output_uri,
        "created_at": export.created_at.isoformat() if export.created_at else ""
    }
