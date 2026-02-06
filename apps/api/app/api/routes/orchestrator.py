"""
Studio Orchestrator API Routes
Chat Studio 统一后端接口
"""
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.orchestrator.studio_orchestrator import (
    StudioOrchestrator,
    OrchestratorResult,
    SessionState
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orchestrator", tags=["Studio Orchestrator"])

# 简单的单例模式存储 orchestrator 实例 (生产环境应使用依赖注入容器或Redis)
_orchestrators: Dict[str, StudioOrchestrator] = {}

def get_orchestrator(project_id: str) -> StudioOrchestrator:
    """获取指定项目的编排器实例"""
    if project_id not in _orchestrators:
        _orchestrators[project_id] = StudioOrchestrator(project_id)
    return _orchestrators[project_id]

class ChatRequest(BaseModel):
    message: str
    session_id: str

class CreateStoryboardRequest(BaseModel):
    prompt: str
    session_id: str

class ModifyStoryboardRequest(BaseModel):
    instruction: str
    session_id: str

@router.post("/sessions/{session_id}", response_model=SessionState)
async def create_or_get_session(
    session_id: str,
    project_id: str = Body(..., embed=True),
):
    """创建或获取会话"""
    orchestrator = get_orchestrator(project_id)
    session = orchestrator.get_session(session_id)
    if not session:
        session = orchestrator.create_session(session_id)
    return session

@router.get("/sessions/{session_id}/status", response_model=Dict[str, Any])
async def get_session_status(
    session_id: str,
    project_id: str,
):
    """获取会话状态"""
    orchestrator = get_orchestrator(project_id)
    return orchestrator.get_workflow_status(session_id)

@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    project_id: str = Body(..., embed=True),
):
    """流式对话接口"""
    orchestrator = get_orchestrator(project_id)
    
    async def event_generator():
        async for chunk in orchestrator.process_message(request.session_id, request.message):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )

@router.post("/storyboard/create", response_model=OrchestratorResult)
async def create_storyboard(
    request: CreateStoryboardRequest,
    project_id: str = Body(..., embed=True),
):
    """创建分镜"""
    orchestrator = get_orchestrator(project_id)
    return await orchestrator.create_storyboard(request.session_id, request.prompt)

@router.post("/storyboard/modify", response_model=OrchestratorResult)
async def modify_storyboard(
    request: ModifyStoryboardRequest,
    project_id: str = Body(..., embed=True),
):
    """修改分镜"""
    orchestrator = get_orchestrator(project_id)
    return await orchestrator.modify_storyboard(request.session_id, request.instruction)

@router.post("/assets/bind", response_model=OrchestratorResult)
async def bind_assets(
    session_id: str = Body(..., embed=True),
    project_id: str = Body(..., embed=True),
):
    """触发资产绑定"""
    orchestrator = get_orchestrator(project_id)
    return await orchestrator.bind_assets(session_id)

@router.post("/render/plan", response_model=OrchestratorResult)
async def create_render_plan(
    session_id: str = Body(..., embed=True),
    project_id: str = Body(..., embed=True),
    panel_ids: Optional[List[str]] = Body(None),
):
    """生成渲染计划"""
    orchestrator = get_orchestrator(project_id)
    return await orchestrator.prepare_render(session_id, panel_ids)
