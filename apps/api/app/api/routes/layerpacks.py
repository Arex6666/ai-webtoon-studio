"""
LayerPack 路由 - 图层包管理 API
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import logging

from app.db.database import get_db
from app.models import LayerPack, Panel

router = APIRouter()
logger = logging.getLogger(__name__)


# ============ Schemas ============

class LayerPackFiles(BaseModel):
    full: Optional[str] = None
    char: Optional[str] = None
    bg: Optional[str] = None
    fg: Optional[str] = None
    mask: Optional[str] = None
    depth: Optional[str] = None
    lineart: Optional[str] = None
    extras: Optional[dict] = None


class LayerPackQA(BaseModel):
    score: float = 0.0
    passed: bool = False
    issues: Optional[List[str]] = None


class LayerPackResponse(BaseModel):
    id: str
    panel_id: str
    attempt: int
    version: int
    status: str
    is_active: bool
    manifest_url: Optional[str]
    full_url: Optional[str]
    files: LayerPackFiles
    qa: LayerPackQA
    width: Optional[int]
    height: Optional[int]
    created_at: str
    generation_params: Optional[dict]

    class Config:
        from_attributes = True


class LayerPackListResponse(BaseModel):
    items: List[LayerPackResponse]
    total: int
    active_id: Optional[str]


class SetActiveRequest(BaseModel):
    layerpack_id: str


# ============ Helper Functions ============

def layerpack_to_response(lp: LayerPack) -> LayerPackResponse:
    """转换 LayerPack 到响应格式"""
    return LayerPackResponse(
        id=lp.id,
        panel_id=lp.panel_id,
        attempt=lp.attempt or 1,
        version=lp.version or 1,
        status=lp.status or "completed",
        is_active=lp.is_active == "true",
        manifest_url=lp.manifest_url,
        full_url=lp.full_url or lp.file_full,
        files=LayerPackFiles(
            full=lp.file_full,
            char=lp.file_char,
            bg=lp.file_bg,
            fg=lp.file_fg,
            mask=lp.file_mask,
            depth=lp.file_depth,
            lineart=lp.file_lineart,
            extras=lp.extra_files,
        ),
        qa=LayerPackQA(
            score=lp.qa_score or 0.0,
            passed=lp.qa_passed == "true",
            issues=(lp.qa_json or {}).get("issues", []),
        ),
        width=lp.width,
        height=lp.height,
        created_at=lp.created_at.isoformat() if lp.created_at else datetime.utcnow().isoformat(),
        generation_params=lp.generation_params or lp.params_json,
    )


# ============ Routes ============

@router.get("/{panel_id}/layerpacks", response_model=LayerPackListResponse)
async def list_panel_layerpacks(panel_id: str, db: Session = Depends(get_db)):
    """获取面板的所有 LayerPack 列表"""
    panel = db.query(Panel).filter(Panel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    layerpacks = db.query(LayerPack).filter(
        LayerPack.panel_id == panel_id
    ).order_by(LayerPack.attempt.desc()).all()
    
    active_id = panel.active_layer_pack_id
    
    return LayerPackListResponse(
        items=[layerpack_to_response(lp) for lp in layerpacks],
        total=len(layerpacks),
        active_id=active_id
    )


@router.get("/{panel_id}/layerpacks/active", response_model=LayerPackResponse)
async def get_active_layerpack(panel_id: str, db: Session = Depends(get_db)):
    """获取面板当前激活的 LayerPack"""
    panel = db.query(Panel).filter(Panel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    if not panel.active_layer_pack_id:
        raise HTTPException(status_code=404, detail="No active layerpack")
    
    lp = db.query(LayerPack).filter(LayerPack.id == panel.active_layer_pack_id).first()
    if not lp:
        raise HTTPException(status_code=404, detail="Active layerpack not found")
    
    return layerpack_to_response(lp)


@router.get("/{panel_id}/layerpacks/{layerpack_id}", response_model=LayerPackResponse)
async def get_layerpack(panel_id: str, layerpack_id: str, db: Session = Depends(get_db)):
    """获取指定 LayerPack"""
    lp = db.query(LayerPack).filter(
        LayerPack.id == layerpack_id,
        LayerPack.panel_id == panel_id
    ).first()
    
    if not lp:
        raise HTTPException(status_code=404, detail="LayerPack not found")
    
    return layerpack_to_response(lp)


@router.post("/{panel_id}/layerpacks/active")
async def set_active_layerpack(
    panel_id: str,
    request: SetActiveRequest,
    db: Session = Depends(get_db)
):
    """设置面板激活的 LayerPack"""
    panel = db.query(Panel).filter(Panel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    lp = db.query(LayerPack).filter(
        LayerPack.id == request.layerpack_id,
        LayerPack.panel_id == panel_id
    ).first()
    
    if not lp:
        raise HTTPException(status_code=404, detail="LayerPack not found")
    
    # 更新所有 LayerPack 的激活状态
    db.query(LayerPack).filter(LayerPack.panel_id == panel_id).update({"is_active": "false"})
    lp.is_active = "true"
    
    # 更新 Panel 的激活 LayerPack
    panel.active_layer_pack_id = request.layerpack_id
    panel.preview_url = lp.full_url or lp.file_full
    panel.preview_key = lp.file_full or None
    
    db.commit()
    
    logger.info(f"Set active layerpack for panel {panel_id}: {request.layerpack_id}")
    
    return {
        "message": "Active layerpack updated",
        "panel_id": panel_id,
        "layerpack_id": request.layerpack_id
    }


@router.get("/{panel_id}/layerpacks/{layerpack_id}/manifest")
async def get_layerpack_manifest(panel_id: str, layerpack_id: str, db: Session = Depends(get_db)):
    """获取 LayerPack 的 manifest 内容"""
    lp = db.query(LayerPack).filter(
        LayerPack.id == layerpack_id,
        LayerPack.panel_id == panel_id
    ).first()
    
    if not lp:
        raise HTTPException(status_code=404, detail="LayerPack not found")
    
    # 构建 manifest
    manifest = {
        "version": "1.0.0",
        "id": lp.id,
        "panel_id": lp.panel_id,
        "attempt": lp.attempt or 1,
        "dimensions": {
            "width": lp.width or 1080,
            "height": lp.height or 1920,
            "aspect": "9:16"
        },
        "generation": lp.generation_params or lp.params_json or {},
        "outputs": {
            "full": lp.file_full,
            "char": lp.file_char,
            "bg": lp.file_bg,
            "mask": lp.file_mask,
            "depth": lp.file_depth,
            "lineart": lp.file_lineart,
            **(lp.extra_files or {})
        },
        "qa": {
            "score": lp.qa_score or 0.0,
            "passed": lp.qa_passed == "true",
            **(lp.qa_json or {})
        },
        "metadata": {
            "created_at": lp.created_at.isoformat() if lp.created_at else None,
            "status": lp.status,
            "version": lp.version,
            **(lp.metadata_json or {})
        }
    }
    
    return manifest
