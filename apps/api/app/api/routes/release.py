"""
发布路由 - Release API
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime
import uuid
import json
import logging

from app.db.database import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


# ============ Schemas ============

class ReleaseCreateRequest(BaseModel):
    release_version: str
    notes: Optional[str] = None


class ReleaseResponse(BaseModel):
    id: str
    chapter_id: str
    release_version: str
    bundle_url: str
    export_spec_url: Optional[str]
    qa_report_url: Optional[str]
    generated_at: str
    notes: Optional[str]


class ReleaseListItem(BaseModel):
    id: str
    release_version: str
    generated_at: str


class ReleaseListResponse(BaseModel):
    items: List[ReleaseListItem]
    total: int


# ============ In-memory Release Store (for mock) ============

_release_store: Dict[str, List[Dict[str, Any]]] = {}


@router.post("/{chapter_id}/release", response_model=ReleaseResponse)
async def create_release(
    chapter_id: str,
    request: ReleaseCreateRequest,
    db: Session = Depends(get_db)
):
    """创建发布版本"""
    now = datetime.utcnow().isoformat()
    release_id = f"release-{uuid.uuid4().hex[:12]}"
    
    release = {
        "id": release_id,
        "chapter_id": chapter_id,
        "release_version": request.release_version,
        "bundle_url": f"https://storage.example.com/releases/{chapter_id}/{release_id}/bundle.json",
        "export_spec_url": f"https://storage.example.com/releases/{chapter_id}/{release_id}/export_spec.json",
        "qa_report_url": f"https://storage.example.com/releases/{chapter_id}/{release_id}/qa_report.json",
        "generated_at": now,
        "notes": request.notes,
    }
    
    if chapter_id not in _release_store:
        _release_store[chapter_id] = []
    
    _release_store[chapter_id].append(release)
    
    logger.info(f"Release created for chapter {chapter_id}: {request.release_version}")
    
    return ReleaseResponse(**release)


@router.get("/{chapter_id}/release/latest", response_model=ReleaseResponse)
async def get_latest_release(chapter_id: str, db: Session = Depends(get_db)):
    """获取最新发布版本"""
    if chapter_id not in _release_store or len(_release_store[chapter_id]) == 0:
        raise HTTPException(status_code=404, detail="No releases found")
    
    latest = _release_store[chapter_id][-1]
    return ReleaseResponse(**latest)


@router.get("/{chapter_id}/releases", response_model=ReleaseListResponse)
async def list_releases(chapter_id: str, db: Session = Depends(get_db)):
    """列出所有发布版本"""
    if chapter_id not in _release_store:
        return ReleaseListResponse(items=[], total=0)
    
    releases = _release_store[chapter_id]
    return ReleaseListResponse(
        items=[
            ReleaseListItem(
                id=r["id"],
                release_version=r["release_version"],
                generated_at=r["generated_at"]
            )
            for r in releases
        ],
        total=len(releases)
    )


@router.get("/{chapter_id}/release/{release_id}", response_model=ReleaseResponse)
async def get_release(chapter_id: str, release_id: str, db: Session = Depends(get_db)):
    """获取指定发布版本"""
    if chapter_id not in _release_store:
        raise HTTPException(status_code=404, detail="Chapter releases not found")
    
    for release in _release_store[chapter_id]:
        if release["id"] == release_id:
            return ReleaseResponse(**release)
    
    raise HTTPException(status_code=404, detail="Release not found")
