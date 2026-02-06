"""
Asset Auto-Build API Routes
P0-CH-02: 触发自动生成角色/场景资产 + 查询状态
"""
import uuid
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Chapter, CharacterCanonical, CanonicalStatus
from app.models.job import Job
from app.schemas.character_canonical import (
    AutoBuildRequest,
    AutoBuildResponse,
    AutoBuildStatusResponse,
    AutoBuildJobStatus,
    CharacterCanonicalItemStatus,
    CanonicalStatusEnum,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chapters/{chapter_id}/assets", tags=["Asset AutoBuild"])


# ============ Job Store (临时内存存储，生产应存 DB) ============
_autobuild_jobs: dict = {}


def get_or_create_job(job_id: str) -> dict:
    if job_id not in _autobuild_jobs:
        _autobuild_jobs[job_id] = {
            "id": job_id,
            "status": "queued",
            "stage": "pending",
            "progress": 0.0,
            "message": None,
            "started_at": None,
            "updated_at": None,
        }
    return _autobuild_jobs[job_id]


def update_job(job_id: str, **kwargs):
    if job_id in _autobuild_jobs:
        from datetime import datetime
        _autobuild_jobs[job_id].update(kwargs)
        _autobuild_jobs[job_id]["updated_at"] = datetime.utcnow()


# ============ API Routes ============

@router.post("/auto-build", response_model=AutoBuildResponse)
async def trigger_auto_build(
    chapter_id: str,
    request: AutoBuildRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    触发自动生成资产
    
    - scope: characters / scenes / all
    - force: 是否强制重新生成
    
    返回 job_id，前端可通过 status API 轮询进度
    """
    # 验证章节存在
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # 获取角色列表 (从 StoryboardDraft 或 layout_json)
    characters = _extract_characters_from_chapter(chapter, db)
    
    if not characters:
        raise HTTPException(
            status_code=400,
            detail="No characters found. Please run AI storyboard first."
        )
    
    # 过滤指定角色
    if request.character_ids:
        characters = [c for c in characters if c["id"] in request.character_ids]
    
    # 创建 Job
    job_id = str(uuid.uuid4())
    get_or_create_job(job_id)
    
    # 初始化 CharacterCanonical 记录
    for char in characters:
        existing = db.query(CharacterCanonical).filter(
            CharacterCanonical.chapter_id == chapter_id,
            CharacterCanonical.character_id == char["id"],
        ).first()
        
        if existing:
            if request.force:
                # 重置状态
                existing.status = CanonicalStatus.PENDING
                existing.candidate_paths = []
                existing.selected_path = None
                existing.error = None
        else:
            # 创建新记录
            canonical = CharacterCanonical(
                id=str(uuid.uuid4()),
                chapter_id=chapter_id,
                character_id=char["id"],
                character_name=char.get("name"),
                status=CanonicalStatus.PENDING,
                generation_config={
                    "candidate_count": request.candidate_count,
                    "style_profile": request.style_profile,
                },
            )
            db.add(canonical)
    
    db.commit()
    
    # 启动后台任务
    from app.services.canonical.canonical_generator import run_autobuild_characters
    background_tasks.add_task(
        run_autobuild_characters,
        job_id=job_id,
        chapter_id=chapter_id,
        characters=characters,
        config={
            "candidate_count": request.candidate_count,
            "style_profile": request.style_profile,
            "force": request.force,
        },
    )
    
    logger.info(f"Started auto-build job {job_id} for chapter {chapter_id} with {len(characters)} characters")
    
    return AutoBuildResponse(
        job_id=job_id,
        message=f"Started auto-build for {len(characters)} characters",
        total_items=len(characters),
    )


@router.get("/auto-build/status", response_model=AutoBuildStatusResponse)
async def get_auto_build_status(
    chapter_id: str,
    scope: str = "characters",
    job_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    查询自动生成状态
    
    - scope: characters / scenes
    - job_id: 可选，指定 job
    """
    # 验证章节存在
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # 获取 Job 状态
    job_status = None
    if job_id and job_id in _autobuild_jobs:
        job_data = _autobuild_jobs[job_id]
        job_status = AutoBuildJobStatus(
            id=job_data["id"],
            status=job_data["status"],
            stage=job_data["stage"],
            progress=job_data["progress"],
            message=job_data.get("message"),
            started_at=job_data.get("started_at"),
            updated_at=job_data.get("updated_at"),
        )
    
    # 获取角色 Canonical 状态
    items = []
    canonicals = db.query(CharacterCanonical).filter(
        CharacterCanonical.chapter_id == chapter_id
    ).all()
    
    completed = 0
    failed = 0
    
    for c in canonicals:
        item = CharacterCanonicalItemStatus(
            character_id=c.character_id,
            character_name=c.character_name,
            status=CanonicalStatusEnum(c.status.value),
            candidates_count=c.candidates_count,
            candidate_paths=c.candidate_paths or [],
            selected_path=c.selected_path,
            selected_score=c.selected_score,
            error=c.error,
        )
        items.append(item)
        
        if c.status == CanonicalStatus.SUCCEEDED:
            completed += 1
        elif c.status == CanonicalStatus.FAILED:
            failed += 1
    
    return AutoBuildStatusResponse(
        job=job_status,
        items=items,
        total=len(items),
        completed=completed,
        failed=failed,
    )


# ============ Helper Functions ============

def _extract_characters_from_chapter(chapter: Chapter, db: Session) -> list:
    """
    从章节中提取角色列表
    
    优先级：
    1. StoryboardDraft 中的 analysis_json
    2. layout_json
    """
    from app.models.storyboard_draft import StoryboardDraft
    
    # 尝试从最新的 StoryboardDraft 获取
    draft = db.query(StoryboardDraft).filter(
        StoryboardDraft.chapter_id == chapter.id
    ).order_by(StoryboardDraft.created_at.desc()).first()
    
    if draft and draft.analysis_json:
        analysis = draft.analysis_json
        if isinstance(analysis, dict) and "characters" in analysis:
            return [
                {
                    "id": c.get("id") or f"ch_{c.get('name', 'unknown').lower().replace(' ', '_')}",
                    "name": c.get("name"),
                    "appearance": c.get("appearance_keywords", []),
                    "style_tags": c.get("personality_keywords", []),
                    "gender": c.get("gender"),
                    "age_range": c.get("age_range"),
                }
                for c in analysis["characters"]
            ]
    
    # Fallback: 从 layout_json 提取
    layout = chapter.layout_json or {}
    characters = layout.get("characters", [])
    
    return [
        {
            "id": c.get("id") or f"ch_{c.get('name', 'unknown').lower().replace(' ', '_')}",
            "name": c.get("name"),
            "appearance": c.get("appearance", []),
            "style_tags": c.get("style_tags", []),
        }
        for c in characters
    ]
