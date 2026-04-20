"""
Versions API - 版本管理路由 (E3: Persistent Version Tree)
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
import logging

from app.db.database import get_db
from app.services.graph.version_manager import VersionManager, Snapshot, DiffResult
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


class SnapshotResponse(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    snapshot_type: str
    reason: Optional[str]
    content_hash: Optional[str]
    parent_id: Optional[str]
    created_at: str


class RollbackRequest(BaseModel):
    created_by: Optional[str] = "user"


def get_version_manager(db: Session = Depends(get_db)) -> VersionManager:
    return VersionManager(db)


@router.get("/{entity_type}/{entity_id}/snapshots")
async def list_snapshots(
    entity_type: str,
    entity_id: str,
    limit: int = 20,
    vm: VersionManager = Depends(get_version_manager),
    current_user: User = Depends(get_current_user),
):
    """List snapshots for an entity."""
    snapshots = vm.list_snapshots(entity_id, limit=limit, entity_type=entity_type)
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "snapshots": [
            {
                "id": s.id,
                "snapshot_type": s.snapshot_type.value if hasattr(s.snapshot_type, 'value') else s.snapshot_type,
                "reason": s.reason,
                "content_hash": s.content_hash,
                "parent_id": s.parent_id,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in snapshots
        ],
        "total": len(snapshots),
    }


@router.get("/snapshots/{snapshot_id}")
async def get_snapshot(
    snapshot_id: str,
    vm: VersionManager = Depends(get_version_manager),
    current_user: User = Depends(get_current_user),
):
    """Get a specific snapshot with full data."""
    snapshot = vm.get_snapshot(snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return {
        "id": snapshot.id,
        "entity_type": snapshot.entity_type,
        "entity_id": snapshot.entity_id,
        "snapshot_type": snapshot.snapshot_type.value if hasattr(snapshot.snapshot_type, 'value') else snapshot.snapshot_type,
        "reason": snapshot.reason,
        "content_hash": snapshot.content_hash,
        "parent_id": snapshot.parent_id,
        "data": snapshot.data,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
    }


@router.get("/snapshots/{id1}/diff/{id2}")
async def diff_snapshots(
    id1: str,
    id2: str,
    vm: VersionManager = Depends(get_version_manager),
    current_user: User = Depends(get_current_user),
):
    """Compute diff between two snapshots."""
    diff = vm.get_diff(id1, id2)
    if not diff:
        raise HTTPException(status_code=404, detail="One or both snapshots not found")
    return diff.model_dump()


@router.post("/{entity_type}/{entity_id}/rollback/{snapshot_id}")
async def rollback_to_snapshot(
    entity_type: str,
    entity_id: str,
    snapshot_id: str,
    body: Optional[RollbackRequest] = None,
    vm: VersionManager = Depends(get_version_manager),
    current_user: User = Depends(get_current_user),
):
    """Rollback an entity to a specific snapshot."""
    data = vm.rollback_to(entity_id, snapshot_id, entity_type=entity_type)
    if data is None:
        raise HTTPException(status_code=404, detail="Snapshot not found or does not match entity")
    return {
        "success": True,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "rolled_back_to": snapshot_id,
        "data": data,
    }
