"""GET/POST/DELETE /v1/skills/* — skill installation management."""
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.skill_installation import SkillInstallation
from app.services.agent.skills import installer, lifecycle

router = APIRouter(prefix="/v1/skills", tags=["Skills"])


class SkillOut(BaseModel):
    id: str
    name: str
    version: str
    source_type: str
    source_url: Optional[str]
    status: str
    scope: str
    project_id: Optional[str]
    manifest_json: dict

    class Config:
        from_attributes = True


@router.get("", response_model=list[SkillOut])
def list_skills(
    scope: Optional[str] = None,
    project_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(SkillInstallation).filter(SkillInstallation.status != "uninstalled")
    if scope:
        q = q.filter(SkillInstallation.scope == scope)
    if project_id:
        q = q.filter(SkillInstallation.project_id == project_id)
    return q.order_by(SkillInstallation.installed_at.desc()).all()


class InstallRequest(BaseModel):
    source_type: Literal["local", "url", "git"]
    source: str
    scope: Literal["global", "project"] = "project"
    project_id: Optional[str] = None


@router.post("/install", response_model=SkillOut)
def install(req: InstallRequest, db: Session = Depends(get_db)):
    try:
        if req.source_type == "local":
            inst = installer.install_local(db, req.source, scope=req.scope, project_id=req.project_id)
        elif req.source_type == "url":
            inst = installer.install_url(db, req.source, scope=req.scope, project_id=req.project_id)
        elif req.source_type == "git":
            inst = installer.install_git(db, req.source, scope=req.scope, project_id=req.project_id)
    except Exception as e:
        raise HTTPException(400, str(e))
    return inst


@router.post("/{skill_id}/enable", response_model=SkillOut)
def enable_skill(skill_id: str, db: Session = Depends(get_db)):
    try:
        return lifecycle.enable(db, skill_id)
    except Exception as e:
        raise HTTPException(400, str(e))


@router.post("/{skill_id}/disable", response_model=SkillOut)
def disable_skill(skill_id: str, db: Session = Depends(get_db)):
    return lifecycle.disable(db, skill_id)


@router.delete("/{skill_id}")
def uninstall_skill(skill_id: str, db: Session = Depends(get_db)):
    lifecycle.uninstall(db, skill_id)
    return {"ok": True}
