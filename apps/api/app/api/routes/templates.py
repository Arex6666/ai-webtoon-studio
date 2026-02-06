"""
模板路由 - Templates API
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import uuid
import logging

from app.db.database import get_db
from app.models import Chapter, Panel, ChapterBindings
from app.models.template import Template

router = APIRouter()
logger = logging.getLogger(__name__)


# ============ Schemas ============

class StyleProfile(BaseModel):
    art_style: str = "anime"
    color_palette: str = "vibrant"
    lighting: str = "soft"
    texture: str = "smooth"


class RenderParams(BaseModel):
    width: int = 1080
    height: int = 1920
    steps: int = 20
    sampler: str = "euler"
    scheduler: str = "normal"
    cfg_scale: float = 7.0


class PromptTemplate(BaseModel):
    positive_prefix: str = "masterpiece, best quality, "
    positive_suffix: str = ""
    negative_prompt: str = "low quality, blurry, watermark"


class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    category: str = "general"
    tags: List[str] = []
    style_profile: Optional[StyleProfile] = None
    render_params: Optional[RenderParams] = None
    prompt_template: Optional[PromptTemplate] = None
    identity_asset_ids: List[str] = []
    scene_asset_ids: List[str] = []
    anchor_ids: List[str] = []


class TemplateResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    thumbnail_url: Optional[str]
    category: str
    tags: List[str]
    style_profile: dict
    render_params: dict
    prompt_template: dict
    identity_asset_ids: List[str]
    scene_asset_ids: List[str]
    use_count: int
    is_public: bool
    created_at: Optional[str]


class ApplyTemplateRequest(BaseModel):
    template_id: str
    apply_to_panels: bool = True  # 是否应用到所有面板


# ============ Routes ============

@router.get("", response_model=List[TemplateResponse])
async def list_templates(
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取模板列表"""
    query = db.query(Template)
    
    if category:
        query = query.filter(Template.category == category)
    
    templates = query.order_by(Template.use_count.desc()).limit(50).all()
    
    return [_to_response(t) for t in templates]


@router.post("", response_model=TemplateResponse)
async def create_template(
    data: TemplateCreate,
    db: Session = Depends(get_db)
):
    """创建模板"""
    template = Template(
        id=str(uuid.uuid4()),
        name=data.name,
        description=data.description,
        thumbnail_url=data.thumbnail_url,
        category=data.category,
        tags=data.tags,
        style_profile=data.style_profile.model_dump() if data.style_profile else {},
        render_params=data.render_params.model_dump() if data.render_params else {},
        prompt_template=data.prompt_template.model_dump() if data.prompt_template else {},
        identity_asset_ids=data.identity_asset_ids,
        scene_asset_ids=data.scene_asset_ids,
        anchor_ids=data.anchor_ids,
    )
    
    db.add(template)
    db.commit()
    db.refresh(template)
    
    logger.info(f"Template created: {template.id} - {template.name}")
    
    return _to_response(template)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: str, db: Session = Depends(get_db)):
    """获取模板详情"""
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return _to_response(template)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    data: TemplateCreate,
    db: Session = Depends(get_db)
):
    """更新模板"""
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    template.name = data.name
    template.description = data.description
    template.thumbnail_url = data.thumbnail_url
    template.category = data.category
    template.tags = data.tags
    if data.style_profile:
        template.style_profile = data.style_profile.model_dump()
    if data.render_params:
        template.render_params = data.render_params.model_dump()
    if data.prompt_template:
        template.prompt_template = data.prompt_template.model_dump()
    template.identity_asset_ids = data.identity_asset_ids
    template.scene_asset_ids = data.scene_asset_ids
    template.anchor_ids = data.anchor_ids
    
    db.commit()
    
    return _to_response(template)


@router.delete("/{template_id}")
async def delete_template(template_id: str, db: Session = Depends(get_db)):
    """删除模板"""
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    db.delete(template)
    db.commit()
    
    return {"message": "Template deleted", "template_id": template_id}


@router.post("/{chapter_id}/apply-template")
async def apply_template_to_chapter(
    chapter_id: str,
    request: ApplyTemplateRequest,
    db: Session = Depends(get_db)
):
    """
    应用模板到章节
    
    - 更新章节 bindings
    - 可选：更新所有面板的渲染参数
    """
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    template = db.query(Template).filter(Template.id == request.template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # 获取或创建 bindings
    bindings = db.query(ChapterBindings).filter(ChapterBindings.chapter_id == chapter_id).first()
    if not bindings:
        bindings = ChapterBindings(
            id=str(uuid.uuid4()),
            chapter_id=chapter_id
        )
        db.add(bindings)
    
    # 应用模板资产
    bindings.identity_asset_ids = template.identity_asset_ids or []
    bindings.scene_asset_ids = template.scene_asset_ids or []
    bindings.anchor_ids = template.anchor_ids or []
    bindings.style_profile_id = template.id
    
    # 更新模板使用次数
    template.use_count = (template.use_count or 0) + 1
    
    panels_updated = 0
    
    # 应用到面板
    if request.apply_to_panels:
        panels = db.query(Panel).filter(Panel.chapter_id == chapter_id).all()
        
        for panel in panels:
            # 更新面板渲染参数
            spec = panel.spec_json or {}
            
            # 合并模板参数
            spec["render_params"] = template.render_params
            spec["style_profile"] = template.style_profile
            spec["prompt_template"] = template.prompt_template
            
            panel.spec_json = spec
            panels_updated += 1
    
    db.commit()
    
    logger.info(f"Template {template.name} applied to chapter {chapter_id}, {panels_updated} panels updated")
    
    return {
        "message": "Template applied",
        "chapter_id": chapter_id,
        "template_id": template.id,
        "template_name": template.name,
        "panels_updated": panels_updated
    }


def _to_response(template: Template) -> dict:
    return {
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "thumbnail_url": template.thumbnail_url,
        "category": template.category,
        "tags": template.tags or [],
        "style_profile": template.style_profile or {},
        "render_params": template.render_params or {},
        "prompt_template": template.prompt_template or {},
        "identity_asset_ids": template.identity_asset_ids or [],
        "scene_asset_ids": template.scene_asset_ids or [],
        "use_count": template.use_count or 0,
        "is_public": template.is_public == "true",
        "created_at": template.created_at.isoformat() if template.created_at else None,
    }
