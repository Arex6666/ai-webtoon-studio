"""
Studios API - 工作室管理
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.models import Studio

router = APIRouter(prefix="/studios", tags=["studios"])


# ============ Schemas ============

class StudioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    quota_json: dict = Field(default_factory=dict)


class StudioUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    quota_json: Optional[dict] = None
    status: Optional[str] = None


class StudioResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    quota_json: dict
    member_count: int
    status: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


# ============ Routes ============

@router.get("", response_model=List[StudioResponse])
async def list_studios(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """获取工作室列表"""
    studios = db.query(Studio).offset(skip).limit(limit).all()
    return [_to_response(s) for s in studios]


@router.post("", response_model=StudioResponse)
async def create_studio(
    data: StudioCreate,
    db: Session = Depends(get_db)
):
    """创建工作室"""
    studio = Studio(
        name=data.name,
        description=data.description,
        quota_json=data.quota_json
    )
    db.add(studio)
    db.commit()
    db.refresh(studio)
    return _to_response(studio)


@router.get("/{studio_id}", response_model=StudioResponse)
async def get_studio(
    studio_id: str,
    db: Session = Depends(get_db)
):
    """获取工作室详情"""
    studio = db.query(Studio).filter(Studio.id == studio_id).first()
    if not studio:
        raise HTTPException(status_code=404, detail="Studio not found")
    return _to_response(studio)


@router.put("/{studio_id}", response_model=StudioResponse)
async def update_studio(
    studio_id: str,
    data: StudioUpdate,
    db: Session = Depends(get_db)
):
    """更新工作室"""
    studio = db.query(Studio).filter(Studio.id == studio_id).first()
    if not studio:
        raise HTTPException(status_code=404, detail="Studio not found")

    if data.name is not None:
        studio.name = data.name
    if data.description is not None:
        studio.description = data.description
    if data.quota_json is not None:
        studio.quota_json = data.quota_json
    if data.status is not None:
        studio.status = data.status

    db.commit()
    db.refresh(studio)
    return _to_response(studio)


@router.delete("/{studio_id}")
async def delete_studio(
    studio_id: str,
    db: Session = Depends(get_db)
):
    """删除工作室"""
    studio = db.query(Studio).filter(Studio.id == studio_id).first()
    if not studio:
        raise HTTPException(status_code=404, detail="Studio not found")

    db.delete(studio)
    db.commit()
    return {"status": "ok", "message": "Studio deleted"}


def _to_response(studio: Studio) -> dict:
    return {
        "id": studio.id,
        "name": studio.name,
        "description": studio.description,
        "quota_json": studio.quota_json or {},
        "member_count": studio.member_count or 0,
        "status": studio.status or "active",
        "created_at": studio.created_at.isoformat() if studio.created_at else "",
        "updated_at": studio.updated_at.isoformat() if studio.updated_at else ""
    }
