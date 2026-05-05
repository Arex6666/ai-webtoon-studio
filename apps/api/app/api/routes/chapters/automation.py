"""
Automation operations for chapters
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, List, Dict
from pydantic import BaseModel

from app.core.database import get_db
from app.models.chapter import Chapter
from app.models.panel import Panel
from app.models.asset import Asset
from app.models.render_job import RenderJob
from app.api.deps import get_current_user
from app.models.user import User
from datetime import datetime

router = APIRouter()


# Request/Response Models
class ConfirmAssetsRequest(BaseModel):
    """确认资产绑定请求"""
    asset_bindings: Dict[str, Dict[str, str]]  # {panel_id: {character_name: asset_id, scene: asset_id}}
    auto_render: bool = False  # 确认后自动渲染首帧


class AutoFillPanelRequest(BaseModel):
    """分镜属性自动填充请求"""
    panel_ids: Optional[List[str]] = None  # 为空则填充所有分镜


# ===== Phase 4: 资产确认与智能填充 API =====

@router.post("/{chapter_id}/confirm-assets")
async def confirm_assets(
    chapter_id: str,
    request: ConfirmAssetsRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    确认资产绑定 (Phase 4)

    1. 保存绑定关系到 assets_lock_json
    2. 更新每个分镜的 spec_json 中的 characters/scene
    3. 如果 auto_render=True，触发批量渲染
    """
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
    render_job_ids: List[str] = []
    if request.auto_render:
        import uuid

        for panel_id in request.asset_bindings.keys():
            panel = db.query(Panel).filter(Panel.id == panel_id).first()
            if not panel:
                continue
            job = RenderJob(
                id=str(uuid.uuid4()),
                chapter_id=chapter_id,
                panel_id=panel_id,
                job_type="full_render",
                status="queued",
                input_params={
                    "render_first_frames": True,
                    "assets_lock": assets_lock,
                },
            )
            db.add(job)
            render_job_ids.append(job.id)
        db.commit()

        if render_job_ids:
            from app.celery_app import celery_app as _celery
            _celery.send_task(
                "app.workers.async_runner.run_batch_render_task_celery",
                args=[render_job_ids, 3],
                queue="image",
            )

    return {
        "success": True,
        "chapter_id": chapter_id,
        "panels_updated": panels_updated,
        "locked_characters": len(characters_lock),
        "locked_scenes": len(scenes_lock),
        "render_job_ids": render_job_ids,
        "render_job_id": render_job_ids[0] if render_job_ids else None,
    }


@router.post("/{chapter_id}/auto-fill-panel-attributes")
async def auto_fill_panel_attributes(
    chapter_id: str,
    request: AutoFillPanelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    智能匹配分镜中的资产引用 (Phase 3)

    将分镜中的角色名/场景名自动匹配到资产库
    """
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
