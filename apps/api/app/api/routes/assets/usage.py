"""Asset usage lookup — where a given asset is referenced."""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.asset import Asset
from app.models.chapter import Chapter
from app.models.panel import Panel
from app.models.user import User

router = APIRouter()


class UsageReference(BaseModel):
    chapter_id: str
    chapter_title: Optional[str]
    panel_id: str
    panel_order: int
    panel_preview_url: Optional[str] = None


class AssetUsageResponse(BaseModel):
    asset_id: str
    references: List[UsageReference]
    total_count: int


def _panel_references_asset(spec: Dict[str, Any], asset_id: str) -> bool:
    for c in (spec.get("characters") or []):
        if isinstance(c, dict) and c.get("asset_id") == asset_id:
            return True
    if (spec.get("scene") or {}).get("anchor_id") == asset_id:
        return True
    for p in (spec.get("props") or []):
        if isinstance(p, dict) and p.get("asset_id") == asset_id:
            return True
    return False


@router.get("/{asset_id}/usage", response_model=AssetUsageResponse)
def get_asset_usage(
    asset_id: str,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Candidate chapters scoped by asset's project
    chapters = (
        db.query(Chapter).filter(Chapter.project_id == asset.project_id).all()
    )
    chapter_ids = [c.id for c in chapters]
    chapter_title_by_id = {c.id: c.title for c in chapters}

    panels = (
        db.query(Panel)
        .filter(Panel.chapter_id.in_(chapter_ids))
        .order_by(Panel.chapter_id, Panel.order_index)
        .all()
    )

    refs: List[UsageReference] = []
    for p in panels:
        if _panel_references_asset(p.spec_json or {}, asset_id):
            refs.append(
                UsageReference(
                    chapter_id=p.chapter_id,
                    chapter_title=chapter_title_by_id.get(p.chapter_id),
                    panel_id=p.id,
                    panel_order=p.order_index or 0,
                    panel_preview_url=p.preview_url,
                )
            )

    return AssetUsageResponse(
        asset_id=asset_id,
        references=refs[:limit],
        total_count=len(refs),
    )
