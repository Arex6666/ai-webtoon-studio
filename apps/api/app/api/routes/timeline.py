"""
时间轴路由 - Timeline API (数据库版本)
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import uuid
import logging

from app.db.database import get_db
from app.models import Timeline, Clip, Chapter

router = APIRouter()
logger = logging.getLogger(__name__)


# ============ Schemas ============

class ClipOutput(BaseModel):
    video_url: Optional[str] = None
    preview_url: Optional[str] = None
    frames: Optional[List[str]] = None


class ClipSchema(BaseModel):
    id: str
    panel_id: str
    order_index: int
    duration_sec: float = 3.0
    fps: int = 8
    provider: str = "mock"
    motion_prompt: str = ""
    status: str = "Draft"
    progress: float = 0.0
    output: Optional[ClipOutput] = None

    class Config:
        from_attributes = True


class TimelineSettings(BaseModel):
    fps_default: int = 8
    aspect: str = "9:16"
    export_preset: str = "webtoon_vertical"


class TimelineInput(BaseModel):
    clips: List[ClipSchema]
    settings: TimelineSettings


class TimelineResponse(BaseModel):
    chapter_id: str
    clips: List[ClipSchema]
    settings: TimelineSettings
    updated_at: str


def get_or_create_timeline(db: Session, chapter_id: str) -> Timeline:
    """获取或创建 Timeline"""
    timeline = db.query(Timeline).filter(Timeline.chapter_id == chapter_id).first()
    if not timeline:
        # 验证 chapter 存在
        chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")
        
        timeline = Timeline(
            id=str(uuid.uuid4()),
            chapter_id=chapter_id,
            settings_json=TimelineSettings().model_dump()
        )
        db.add(timeline)
        db.commit()
        db.refresh(timeline)
    return timeline


@router.get("/{chapter_id}/timeline", response_model=TimelineResponse)
async def get_timeline(chapter_id: str, db: Session = Depends(get_db)):
    """获取章节时间轴"""
    timeline = get_or_create_timeline(db, chapter_id)
    
    clips = [
        ClipSchema(
            id=clip.id,
            panel_id=clip.panel_id,
            order_index=clip.order_index,
            duration_sec=clip.duration_sec,
            fps=clip.fps,
            provider=clip.provider,
            motion_prompt=clip.motion_prompt or "",
            status=clip.status,
            progress=clip.progress,
            output=ClipOutput(**(clip.output_json or {})) if clip.output_json else None
        )
        for clip in timeline.clips
    ]

    return TimelineResponse(
        chapter_id=chapter_id,
        clips=clips,
        settings=TimelineSettings(**(timeline.settings_json or {})),
        updated_at=timeline.updated_at.isoformat() if timeline.updated_at else datetime.utcnow().isoformat()
    )


@router.put("/{chapter_id}/timeline")
async def save_timeline(
    chapter_id: str,
    timeline_input: TimelineInput,
    db: Session = Depends(get_db)
):
    """保存章节时间轴（整章覆盖）"""
    timeline = get_or_create_timeline(db, chapter_id)
    
    # 删除旧的 clips
    db.query(Clip).filter(Clip.timeline_id == timeline.id).delete()
    
    # 创建新的 clips
    for clip_data in timeline_input.clips:
        clip = Clip(
            id=clip_data.id or str(uuid.uuid4()),
            timeline_id=timeline.id,
            panel_id=clip_data.panel_id,
            order_index=clip_data.order_index,
            duration_sec=clip_data.duration_sec,
            fps=clip_data.fps,
            provider=clip_data.provider,
            motion_prompt=clip_data.motion_prompt,
            status=clip_data.status,
            progress=clip_data.progress,
            output_json=clip_data.output.model_dump() if clip_data.output else None
        )
        db.add(clip)
    
    # 更新设置
    timeline.settings_json = timeline_input.settings.model_dump()
    
    db.commit()
    
    logger.info(f"Timeline saved for chapter {chapter_id}: {len(timeline_input.clips)} clips")
    
    return {
        "message": "Timeline saved",
        "chapter_id": chapter_id,
        "clips_count": len(timeline_input.clips),
        "updated_at": datetime.utcnow().isoformat()
    }


@router.post("/{chapter_id}/timeline/clips")
async def add_clip(
    chapter_id: str,
    clip_data: ClipSchema,
    db: Session = Depends(get_db)
):
    """添加单个 Clip"""
    timeline = get_or_create_timeline(db, chapter_id)
    
    clip = Clip(
        id=clip_data.id or str(uuid.uuid4()),
        timeline_id=timeline.id,
        panel_id=clip_data.panel_id,
        order_index=clip_data.order_index,
        duration_sec=clip_data.duration_sec,
        fps=clip_data.fps,
        provider=clip_data.provider,
        motion_prompt=clip_data.motion_prompt,
        status=clip_data.status,
        progress=clip_data.progress,
        output_json=clip_data.output.model_dump() if clip_data.output else None
    )
    db.add(clip)
    db.commit()

    return {"message": "Clip added", "clip_id": clip.id}


@router.delete("/{chapter_id}/timeline/clips/{clip_id}")
async def delete_clip(
    chapter_id: str,
    clip_id: str,
    db: Session = Depends(get_db)
):
    """删除 Clip"""
    timeline = db.query(Timeline).filter(Timeline.chapter_id == chapter_id).first()
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")
    
    clip = db.query(Clip).filter(Clip.id == clip_id, Clip.timeline_id == timeline.id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    
    db.delete(clip)
    db.commit()

    return {"message": "Clip deleted", "clip_id": clip_id}
