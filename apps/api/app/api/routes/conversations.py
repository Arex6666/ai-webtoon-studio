"""
Conversation API Routes
对话相关的REST API端点
"""
import logging
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.conversation.conversation_service import ConversationService
# B-1 Phase E Batch 2: AgentOrchestrator + IntentRouter and the legacy chat-stream
# REST endpoint + /chat WS handler have been removed. Conversation routes are now
# CRUD-only — chat streaming lives at /v1/agent/chat (SSE).
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    ConversationMessageCreate,
    ConversationMessageResponse,
    ConversationActionResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


def get_conversation_service(db: Session = Depends(get_db)) -> ConversationService:
    """获取对话服务实例"""
    return ConversationService(db)


@router.post("", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    data: ConversationCreate,
    service: ConversationService = Depends(get_conversation_service),
):
    """
    创建新对话

    - **project_id**: 项目ID
    - **chapter_id**: 章节ID（可选）
    - **title**: 对话标题（可选）
    """
    try:
        conversation = service.create_conversation(data)
        return conversation
    except Exception as e:
        logger.error(f"Failed to create conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    service: ConversationService = Depends(get_conversation_service),
):
    """
    获取对话详情

    - **conversation_id**: 对话ID
    """
    conversation = service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.get("/episode/{episode_number}", response_model=ConversationResponse)
async def get_or_create_episode_conversation(
    episode_number: int,
    project_id: str = Query(..., description="项目ID"),
    service: ConversationService = Depends(get_conversation_service),
):
    """
    获取或创建分集对话
    
    如果该分集已有对话则返回现有的，否则创建新的。
    用于分集页面持久化聊天历史。
    
    - **episode_number**: 分集编号
    - **project_id**: 项目ID
    """
    try:
        conversation = service.get_or_create_episode_conversation(
            project_id=project_id,
            episode_number=episode_number
        )
        return conversation
    except Exception as e:
        logger.error(f"Failed to get/create episode conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[ConversationResponse])
async def list_conversations(
    project_id: Optional[str] = Query(None, description="项目ID"),
    status: Optional[str] = Query(None, description="状态筛选"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    service: ConversationService = Depends(get_conversation_service),
):
    """
    获取对话列表

    - **project_id**: 项目ID（可选）
    - **status**: 状态筛选（可选）
    - **limit**: 返回数量
    - **offset**: 偏移量
    """
    try:
        conversations = service.list_conversations(
            project_id=project_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        return conversations
    except Exception as e:
        logger.error(f"Failed to list conversations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}/messages", response_model=List[ConversationMessageResponse])
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    service: ConversationService = Depends(get_conversation_service),
):
    """
    获取对话消息历史

    - **conversation_id**: 对话ID
    - **limit**: 返回数量
    - **offset**: 偏移量
    """
    try:
        messages = service.get_messages(
            conversation_id=conversation_id,
            limit=limit,
            offset=offset,
        )
        return messages
    except Exception as e:
        logger.error(f"Failed to get messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{conversation_id}/messages/save", response_model=dict)
async def save_message(
    conversation_id: str,
    body: dict,
    service: ConversationService = Depends(get_conversation_service),
):
    """
    直接保存消息（不触发AI处理）
    
    用于持久化前端的消息记录，例如Agent对话历史
    
    - **conversation_id**: 对话ID
    - **body.content**: 消息内容
    - **body.role**: 角色 (user, assistant, system)
    - **body.metadata**: 元数据（可选，用于存储卡片信息等）
    """
    try:
        content = body.get("content", "")
        role = body.get("role", "user")
        metadata = body.get("metadata")
        
        if not content:
            raise HTTPException(status_code=400, detail="Content is required")
        
        conversation = service.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Create message using the service
        message_data = ConversationMessageCreate(
            conversation_id=conversation_id,
            role=role,
            content=content,
            content_type="text",
            entities_json=metadata or {},
            tokens_used=0,
        )
        
        message = service.add_message(message_data)
        
        return {
            "success": True,
            "message_id": message.id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/messages/{message_id}", response_model=dict)
async def delete_message(
    message_id: str,
    service: ConversationService = Depends(get_conversation_service),
):
    """
    删除单条消息
    
    - **message_id**: 消息ID
    """
    try:
        success = service.delete_message(message_id)
        if not success:
            raise HTTPException(status_code=404, detail="Message not found")
        
        return {
            "success": True,
            "message": "Message deleted successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{conversation_id}/reset", response_model=dict)
async def reset_conversation(
    conversation_id: str,
    service: ConversationService = Depends(get_conversation_service),
):
    """
    重置对话上下文

    - **conversation_id**: 对话ID
    """
    try:
        service.reset_context(conversation_id)
        return {
            "success": True,
            "message": "Conversation context reset successfully",
        }
    except Exception as e:
        logger.error(f"Failed to reset conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{conversation_id}", response_model=dict)
async def delete_conversation(
    conversation_id: str,
    service: ConversationService = Depends(get_conversation_service),
):
    """
    删除对话（软删除，标记为archived）

    - **conversation_id**: 对话ID
    """
    try:
        success = service.archive_conversation(conversation_id)
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return {
            "success": True,
            "message": "Conversation archived successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}/actions", response_model=List[ConversationActionResponse])
async def get_conversation_actions(
    conversation_id: str,
    status: Optional[str] = Query(None, description="状态筛选"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    service: ConversationService = Depends(get_conversation_service),
):
    """
    获取对话触发的动作列表

    - **conversation_id**: 对话ID
    - **status**: 状态筛选（可选）
    - **limit**: 返回数量
    """
    try:
        actions = service.get_actions(
            conversation_id=conversation_id,
            status=status,
            limit=limit,
        )
        return actions
    except Exception as e:
        logger.error(f"Failed to get actions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}/context", response_model=dict)
async def get_conversation_context(
    conversation_id: str,
    service: ConversationService = Depends(get_conversation_service),
):
    """
    获取对话上下文

    - **conversation_id**: 对话ID
    """
    try:
        context = service.get_context(conversation_id)
        return context
    except Exception as e:
        logger.error(f"Failed to get context: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
