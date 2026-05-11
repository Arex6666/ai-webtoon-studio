"""
Drafts API Routes (S3-02)

分镜草稿 API：获取、应用、丢弃 Draft
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.storyboard_draft import StoryboardDraft
from app.models.chapter import Chapter
from app.models.panel import Panel
import uuid


router = APIRouter(prefix="/drafts", tags=["drafts"])


# ============ Service Function (可直接调用，无 FastAPI 依赖) ============

async def apply_draft_internal(db: Session, draft_id: str, create_missing_assets: bool = True) -> dict:
    """
    内部服务函数：应用 Draft，将生成的 panels 写入正式表
    可从后台任务直接调用，不依赖 FastAPI 的 Depends

    Returns:
        dict with keys: success, applied_panels_count, created_assets_count, new_version, already_applied
    """
    from app.models.asset import Asset

    draft = db.query(StoryboardDraft).filter(StoryboardDraft.id == draft_id).first()
    if not draft:
        raise ValueError(f"Draft not found: {draft_id}")

    # 幂等检查 - 已应用的 Draft 返回已有版本
    if draft.status == "applied":
        return {
            "success": True,
            "applied_panels_count": draft.applied_panels_count or 0,
            "created_assets_count": 0,
            "new_version": draft.applied_as_storyboard_version or 0,
            "already_applied": True
        }

    if draft.status == "discarded":
        raise ValueError("Draft was discarded")

    chapter = db.query(Chapter).filter(Chapter.id == draft.chapter_id).first()
    if not chapter:
        raise ValueError(f"Chapter not found: {draft.chapter_id}")

    # 获取当前版本号
    current_version = chapter.storyboard_version or 0
    new_version = current_version + 1

    # 筛选要应用的 panels
    panels_to_apply = draft.panels_json or []

    # 清除旧 panels
    db.query(Panel).filter(Panel.chapter_id == chapter.id).delete()

    # 创建新 panels
    applied_count = 0
    for i, panel_data in enumerate(panels_to_apply):
        panel = Panel(
            id=str(uuid.uuid4()),
            chapter_id=chapter.id,
            order_index=i,
            title=panel_data.get("title", f"Panel {i+1}"),
            summary=panel_data.get("description", ""),
            spec_json=panel_data,
            render_status="Draft"
        )
        db.add(panel)
        applied_count += 1

    # 更新 Draft 状态
    draft.status = "applied"
    draft.applied_at = datetime.utcnow()
    draft.applied_panels_count = applied_count
    draft.applied_as_storyboard_version = new_version

    # 调用 AssetResolver 生成 AssetsLock
    from app.services.asset_resolver import get_asset_resolver
    from app.schemas.assets_lock import create_assets_lock, CharacterLock, SceneLock

    resolver = get_asset_resolver(db, chapter.project_id)

    # 收集角色和场景名称
    character_names = set()
    scene_names = set()
    for panel_data in panels_to_apply:
        for char in panel_data.get("characters", []):
            if isinstance(char, dict):
                name = char.get("name")
            else:
                name = char
            if name:
                character_names.add(name)

        scene = panel_data.get("scene", {})
        location = scene.get("location")
        if location and location != "未指定":
            scene_names.add(location)

    # 解析资产
    resolve_result = resolver.resolve_all(list(character_names), list(scene_names))

    # 创建 AssetsLock
    lock = create_assets_lock(chapter.id, chapter.project_id, draft.id)
    lock.storyboard_version = new_version

    created_assets_count = 0
    pending_assets = []

    # 处理角色
    for char_result in resolve_result["characters"]:
        if char_result.matched:
            asset = db.query(Asset).filter(Asset.id == char_result.asset_id).first()
            if asset:
                lock.add_character(asset.id, CharacterLock(
                    asset_id=asset.id,
                    name=asset.name,
                    face_embedding_path=asset.data_json.get("face_embedding_path") if asset.data_json else None,
                    lora_path=asset.data_json.get("lora_path") if asset.data_json else None,
                    reference_images=asset.data_json.get("reference_images", []) if asset.data_json else []
                ))
        else:
            pending_id = f"pending_{char_result.suggested_name}"
            lock.add_character(pending_id, CharacterLock(
                asset_id=None,
                name=char_result.suggested_name,
                face_embedding_path=None,
                lora_path=None,
                reference_images=[]
            ))
            pending_assets.append({
                "type": "character",
                "name": char_result.suggested_name,
                "similar": char_result.similar_assets
            })
            if create_missing_assets:
                new_asset = Asset(
                    id=str(uuid.uuid4()),
                    project_id=chapter.project_id,
                    name=char_result.suggested_name,
                    type="character",
                    description="从分镜自动创建",
                    data_json={"auto_created": True, "pending": True}
                )
                db.add(new_asset)
                created_assets_count += 1

    # 处理场景
    for scene_result in resolve_result["scenes"]:
        if scene_result.matched:
            asset = db.query(Asset).filter(Asset.id == scene_result.asset_id).first()
            if asset:
                lock.add_scene(asset.id, SceneLock(
                    asset_id=asset.id,
                    name=asset.name,
                    anchor_image_path=asset.data_json.get("anchor_image_path") if asset.data_json else None,
                    depth_map_path=asset.data_json.get("depth_map_path") if asset.data_json else None,
                    reference_images=asset.data_json.get("reference_images", []) if asset.data_json else []
                ))
        else:
            pending_assets.append({
                "type": "scene",
                "name": scene_result.suggested_name,
                "similar": scene_result.similar_assets
            })
            if create_missing_assets:
                new_asset = Asset(
                    id=str(uuid.uuid4()),
                    project_id=chapter.project_id,
                    name=scene_result.suggested_name,
                    type="scene",
                    description="从分镜自动创建",
                    data_json={"auto_created": True, "pending": True}
                )
                db.add(new_asset)
                created_assets_count += 1

    # 保存 AssetsLock 到 Chapter
    from fastapi.encoders import jsonable_encoder
    chapter.assets_lock_json = jsonable_encoder(lock.dict())

    # 更新 Chapter 版本
    chapter.storyboard_version = new_version
    chapter.layout_json = jsonable_encoder({
        **(chapter.layout_json or {}),
        "storyboard_version": new_version,
        "last_draft_id": draft.id,
        "status": "storyboarded",
        "pending_assets_count": len(pending_assets)
    })
    chapter.status = "storyboarded"

    # 自动生成 Timeline clips
    timeline_clips = []
    current_start_ms = 0

    for i, panel_data in enumerate(panels_to_apply):
        shot = panel_data.get("shot", {})
        duration_sec = shot.get("durationSec", 3.0)
        duration_ms = int(duration_sec * 1000)

        clip = {
            "id": str(uuid.uuid4()),
            "panelId": panel_data.get("id") or f"panel_{i}",
            "startMs": current_start_ms,
            "durationMs": duration_ms,
            "track": 0,
            "status": "Draft",
            "title": panel_data.get("title", f"Panel {i+1}")
        }
        timeline_clips.append(clip)
        current_start_ms += duration_ms

    chapter.timeline_json = {
        "chapterId": chapter.id,
        "clips": timeline_clips,
        "settings": {"fpsDefault": 24, "aspect": "9:16", "totalDurationMs": current_start_ms}
    }

    db.commit()

    return {
        "success": True,
        "applied_panels_count": applied_count,
        "created_assets_count": created_assets_count,
        "new_version": new_version,
        "already_applied": False
    }


# ============ Pydantic Schemas ============

class DraftPanelPreview(BaseModel):
    """Draft 中的 Panel 预览"""
    index: int
    title: str
    description: str
    shot_type: Optional[str] = None
    characters: List[str] = []
    location: Optional[str] = None


class DraftCharacterPreview(BaseModel):
    """Draft 中识别的角色"""
    name: str
    description: Optional[str] = None
    appearances: int = 0
    matched_asset_id: Optional[str] = None


class DraftScenePreview(BaseModel):
    """Draft 中识别的场景"""
    name: str
    description: Optional[str] = None
    appearances: int = 0
    matched_asset_id: Optional[str] = None


class DraftDetailResponse(BaseModel):
    """Draft 详情响应"""
    id: str
    chapter_id: str
    job_id: Optional[str]
    status: str
    version: int
    panels: List[DraftPanelPreview]
    characters: List[DraftCharacterPreview]
    scenes: List[DraftScenePreview]
    generated_panels_count: int
    generated_characters_count: int
    generated_scenes_count: int
    created_at: str


class ApplyDraftRequest(BaseModel):
    """应用 Draft 请求"""
    panel_indices: Optional[List[int]] = None  # None = 应用全部
    create_missing_assets: bool = False  # 自动创建缺失资产
    expected_storyboard_version: Optional[int] = None  # S3-04: 乐观锁


class ApplyDraftResponse(BaseModel):
    """应用 Draft 响应"""
    success: bool
    applied_panels_count: int
    created_assets_count: int
    new_version: int
    already_applied: bool = False  # S3-04: 幂等标记


class DiscardDraftResponse(BaseModel):
    """丢弃 Draft 响应"""
    success: bool
    message: str


# ============ API Endpoints ============

@router.get("/{draft_id}", response_model=DraftDetailResponse)
async def get_draft(
    draft_id: str,
    db: Session = Depends(get_db)
):
    """
    获取 Draft 详情供前端预览
    """
    draft = db.query(StoryboardDraft).filter(StoryboardDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    # 解析 panels JSON
    panels_preview = []
    if draft.panels_json:
        for i, p in enumerate(draft.panels_json):
            panels_preview.append(DraftPanelPreview(
                index=i,
                title=p.get("title", f"Panel {i+1}"),
                description=p.get("description", ""),
                shot_type=p.get("shot", {}).get("shotType"),
                characters=p.get("characters", []),
                location=p.get("scene", {}).get("location")
            ))
    
    # 解析 characters JSON
    characters_preview = []
    if draft.characters_json:
        for c in draft.characters_json:
            characters_preview.append(DraftCharacterPreview(
                name=c.get("name", "Unknown"),
                description=c.get("description"),
                appearances=c.get("appearances", 0),
                matched_asset_id=c.get("matched_asset_id")
            ))
    
    # 解析 scenes JSON
    scenes_preview = []
    if draft.scenes_json:
        for s in draft.scenes_json:
            scenes_preview.append(DraftScenePreview(
                name=s.get("name", "Unknown"),
                description=s.get("description"),
                appearances=s.get("appearances", 0),
                matched_asset_id=s.get("matched_asset_id")
            ))
    
    return DraftDetailResponse(
        id=draft.id,
        chapter_id=draft.chapter_id,
        job_id=draft.job_id,
        status=draft.status,
        version=draft.version,
        panels=panels_preview,
        characters=characters_preview,
        scenes=scenes_preview,
        generated_panels_count=draft.generated_panels_count or 0,
        generated_characters_count=draft.generated_characters_count or 0,
        generated_scenes_count=draft.generated_scenes_count or 0,
        created_at=draft.created_at.isoformat() if draft.created_at else ""
    )


@router.post("/{draft_id}/apply", response_model=ApplyDraftResponse)
async def apply_draft(
    draft_id: str,
    request: ApplyDraftRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    应用 Draft，将生成的 panels 写入正式表
    
    S3-04 版本控制：
    - 幂等：重复 apply 返回已应用的版本
    - 乐观锁：expected_storyboard_version 检查
    - 版本递增：storyboard_version +1
    """
    draft = db.query(StoryboardDraft).filter(StoryboardDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    # S3-04: 幂等检查 - 已应用的 Draft 返回已有版本
    if draft.status == "applied":
        return ApplyDraftResponse(
            success=True,
            applied_panels_count=draft.applied_panels_count or 0,
            created_assets_count=0,
            new_version=draft.applied_as_storyboard_version or 0,
            already_applied=True
        )
    
    if draft.status == "discarded":
        raise HTTPException(status_code=400, detail="Draft was discarded")
    
    chapter = db.query(Chapter).filter(Chapter.id == draft.chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # 获取当前版本号
    current_version = chapter.storyboard_version or 0
    
    # S3-04: 乐观锁检查
    if request.expected_storyboard_version is not None:
        if current_version != request.expected_storyboard_version:
            raise HTTPException(
                status_code=409, 
                detail=f"版本冲突：当前版本 {current_version}，期望版本 {request.expected_storyboard_version}。请刷新后重试。"
            )
    
    new_version = current_version + 1
    
    # 筛选要应用的 panels
    panels_to_apply = draft.panels_json or []
    if request.panel_indices:
        panels_to_apply = [
            p for i, p in enumerate(panels_to_apply) 
            if i in request.panel_indices
        ]
    
    # 清除旧 panels
    db.query(Panel).filter(Panel.chapter_id == chapter.id).delete()
    
    # 创建新 panels
    applied_count = 0
    for i, panel_data in enumerate(panels_to_apply):
        panel = Panel(
            id=str(uuid.uuid4()),
            chapter_id=chapter.id,
            order_index=i,
            title=panel_data.get("title", f"Panel {i+1}"),
            summary=panel_data.get("description", ""),
            spec_json=panel_data,
            render_status="Draft"
        )
        db.add(panel)
        applied_count += 1
    
    # 更新 Draft 状态
    draft.status = "applied"
    draft.applied_at = datetime.utcnow()
    draft.applied_panels_count = applied_count
    draft.applied_as_storyboard_version = new_version  # S3-04: 记录应用时的版本
    
    # S3-06: 调用 AssetResolver 生成 AssetsLock
    from app.services.asset_resolver import get_asset_resolver
    from app.schemas.assets_lock import (
        create_assets_lock, CharacterLock, SceneLock
    )
    from app.models.asset import Asset
    
    resolver = get_asset_resolver(db, chapter.project_id)
    
    # 收集角色和场景名称
    character_names = set()
    scene_names = set()
    for panel_data in panels_to_apply:
        for char in panel_data.get("characters", []):
            if isinstance(char, dict):
                name = char.get("name")
            else:
                name = char
            if name:
                character_names.add(name)
        
        scene = panel_data.get("scene", {})
        location = scene.get("location")
        if location and location != "未指定":
            scene_names.add(location)
    
    # 解析资产
    resolve_result = resolver.resolve_all(list(character_names), list(scene_names))
    
    # 创建 AssetsLock
    lock = create_assets_lock(chapter.id, chapter.project_id, draft.id)
    lock.storyboard_version = new_version
    
    created_assets_count = 0
    pending_assets = []
    
    # 处理角色 - 始终写入 AssetsLock（包括 pending）
    for char_result in resolve_result["characters"]:
        if char_result.matched:
            # 查询 Asset 详情
            asset = db.query(Asset).filter(Asset.id == char_result.asset_id).first()
            if asset:
                lock.add_character(asset.id, CharacterLock(
                    asset_id=asset.id,
                    name=asset.name,
                    face_embedding_path=asset.data_json.get("face_embedding_path") if asset.data_json else None,
                    lora_path=asset.data_json.get("lora_path") if asset.data_json else None,
                    reference_images=asset.data_json.get("reference_images", []) if asset.data_json else []
                ))
        else:
            # P0-UI-FIX-01: 将 pending 角色也写入 AssetsLock
            pending_id = f"pending_{char_result.suggested_name}"
            lock.add_character(pending_id, CharacterLock(
                asset_id=None,
                name=char_result.suggested_name,
                face_embedding_path=None,
                lora_path=None,
                reference_images=[]
            ))
            pending_assets.append({
                "type": "character",
                "name": char_result.suggested_name,
                "similar": char_result.similar_assets
            })
            # 自动创建占位
            if request.create_missing_assets:
                new_asset = Asset(
                    id=str(uuid.uuid4()),
                    project_id=chapter.project_id,
                    name=char_result.suggested_name,
                    type="character",
                    description=f"从分镜自动创建",
                    data_json={"auto_created": True, "pending": True}
                )
                db.add(new_asset)
                created_assets_count += 1
    
    # 处理场景
    for scene_result in resolve_result["scenes"]:
        if scene_result.matched:
            asset = db.query(Asset).filter(Asset.id == scene_result.asset_id).first()
            if asset:
                lock.add_scene(asset.id, SceneLock(
                    asset_id=asset.id,
                    name=asset.name,
                    anchor_image_path=asset.data_json.get("anchor_image_path") if asset.data_json else None,
                    depth_map_path=asset.data_json.get("depth_map_path") if asset.data_json else None,
                    reference_images=asset.data_json.get("reference_images", []) if asset.data_json else []
                ))
        else:
            pending_assets.append({
                "type": "scene",
                "name": scene_result.suggested_name,
                "similar": scene_result.similar_assets
            })
            if request.create_missing_assets:
                new_asset = Asset(
                    id=str(uuid.uuid4()),
                    project_id=chapter.project_id,
                    name=scene_result.suggested_name,
                    type="scene",
                    description=f"从分镜自动创建",
                    data_json={"auto_created": True, "pending": True}
                )
                db.add(new_asset)
                created_assets_count += 1
    
    # 保存 AssetsLock 到 Chapter (确保 datetime 可 JSON 序列化)
    from fastapi.encoders import jsonable_encoder
    chapter.assets_lock_json = jsonable_encoder(lock.dict())
    
    # 更新 Chapter 版本
    chapter.storyboard_version = new_version
    chapter.layout_json = jsonable_encoder({
        **(chapter.layout_json or {}),
        "storyboard_version": new_version,
        "last_draft_id": draft.id,
        "status": "storyboarded",
        "pending_assets_count": len(pending_assets)
    })
    chapter.status = "storyboarded"
    
    # P0-TL-01: 自动生成 Timeline clips
    timeline_clips = []
    current_start_ms = 0
    
    for i, panel_data in enumerate(panels_to_apply):
        shot = panel_data.get("shot", {})
        duration_sec = shot.get("durationSec", 3.0)
        duration_ms = int(duration_sec * 1000)
        
        clip = {
            "id": str(uuid.uuid4()),
            "panelId": panel_data.get("id") or f"panel_{i}",
            "startMs": current_start_ms,
            "durationMs": duration_ms,
            "track": 0,
            "status": "Draft",
            "title": panel_data.get("title", f"Panel {i+1}")
        }
        timeline_clips.append(clip)
        current_start_ms += duration_ms
    
    chapter.timeline_json = {
        "chapterId": chapter.id,
        "clips": timeline_clips,
        "settings": {"fpsDefault": 24, "aspect": "9:16", "totalDurationMs": current_start_ms}
    }
    
    db.commit()
    
    # S5-01: 触发角色参考图自动生成
    from app.services.portrait.retry_strategy import enqueue_portrait_generation
    
    # 收集需要生成参考图的角色
    characters_to_generate = []
    for char_id, char_lock in lock.characters.items():
        # 只处理还没有参考图的角色
        if not char_lock.reference_image_path:
            # 从 draft 的 characters_json 查找描述信息
            char_info = next(
                (c for c in (draft.characters_json or []) if c.get("name") == char_lock.name),
                {}
            )
            characters_to_generate.append({
                "character_id": char_id,
                "name": char_lock.name,
                "description": char_info.get("description"),
                "appearance_traits": char_info.get("appearance_traits", [])
            })
    
    # 异步触发生成
    for char in characters_to_generate:
        background_tasks.add_task(
            enqueue_portrait_generation,
            character_id=char["character_id"],
            project_id=chapter.project_id,
            character_name=char["name"],
            character_description=char.get("description"),
            appearance_traits=char.get("appearance_traits"),
            provider="mock",  # 可配置
            db_session=None  # 异步任务中需要新 session
        )
    
    # S5-SC: 触发场景锚点自动生成
    from app.services.scene.retry_strategy import enqueue_scene_anchor_generation
    
    scenes_to_generate = []
    for scene_id, scene_lock in lock.scenes.items():
        # 只处理还没有锚点的场景
        if not scene_lock.anchor_image_path:
            # 从 draft 的 scenes_json 查找描述信息
            scene_info = next(
                (s for s in (draft.scenes_json or []) if s.get("name") == scene_lock.name),
                {}
            )
            scenes_to_generate.append({
                "scene_id": scene_id,
                "name": scene_lock.name,
                "location": scene_info.get("location"),
                "time_of_day": scene_info.get("time_of_day"),
                "mood": scene_info.get("mood")
            })
    
    # 异步触发场景锚点生成
    for scene in scenes_to_generate:
        background_tasks.add_task(
            enqueue_scene_anchor_generation,
            scene_id=scene["scene_id"],
            project_id=chapter.project_id,
            scene_name=scene["name"],
            location=scene.get("location"),
            time_of_day=scene.get("time_of_day"),
            mood=scene.get("mood"),
            db_session=None,
        )
    
    return ApplyDraftResponse(
        success=True,
        applied_panels_count=applied_count,
        created_assets_count=created_assets_count,
        new_version=new_version,
        already_applied=False
    )


@router.post("/{draft_id}/discard", response_model=DiscardDraftResponse)
async def discard_draft(
    draft_id: str,
    db: Session = Depends(get_db)
):
    """
    丢弃 Draft
    """
    draft = db.query(StoryboardDraft).filter(StoryboardDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    if draft.status == "applied":
        raise HTTPException(status_code=400, detail="Cannot discard applied draft")
    
    draft.status = "discarded"
    db.commit()
    
    return DiscardDraftResponse(
        success=True,
        message=f"Draft {draft_id} discarded"
    )


# ============ S3-05: QA Endpoints ============

class QAIssueResponse(BaseModel):
    """QA 问题响应"""
    panel_index: int
    field: str
    severity: str
    message: str
    auto_fixable: bool
    suggested_fix: Optional[str] = None


class QAResultResponse(BaseModel):
    """QA 结果响应"""
    score: float
    passed: bool
    error_count: int
    warning_count: int
    fixable_count: int
    issues: List[QAIssueResponse]


class FixDraftRequest(BaseModel):
    """修复请求"""
    issue_indices: Optional[List[int]] = None  # None = 修复全部


class FixDraftResponse(BaseModel):
    """修复响应"""
    success: bool
    fixed_count: int
    panels_modified: List[int]
    new_score: float


@router.get("/{draft_id}/qa", response_model=QAResultResponse)
async def get_draft_qa(
    draft_id: str,
    db: Session = Depends(get_db)
):
    """
    获取 Draft QA 评分 (S3-05)
    
    返回质量评分 (0-100) 和问题列表
    """
    from app.services.draft_qa import get_draft_qa
    
    draft = db.query(StoryboardDraft).filter(StoryboardDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    qa = get_draft_qa()
    result = qa.evaluate(draft)
    
    return QAResultResponse(
        score=result.score,
        passed=result.passed,
        error_count=result.error_count,
        warning_count=result.warning_count,
        fixable_count=result.fixable_count,
        issues=[
            QAIssueResponse(
                panel_index=i.panel_index,
                field=i.field,
                severity=i.severity.value,
                message=i.message,
                auto_fixable=i.auto_fixable,
                suggested_fix=i.suggested_fix
            )
            for i in result.issues
        ]
    )


@router.post("/{draft_id}/fix", response_model=FixDraftResponse)
async def fix_draft(
    draft_id: str,
    request: FixDraftRequest,
    db: Session = Depends(get_db)
):
    """
    自动修复 Draft 问题 (S3-05)
    
    - issue_indices: 指定要修复的问题索引，None 表示全部
    """
    from app.services.draft_qa import get_draft_qa
    
    draft = db.query(StoryboardDraft).filter(StoryboardDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    if draft.status == "applied":
        raise HTTPException(status_code=400, detail="Cannot fix applied draft")
    
    qa = get_draft_qa()
    
    # 执行修复
    fix_result = qa.auto_fix(draft, request.issue_indices)
    
    # 保存修复后的 Draft
    db.commit()
    db.refresh(draft)
    
    # 重新评分
    new_result = qa.evaluate(draft)
    
    return FixDraftResponse(
        success=True,
        fixed_count=fix_result["fixed_count"],
        panels_modified=fix_result["panels_modified"],
        new_score=new_result.score
    )



@router.get("/chapter/{chapter_id}/latest")
async def get_latest_draft(
    chapter_id: str,
    db: Session = Depends(get_db)
):
    """
    获取章节最新的未应用 Draft
    """
    draft = db.query(StoryboardDraft).filter(
        StoryboardDraft.chapter_id == chapter_id,
        StoryboardDraft.status.in_(["pending", "completed"])
    ).order_by(StoryboardDraft.created_at.desc()).first()
    
    if not draft:
        return {"draft": None}
    
    return {"draft": draft.to_dict()}


class RollbackRequest(BaseModel):
    """回滚请求 (S3-04)"""
    target_storyboard_version: Optional[int] = None  # 回滚到的目标版本


@router.post("/chapter/{chapter_id}/rollback")
async def rollback_storyboard(
    chapter_id: str,
    request: RollbackRequest = RollbackRequest(),
    db: Session = Depends(get_db)
):
    """
    回滚到指定的 storyboard 版本
    
    S3-04 改进：
    - 支持回滚到任意历史版本（通过 applied_as_storyboard_version 查找）
    - 回滚产生新版本（不覆盖历史）
    """
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    current_version = chapter.storyboard_version or 0
    
    if current_version <= 0:
        raise HTTPException(status_code=400, detail="No storyboard version to rollback")
    
    # 确定目标版本
    target_version = request.target_storyboard_version or (current_version - 1)
    
    if target_version <= 0:
        raise HTTPException(status_code=400, detail="Invalid target version")
    
    if target_version >= current_version:
        raise HTTPException(status_code=400, detail="Cannot rollback to current or future version")
    
    # 查找目标版本对应的 Draft
    target_draft = db.query(StoryboardDraft).filter(
        StoryboardDraft.chapter_id == chapter_id,
        StoryboardDraft.applied_as_storyboard_version == target_version
    ).first()
    
    if not target_draft:
        # 尝试查找最接近的已应用 Draft
        target_draft = db.query(StoryboardDraft).filter(
            StoryboardDraft.chapter_id == chapter_id,
            StoryboardDraft.status == "applied",
            StoryboardDraft.applied_as_storyboard_version <= target_version
        ).order_by(StoryboardDraft.applied_as_storyboard_version.desc()).first()
    
    if not target_draft:
        raise HTTPException(status_code=400, detail=f"No draft found for version {target_version}")
    
    # 重新应用目标 Draft 的 panels
    db.query(Panel).filter(Panel.chapter_id == chapter.id).delete()
    
    applied_count = 0
    for i, panel_data in enumerate(target_draft.panels_json or []):
        panel = Panel(
            id=str(uuid.uuid4()),
            chapter_id=chapter.id,
            project_id=chapter.project_id,
            order_index=i,
            title=panel_data.get("title", f"Panel {i+1}"),
            summary=panel_data.get("description", ""),
            spec_json=panel_data,
            render_status="Draft"
        )
        db.add(panel)
        applied_count += 1
    
    # 回滚产生新版本
    new_version = current_version + 1
    chapter.storyboard_version = new_version
    chapter.layout_json = {
        **(chapter.layout_json or {}),
        "storyboard_version": new_version,
        "rollback_from_version": current_version,
        "rollback_to_version": target_version,
        "rollback_source_draft_id": target_draft.id
    }
    
    db.commit()
    
    return {
        "success": True,
        "rolled_back_to_version": target_version,
        "rolled_back_to_draft": target_draft.id,
        "restored_panels_count": applied_count,
        "new_version": new_version,
        "message": f"已回滚到版本 {target_version}，当前版本更新为 {new_version}"
    }
