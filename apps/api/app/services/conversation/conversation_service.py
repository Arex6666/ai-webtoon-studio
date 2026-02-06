"""
ConversationService - 对话服务
处理对话的 CRUD 操作和消息管理
"""
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime

from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.conversation_action import ConversationAction
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationWithMessages,
    ConversationMessageCreate,
    ConversationMessageResponse,
    ConversationActionCreate,
    ConversationActionResponse,
)

logger = logging.getLogger(__name__)


class ConversationService:
    """对话服务"""

    def __init__(self, db: Session):
        self.db = db

    # ========== Conversation CRUD ==========

    def create_conversation(self, data: ConversationCreate) -> Conversation:
        """创建新对话"""
        conversation = Conversation(
            project_id=data.project_id,
            chapter_id=data.chapter_id,
            episode_number=data.episode_number,  # 分集编号
            title=data.title,
            status="active",
            message_count=0,
            total_tokens_used=0,
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        logger.info(f"Created conversation {conversation.id} for project {data.project_id} episode {data.episode_number}")
        return conversation

    def get_or_create_episode_conversation(
        self, 
        project_id: str, 
        episode_number: int
    ) -> Conversation:
        """获取或创建分集对话
        
        如果该分集已有对话则返回现有的，否则创建新的
        """
        # 查找现有的分集对话
        existing = (
            self.db.query(Conversation)
            .filter(
                Conversation.project_id == project_id,
                Conversation.episode_number == episode_number,
                Conversation.status != "archived"
            )
            .first()
        )
        
        if existing:
            logger.info(f"Found existing conversation {existing.id} for project {project_id} episode {episode_number}")
            return existing
        
        # 创建新的分集对话
        from app.schemas.conversation import ConversationCreate
        data = ConversationCreate(
            project_id=project_id,
            episode_number=episode_number,
            title=f"第{episode_number}集对话"
        )
        return self.create_conversation(data)

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """获取对话"""
        return self.db.query(Conversation).filter(Conversation.id == conversation_id).first()

    def get_conversation_with_messages(
        self, conversation_id: str, limit: int = 50, offset: int = 0
    ) -> Optional[ConversationWithMessages]:
        """获取对话及其消息"""
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return None

        # 获取消息（按时间倒序，最新的在前）
        messages = (
            self.db.query(ConversationMessage)
            .filter(ConversationMessage.conversation_id == conversation_id)
            .order_by(desc(ConversationMessage.created_at))
            .limit(limit)
            .offset(offset)
            .all()
        )

        # 获取动作
        actions = (
            self.db.query(ConversationAction)
            .filter(ConversationAction.conversation_id == conversation_id)
            .order_by(desc(ConversationAction.created_at))
            .all()
        )

        return ConversationWithMessages(
            **conversation.__dict__,
            messages=[ConversationMessageResponse.from_orm(m) for m in reversed(messages)],
            actions=[ConversationActionResponse.from_orm(a) for a in actions],
        )

    def list_conversations(
        self,
        project_id: Optional[str] = None,
        chapter_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Conversation]:
        """列出对话"""
        query = self.db.query(Conversation)

        if project_id:
            query = query.filter(Conversation.project_id == project_id)
        if chapter_id:
            query = query.filter(Conversation.chapter_id == chapter_id)
        if status:
            query = query.filter(Conversation.status == status)

        return query.order_by(desc(Conversation.updated_at)).limit(limit).offset(offset).all()

    def update_conversation(
        self, conversation_id: str, data: ConversationUpdate
    ) -> Optional[Conversation]:
        """更新对话"""
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return None

        update_data = data.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(conversation, key, value)

        self.db.commit()
        self.db.refresh(conversation)
        logger.info(f"Updated conversation {conversation_id}")
        return conversation

    def delete_conversation(self, conversation_id: str) -> bool:
        """删除对话（软删除，设置为 archived）"""
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return False

        conversation.status = "archived"
        self.db.commit()
        logger.info(f"Archived conversation {conversation_id}")
        return True

    # ========== Message Operations ==========

    def add_message(self, data: ConversationMessageCreate) -> ConversationMessage:
        """添加消息"""
        message = ConversationMessage(
            conversation_id=data.conversation_id,
            role=data.role,
            content=data.content,
            content_type=data.content_type,
            intent=data.intent,
            entities_json=data.entities_json or {},
            tool_calls_json=data.tool_calls_json or [],
            tool_results_json=data.tool_results_json or [],
            model_used=data.model_used,
            tokens_used=data.tokens_used,
            latency_ms=data.latency_ms,
        )
        self.db.add(message)

        # 更新对话统计
        conversation = self.get_conversation(data.conversation_id)
        if conversation:
            conversation.message_count += 1
            conversation.total_tokens_used += data.tokens_used

        self.db.commit()
        self.db.refresh(message)
        logger.info(f"Added message {message.id} to conversation {data.conversation_id}")
        return message

    def get_messages(
        self, conversation_id: str, limit: int = 50, offset: int = 0
    ) -> List[ConversationMessage]:
        """获取对话消息"""
        return (
            self.db.query(ConversationMessage)
            .filter(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at)
            .limit(limit)
            .offset(offset)
            .all()
        )

    def get_recent_messages(
        self, conversation_id: str, count: int = 10
    ) -> List[ConversationMessage]:
        """获取最近的消息（用于上下文）"""
        return (
            self.db.query(ConversationMessage)
            .filter(ConversationMessage.conversation_id == conversation_id)
            .order_by(desc(ConversationMessage.created_at))
            .limit(count)
            .all()
        )

    def delete_message(self, message_id: str) -> bool:
        """删除消息"""
        message = self.db.query(ConversationMessage).filter(ConversationMessage.id == message_id).first()
        if not message:
            return False

        # 更新对话统计
        conversation = self.get_conversation(message.conversation_id)
        if conversation and conversation.message_count > 0:
            conversation.message_count -= 1
            # tokens 统计比较复杂，暂时忽略或只减去该消息的 usage

        self.db.delete(message)
        self.db.commit()
        logger.info(f"Deleted message {message_id}")
        return True

    # ========== Action Operations ==========

    def create_action(self, data: ConversationActionCreate) -> ConversationAction:
        """创建动作"""
        action = ConversationAction(
            conversation_id=data.conversation_id,
            message_id=data.message_id,
            action_type=data.action_type,
            action_params_json=data.action_params_json or {},
            status="pending",
            job_id=data.job_id,
        )
        self.db.add(action)
        self.db.commit()
        self.db.refresh(action)
        logger.info(f"Created action {action.id} type={data.action_type}")
        return action

    def update_action_status(
        self,
        action_id: str,
        status: str,
        result_json: Optional[Dict[str, Any]] = None,
        error_json: Optional[Dict[str, Any]] = None,
    ) -> Optional[ConversationAction]:
        """更新动作状态"""
        action = self.db.query(ConversationAction).filter(ConversationAction.id == action_id).first()
        if not action:
            return None

        action.status = status
        if result_json:
            action.result_json = result_json
        if error_json:
            action.error_json = error_json

        self.db.commit()
        self.db.refresh(action)
        logger.info(f"Updated action {action_id} status={status}")
        return action

    def get_pending_actions(self, conversation_id: str) -> List[ConversationAction]:
        """获取待处理的动作"""
        return (
            self.db.query(ConversationAction)
            .filter(
                ConversationAction.conversation_id == conversation_id,
                ConversationAction.status.in_(["pending", "running"]),
            )
            .all()
        )

    # ========== Context Management ==========

    def get_context(self, conversation_id: str) -> Dict[str, Any]:
        """获取对话上下文"""
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return {}

        # 获取最近的消息作为短期记忆
        recent_messages = self.get_recent_messages(conversation_id, count=10)

        # 构建上下文
        context = {
            "conversation_id": conversation_id,
            "current_intent": conversation.current_intent,
            "context_data": conversation.context_json or {},
            "recent_messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "intent": msg.intent,
                    "entities": msg.entities_json,
                }
                for msg in reversed(recent_messages)
            ],
        }

        return context

    def update_context(
        self, conversation_id: str, context_data: Dict[str, Any], current_intent: Optional[str] = None
    ) -> bool:
        """更新对话上下文"""
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return False

        conversation.context_json = context_data
        if current_intent:
            conversation.current_intent = current_intent

        self.db.commit()
        logger.info(f"Updated context for conversation {conversation_id}")
        return True

    def reset_context(self, conversation_id: str) -> bool:
        """重置对话上下文"""
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return False

        conversation.context_json = {}
        conversation.current_intent = None

        self.db.commit()
        logger.info(f"Reset context for conversation {conversation_id}")
        return True
