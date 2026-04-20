"""
Music 路由 - 音乐资产管理
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import ConfigDict, BaseModel
from datetime import datetime

from app.core.database import get_db
from app.models.voice_asset import MusicAsset, MusicStatus
from app.services.music.suno_provider import get_suno_provider

router = APIRouter()


# Request/Response Models
class MusicGenerateRequest(BaseModel):
    """生成音乐请求"""
    project_id: str
    name: str
    prompt: str
    style: str = "cinematic"
    duration: int = 30
    genre: Optional[str] = None
    mood: Optional[str] = None


class MusicCreate(BaseModel):
    """创建音乐资产请求"""
    project_id: str
    name: str
    audio_url: Optional[str] = None
    genre: Optional[str] = None
    mood: Optional[str] = None
    duration_sec: Optional[float] = None


class MusicUpdate(BaseModel):
    """更新音乐资产请求"""
    name: Optional[str] = None
    audio_url: Optional[str] = None
    genre: Optional[str] = None
    mood: Optional[str] = None
    status: Optional[str] = None


class MusicResponse(BaseModel):
    """音乐资产响应"""
    id: str
    project_id: str
    name: str
    genre: Optional[str]
    mood: Optional[str]
    duration_sec: Optional[float]
    audio_url: Optional[str]
    provider: str
    generation_prompt: Optional[str]
    status: str
    thumbnail_url: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes = True)

class MusicListResponse(BaseModel):
    items: List[MusicResponse]
    total: int


class MusicGenerateResponse(BaseModel):
    """音乐生成响应"""
    music_id: str
    job_id: Optional[str]
    status: str
    message: str


# Routes

@router.get("/project/{project_id}", response_model=MusicListResponse)
async def list_music_assets(
    project_id: str,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取项目的所有音乐资产"""
    query = db.query(MusicAsset).filter(
        MusicAsset.project_id == project_id,
        MusicAsset.status != "archived"
    )

    if status:
        query = query.filter(MusicAsset.status == status)

    music_assets = query.order_by(MusicAsset.created_at.desc()).all()

    items = [
        MusicResponse(
            id=m.id,
            project_id=m.project_id,
            name=m.name,
            genre=m.genre,
            mood=m.mood,
            duration_sec=m.duration_sec,
            audio_url=m.audio_url,
            provider=m.provider,
            generation_prompt=m.generation_prompt,
            status=m.status,
            thumbnail_url=m.thumbnail_url,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
        for m in music_assets
    ]

    return MusicListResponse(items=items, total=len(items))


@router.post("", response_model=MusicResponse)
async def create_music_asset(
    music: MusicCreate,
    db: Session = Depends(get_db)
):
    """创建音乐资产（手动上传）"""
    db_music = MusicAsset(
        project_id=music.project_id,
        name=music.name,
        audio_url=music.audio_url,
        genre=music.genre,
        mood=music.mood,
        duration_sec=music.duration_sec,
        provider="manual",
        status="ready",
    )

    db.add(db_music)
    db.commit()
    db.refresh(db_music)

    return MusicResponse(
        id=db_music.id,
        project_id=db_music.project_id,
        name=db_music.name,
        genre=db_music.genre,
        mood=db_music.mood,
        duration_sec=db_music.duration_sec,
        audio_url=db_music.audio_url,
        provider=db_music.provider,
        generation_prompt=db_music.generation_prompt,
        status=db_music.status,
        thumbnail_url=db_music.thumbnail_url,
        created_at=db_music.created_at,
        updated_at=db_music.updated_at,
    )


@router.post("/generate", response_model=MusicGenerateResponse)
async def generate_music(
    request: MusicGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """生成音乐"""
    # 创建音乐记录
    db_music = MusicAsset(
        project_id=request.project_id,
        name=request.name,
        genre=request.genre,
        mood=request.mood,
        generation_prompt=request.prompt,
        generation_params={
            "style": request.style,
            "duration": request.duration,
        },
        provider="suno_via_comfyui",
        status="generating",
    )

    db.add(db_music)
    db.commit()
    db.refresh(db_music)

    # 异步生成音乐
    from app.workers.async_runner import generate_music_task_celery
    generate_music_task_celery.delay(
        music_id=db_music.id,
        prompt=request.prompt,
        style=request.style,
        duration=request.duration,
    )

    return MusicGenerateResponse(
        music_id=db_music.id,
        job_id=None,
        status="generating",
        message="Music generation started",
    )


async def _generate_music_task(
    music_id: str,
    prompt: str,
    style: str,
    duration: int,
):
    """异步音乐生成任务"""
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        suno_provider = get_suno_provider()
        result = await suno_provider.generate_music(
            prompt=prompt,
            style=style,
            duration=duration,
        )

        # 更新音乐记录
        music = db.query(MusicAsset).filter(MusicAsset.id == music_id).first()
        if music:
            if result.success:
                music.audio_url = result.audio_url
                music.duration_sec = result.duration_sec
                music.job_id = result.job_id
                music.status = "ready"
            else:
                music.status = "failed"

            db.commit()

    except Exception as e:
        logger = __import__("logging").getLogger(__name__)
        logger.error(f"[Music] Generation task failed: {e}")

        # 更新状态为失败
        music = db.query(MusicAsset).filter(MusicAsset.id == music_id).first()
        if music:
            music.status = "failed"
            db.commit()
    finally:
        db.close()


@router.get("/{music_id}", response_model=MusicResponse)
async def get_music_asset(
    music_id: str,
    db: Session = Depends(get_db)
):
    """获取音乐资产详情"""
    music = db.query(MusicAsset).filter(MusicAsset.id == music_id).first()

    if not music:
        raise HTTPException(status_code=404, detail="Music asset not found")

    return MusicResponse(
        id=music.id,
        project_id=music.project_id,
        name=music.name,
        genre=music.genre,
        mood=music.mood,
        duration_sec=music.duration_sec,
        audio_url=music.audio_url,
        provider=music.provider,
        generation_prompt=music.generation_prompt,
        status=music.status,
        thumbnail_url=music.thumbnail_url,
        created_at=music.created_at,
        updated_at=music.updated_at,
    )


@router.put("/{music_id}", response_model=MusicResponse)
async def update_music_asset(
    music_id: str,
    music_update: MusicUpdate,
    db: Session = Depends(get_db)
):
    """更新音乐资产"""
    music = db.query(MusicAsset).filter(MusicAsset.id == music_id).first()

    if not music:
        raise HTTPException(status_code=404, detail="Music asset not found")

    if music_update.name is not None:
        music.name = music_update.name
    if music_update.audio_url is not None:
        music.audio_url = music_update.audio_url
    if music_update.genre is not None:
        music.genre = music_update.genre
    if music_update.mood is not None:
        music.mood = music_update.mood
    if music_update.status is not None:
        music.status = music_update.status

    db.commit()
    db.refresh(music)

    return MusicResponse(
        id=music.id,
        project_id=music.project_id,
        name=music.name,
        genre=music.genre,
        mood=music.mood,
        duration_sec=music.duration_sec,
        audio_url=music.audio_url,
        provider=music.provider,
        generation_prompt=music.generation_prompt,
        status=music.status,
        thumbnail_url=music.thumbnail_url,
        created_at=music.created_at,
        updated_at=music.updated_at,
    )


@router.delete("/{music_id}")
async def delete_music_asset(
    music_id: str,
    db: Session = Depends(get_db)
):
    """删除音乐资产"""
    music = db.query(MusicAsset).filter(MusicAsset.id == music_id).first()

    if not music:
        raise HTTPException(status_code=404, detail="Music asset not found")

    # 软删除
    music.status = "archived"
    db.commit()

    return {"message": "Music asset deleted", "id": music_id}
