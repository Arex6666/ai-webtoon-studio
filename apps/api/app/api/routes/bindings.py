"""
资产绑定路由 - Bindings API (数据库版本)
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import uuid
import logging

from app.db.database import get_db
from app.models import ChapterBindings, Chapter

router = APIRouter()
logger = logging.getLogger(__name__)


# ============ Schemas ============

class QAConfig(BaseModel):
    threshold: float = 0.75
    max_issues: int = 3


class Budget(BaseModel):
    max_cost: float = 50.0
    cost_used: float = 0.0


class RetryPolicy(BaseModel):
    max_attempts: int = 3
    provider_chain: List[str] = ["kling", "tongyi", "doubao", "mock"]
    budget: Budget = Budget()


class BindingsInput(BaseModel):
    identity_asset_ids: List[str] = []
    scene_asset_ids: List[str] = []
    style_profile_id: Optional[str] = None
    anchor_ids: List[str] = []
    qa_config: Optional[QAConfig] = None
    retry_policy: Optional[RetryPolicy] = None


class BindingsResponse(BaseModel):
    chapter_id: str
    identity_asset_ids: List[str]
    scene_asset_ids: List[str]
    style_profile_id: Optional[str]
    anchor_ids: List[str]
    qa_config: Optional[QAConfig]
    retry_policy: Optional[RetryPolicy]
    updated_at: str


def get_or_create_bindings(db: Session, chapter_id: str) -> ChapterBindings:
    """获取或创建 Bindings"""
    bindings = db.query(ChapterBindings).filter(ChapterBindings.chapter_id == chapter_id).first()
    if not bindings:
        # 验证 chapter 存在
        chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")
        
        bindings = ChapterBindings(
            id=str(uuid.uuid4()),
            chapter_id=chapter_id
        )
        db.add(bindings)
        db.commit()
        db.refresh(bindings)
    return bindings


@router.get("/{chapter_id}/bindings", response_model=BindingsResponse)
async def get_bindings(chapter_id: str, db: Session = Depends(get_db)):
    """获取章节资产绑定"""
    bindings = get_or_create_bindings(db, chapter_id)
    
    return BindingsResponse(
        chapter_id=chapter_id,
        identity_asset_ids=bindings.identity_asset_ids or [],
        scene_asset_ids=bindings.scene_asset_ids or [],
        style_profile_id=bindings.style_profile_id,
        anchor_ids=bindings.anchor_ids or [],
        qa_config=QAConfig(**(bindings.qa_config_json or {})) if bindings.qa_config_json else QAConfig(),
        retry_policy=RetryPolicy(**(bindings.retry_policy_json or {})) if bindings.retry_policy_json else RetryPolicy(),
        updated_at=bindings.updated_at.isoformat() if bindings.updated_at else datetime.utcnow().isoformat()
    )


@router.put("/{chapter_id}/bindings")
async def save_bindings(
    chapter_id: str,
    bindings_input: BindingsInput,
    db: Session = Depends(get_db)
):
    """保存章节资产绑定"""
    bindings = get_or_create_bindings(db, chapter_id)
    
    bindings.identity_asset_ids = bindings_input.identity_asset_ids
    bindings.scene_asset_ids = bindings_input.scene_asset_ids
    bindings.style_profile_id = bindings_input.style_profile_id
    bindings.anchor_ids = bindings_input.anchor_ids
    bindings.qa_config_json = bindings_input.qa_config.model_dump() if bindings_input.qa_config else None
    bindings.retry_policy_json = bindings_input.retry_policy.model_dump() if bindings_input.retry_policy else None
    
    db.commit()
    
    logger.info(f"Bindings saved for chapter {chapter_id}")
    
    return {
        "message": "Bindings saved",
        "chapter_id": chapter_id,
        "updated_at": datetime.utcnow().isoformat()
    }


@router.patch("/{chapter_id}/bindings")
async def update_bindings(
    chapter_id: str,
    bindings_input: BindingsInput,
    db: Session = Depends(get_db)
):
    """部分更新章节资产绑定"""
    bindings = get_or_create_bindings(db, chapter_id)
    
    # 只更新提供的字段
    if bindings_input.identity_asset_ids:
        bindings.identity_asset_ids = bindings_input.identity_asset_ids
    if bindings_input.scene_asset_ids:
        bindings.scene_asset_ids = bindings_input.scene_asset_ids
    if bindings_input.style_profile_id is not None:
        bindings.style_profile_id = bindings_input.style_profile_id
    if bindings_input.anchor_ids:
        bindings.anchor_ids = bindings_input.anchor_ids
    if bindings_input.qa_config:
        bindings.qa_config_json = bindings_input.qa_config.model_dump()
    if bindings_input.retry_policy:
        bindings.retry_policy_json = bindings_input.retry_policy.model_dump()
    
    db.commit()
    
    return {
        "message": "Bindings updated",
        "chapter_id": chapter_id,
        "updated_at": datetime.utcnow().isoformat()
    }
