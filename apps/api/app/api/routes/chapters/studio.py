"""
Studio operations for chapters
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.core.database import get_db
from app.models.chapter import Chapter
from app.models.panel import Panel
from app.models.asset import Asset
from app.models.render_job import RenderJob
from app.models.prop_asset import PropAsset
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/{chapter_id}/studio")
async def get_chapter_studio(
    chapter_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取章节工作台所需的全部数据（聚合接口）
    包含：章节信息、布局、分镜列表、资产、任务状态、警告汇总

    这是前端 Studio 页面的主要数据源
    """
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
        # 安全处理 dialogue - 可能是列表、字典或字符串
        dialogue_preview = None
        if isinstance(dialogue, list) and len(dialogue) > 0:
            first_dialogue = dialogue[0]
            if isinstance(first_dialogue, dict):
                dialogue_preview = first_dialogue.get("text", "")[:50]
            elif isinstance(first_dialogue, str):
                dialogue_preview = first_dialogue[:50]
        elif isinstance(dialogue, dict):
            dialogue_preview = dialogue.get("text", "")[:50]
        elif isinstance(dialogue, str):
            dialogue_preview = dialogue[:50]

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
            "summary": p.summary or spec.get("shot", {}).get("description", "") or spec.get("shot_description", "") or spec.get("action_description", "") or spec.get("meta", {}).get("description", ""),
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
