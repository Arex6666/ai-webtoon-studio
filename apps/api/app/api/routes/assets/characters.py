"""
Character asset routes
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
from app.workers.async_runner import run_portrait_generation

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

@router.post("/{asset_id}/regenerate-reference")
async def regenerate_asset_reference(
    asset_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """重新生成资产参考图"""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    if asset.type != "character":
        raise HTTPException(status_code=400, detail="Only character assets support reference generation")

    # 提取描述信息
    data = asset.data_json or {}
    traits = data.get("appearance_traits", [])

    # Update status immediately
    asset.reference_image_status = "generating"
    db.commit()

    # Trigger generation
    run_portrait_generation.delay(
        character_id=asset.id,
        project_id=asset.project_id,
        character_name=asset.name,
        character_description=asset.description,
        appearance_traits=traits,
        provider="mock",
        db_session=None
    )

    return {"message": "Generation started", "status": "generating"}
