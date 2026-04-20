"""
Basic CRUD operations for chapters
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional, Dict, Any
from pydantic import ConfigDict, BaseModel
from datetime import datetime

from app.core.database import get_db
from app.models.chapter import Chapter
from app.models.project import Project
from app.models.revision import Revision
from app.schemas.chapter_layout import ChapterLayout, ReadingFlow
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="")


# Request/Response Models
class ChapterCreate(BaseModel):
    project_id: str
    title: str
    description: Optional[str] = None


class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    order_index: Optional[int] = None


class ChapterResponse(BaseModel):
    id: str
    project_id: str
    title: str
    description: Optional[str]
    order_index: int
    layout_json: Dict[str, Any]
    export_status: str
    exported_url: Optional[str]
    created_at: datetime
    updated_at: datetime
    panel_count: int = 0

    model_config = ConfigDict(from_attributes = True)

class ChapterListResponse(BaseModel):
    items: List[ChapterResponse]
    total: int


# Routes
@router.get("/project/{project_id}", response_model=ChapterListResponse)
async def list_chapters(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取项目的所有章节"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    chapters = db.query(Chapter).options(
        joinedload(Chapter.panels)
    ).filter(
        Chapter.project_id == project_id
    ).order_by(Chapter.order_index).all()

    items = []
    for c in chapters:
        items.append(ChapterResponse(
            id=c.id,
            project_id=c.project_id,
            title=c.title,
            description=c.description,
            order_index=c.order_index,
            layout_json=c.layout_json or {},
            export_status=c.export_status,
            exported_url=c.exported_url,
            created_at=c.created_at,
            updated_at=c.updated_at,
            panel_count=len(c.panels)
        ))

    return ChapterListResponse(items=items, total=len(items))


@router.post("/", response_model=ChapterResponse)
async def create_chapter(
    request: ChapterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建新章节"""
    project = db.query(Project).filter(Project.id == request.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 获取当前最大 order_index
    max_order = db.query(Chapter).filter(
        Chapter.project_id == request.project_id
    ).count()

    # 创建默认 layout
    import uuid
    chapter_id = str(uuid.uuid4())
    default_layout = ChapterLayout(
        chapter_id=chapter_id,
        title=request.title,
        reading_flow=ReadingFlow.VERTICAL,
        panels=[]
    )

    chapter = Chapter(
        id=chapter_id,
        project_id=request.project_id,
        title=request.title,
        description=request.description,
        order_index=max_order,
        layout_json=default_layout.model_dump()
    )
    db.add(chapter)
    db.commit()
    db.refresh(chapter)

    return ChapterResponse(
        id=chapter.id,
        project_id=chapter.project_id,
        title=chapter.title,
        description=chapter.description,
        order_index=chapter.order_index,
        layout_json=chapter.layout_json,
        export_status=chapter.export_status,
        exported_url=chapter.exported_url,
        created_at=chapter.created_at,
        updated_at=chapter.updated_at,
        panel_count=0
    )


@router.get("/{chapter_id}", response_model=ChapterResponse)
async def get_chapter(
    chapter_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取章节详情"""
    chapter = db.query(Chapter).options(
        joinedload(Chapter.panels)
    ).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    return ChapterResponse(
        id=chapter.id,
        project_id=chapter.project_id,
        title=chapter.title,
        description=chapter.description,
        order_index=chapter.order_index,
        layout_json=chapter.layout_json or {},
        export_status=chapter.export_status,
        exported_url=chapter.exported_url,
        created_at=chapter.created_at,
        updated_at=chapter.updated_at,
        panel_count=len(chapter.panels)
    )


@router.put("/{chapter_id}", response_model=ChapterResponse)
async def update_chapter(
    chapter_id: str,
    request: ChapterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新章节基本信息"""
    chapter = db.query(Chapter).options(
        joinedload(Chapter.panels)
    ).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    if request.title is not None:
        chapter.title = request.title
        # 同步更新 layout_json 中的 title
        if chapter.layout_json:
            chapter.layout_json["title"] = request.title
    if request.description is not None:
        chapter.description = request.description
    if request.order_index is not None:
        chapter.order_index = request.order_index

    db.commit()
    db.refresh(chapter)

    return ChapterResponse(
        id=chapter.id,
        project_id=chapter.project_id,
        title=chapter.title,
        description=chapter.description,
        order_index=chapter.order_index,
        layout_json=chapter.layout_json or {},
        export_status=chapter.export_status,
        exported_url=chapter.exported_url,
        created_at=chapter.created_at,
        updated_at=chapter.updated_at,
        panel_count=len(chapter.panels)
    )


@router.put("/{chapter_id}/layout")
async def update_chapter_layout(
    chapter_id: str,
    layout: ChapterLayout,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新章节布局 JSON（Single Source of Truth）
    会自动创建版本记录
    """
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    # 创建版本记录
    revision_count = db.query(Revision).filter(
        Revision.chapter_id == chapter_id
    ).count()

    revision = Revision(
        chapter_id=chapter_id,
        revision_number=revision_count + 1,
        change_type="layout",
        snapshot_json=chapter.layout_json or {},
        description="Layout updated"
    )
    db.add(revision)

    # 更新布局
    chapter.layout_json = layout.model_dump()
    chapter.title = layout.title  # 同步标题

    db.commit()

    return {
        "message": "Layout updated",
        "chapter_id": chapter_id,
        "revision": revision_count + 1
    }


@router.delete("/{chapter_id}")
async def delete_chapter(
    chapter_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除章节"""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    db.delete(chapter)
    db.commit()

    return {"message": "Chapter deleted", "id": chapter_id}
