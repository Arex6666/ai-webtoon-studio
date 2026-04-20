"""
Script operations for chapters
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.models.chapter import Chapter
from app.models.panel import Panel
from app.models.asset import Asset
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()


# Request/Response Models
class ScriptSaveRequest(BaseModel):
    script: str


class ScriptSaveResponse(BaseModel):
    chapter_id: str
    script: str
    script_version: str
    word_count: int


# ===== 剧本保存接口 (S2-01) =====

@router.put("/{chapter_id}/script/save", response_model=ScriptSaveResponse)
async def save_script(
    chapter_id: str,
    request: ScriptSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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


# ===== 提交剧本接口 (combines script operations with AI storyboard) =====

@router.put("/{chapter_id}/script")
async def submit_script(
    chapter_id: str,
    script_text: str,
    style_hint: str = "korean_webtoon",
    auto_storyboard: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    from app.services.asset_name_extractor import (
        sanitize_character_names,
        sanitize_scene_name,
        sanitize_scene_names,
    )
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

            # 添加角色引用（先清洗，避免把对白碎片识别成角色）
            cleaned_character_refs = sanitize_character_names(
                panel_data.character_refs or panel_data.characters or []
            )
            if cleaned_character_refs:
                spec["characters"] = [
                    {"character_id": ref, "name": ref, "importance": "primary"}
                    for ref in cleaned_character_refs
                ]
                character_ids.update(cleaned_character_refs)

            # 添加场景引用（归一化为基础地点名，减少重复场景）
            cleaned_scene = sanitize_scene_name(panel_data.scene_ref or panel_data.scene_description)
            if cleaned_scene:
                spec["scene"] = {
                    "scene_id": cleaned_scene,
                    "name": cleaned_scene
                }
                scene_ids.add(cleaned_scene)

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
        detected_characters = sanitize_character_names(
            list(result.detected_characters or []) + sorted(character_ids)
        )
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
        detected_scenes = sanitize_scene_names(
            list(result.detected_scenes or []) + sorted(scene_ids)
        )
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
