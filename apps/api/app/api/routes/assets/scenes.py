"""
Scene asset routes
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from pydantic import ConfigDict, BaseModel
from datetime import datetime

from app.core.database import get_db
from app.models.asset import Asset
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter()


class AssetResponse(BaseModel):
    id: str
    project_id: str
    name: str
    type: str
    description: Optional[str]
    thumbnail_url: Optional[str]
    data_json: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes = True)

@router.post("/{asset_id}/regenerate-anchor")
async def regenerate_asset_anchor(
    asset_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """S5-SC: 重新生成场景锚点图"""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    if asset.type != "scene":
        raise HTTPException(status_code=400, detail="Only scene assets support anchor generation")

    # 提取场景信息
    data = asset.data_json or {}

    # Update status immediately
    data["anchor_status"] = "generating"
    asset.data_json = data
    db.commit()

    # Trigger generation
    from app.workers.async_runner import run_scene_anchor_generation

    run_scene_anchor_generation.delay(
        scene_id=asset.id,
        project_id=asset.project_id,
        scene_name=asset.name,
        location=data.get("location"),
        time_of_day=data.get("time_of_day"),
        mood=data.get("mood"),
        provider="mock",
        db_session=None
    )

    return {"message": "Anchor generation started", "status": "generating"}
