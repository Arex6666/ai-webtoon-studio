"""
Script Pipeline API - 剧本流水线 API 路由

提供 3 阶段 LLM 流水线的 HTTP API 接口
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging

from app.core.database import get_db
from app.models.chapter import Chapter
from app.models.asset import Asset
from app.services.script_pipeline import (
    ScriptPipelineService, 
    create_pipeline,
    ParseResult,
    PlanResult,
    BindResult
)
from app.schemas.script_ir import ScriptIR
from app.schemas.director_profile import (
    DirectorProfile, 
    get_default_director,
    get_romance_director,
    get_thriller_director,
    get_contemplative_director
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/script-pipeline", tags=["script-pipeline"])


# ============ Request/Response Models ============

class ParseRequest(BaseModel):
    """Parse 请求"""
    script_text: str = Field(..., min_length=10, description="剧本文本")
    extract_props: bool = Field(default=False, description="是否同时提取物品和服装")
    project_id: Optional[str] = Field(default=None, description="项目ID（extract_props=true时必填）")
    chapter_id: Optional[str] = Field(default=None, description="章节ID（可选）")


class PlanRequest(BaseModel):
    """Plan 请求"""
    script_ir: Dict[str, Any] = Field(..., description="ScriptIR JSON")
    director_preset: Optional[str] = Field(
        default="default",
        description="导演预设: default/romance/thriller/contemplative"
    )
    custom_director: Optional[Dict[str, Any]] = Field(
        default=None,
        description="自定义导演配置"
    )


class FullPipelineRequest(BaseModel):
    """完整流水线请求"""
    chapter_id: str = Field(..., description="章节 ID")
    director_preset: Optional[str] = "default"
    save_draft: bool = Field(default=True, description="是否保存为 Draft")


class PipelineStatusResponse(BaseModel):
    """流水线状态响应"""
    stage: str  # parse/plan/bind/complete/failed
    progress: float  # 0-100
    parse_result: Optional[Dict] = None
    plan_result: Optional[Dict] = None
    bind_result: Optional[Dict] = None
    error: Optional[str] = None


# ============ Routes ============

@router.post("/parse")
async def run_parse(
    request: ParseRequest,
    db: Session = Depends(get_db)
):
    """
    Task A: Parse
    
    将剧本文本解析为 ScriptIR
    可选：同时提取物品和服装信息
    """
    pipeline = create_pipeline()
    result = await pipeline.task_parse(request.script_text)
    
    if not result.success:
        raise HTTPException(status_code=400, detail={
            "errors": result.errors,
            "message": "剧本解析失败"
        })
    
    # 物品提取（可选）
    props_extraction = None
    if request.extract_props:
        if not request.project_id:
            raise HTTPException(
                status_code=400, 
                detail="extract_props=true 时必须提供 project_id"
            )
        from app.services.prop_extractor import PropExtractorService
        extractor = PropExtractorService(
            db=db,
            project_id=request.project_id,
            chapter_id=request.chapter_id
        )
        props_extraction = await extractor.extract_and_create_from_script(request.script_text)
    
    return {
        "success": True,
        "script_ir": result.script_ir.model_dump() if result.script_ir else None,
        "stats": {
            "characters": result.character_count,
            "scenes": result.scene_count,
            "beats": result.beat_count
        },
        "warnings": result.warnings,
        "props_extraction": props_extraction
    }


@router.post("/plan")
async def run_plan(
    request: PlanRequest,
    db: Session = Depends(get_db)
):
    """
    Task B: Plan
    
    将 ScriptIR 转换为 StoryboardPlan
    """
    # 获取导演配置
    director = _get_director(request.director_preset, request.custom_director)
    
    # 构建 ScriptIR
    try:
        script_ir = ScriptIR(**request.script_ir)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"ScriptIR 格式错误: {e}")
    
    pipeline = create_pipeline()
    result = await pipeline.task_plan(script_ir, director)
    
    if not result.success:
        raise HTTPException(status_code=400, detail={
            "errors": result.errors,
            "message": "分镜计划生成失败"
        })
    
    return {
        "success": True,
        "plan": result.plan.model_dump() if result.plan else None,
        "validation_score": result.plan.validation_score if result.plan else 0,
        "warnings": result.warnings
    }


@router.post("/bind")
async def run_bind(
    chapter_id: str,
    plan: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Task C: Bind
    
    资产绑定建议
    """
    # 获取章节和资产
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    
    # 获取资产库
    assets_index = _get_assets_index(db, chapter.project_id)
    
    # 构建 Plan（简化版）
    from app.services.script_pipeline import StoryboardPlan, PanelPlanSpec
    panels = [PanelPlanSpec(**p) for p in plan.get("panels", [])]
    storyboard_plan = StoryboardPlan(panels=panels)
    
    pipeline = create_pipeline()
    result = await pipeline.task_bind(storyboard_plan, assets_index)
    
    if not result.success:
        raise HTTPException(status_code=400, detail={
            "errors": result.errors,
            "message": "资产绑定失败"
        })
    
    return {
        "success": True,
        "proposal": result.proposal.model_dump() if result.proposal else None
    }


@router.post("/full/{chapter_id}")
async def run_full_pipeline(
    chapter_id: str,
    request: FullPipelineRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    运行完整流水线
    
    Parse → Plan → Bind → (可选) 保存 Draft
    """
    # 获取章节
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")
    
    script_text = chapter.script_raw
    if not script_text:
        raise HTTPException(status_code=400, detail="章节没有剧本内容")
    
    # 获取导演和资产
    director = _get_director(request.director_preset)
    assets_index = _get_assets_index(db, chapter.project_id)
    
    # 运行流水线
    pipeline = create_pipeline()
    parse_result, plan_result, bind_result = await pipeline.run_full_pipeline(
        script_text=script_text,
        director=director,
        assets_index=assets_index,
        chapter_id=chapter_id
    )
    
    # 检查结果
    if not parse_result.success:
        raise HTTPException(status_code=400, detail={
            "stage": "parse",
            "errors": parse_result.errors
        })
    
    if not plan_result.success:
        raise HTTPException(status_code=400, detail={
            "stage": "plan",
            "errors": plan_result.errors
        })
    
    # 保存为 Draft
    draft_id = None
    if request.save_draft and plan_result.plan:
        draft_id = await _save_as_draft(
            db, chapter_id, 
            parse_result.script_ir,
            plan_result.plan,
            bind_result.proposal
        )
    
    return {
        "success": True,
        "parse": {
            "characters": parse_result.character_count,
            "scenes": parse_result.scene_count,
            "beats": parse_result.beat_count,
            "warnings": parse_result.warnings
        },
        "plan": {
            "panels": len(plan_result.plan.panels) if plan_result.plan else 0,
            "total_duration": plan_result.plan.total_duration if plan_result.plan else 0,
            "validation_score": plan_result.plan.validation_score if plan_result.plan else 0,
            "warnings": plan_result.warnings
        },
        "bind": {
            "all_resolved": bind_result.proposal.all_resolved if bind_result.proposal else False,
            "pending_count": bind_result.proposal.pending_count if bind_result.proposal else 0,
            "missing_assets": bind_result.proposal.missing_assets if bind_result.proposal else []
        },
        "draft_id": draft_id
    }


@router.get("/directors")
async def list_directors():
    """获取可用的导演预设"""
    return {
        "presets": [
            {
                "id": "default",
                "name": "默认导演",
                "description": "韩式条漫风格，温柔细腻"
            },
            {
                "id": "romance",
                "name": "浪漫韩剧导演",
                "description": "唯美浪漫，大量特写和慢镜头"
            },
            {
                "id": "thriller",
                "name": "悬疑导演",
                "description": "紧张压迫，快速剪辑"
            },
            {
                "id": "contemplative",
                "name": "文艺导演",
                "description": "大量留白，长镜头，诗意"
            }
        ]
    }


# ============ Helper Functions ============

def _get_director(
    preset: Optional[str] = "default",
    custom: Optional[Dict] = None
) -> DirectorProfile:
    """获取导演配置"""
    if custom:
        return DirectorProfile(**custom)
    
    presets = {
        "default": get_default_director,
        "romance": get_romance_director,
        "thriller": get_thriller_director,
        "contemplative": get_contemplative_director,
    }
    
    return presets.get(preset, get_default_director)()


def _get_assets_index(db: Session, project_id: str) -> Dict[str, List[Dict]]:
    """获取资产库索引"""
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
    
    # 获取 PropAssets
    from app.models.prop_asset import PropAsset
    props = db.query(PropAsset).filter(
        PropAsset.project_id == project_id,
        PropAsset.status.in_(["active", "pending"])
    ).all()
    
    return {
        "characters": [{"id": a.id, "name": a.name} for a in characters],
        "scenes": [{"id": a.id, "name": a.name} for a in scenes],
        "props": [{"id": p.id, "name": p.canonical_name, "category": p.category} for p in props]
    }


async def _save_as_draft(
    db: Session,
    chapter_id: str,
    script_ir: ScriptIR,
    plan: Any,
    bind_proposal: Any
) -> str:
    """保存为 StoryboardDraft"""
    from app.models.storyboard_draft import StoryboardDraft
    import uuid
    
    draft_id = str(uuid.uuid4())
    
    # 转换 panels
    panels_json = []
    for p in plan.panels:
        panels_json.append({
            "panel_id": p.panel_id,
            "order": p.panel_index,
            "title": f"分镜 {p.panel_index + 1}",
            "description": p.actions,
            "action_description": p.actions,
            "shot": {
                "shotType": p.shot_type,
                "cameraMove": p.camera_move,
                "durationSec": p.duration_sec,
                "lensHint": p.lens_hint
            },
            "camera": {
                "angle": p.camera_angle,
                "move": p.camera_move
            },
            "scene": {
                "location": p.location,
                "timeOfDay": p.time_of_day,
                "weather": p.weather,
                "mood": p.mood,
                "scene_id": p.scene_id
            },
            "characters": [{"character_id": c, "name": c} for c in p.cast],
            "dialogue": [{"text": p.dialogue}] if p.dialogue else [],
            "composition_notes": p.composition_notes,
            "continuity_notes": p.continuity_notes,
            "source_beat_quote": p.source_beat_quote
        })
    
    # 创建 Draft
    draft = StoryboardDraft(
        id=draft_id,
        chapter_id=chapter_id,
        status="pending",
        panels_json=panels_json,
        characters_json=[c.model_dump() for c in script_ir.characters],
        scenes_json=[s.model_dump() for s in script_ir.scenes],
    )
    
    db.add(draft)
    
    # 更新 chapter 的 pending_draft_id
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if chapter:
        layout = chapter.layout_json or {}
        layout["pending_draft_id"] = draft_id
        chapter.layout_json = layout
    
    db.commit()
    
    return draft_id
