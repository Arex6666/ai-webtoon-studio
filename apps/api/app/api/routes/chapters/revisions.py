"""
Revision operations for chapters
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.chapter import Chapter
from app.models.revision import Revision
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/{chapter_id}/revisions")
async def list_revisions(
    chapter_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取章节的版本历史"""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    revisions = db.query(Revision).filter(
        Revision.chapter_id == chapter_id
    ).order_by(Revision.revision_number.desc()).all()

    return {
        "chapter_id": chapter_id,
        "revisions": [
            {
                "id": r.id,
                "revision_number": r.revision_number,
                "change_type": r.change_type,
                "description": r.description,
                "created_at": r.created_at
            }
            for r in revisions
        ]
    }


@router.post("/{chapter_id}/revisions/{revision_id}/rollback")
async def rollback_to_revision(
    chapter_id: str,
    revision_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """回滚到指定版本"""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    revision = db.query(Revision).filter(
        Revision.id == revision_id,
        Revision.chapter_id == chapter_id
    ).first()
    if not revision:
        raise HTTPException(status_code=404, detail="Revision not found")

    # 先保存当前版本
    revision_count = db.query(Revision).filter(
        Revision.chapter_id == chapter_id
    ).count()

    new_revision = Revision(
        chapter_id=chapter_id,
        revision_number=revision_count + 1,
        change_type="rollback",
        snapshot_json=chapter.layout_json or {},
        description=f"Rollback to revision {revision.revision_number}"
    )
    db.add(new_revision)

    # 恢复到指定版本
    chapter.layout_json = revision.snapshot_json

    db.commit()

    return {
        "message": f"Rolled back to revision {revision.revision_number}",
        "new_revision": revision_count + 1
    }
