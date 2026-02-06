"""
Shot Versions API - 镜头版本管理
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.models import ShotVersion, Panel

router = APIRouter(prefix="/shot-versions", tags=["shot-versions"])


# ============ Schemas ============

class ShotVersionCreate(BaseModel):
    panel_id: str
    shot_spec_json: dict = Field(default_factory=dict)
    style_profile_id: Optional[str] = None
    commit_message: Optional[str] = None


class ShotVersionResponse(BaseModel):
    id: str
    panel_id: str
    version_no: int
    shot_spec_json: dict
    style_profile_id: Optional[str]
    commit_message: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


# ============ Routes ============

@router.get("/panel/{panel_id}", response_model=List[ShotVersionResponse])
async def list_versions(
    panel_id: str,
    db: Session = Depends(get_db)
):
    """获取镜头的所有版本"""
    versions = db.query(ShotVersion).filter(
        ShotVersion.panel_id == panel_id
    ).order_by(ShotVersion.version_no.desc()).all()
    return [_to_response(v) for v in versions]


@router.post("", response_model=ShotVersionResponse)
async def create_version(
    data: ShotVersionCreate,
    db: Session = Depends(get_db)
):
    """创建新版本"""
    panel = db.query(Panel).filter(Panel.id == data.panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")

    # 获取最新版本号
    latest = db.query(ShotVersion).filter(
        ShotVersion.panel_id == data.panel_id
    ).order_by(ShotVersion.version_no.desc()).first()

    version_no = (latest.version_no + 1) if latest else 1

    version = ShotVersion(
        panel_id=data.panel_id,
        version_no=version_no,
        shot_spec_json=data.shot_spec_json,
        style_profile_id=data.style_profile_id,
        commit_message=data.commit_message
    )
    db.add(version)

    # 更新 panel 的 current_version_id
    panel.current_version_id = version.id
    panel.spec_json = data.shot_spec_json

    db.commit()
    db.refresh(version)
    return _to_response(version)


@router.get("/{version_id}", response_model=ShotVersionResponse)
async def get_version(
    version_id: str,
    db: Session = Depends(get_db)
):
    """获取版本详情"""
    version = db.query(ShotVersion).filter(ShotVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return _to_response(version)


@router.post("/{version_id}/restore")
async def restore_version(
    version_id: str,
    db: Session = Depends(get_db)
):
    """恢复到指定版本"""
    version = db.query(ShotVersion).filter(ShotVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    panel = db.query(Panel).filter(Panel.id == version.panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")

    panel.current_version_id = version.id
    panel.spec_json = version.shot_spec_json
    panel.render_status = "draft"

    db.commit()
    return {"status": "ok", "message": f"Restored to version {version.version_no}"}


def _to_response(version: ShotVersion) -> dict:
    return {
        "id": version.id,
        "panel_id": version.panel_id,
        "version_no": version.version_no,
        "shot_spec_json": version.shot_spec_json or {},
        "style_profile_id": version.style_profile_id,
        "commit_message": version.commit_message,
        "created_at": version.created_at.isoformat() if version.created_at else ""
    }
