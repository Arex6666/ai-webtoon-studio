"""
章节管理路由
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.models.chapter import Chapter
from app.models.project import Project
from app.models.revision import Revision
from app.schemas.chapter_layout import ChapterLayout, PanelSlot, PanelWeight, ReadingFlow

router = APIRouter()


# Request/Response Models
class ChapterCreate(BaseModel):
    project_id: str
    title: str
    description: Optional[str] = None


class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    order_index: Optional[int] = None


class ChapterResponse(BaseModel):
    id: str
    project_id: str
    title: str
    description: Optional[str]
    order_index: int
    layout_json: Dict[str, Any]
    export_status: str
    exported_url: Optional[str]
    created_at: datetime
    updated_at: datetime
    panel_count: int = 0

    class Config:
        from_attributes = True


class ChapterListResponse(BaseModel):
    items: List[ChapterResponse]
    total: int


# Routes
@router.get("/project/{project_id}", response_model=ChapterListResponse)
async def list_chapters(
    project_id: str,
    db: Session = Depends(get_db)
):
    """获取项目的所有章节"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    chapters = db.query(Chapter).filter(
        Chapter.project_id == project_id
    ).order_by(Chapter.order_index).all()
    
    items = []
    for c in chapters:
        items.append(ChapterResponse(
            id=c.id,
            project_id=c.project_id,
            title=c.title,
            description=c.description,
            order_index=c.order_index,
            layout_json=c.layout_json or {},
            export_status=c.export_status,
            exported_url=c.exported_url,
            created_at=c.created_at,
            updated_at=c.updated_at,
            panel_count=len(c.panels)
        ))
    
    return ChapterListResponse(items=items, total=len(items))


@router.post("", response_model=ChapterResponse)
async def create_chapter(
    request: ChapterCreate,
    db: Session = Depends(get_db)
):
    """创建新章节"""
    project = db.query(Project).filter(Project.id == request.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # 获取当前最大 order_index
    max_order = db.query(Chapter).filter(
        Chapter.project_id == request.project_id
    ).count()
    
    # 创建默认 layout
    import uuid
    chapter_id = str(uuid.uuid4())
    default_layout = ChapterLayout(
        chapter_id=chapter_id,
        title=request.title,
        reading_flow=ReadingFlow.VERTICAL,
        panels=[]
    )
    
    chapter = Chapter(
        id=chapter_id,
        project_id=request.project_id,
        title=request.title,
        description=request.description,
        order_index=max_order,
        layout_json=default_layout.model_dump()
    )
    db.add(chapter)
    db.commit()
    db.refresh(chapter)
    
    return ChapterResponse(
        id=chapter.id,
        project_id=chapter.project_id,
        title=chapter.title,
        description=chapter.description,
        order_index=chapter.order_index,
        layout_json=chapter.layout_json,
        export_status=chapter.export_status,
        exported_url=chapter.exported_url,
        created_at=chapter.created_at,
        updated_at=chapter.updated_at,
        panel_count=0
    )


@router.get("/{chapter_id}", response_model=ChapterResponse)
async def get_chapter(
    chapter_id: str,
    db: Session = Depends(get_db)
):
    """获取章节详情"""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    return ChapterResponse(
        id=chapter.id,
        project_id=chapter.project_id,
        title=chapter.title,
        description=chapter.description,
        order_index=chapter.order_index,
        layout_json=chapter.layout_json or {},
        export_status=chapter.export_status,
        exported_url=chapter.exported_url,
        created_at=chapter.created_at,
        updated_at=chapter.updated_at,
        panel_count=len(chapter.panels)
    )


@router.put("/{chapter_id}", response_model=ChapterResponse)
async def update_chapter(
    chapter_id: str,
    request: ChapterUpdate,
    db: Session = Depends(get_db)
):
    """更新章节基本信息"""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    if request.title is not None:
        chapter.title = request.title
        # 同步更新 layout_json 中的 title
        if chapter.layout_json:
            chapter.layout_json["title"] = request.title
    if request.description is not None:
        chapter.description = request.description
    if request.order_index is not None:
        chapter.order_index = request.order_index
    
    db.commit()
    db.refresh(chapter)
    
    return ChapterResponse(
        id=chapter.id,
        project_id=chapter.project_id,
        title=chapter.title,
        description=chapter.description,
        order_index=chapter.order_index,
        layout_json=chapter.layout_json or {},
        export_status=chapter.export_status,
        exported_url=chapter.exported_url,
        created_at=chapter.created_at,
        updated_at=chapter.updated_at,
        panel_count=len(chapter.panels)
    )


@router.put("/{chapter_id}/layout")
async def update_chapter_layout(
    chapter_id: str,
    layout: ChapterLayout,
    db: Session = Depends(get_db)
):
    """
    更新章节布局 JSON（Single Source of Truth）
    会自动创建版本记录
    """
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # 创建版本记录
    revision_count = db.query(Revision).filter(
        Revision.chapter_id == chapter_id
    ).count()
    
    revision = Revision(
        chapter_id=chapter_id,
        revision_number=revision_count + 1,
        change_type="layout",
        snapshot_json=chapter.layout_json or {},
        description="Layout updated"
    )
    db.add(revision)
    
    # 更新布局
    chapter.layout_json = layout.model_dump()
    chapter.title = layout.title  # 同步标题
    
    db.commit()
    
    return {
        "message": "Layout updated",
        "chapter_id": chapter_id,
        "revision": revision_count + 1
    }


@router.delete("/{chapter_id}")
async def delete_chapter(
    chapter_id: str,
    db: Session = Depends(get_db)
):
    """删除章节"""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    db.delete(chapter)
    db.commit()
    
    return {"message": "Chapter deleted", "id": chapter_id}


@router.get("/{chapter_id}/revisions")
async def list_revisions(
    chapter_id: str,
    db: Session = Depends(get_db)
):
    """获取章节的版本历史"""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    revisions = db.query(Revision).filter(
        Revision.chapter_id == chapter_id
    ).order_by(Revision.revision_number.desc()).all()
    
    return {
        "chapter_id": chapter_id,
        "revisions": [
            {
                "id": r.id,
                "revision_number": r.revision_number,
                "change_type": r.change_type,
                "description": r.description,
                "created_at": r.created_at
            }
            for r in revisions
        ]
    }


@router.post("/{chapter_id}/revisions/{revision_id}/rollback")
async def rollback_to_revision(
    chapter_id: str,
    revision_id: str,
    db: Session = Depends(get_db)
):
    """回滚到指定版本"""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    revision = db.query(Revision).filter(
        Revision.id == revision_id,
        Revision.chapter_id == chapter_id
    ).first()
    if not revision:
        raise HTTPException(status_code=404, detail="Revision not found")
    
    # 先保存当前版本
    revision_count = db.query(Revision).filter(
        Revision.chapter_id == chapter_id
    ).count()
    
    new_revision = Revision(
        chapter_id=chapter_id,
        revision_number=revision_count + 1,
        change_type="rollback",
        snapshot_json=chapter.layout_json or {},
        description=f"Rollback to revision {revision.revision_number}"
    )
    db.add(new_revision)
    
    # 恢复到指定版本
    chapter.layout_json = revision.snapshot_json
    
    db.commit()
    
    return {
        "message": f"Rolled back to revision {revision.revision_number}",
        "new_revision": revision_count + 1
    }


# ===== Studio 聚合接口 =====

@router.get("/{chapter_id}/studio")
async def get_chapter_studio(
    chapter_id: str,
    db: Session = Depends(get_db)
):
    """
    获取章节工作台所需的全部数据（聚合接口）
    包含：章节信息、布局、分镜列表、资产、任务状态、警告汇总
    
    这是前端 Studio 页面的主要数据源
    """
    from app.models.panel import Panel
    from app.models.asset import Asset
    from app.models.render_job import RenderJob
    
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # 获取分镜列表（按顺序）
    panels = db.query(Panel).filter(
        Panel.chapter_id == chapter_id
    ).order_by(Panel.order_index).all()
    
    # 获取项目资产
    characters = db.query(Asset).filter(
        Asset.project_id == chapter.project_id,
        Asset.type == "character",
        Asset.status == "active"
    ).all()
    
    scenes = db.query(Asset).filter(
        Asset.project_id == chapter.project_id,
        Asset.type == "scene",
        Asset.status == "active"
    ).all()
    
    styles = db.query(Asset).filter(
        Asset.project_id == chapter.project_id,
        Asset.type == "style",
        Asset.status == "active"
    ).all()
    
    bubble_styles = db.query(Asset).filter(
        Asset.project_id == chapter.project_id,
        Asset.type == "bubble",
        Asset.status == "active"
    ).all()
    
    # 获取活跃任务
    active_jobs = db.query(RenderJob).filter(
        RenderJob.chapter_id == chapter_id,
        RenderJob.status.in_(["pending", "queued", "processing"])
    ).all()
    
    # 收集警告
    warnings = []
    for panel in panels:
        spec = panel.spec_json or {}
        panel_warnings = spec.get("warnings", [])
        for w in panel_warnings:
            warnings.append({
                "type": w.get("code", "unknown"),
                "severity": w.get("severity", "warning"),
                "message": w.get("message", ""),
                "panel_id": panel.id,
                "asset_id": None,
                "auto_fixable": w.get("auto_fixable", False)
            })
        
        # 检查分镜状态警告
        if panel.render_status == "needs_fix":
            warnings.append({
                "type": "render_failed",
                "severity": "error",
                "message": f"分镜 #{panel.order_index + 1} 渲染失败或需要修复",
                "panel_id": panel.id,
                "asset_id": None,
                "auto_fixable": True
            })
    
    # 检查资产警告（缺少 FaceID 等）
    for char in characters:
        data = char.data_json or {}
        if not data.get("face_embedding_path"):
            warnings.append({
                "type": "missing_face_embedding",
                "severity": "warning",
                "message": f"角色 '{char.name}' 缺少 FaceID，可能导致一致性问题",
                "panel_id": None,
                "asset_id": char.id,
                "auto_fixable": False
            })
    
    for scene in scenes:
        data = scene.data_json or {}
        if not data.get("anchor_image_path"):
            warnings.append({
                "type": "missing_scene_anchor",
                "severity": "info",
                "message": f"场景 '{scene.name}' 缺少空镜锚点，建议添加以保持一致性",
                "panel_id": None,
                "asset_id": scene.id,
                "auto_fixable": False
            })
    
    # 统计信息
    total_panels = len(panels)
    rendered_panels = sum(1 for p in panels if p.render_status == "rendered")
    failed_panels = sum(1 for p in panels if p.render_status in ["needs_fix", "failed"])
    # 安全处理 qa_score - 可能为 NULL
    avg_qa_score = sum((p.qa_score or 0) for p in panels) / total_panels if total_panels > 0 else 0.0
    
    # 构建分镜摘要
    panel_summaries = []
    panels_by_id = {}
    for p in panels:
        spec = p.spec_json or {}
        dialogue = spec.get("dialogue", [])
        # 安全处理 dialogue - 可能是字符串或字典
        if dialogue:
            first_dialogue = dialogue[0]
            if isinstance(first_dialogue, dict):
                dialogue_preview = first_dialogue.get("text", "")[:50]
            elif isinstance(first_dialogue, str):
                dialogue_preview = first_dialogue[:50]
            else:
                dialogue_preview = None
        else:
            dialogue_preview = None

        # 安全处理 characters - 可能是字符串或字典列表
        characters_in_panel = []
        for c in spec.get("characters", []):
            if isinstance(c, dict):
                characters_in_panel.append(c.get("character_id") or c.get("name"))
            elif isinstance(c, str):
                characters_in_panel.append(c)

        scene_id = spec.get("scene", {}).get("scene_id")
        
        summary = {
            "id": p.id,
            "order_index": p.order_index,
            "title": p.title,
            "summary": p.summary or spec.get("action_description", "")[:100],
            "preview_url": p.preview_url,
            "render_status": p.render_status,
            "typeset_status": p.typeset_status,
            "qa_score": p.qa_score,
            "warning_count": p.warning_count,
            "error_count": p.error_count,
            "render_tier": p.render_tier,
            "dialogue_preview": dialogue_preview,
            "character_ids": characters_in_panel,
            "scene_id": scene_id,
            # 结构化字段 (从 spec_json 提取)
            "shot_type": spec.get("shot", {}).get("shotType") or spec.get("shot_type"),
            "camera_move": spec.get("shot", {}).get("cameraMove") or spec.get("camera", {}).get("move"),
            "camera_angle": spec.get("camera", {}).get("angle") or spec.get("camera_angle"),
            "duration_sec": spec.get("shot", {}).get("durationSec") or spec.get("suggested_duration"),
            "location": spec.get("scene", {}).get("location") or spec.get("scene_description"),
            "time_of_day": spec.get("scene", {}).get("timeOfDay") or spec.get("time_of_day"),
            "mood": spec.get("scene", {}).get("mood"),
            "emotion": spec.get("emotion"),
            "action_description": spec.get("action_description") or spec.get("description", "")
        }
        panel_summaries.append(summary)
        
        panels_by_id[p.id] = {
            "id": p.id,
            "chapter_id": p.chapter_id,
            "order_index": p.order_index,
            "title": p.title,
            "summary": p.summary,
            "spec_json": p.spec_json or {},
            "render_status": p.render_status,
            "active_layer_pack_id": p.active_layer_pack_id,
            "preview_url": p.preview_url,
            "typeset_status": p.typeset_status,
            "typeset_image_url": p.typeset_image_url,
            "qa_score": p.qa_score,
            "needs_manual_fix": p.needs_manual_fix,
            "warning_count": p.warning_count,
            "error_count": p.error_count,
            "render_tier": p.render_tier,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None
        }
    
    # 构建角色摘要
    character_summaries = []
    for c in characters:
        data = c.data_json or {}
        embedding_status = "ready" if data.get("face_embedding_path") else "none"
        if data.get("embedding_status") == "pending":
            embedding_status = "pending"
        
        character_summaries.append({
            "id": c.id,
            "name": c.name,
            "thumbnail_url": c.thumbnail_url,
            "face_embedding_status": embedding_status,
            "reference_count": len(data.get("reference_images", []))
        })
    
    # 构建场景摘要
    scene_summaries = []
    for s in scenes:
        data = s.data_json or {}
        anchor_status = "ready" if data.get("anchor_image_path") else "none"
        if data.get("anchor_status") == "pending":
            anchor_status = "pending"
        
        scene_summaries.append({
            "id": s.id,
            "name": s.name,
            "thumbnail_url": s.thumbnail_url,
            "anchor_status": anchor_status,
            "control_maps_ready": bool(data.get("control_maps", {}))
        })
    
    # 构建任务摘要
    job_summaries = [
        {
            "id": j.id,
            "panel_id": j.panel_id,
            "job_type": j.job_type,
            "status": j.status,
            "progress": j.progress,
            "current_step": j.current_step
        }
        for j in active_jobs
    ]
    
    # 资产响应
    def asset_to_dict(a):
        return {
            "id": a.id,
            "project_id": a.project_id,
            "name": a.name,
            "type": a.type,
            "description": a.description,
            "thumbnail_url": a.thumbnail_url,
            "data_json": a.data_json or {},
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None
        }
    
    # S5-04: 获取 PropAssets
    from app.models.prop_asset import PropAsset
    props = db.query(PropAsset).filter(
        PropAsset.project_id == chapter.project_id,
        PropAsset.status.in_(["active", "pending"])
    ).all()
    
    prop_summaries = []
    for p in props:
        prop_summaries.append({
            "id": p.id,
            "canonical_name": p.canonical_name,
            "category": p.category,
            "visual_brief": p.visual_brief,
            "ref_image_paths": p.ref_image_paths or [],
            "status": p.status
        })
    
    return {
        "chapter": {
            "id": chapter.id,
            "project_id": chapter.project_id,
            "title": chapter.title,
            "description": chapter.description,
            "order_index": chapter.order_index,
            "script_raw": chapter.script_raw or "",
            "layout_json": chapter.layout_json or {},
            "export_status": chapter.export_status,
            "exported_url": chapter.exported_url,
            "created_at": chapter.created_at.isoformat() if chapter.created_at else None,
            "updated_at": chapter.updated_at.isoformat() if chapter.updated_at else None,
            "panel_count": total_panels
        },
        "layout": chapter.layout_json or {},
        "panels": panel_summaries,
        "panels_by_id": panels_by_id,
        # Legacy fields (keep for backwards compatibility)
        "characters": character_summaries,
        "scenes": scene_summaries,
        "styles": [asset_to_dict(s) for s in styles],
        "bubble_styles": [asset_to_dict(b) for b in bubble_styles],
        # S5-04: Wrapped assets object for frontend store
        "assets": {
            "characters": character_summaries,
            "scenes": scene_summaries,
            "styles": [asset_to_dict(s) for s in styles],
            "props": prop_summaries
        },
        "active_jobs": job_summaries,
        "warnings": warnings,
        "stats": {
            "total_panels": total_panels,
            "rendered_panels": rendered_panels,
            "failed_panels": failed_panels,
            "pending_jobs": len(active_jobs),
            "avg_qa_score": round(avg_qa_score, 2)
        }
    }


# ===== S3-06: Assets Lock API =====

@router.get("/{chapter_id}/assets-lock")
async def get_assets_lock(
    chapter_id: str,
    db: Session = Depends(get_db)
):
    """
    获取章节资产锁定信息 (S3-06)
    
    自动同步 Asset 表的最新状态到 AssetsLock (S5-02)
    """
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    assets_lock = chapter.assets_lock_json or {}
    
    # S5-02 Sync Logic: Check Asset table for updates
    from app.models.asset import Asset
    characters = assets_lock.get("characters", {})
    changed = False
    
    if characters:
        # Get all asset IDs in the lock
        asset_ids = list(characters.keys())
        # Query DB
        db_assets = db.query(Asset).filter(Asset.id.in_(asset_ids)).all()
        db_assets_map = {a.id: a for a in db_assets}
        
        for asset_id, char_lock in characters.items():
            asset = db_assets_map.get(asset_id)
            if not asset:
                continue
            
            # 1. Sync Reference Image Status (S5-01)
            # data_json or columns? Asset model has columns for reference_image_*
            if asset.reference_image_status != char_lock.get("reference_image_status"):
                char_lock["reference_image_status"] = asset.reference_image_status
                char_lock["reference_image_path"] = asset.reference_image_path
                changed = True
                
            # 2. Sync FaceID Status (S5-02)
            # Check data_json for face_embedding_path
            data = asset.data_json or {}
            embedding_path = data.get("face_embedding_path")
            
            if embedding_path and embedding_path != char_lock.get("face_embedding_path"):
                char_lock["face_embedding_path"] = embedding_path
                # If faceID is ready, update binding status to exact?
                # User rule: AssetsLock.status = "exact"
                char_lock["binding_status"] = "exact"
                char_lock["face_embedding"] = {
                    "status": "ready",
                    "embedding_path": embedding_path
                }
                changed = True
            elif not embedding_path and char_lock.get("binding_status") == "exact":
                # Revert if missing?
                pass

    if changed:
        chapter.assets_lock_json = assets_lock
        db.commit()

    # S5-SC: Sync Scene status from Asset table
    scenes = assets_lock.get("scenes", {})
    if scenes:
        scene_ids = list(scenes.keys())
        db_scene_assets = db.query(Asset).filter(Asset.id.in_(scene_ids)).all()
        db_scene_map = {a.id: a for a in db_scene_assets}
        
        for scene_id, scene_lock in scenes.items():
            asset = db_scene_map.get(scene_id)
            if not asset:
                continue
            
            data = asset.data_json or {}
            
            # Sync anchor status
            if data.get("anchor_status") and data.get("anchor_status") != scene_lock.get("anchor_status"):
                scene_lock["anchor_status"] = data.get("anchor_status")
                scene_lock["anchor_image_path"] = data.get("anchor_image_path")
                changed = True
                
            # Sync control maps
            if data.get("control_maps") and data.get("control_maps") != scene_lock.get("control_maps"):
                scene_lock["control_maps"] = data.get("control_maps")
                scene_lock["control_map_status"] = data.get("control_map_status", "none")
                scene_lock["depth_map_path"] = data.get("control_maps", {}).get("depth")
                changed = True

    if changed:
        chapter.assets_lock_json = assets_lock
        db.commit()

    # 计算统计
    characters = assets_lock.get("characters", {})  # Refresh from updated dict
    scenes = assets_lock.get("scenes", {})
    styles = assets_lock.get("styles", {})
    
    # Recalculate pending count
    # Characters: pending if binding_status != exact
    pending_chars = sum(1 for c in characters.values() if c.get("binding_status") != "exact")
    # Scenes: pending if anchor_status != ready
    pending_scenes = sum(1 for s in scenes.values() if s.get("anchor_status") != "ready")
    pending_count = pending_chars + pending_scenes
    
    return {
        "chapter_id": chapter.id,
        "storyboard_version": assets_lock.get("storyboard_version", 0),
        "locked_at": assets_lock.get("locked_at"),
        "characters": characters,
        "scenes": scenes,
        "styles": styles,
        "stats": {
            "locked_characters": len(characters),
            "locked_scenes": len(scenes),
            "locked_styles": len(styles),
            "pending_count": pending_count,
            "pending_characters": pending_chars,
            "pending_scenes": pending_scenes
        },
        "can_render": pending_count == 0
    }


# ===== 剧本保存接口 (S2-01) =====

class ScriptSaveRequest(BaseModel):
    script: str


class ScriptSaveResponse(BaseModel):
    chapter_id: str
    script: str
    script_version: str
    word_count: int


@router.put("/{chapter_id}/script/save", response_model=ScriptSaveResponse)
async def save_script(
    chapter_id: str,
    request: ScriptSaveRequest,
    db: Session = Depends(get_db)
):
    """
    保存剧本（纯保存，不触发 AI 分镜）
    
    用于前端自动保存，debounce 后调用
    """
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # 保存剧本
    chapter.script_raw = request.script
    
    # S3-04: 递增 script 版本
    chapter.script_version = (chapter.script_version or 0) + 1
    
    # 同时更新 layout_json 中的 script 信息
    layout = chapter.layout_json or {}
    layout["script"] = {
        "text": request.script,
        "word_count": len(request.script),
        "updated_at": datetime.utcnow().isoformat(),
        "version": chapter.script_version
    }
    chapter.layout_json = layout
    
    db.commit()
    db.refresh(chapter)
    
    return ScriptSaveResponse(
        chapter_id=chapter_id,
        script=request.script,
        script_version=str(chapter.script_version),
        word_count=len(request.script)
    )


# ===== AI 分镜任务接口 (S2-02) =====

class CreateStoryboardRequest(BaseModel):
    provider: Optional[str] = "mock"
    target_panels: Optional[int] = None
    style_hint: Optional[str] = "korean_webtoon"
    auto_apply: Optional[bool] = True


class StoryboardResponse(BaseModel):
    """分镜生成响应"""
    job_id: str
    status: str
    message: str = "queued"


@router.post("/{chapter_id}/storyboard", response_model=StoryboardResponse)
async def create_storyboard(
    chapter_id: str,
    request: CreateStoryboardRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    创建 AI 分镜任务（异步）
    
    该 API 会立即返回 job_id，实际分镜在后台执行。
    进度通过 WebSocket 推送：storyboard_progress, storyboard_done, storyboard_error
    """
    from app.models.reqnder_job import RenderJob
    import uuid
    
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # 校验：剧本非空
    if not chapter.script_raw or not chapter.script_raw.strip():
        raise HTTPException(
            status_code=400, 
            detail="Script is empty. Please save a script first."
        )
    
    # 创建 Job 记录
    try:
        job_id = str(uuid.uuid4())
        job = RenderJob(
            id=job_id,
            chapter_id=chapter_id,
            panel_id=None,
            job_type="storyboard",
            engine=request.provider or "mock",
            status="queued",
            input_params={
                "script": chapter.script_raw,
                "style_hint": request.style_hint,
                "target_panels": request.target_panels,
                "provider": request.provider or "mock"
            }
        )
        db.add(job)
        db.commit()

        # 添加后台任务
        background_tasks.add_task(
           run_storyboard_task,
           job_id=job_id,
           chapter_id=chapter_id,
           script=chapter.script_raw,
           style_hint=request.style_hint or "korean_webtoon",
           provider=request.provider or "mock",
           auto_apply=request.auto_apply if request.auto_apply is not None else True,
        )
        
        return StoryboardResponse(job_id=job_id, status="queued", message="queued")

    except HTTPException as he:
        raise he
    except Exception as e:
        import traceback
        error_msg = f"Failed to create job: {str(e)}"
        print(traceback.format_exc())
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"message": error_msg, "trace": traceback.format_exc()})


async def run_storyboard_task(
    job_id: str,
    chapter_id: str,
    script: str,
    style_hint: str,
    provider: str,
    auto_apply: bool = True
):
    """
    后台执行 AI 分镜任务 (S3-02: 写入 Draft 而非直接写 panels)
    """
    from app.core.database import SessionLocal
    from app.services.brain.base import get_brain_service
    from app.models.render_job import RenderJob
    from app.models.storyboard_draft import StoryboardDraft
    import uuid
    import asyncio
    
    db = SessionLocal()
    
    try:
        # 更新 Job 状态
        job = db.query(RenderJob).filter(RenderJob.id == job_id).first()
        if job:
            job.status = "running"
            job.current_step = "validating"
            db.commit()
        
        # Stage 1: Validating (模拟进度)
        await asyncio.sleep(0.3)
        
        # Stage 2: Analyzing - 调用 LLM
        if job:
            job.current_step = "analyzing"
            job.progress = 20
            db.commit()
        
        brain = get_brain_service()
        result = await brain.parse_script(script, style_hint)

        if not result.panels:
            raise Exception("Storyboard generation produced 0 panels")
        
        # Stage 3: Planning
        if job:
            job.current_step = "planning"
            job.progress = 40
            db.commit()
        
        chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if not chapter:
            raise Exception("Chapter not found")
        
        # S3-02: 不再直接删除/创建 panels，而是构建 Draft
        # Stage 4: Generating Panel Specs (不写入 DB)
        character_ids = set()
        scene_ids = set()
        panels_json = []
        
        for i, panel_data in enumerate(result.panels):
            if job:
                job.current_step = f"generating_panel_{i+1}"
                job.progress = 40 + int(40 * (i / max(len(result.panels), 1)))
                db.commit()
            
            panel_id = str(uuid.uuid4())
            
            # 构建 PanelSpec
            spec = {
                "panel_id": panel_id,
                "order": i,
                "title": f"分镜 {i + 1}",
                "description": panel_data.action_description,
                "action_description": panel_data.action_description,
                "dialogue": [],
                "shot": {
                    "shotType": panel_data.shot_type.upper() if panel_data.shot_type else "MS",
                    "durationSec": panel_data.suggested_duration or 3.0,
                    "description": panel_data.action_description
                },
                "camera": {
                    "move": "static",
                    "angle": panel_data.camera_angle or "eye_level"
                },
                "scene": {
                    "location": panel_data.scene_description or panel_data.scene_ref or "未指定",
                    "timeOfDay": panel_data.time_of_day or "day",
                    "weather": panel_data.weather or "clear"
                },
                "characters": [],
                "render": {"status": "draft"},
                "warnings": []
            }
            
            # 添加对话
            if panel_data.dialogue:
                spec["dialogue"].append({
                    "id": f"dlg_{panel_id}_0",
                    "type": "speech",
                    "text": panel_data.dialogue,
                    "emotion_tag": panel_data.emotion or "neutral"
                })
            
            # 添加角色引用
            if panel_data.character_refs:
                spec["characters"] = [
                    {"character_id": ref, "name": ref, "importance": "primary"}
                    for ref in panel_data.character_refs
                ]
                character_ids.update(panel_data.character_refs)
            
            # 添加场景引用
            if panel_data.scene_ref:
                spec["scene"]["scene_id"] = panel_data.scene_ref
                scene_ids.add(panel_data.scene_ref)
            
            panels_json.append(spec)
        
        # Stage 5: Building Draft
        if job:
            job.current_step = "building_draft"
            job.progress = 85
            db.commit()
        
        # 构建角色和场景列表
        characters_json = [
            {"name": name, "appearances": 0}
            for name in (result.detected_characters or list(character_ids))
        ]
        
        # 使用 SceneResolver 去重场景
        from app.services.brain.scene_resolver import get_scene_resolver
        scene_resolver = get_scene_resolver()
        
        raw_scenes = [
            {"canonical_location": name, "anchor_hint": ""}
            for name in (result.detected_scenes or list(scene_ids))
        ]
        normalized_scenes = scene_resolver.normalize_locations(raw_scenes)
        
        scenes_json = [
            {
                "name": s["canonical_location"], 
                "appearances": 0,
                "sub_locations": s.get("sub_locations", []),
                "variants": s.get("variants", []),
                "merged_count": s.get("merged_from_count", 1)
            }
            for s in normalized_scenes
        ]
        
        # 计算每个角色/场景的出场次数
        for panel in panels_json:
            for char in panel.get("characters", []):
                char_name = char.get("name")
                for c in characters_json:
                    if c["name"] == char_name:
                        c["appearances"] += 1
                        break
            
            scene_name = panel.get("scene", {}).get("location")
            for s in scenes_json:
                if s["name"] == scene_name:
                    s["appearances"] += 1
                    break
        
        # 创建 StoryboardDraft
        draft_id = str(uuid.uuid4())
        draft = StoryboardDraft(
            id=draft_id,
            chapter_id=chapter_id,
            job_id=job_id,
            status="completed",
            version=1,
            panels_json=panels_json,
            characters_json=characters_json,
            scenes_json=scenes_json,
            script_snapshot=script,
            provider=provider,
            style_hint=style_hint,
            generated_panels_count=len(panels_json),
            generated_characters_count=len(characters_json),
            generated_scenes_count=len(scenes_json)
        )
        db.add(draft)
        
        # 更新章节状态（标记有待审核的 Draft）
        layout = chapter.layout_json or {}
        layout["pending_draft_id"] = draft_id
        layout["storyboard_job_id"] = job_id
        chapter.layout_json = layout
        
        # 完成 Job
        if job:
            job.status = "succeeded"
            job.current_step = "done"
            job.progress = 100
            job.output_data = {
                "draft_id": draft_id,
                "panels_count": len(panels_json),
                "characters_detected": [c["name"] for c in characters_json],
                "scenes_detected": [s["name"] for s in scenes_json]
            }
        
        db.commit()

        # 可选：自动应用 Draft，生成正式 panels，避免前端显示为 0 分镜
        if auto_apply:
            try:
                from app.api.routes.drafts import apply_draft_internal
                await apply_draft_internal(db, draft_id, create_missing_assets=True)
                # 清理 pending_draft_id（已应用）
                chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
                if chapter and chapter.layout_json:
                    layout = dict(chapter.layout_json)
                    layout.pop("pending_draft_id", None)
                    chapter.layout_json = layout
                    db.commit()
            except Exception as apply_err:
                raise Exception(f"Auto-apply draft failed: {apply_err}") from apply_err
        
        # TODO: 发送 WebSocket 事件 storyboard_draft_ready
        # await ws_manager.broadcast({
        #     "type": "storyboard_draft_ready",
        #     "payload": {
        #         "jobId": job_id,
        #         "chapterId": chapter_id,
        #         "draftId": draft_id,
        #         "panelsCount": len(panels_json)
        #     }
        # })
        
    except Exception as e:
        db.rollback()
        # 更新 Job 为失败
        try:
            job = db.query(RenderJob).filter(RenderJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                db.commit()
        except:
            pass
        raise
    finally:
        db.close()




@router.put("/{chapter_id}/script")
async def submit_script(
    chapter_id: str,
    script_text: str,
    style_hint: str = "korean_webtoon",
    auto_storyboard: bool = True,
    db: Session = Depends(get_db)
):
    """
    提交剧本并自动分镜
    
    步骤:
    1. LLM 解析剧本，生成分镜草案
    2. 角色/场景归一化，创建资产占位
    3. 连续性检查，生成警告
    4. 落库保存
    """
    from app.services.brain.base import get_brain_service
    from app.models.panel import Panel
    from app.models.asset import Asset
    import uuid
    
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # 获取 Brain 服务
    brain = get_brain_service()
    
    try:
        # 1. 解析剧本
        result = await brain.parse_script(script_text, style_hint)
        
        # 2. 创建/更新分镜
        panels_created = 0
        character_ids = set()
        scene_ids = set()
        warnings = []
        
        for i, panel_data in enumerate(result.panels):
            panel_id = str(uuid.uuid4())
            
            # 构建 PanelSpec
            spec = {
                "panel_id": panel_id,
                "order": i,
                "title": f"分镜 {i + 1}",
                "action_description": panel_data.action_description,
                "dialogue": [],
                "composition": {
                    "shot_size": panel_data.shot_type,
                    "camera_angle": "eye_level"
                },
                "look": {
                    "style_preset": style_hint
                },
                "render_tier": "normal",
                "render": {"status": "draft"},
                "warnings": []
            }
            
            # 添加对话
            if panel_data.dialogue:
                spec["dialogue"].append({
                    "id": f"dlg_{panel_id}_0",
                    "type": "speech",
                    "text": panel_data.dialogue,
                    "emotion_tag": panel_data.emotion
                })
            
            # 添加角色引用
            if panel_data.character_refs:
                spec["characters"] = [
                    {"character_id": ref, "name": ref, "importance": "primary"}
                    for ref in panel_data.character_refs
                ]
                character_ids.update(panel_data.character_refs)
            
            # 添加场景引用
            if panel_data.scene_ref:
                spec["scene"] = {
                    "scene_id": panel_data.scene_ref,
                    "name": panel_data.scene_ref
                }
                scene_ids.add(panel_data.scene_ref)
            
            # 创建分镜记录
            panel = Panel(
                id=panel_id,
                chapter_id=chapter_id,
                order_index=i,
                title=f"分镜 {i + 1}",
                summary=panel_data.action_description[:100] if panel_data.action_description else None,
                spec_json=spec,
                render_tier="hero" if i == 0 else "normal"
            )
            db.add(panel)
            panels_created += 1
        
        # 3. 创建角色资产占位
        detected_characters = list(result.detected_characters or character_ids)
        for char_name in detected_characters:
            existing = db.query(Asset).filter(
                Asset.project_id == chapter.project_id,
                Asset.name == char_name,
                Asset.type == "character"
            ).first()
            
            if not existing:
                asset = Asset(
                    id=str(uuid.uuid4()),
                    project_id=chapter.project_id,
                    name=char_name,
                    type="character",
                    description=f"从剧本自动检测: {char_name}",
                    data_json={"auto_detected": True, "reference_images": []}
                )
                db.add(asset)
                warnings.append({
                    "type": "new_character",
                    "severity": "info",
                    "message": f"新角色 '{char_name}' 已创建，请上传参考图",
                    "panel_id": None,
                    "asset_id": asset.id,
                    "auto_fixable": False
                })
        
        # 4. 创建场景资产占位
        detected_scenes = list(result.detected_scenes or scene_ids)
        for scene_name in detected_scenes:
            existing = db.query(Asset).filter(
                Asset.project_id == chapter.project_id,
                Asset.name == scene_name,
                Asset.type == "scene"
            ).first()
            
            if not existing:
                asset = Asset(
                    id=str(uuid.uuid4()),
                    project_id=chapter.project_id,
                    name=scene_name,
                    type="scene",
                    description=f"从剧本自动检测: {scene_name}",
                    data_json={"auto_detected": True}
                )
                db.add(asset)
        
        # 5. 更新章节布局
        layout = chapter.layout_json or {}
        layout["script"] = {
            "original_script": script_text,
            "parsed_at": datetime.utcnow().isoformat(),
            "word_count": len(script_text)
        }
        layout["status"] = "storyboarded"
        chapter.layout_json = layout
        
        # 6. 添加连续性警告
        for issue in result.continuity_issues:
            warnings.append({
                "type": issue.type,
                "severity": issue.severity,
                "message": issue.description,
                "panel_id": issue.panel_ids[0] if issue.panel_ids else None,
                "asset_id": None,
                "auto_fixable": False
            })
        
        db.commit()
        
        return {
            "success": True,
            "chapter_id": chapter_id,
            "panels_created": panels_created,
            "characters_detected": detected_characters,
            "scenes_detected": detected_scenes,
            "warnings": warnings
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Script parsing failed: {str(e)}")


# ===== Phase 4: 资产确认与智能填充 API =====

class ConfirmAssetsRequest(BaseModel):
    """确认资产绑定请求"""
    asset_bindings: Dict[str, Dict[str, str]]  # {panel_id: {character_name: asset_id, scene: asset_id}}
    auto_render: bool = False  # 确认后自动渲染首帧


class AutoFillPanelRequest(BaseModel):
    """分镜属性自动填充请求"""
    panel_ids: Optional[List[str]] = None  # 为空则填充所有分镜


@router.post("/{chapter_id}/confirm-assets")
async def confirm_assets(
    chapter_id: str,
    request: ConfirmAssetsRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    确认资产绑定 (Phase 4)
    
    1. 保存绑定关系到 assets_lock_json
    2. 更新每个分镜的 spec_json 中的 characters/scene
    3. 如果 auto_render=True，触发批量渲染
    """
    from app.models.panel import Panel
    from app.models.asset import Asset
    from datetime import datetime
    
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # 获取所有资产
    asset_ids = set()
    for bindings in request.asset_bindings.values():
        asset_ids.update(bindings.values())
    
    assets = db.query(Asset).filter(Asset.id.in_(asset_ids)).all()
    assets_map = {a.id: a for a in assets}
    
    # 更新 assets_lock_json
    assets_lock = chapter.assets_lock_json or {}
    now = datetime.utcnow().isoformat()
    
    # 构建锁定信息
    characters_lock = assets_lock.get("characters", {})
    scenes_lock = assets_lock.get("scenes", {})
    
    panels_updated = 0
    
    for panel_id, bindings in request.asset_bindings.items():
        panel = db.query(Panel).filter(Panel.id == panel_id).first()
        if not panel:
            continue
        
        spec = panel.spec_json or {}
        
        # 更新角色绑定
        for char_name, asset_id in bindings.items():
            if char_name == "scene":
                # 场景绑定
                asset = assets_map.get(asset_id)
                if asset:
                    spec["scene"] = spec.get("scene", {})
                    spec["scene"]["asset_id"] = asset_id
                    spec["scene"]["locked_at"] = now
                    
                    # 添加到场景锁
                    if asset_id not in scenes_lock:
                        data = asset.data_json or {}
                        scenes_lock[asset_id] = {
                            "name": asset.name,
                            "locked_at": now,
                            "anchor_status": data.get("anchor_status", "none"),
                            "anchor_image_path": data.get("anchor_image_path"),
                            "control_maps": data.get("control_maps", {})
                        }
            else:
                # 角色绑定
                asset = assets_map.get(asset_id)
                if asset:
                    # 更新分镜的 characters
                    chars = spec.get("characters", [])
                    for c in chars:
                        if c.get("name") == char_name:
                            c["asset_id"] = asset_id
                            c["locked_at"] = now
                            break
                    spec["characters"] = chars
                    
                    # 添加到角色锁
                    if asset_id not in characters_lock:
                        data = asset.data_json or {}
                        characters_lock[asset_id] = {
                            "name": asset.name,
                            "locked_at": now,
                            "binding_status": "exact" if data.get("face_embedding_path") else "pending",
                            "reference_image_path": asset.reference_image_path,
                            "face_embedding_path": data.get("face_embedding_path"),
                            "face_embedding": {
                                "status": "ready" if data.get("face_embedding_path") else "none",
                                "embedding_path": data.get("face_embedding_path")
                            }
                        }
        
        panel.spec_json = spec
        panels_updated += 1
    
    # 保存 assets_lock
    assets_lock["characters"] = characters_lock
    assets_lock["scenes"] = scenes_lock
    assets_lock["locked_at"] = now
    assets_lock["storyboard_version"] = (assets_lock.get("storyboard_version", 0)) + 1
    
    chapter.assets_lock_json = assets_lock
    db.commit()
    
    # 自动渲染
    render_job_id = None
    if request.auto_render:
        # 触发批量渲染任务
        from app.models.render_job import RenderJob
        import uuid
        
        render_job_id = str(uuid.uuid4())
        job = RenderJob(
            id=render_job_id,
            chapter_id=chapter_id,
            job_type="batch_render",
            status="queued",
            input_params={"render_first_frames": True}
        )
        db.add(job)
        db.commit()
        
        # TODO: 添加后台渲染任务
        # background_tasks.add_task(run_batch_render, render_job_id, chapter_id)
    
    return {
        "success": True,
        "chapter_id": chapter_id,
        "panels_updated": panels_updated,
        "locked_characters": len(characters_lock),
        "locked_scenes": len(scenes_lock),
        "render_job_id": render_job_id
    }


@router.post("/{chapter_id}/auto-fill-panel-attributes")
async def auto_fill_panel_attributes(
    chapter_id: str,
    request: AutoFillPanelRequest,
    db: Session = Depends(get_db)
):
    """
    智能填充分镜属性 (Phase 3)
    
    根据分镜描述自动推断：
    - shot_type (景别)
    - camera_move (运镜)
    - duration_s (时长)
    - mood (氛围)
    - time_of_day (时间)
    - weather (天气)
    """
    from app.models.panel import Panel
    from app.services.brain.panel_attribute_filler import PanelAttributeFiller
    
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # 获取分镜
    query = db.query(Panel).filter(Panel.chapter_id == chapter_id)
    if request.panel_ids:
        query = query.filter(Panel.id.in_(request.panel_ids))
    panels = query.order_by(Panel.order_index).all()
    
    filler = PanelAttributeFiller()
    updated_panels = []
    
    for panel in panels:
        spec = panel.spec_json or {}
        
        # 构建用于分析的 panel 数据
        panel_data = {
            "description": spec.get("action_description", "") or spec.get("description", ""),
            "actions": spec.get("action_description", ""),
            "visual_prompt": spec.get("visual_prompt", ""),
            "location": spec.get("scene", {}).get("location", ""),
        }
        
        # 调用填充服务
        try:
            filled = await filler.fill_attributes(panel_data)
            
            # 更新 spec_json
            shot = spec.get("shot", {})
            if filled.get("shot_type"):
                shot["shotType"] = filled["shot_type"]
            if filled.get("duration_s"):
                shot["durationSec"] = filled["duration_s"]
            spec["shot"] = shot
            
            camera = spec.get("camera", {})
            if filled.get("camera_move"):
                camera["move"] = filled["camera_move"]
            if filled.get("motion_description"):
                camera["description"] = filled["motion_description"]
            spec["camera"] = camera
            
            scene = spec.get("scene", {})
            if filled.get("time_of_day"):
                scene["timeOfDay"] = filled["time_of_day"]
            if filled.get("weather"):
                scene["weather"] = filled["weather"]
            spec["scene"] = scene
            
            if filled.get("mood"):
                spec["mood"] = filled["mood"]
            
            panel.spec_json = spec
            updated_panels.append({
                "panel_id": panel.id,
                "filled_attributes": filled
            })
            
        except Exception as e:
            updated_panels.append({
                "panel_id": panel.id,
                "error": str(e)
            })
    
    db.commit()
    
    return {
        "success": True,
        "chapter_id": chapter_id,
        "panels_processed": len(panels),
        "results": updated_panels
    }


@router.post("/{chapter_id}/auto-match-assets")
async def auto_match_assets(
    chapter_id: str,
    db: Session = Depends(get_db)
):
    """
    智能匹配分镜中的资产引用 (Phase 3)
    
    将分镜中的角色名/场景名自动匹配到资产库
    """
    from app.models.panel import Panel
    from app.models.asset import Asset
    from app.services.brain.asset_matcher import AssetMatcher
    
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # 获取项目资产
    assets = db.query(Asset).filter(Asset.project_id == chapter.project_id).all()
    
    # 获取所有分镜
    panels = db.query(Panel).filter(
        Panel.chapter_id == chapter_id
    ).order_by(Panel.order_index).all()
    
    matcher = AssetMatcher()
    results = []
    unmatched_chars = set()
    unmatched_scenes = set()
    
    for panel in panels:
        spec = panel.spec_json or {}
        
        # 提取角色名和场景
        panel_chars = [c.get("name") for c in spec.get("characters", []) if c.get("name")]
        location = spec.get("scene", {}).get("location", "")
        
        panel_data = {
            "characters": panel_chars,
            "location": location
        }
        
        try:
            match_result = await matcher.auto_match_panel(panel_data, assets)
            
            # 记录未匹配的
            unmatched_chars.update(match_result.get("unmatched_characters", []))
            if match_result.get("unmatched_scene"):
                unmatched_scenes.add(location)
            
            results.append({
                "panel_id": panel.id,
                "matches": match_result
            })
            
        except Exception as e:
            results.append({
                "panel_id": panel.id,
                "error": str(e)
            })
    
    return {
        "success": True,
        "chapter_id": chapter_id,
        "panels_processed": len(panels),
        "unmatched_characters": list(unmatched_chars),
        "unmatched_scenes": list(unmatched_scenes),
        "results": results
    }

