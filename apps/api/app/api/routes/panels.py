"""
分镜管理路由
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.core.storage import storage_client
from app.models.panel import Panel
from app.models.chapter import Chapter
from app.models.render_job import RenderJob, JobType, JobStatus
from app.schemas.panel_spec import PanelSpec
from app.schemas.chapter_layout import PanelSlot, PanelWeight
from app.schemas.panel_bindings import PanelBindingPatch, PanelBindingResponse
from app.services.binding import (
    apply_panel_binding,
    refresh_chapter_bindings,
)
from app.services.binding.binding_service import get_asset_or_raise
from sqlalchemy.orm.attributes import flag_modified

router = APIRouter()


def get_panel_image_url(panel: Panel, db: Session) -> Optional[str]:
    """获取分镜的预览图 URL（预签名）"""
    # 优先使用嵌字图
    if panel.typeset_image_url:
        try:
            return storage_client.get_url(panel.typeset_image_url, expires=3600)
        except:
            pass
    
    # 其次使用渲染结果
    if panel.render_status == "rendered":
        render_job = db.query(RenderJob).filter(
            RenderJob.panel_id == panel.id,
            RenderJob.job_type == JobType.LAYER_GENERATION.value,
            RenderJob.status == JobStatus.COMPLETED.value
        ).order_by(RenderJob.completed_at.desc()).first()
        
        if render_job and render_job.output_data:
            layers = render_job.output_data.get("layers", [])
            for layer in layers:
                if layer.get("type") == "full" and layer.get("storage_path"):
                    try:
                        return storage_client.get_url(layer["storage_path"], expires=3600)
                    except:
                        pass
    
    return None


# Request/Response Models
class PanelCreate(BaseModel):
    chapter_id: str
    spec: Optional[PanelSpec] = None


class PanelResponse(BaseModel):
    id: str
    chapter_id: str
    order_index: int
    spec_json: Dict[str, Any]
    render_status: str
    active_layer_pack_id: Optional[str]
    typeset_status: str
    typeset_image_url: Optional[str]
    preview_url: Optional[str] = None  # 预签名的可访问 URL
    qa_score: float
    needs_manual_fix: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PanelListResponse(BaseModel):
    items: List[PanelResponse]
    total: int


# Routes
@router.get("/chapter/{chapter_id}", response_model=PanelListResponse)
async def list_panels(
    chapter_id: str,
    db: Session = Depends(get_db)
):
    """获取章节的所有分镜"""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    panels = db.query(Panel).filter(
        Panel.chapter_id == chapter_id
    ).order_by(Panel.order_index).all()

    # Batch pre-fetch latest completed render jobs for all panels (avoids N+1)
    panel_ids = [p.id for p in panels]
    render_job_map: dict = {}
    if panel_ids:
        from sqlalchemy import and_
        # Get the latest completed render job per panel
        render_jobs = db.query(RenderJob).filter(
            RenderJob.panel_id.in_(panel_ids),
            RenderJob.job_type == JobType.LAYER_GENERATION.value,
            RenderJob.status == JobStatus.COMPLETED.value
        ).order_by(RenderJob.completed_at.desc()).all()
        for rj in render_jobs:
            if rj.panel_id not in render_job_map:
                render_job_map[rj.panel_id] = rj

    def get_panel_image_url_batch(panel: Panel) -> Optional[str]:
        """Get panel image URL using pre-fetched render jobs."""
        if panel.typeset_image_url:
            try:
                return storage_client.get_url(panel.typeset_image_url, expires=3600)
            except Exception:
                pass
        if panel.render_status == "rendered":
            render_job = render_job_map.get(panel.id)
            if render_job and render_job.output_data:
                layers = render_job.output_data.get("layers", [])
                for layer in layers:
                    if layer.get("type") == "full" and layer.get("storage_path"):
                        try:
                            return storage_client.get_url(layer["storage_path"], expires=3600)
                        except Exception:
                            pass
        return None

    items = [
        PanelResponse(
            id=p.id,
            chapter_id=p.chapter_id,
            order_index=p.order_index,
            spec_json=p.spec_json or {},
            render_status=p.render_status,
            active_layer_pack_id=p.active_layer_pack_id,
            typeset_status=p.typeset_status,
            typeset_image_url=p.typeset_image_url,
            preview_url=get_panel_image_url_batch(p),
            qa_score=p.qa_score,
            needs_manual_fix=p.needs_manual_fix,
            created_at=p.created_at,
            updated_at=p.updated_at
        )
        for p in panels
    ]

    return PanelListResponse(items=items, total=len(items))


@router.post("", response_model=PanelResponse)
async def create_panel(
    request: PanelCreate,
    db: Session = Depends(get_db)
):
    """创建新分镜"""
    chapter = db.query(Chapter).filter(Chapter.id == request.chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # 获取当前最大 order_index
    max_order = db.query(Panel).filter(
        Panel.chapter_id == request.chapter_id
    ).count()
    
    import uuid
    panel_id = str(uuid.uuid4())
    
    # 创建默认 spec
    default_spec = request.spec or PanelSpec(panel_id=panel_id)
    default_spec.panel_id = panel_id  # 确保 ID 一致
    
    panel = Panel(
        id=panel_id,
        chapter_id=request.chapter_id,
        order_index=max_order,
        spec_json=default_spec.model_dump()
    )
    db.add(panel)
    
    # 自动更新 chapter layout
    if chapter.layout_json:
        layout = chapter.layout_json
        if "panels" not in layout:
            layout["panels"] = []
        layout["panels"].append({
            "panel_id": panel_id,
            "weight": "normal",
            "height_ratio": 1.0,
            "order": max_order
        })
        chapter.layout_json = layout
    
    db.commit()
    db.refresh(panel)
    
    return PanelResponse(
        id=panel.id,
        chapter_id=panel.chapter_id,
        order_index=panel.order_index,
        spec_json=panel.spec_json,
        render_status=panel.render_status,
        active_layer_pack_id=panel.active_layer_pack_id,
        typeset_status=panel.typeset_status,
        typeset_image_url=panel.typeset_image_url,
        preview_url=None,  # 新创建的分镜没有图片
        qa_score=panel.qa_score,
        needs_manual_fix=panel.needs_manual_fix,
        created_at=panel.created_at,
        updated_at=panel.updated_at
    )


@router.get("/{panel_id}", response_model=PanelResponse)
async def get_panel(
    panel_id: str,
    db: Session = Depends(get_db)
):
    """获取分镜详情"""
    panel = db.query(Panel).filter(Panel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    return PanelResponse(
        id=panel.id,
        chapter_id=panel.chapter_id,
        order_index=panel.order_index,
        spec_json=panel.spec_json or {},
        render_status=panel.render_status,
        active_layer_pack_id=panel.active_layer_pack_id,
        typeset_status=panel.typeset_status,
        typeset_image_url=panel.typeset_image_url,
        preview_url=get_panel_image_url(panel, db),  # 获取预签名 URL
        qa_score=panel.qa_score,
        needs_manual_fix=panel.needs_manual_fix,
        created_at=panel.created_at,
        updated_at=panel.updated_at
    )


@router.put("/{panel_id}/spec")
async def update_panel_spec(
    panel_id: str,
    spec: PanelSpec,
    db: Session = Depends(get_db)
):
    """
    更新分镜规格 JSON（Single Source of Truth）
    """
    panel = db.query(Panel).filter(Panel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    # 确保 panel_id 一致
    spec.panel_id = panel_id
    panel.spec_json = spec.model_dump()
    
    db.commit()
    
    return {
        "message": "Panel spec updated",
        "panel_id": panel_id
    }


@router.patch("/{panel_id}/bindings", response_model=PanelBindingResponse)
def patch_panel_bindings(
    panel_id: str,
    body: PanelBindingPatch,
    db: Session = Depends(get_db),
):
    """Update a single binding slot on a panel's spec_json.

    Slot='character'/'prop' use slot_index; slot='scene' ignores slot_index.
    asset_id=null clears the binding.
    """
    panel = db.query(Panel).filter(Panel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")

    if panel.render_status in ("queued", "running", "rendering"):
        raise HTTPException(
            status_code=409,
            detail="Panel is rendering; cannot modify bindings. Wait or cancel render first.",
        )

    if body.asset_id is not None:
        try:
            get_asset_or_raise(db, body.asset_id, body.slot)
        except LookupError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    new_spec = apply_panel_binding(
        panel.spec_json or {},
        body.slot,
        body.slot_index,
        body.asset_id,
        body.asset_version_id,
    )
    panel.spec_json = new_spec
    flag_modified(panel, "spec_json")
    db.commit()
    db.refresh(panel)

    refresh_chapter_bindings(db, panel.chapter_id)

    return PanelBindingResponse(
        panel_id=panel.id,
        spec_json=panel.spec_json,
        chapter_bindings_updated=True,
    )


@router.put("/{panel_id}/order")
async def update_panel_order(
    panel_id: str,
    new_order: int,
    db: Session = Depends(get_db)
):
    """更新分镜顺序"""
    panel = db.query(Panel).filter(Panel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    old_order = panel.order_index
    chapter_id = panel.chapter_id
    
    # 调整其他分镜的顺序
    if new_order > old_order:
        # 向后移动
        db.query(Panel).filter(
            Panel.chapter_id == chapter_id,
            Panel.order_index > old_order,
            Panel.order_index <= new_order
        ).update({Panel.order_index: Panel.order_index - 1})
    else:
        # 向前移动
        db.query(Panel).filter(
            Panel.chapter_id == chapter_id,
            Panel.order_index >= new_order,
            Panel.order_index < old_order
        ).update({Panel.order_index: Panel.order_index + 1})
    
    panel.order_index = new_order
    
    # 同步更新 chapter layout
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if chapter and chapter.layout_json:
        layout = chapter.layout_json
        if "panels" in layout:
            # 重新排序 layout 中的 panels
            layout["panels"] = sorted(layout["panels"], key=lambda x: x.get("order", 0))
            chapter.layout_json = layout
    
    db.commit()
    
    return {"message": "Panel order updated", "panel_id": panel_id, "new_order": new_order}


@router.delete("/{panel_id}")
async def delete_panel(
    panel_id: str,
    db: Session = Depends(get_db)
):
    """删除分镜"""
    panel = db.query(Panel).filter(Panel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    chapter_id = panel.chapter_id
    deleted_order = panel.order_index
    
    # 删除分镜
    db.delete(panel)
    
    # 调整后续分镜的顺序
    db.query(Panel).filter(
        Panel.chapter_id == chapter_id,
        Panel.order_index > deleted_order
    ).update({Panel.order_index: Panel.order_index - 1})
    
    # 从 chapter layout 中移除
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if chapter and chapter.layout_json:
        layout = chapter.layout_json
        if "panels" in layout:
            layout["panels"] = [p for p in layout["panels"] if p.get("panel_id") != panel_id]
            chapter.layout_json = layout
    
    db.commit()
    
    return {"message": "Panel deleted", "id": panel_id}


@router.post("/batch")
async def batch_create_panels(
    chapter_id: str,
    count: int = 1,
    db: Session = Depends(get_db)
):
    """批量创建分镜"""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    if count < 1 or count > 50:
        raise HTTPException(status_code=400, detail="Count must be between 1 and 50")
    
    import uuid
    
    current_max = db.query(Panel).filter(Panel.chapter_id == chapter_id).count()
    created_panels = []
    
    layout = chapter.layout_json or {"panels": []}
    if "panels" not in layout:
        layout["panels"] = []
    
    for i in range(count):
        panel_id = str(uuid.uuid4())
        order = current_max + i
        
        default_spec = PanelSpec(panel_id=panel_id)
        
        panel = Panel(
            id=panel_id,
            chapter_id=chapter_id,
            order_index=order,
            spec_json=default_spec.model_dump()
        )
        db.add(panel)
        created_panels.append(panel_id)
        
        layout["panels"].append({
            "panel_id": panel_id,
            "weight": "normal",
            "height_ratio": 1.0,
            "order": order
        })
    
    chapter.layout_json = layout
    db.commit()
    
    return {
        "message": f"Created {count} panels",
        "panel_ids": created_panels
    }


class PanelAnalyzeRequest(BaseModel):
    chapter_id: str
    text: str


@router.post("/analyze")
async def analyze_panel_content(
    request: PanelAnalyzeRequest,
    db: Session = Depends(get_db)
):
    """
    智能分析分镜内容
    - 匹配项目中的角色和场景
    - 推断镜头参数
    """
    chapter = db.query(Chapter).filter(Chapter.id == request.chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
        
    project_id = chapter.project_id
    
    # 获取项目资产
    from app.models.asset import Asset
    
    characters = db.query(Asset).filter(
        Asset.project_id == project_id,
        Asset.type == "character",
        Asset.status == "active"
    ).all()
    
    scenes = db.query(Asset).filter(
        Asset.project_id == project_id,
        Asset.type == "scene",
        Asset.status == "active"
    ).all()
    
    char_info = [{"id": c.id, "name": c.name} for c in characters]
    scene_info = [{"id": s.id, "name": s.name} for s in scenes]
    
    # 构建 LLM 请求
    from app.services.brain.standard_llm import StandardLLMService
    llm = StandardLLMService()
    
    prompt = f"""
    Analyze the following storyboard panel description and match it with available assets.
    
    Description: "{request.text}"
    
    Available Characters:
    {json.dumps(char_info, ensure_ascii=False)}
    
    Available Scenes:
    {json.dumps(scene_info, ensure_ascii=False)}
    
    Tasks:
    1. Identify which characters appear in the description. Return a list of their IDs.
    2. Identify the scene location. Return the best matching scene ID, or null if none matches well.
    3. Infer visual attributes: shot_type, camera_move, time_of_day, mood.
    
    Return JSON format:
    {{
        "character_ids": ["id1", "id2"],
        "scene_id": "id_or_null",
        "shot_type": "medium/close_up/etc",
        "camera_move": "static/pan/etc",
        "time_of_day": "day/night/etc",
        "mood": "happy/tense/etc"
    }}
    """
    
    import json
    try:
        result = await llm._chat_completion(
            messages=[{"role": "user", "content": prompt}],
            response_format="json"
        )
        data = json.loads(result)
        return {
            "success": True,
            "data": data
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
