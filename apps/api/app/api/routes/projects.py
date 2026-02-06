"""
项目管理路由
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import json
import logging

from app.core.database import get_db
from app.models.project import Project
from app.services.brain.standard_llm import StandardLLMService

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    creation_method: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_archived: Optional[bool] = None
    creation_method: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    cover_image: Optional[str]
    is_archived: bool
    creation_method: str
    created_at: datetime
    updated_at: datetime
    chapter_count: int = 0

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    items: List[ProjectResponse]
    total: int


class AutoNameRequest(BaseModel):
    """项目 AI 命名请求

    支持基于：
    - outline_text: 策划大纲
    - script_text: 最终剧本

    推荐在“确认剧本”后传入 script_text。
    """

    outline_text: Optional[str] = None
    script_text: Optional[str] = None


class AutoNameResponse(BaseModel):
    project_id: str
    name: str


# Routes
@router.get("", response_model=ProjectListResponse)
async def list_projects(
    skip: int = 0,
    limit: int = 20,
    archived: bool = False,
    db: Session = Depends(get_db)
):
    """获取项目列表"""
    query = db.query(Project).filter(Project.is_archived == archived)
    total = query.count()
    projects = query.order_by(Project.updated_at.desc()).offset(skip).limit(limit).all()

    items = []
    for p in projects:
        item = ProjectResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            cover_image=p.cover_image,
            is_archived=p.is_archived,
            creation_method=p.creation_method,
            created_at=p.created_at,
            updated_at=p.updated_at,
            chapter_count=len(p.chapters)
        )
        items.append(item)

    return ProjectListResponse(items=items, total=total)


@router.post("", response_model=ProjectResponse)
async def create_project(
    request: ProjectCreate,
    db: Session = Depends(get_db)
):
    """创建新项目"""
    project = Project(
        name=request.name,
        description=request.description,
        creation_method=request.creation_method or "agent",
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        cover_image=project.cover_image,
        is_archived=project.is_archived,
        creation_method=project.creation_method,
        created_at=project.created_at,
        updated_at=project.updated_at,
        chapter_count=0
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: Session = Depends(get_db)
):
    """获取项目详情"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        cover_image=project.cover_image,
        is_archived=project.is_archived,
        creation_method=project.creation_method,
        created_at=project.created_at,
        updated_at=project.updated_at,
        chapter_count=len(project.chapters)
    )


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    request: ProjectUpdate,
    db: Session = Depends(get_db)
):
    """更新项目"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if request.name is not None:
        project.name = request.name
    if request.description is not None:
        project.description = request.description
    if request.is_archived is not None:
        project.is_archived = request.is_archived

    db.commit()
    db.refresh(project)

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        cover_image=project.cover_image,
        is_archived=project.is_archived,
        creation_method=project.creation_method,
        created_at=project.created_at,
        updated_at=project.updated_at,
        chapter_count=len(project.chapters)
    )


@router.post("/{project_id}/auto-name", response_model=AutoNameResponse)
async def auto_name_project(
    project_id: str,
    request: AutoNameRequest,
    db: Session = Depends(get_db)
):
    """基于大纲/剧本为项目自动命名，并写回 Project.name。

    优先使用 script_text，其次 outline_text。
    """

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    source_text = (request.script_text or "").strip() or (request.outline_text or "").strip()
    if not source_text:
        raise HTTPException(status_code=400, detail="script_text or outline_text is required")

    llm = StandardLLMService()

    system_prompt = (
        "你是一名资深的影视/漫画项目命名编辑。你的任务：为用户的漫剧项目生成一个简洁、有辨识度、适合都市情感韩漫风格的中文标题。\n\n"
        "规则：\n"
        "1) 返回 JSON：{ \"name\": string }，不要返回任何额外文字或 Markdown。\n"
        "2) 标题长度 2-10 个汉字为佳，最多不超过 16 个汉字。\n"
        "3) 不要包含书名号《》、引号、冒号、换行。\n"
        "4) 避免过于泛化的名字（例如：\"我的故事\"、\"爱情故事\"）。\n"
        "5) 若文本中已有明确剧集名称，优先采用并可轻微润色。"
    )

    user_prompt = f"请基于以下内容命名项目：\n\n{source_text}"

    try:
        content = await llm._chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format="json",
        )

        content = content.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(content)
        except Exception:
            import re
            m = re.search(r"\{[\s\S]*\}", content)
            if not m:
                raise
            data = json.loads(m.group(0))

        name = (data.get("name") or "").strip()
        name = name.replace("《", "").replace("》", "").replace("\n", " ").strip()

        if not name:
            raise ValueError("Invalid LLM output: missing name")

        # 简单长度保护
        if len(name) > 16:
            name = name[:16]

        project.name = name
        db.commit()
        db.refresh(project)

        return AutoNameResponse(project_id=project.id, name=project.name)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"auto-name failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    db: Session = Depends(get_db)
):
    """删除项目"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(project)
    db.commit()

    return {"message": "Project deleted", "id": project_id}
