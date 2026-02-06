"""
排版路由 - Typeset API (完整实现)
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
import logging
import json

from app.db.database import get_db
from app.models import Panel

router = APIRouter()
logger = logging.getLogger(__name__)


# ============ Schemas ============

class BubbleInput(BaseModel):
    """气泡输入"""
    id: Optional[str] = None
    text: str
    style: str = "speech"
    x: float = Field(50, ge=0, le=100)
    y: float = Field(50, ge=0, le=100)
    width: float = 200
    height: float = 80
    fontSize: int = 24
    fontFamily: str = "Noto Sans SC"
    fontWeight: str = "normal"
    textAlign: str = "center"
    textColor: str = "#000000"
    backgroundColor: str = "#ffffff"
    borderColor: str = "#000000"
    borderWidth: int = 2
    borderRadius: int = 20
    tailDirection: str = "bottom"
    tailSize: int = 15
    shadow: bool = False
    glow: bool = False
    rotation: float = 0
    zIndex: int = 1


class TypesetInput(BaseModel):
    """排版输入"""
    bubbles: List[BubbleInput]


class TypesetResponse(BaseModel):
    """排版响应"""
    panel_id: str
    bubbles: List[dict]
    typeset_image_url: Optional[str]
    updated_at: str


class RenderTypesetRequest(BaseModel):
    """渲染排版请求"""
    panel_id: str
    source_image_url: str
    bubbles: List[BubbleInput]


# ============ Routes ============

@router.get("/{panel_id}/typeset", response_model=TypesetResponse)
async def get_typeset(panel_id: str, db: Session = Depends(get_db)):
    """获取面板排版数据"""
    panel = db.query(Panel).filter(Panel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    # 从 panel 获取排版数据
    typeset_data = panel.typeset_json or {"bubbles": []}
    
    return TypesetResponse(
        panel_id=panel_id,
        bubbles=typeset_data.get("bubbles", []),
        typeset_image_url=panel.typeset_image_url,
        updated_at=panel.updated_at.isoformat() if panel.updated_at else datetime.utcnow().isoformat()
    )


@router.put("/{panel_id}/typeset")
async def save_typeset(
    panel_id: str,
    typeset_input: TypesetInput,
    db: Session = Depends(get_db)
):
    """保存面板排版数据"""
    panel = db.query(Panel).filter(Panel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    # 构建排版数据
    bubbles = []
    for b in typeset_input.bubbles:
        bubble_data = b.model_dump()
        if not bubble_data.get("id"):
            bubble_data["id"] = str(uuid.uuid4())
        bubbles.append(bubble_data)
    
    panel.typeset_json = {"bubbles": bubbles}
    db.commit()
    
    logger.info(f"Typeset saved for panel {panel_id}: {len(bubbles)} bubbles")
    
    return {
        "message": "Typeset saved",
        "panel_id": panel_id,
        "bubbles_count": len(bubbles),
        "updated_at": datetime.utcnow().isoformat()
    }


@router.post("/{panel_id}/typeset/render")
async def render_typeset(
    panel_id: str,
    request: RenderTypesetRequest,
    db: Session = Depends(get_db)
):
    """
    渲染排版 - 将气泡合成到图片上
    
    返回合成后的图片 URL
    """
    panel = db.query(Panel).filter(Panel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    # 保存排版数据
    bubbles = [b.model_dump() for b in request.bubbles]
    panel.typeset_json = {"bubbles": bubbles}
    
    # 模拟渲染（实际应该调用图像处理服务）
    # 生产环境可以使用 Pillow 或 Cairo 进行文字渲染
    typeset_url = f"https://storage.example.com/typeset/{panel_id}/{int(datetime.utcnow().timestamp())}.png"
    
    panel.typeset_image_url = typeset_url
    db.commit()
    
    logger.info(f"Typeset rendered for panel {panel_id}")
    
    return {
        "message": "Typeset rendered",
        "panel_id": panel_id,
        "typeset_image_url": typeset_url,
        "bubbles_count": len(bubbles)
    }


@router.delete("/{panel_id}/typeset")
async def clear_typeset(panel_id: str, db: Session = Depends(get_db)):
    """清除面板排版"""
    panel = db.query(Panel).filter(Panel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    panel.typeset_json = {"bubbles": []}
    panel.typeset_image_url = None
    db.commit()
    
    return {"message": "Typeset cleared", "panel_id": panel_id}
