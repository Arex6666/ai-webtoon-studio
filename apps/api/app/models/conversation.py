"""
Conversation Model - 对话会话模型
"""
from sqlalchemy import Column, String, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
import uuid

from app.models.base import Base, TimestampMixin


class Conversation(Base, TimestampMixin):
    """对话会话"""
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # 关联关系
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    chapter_id = Column(String, ForeignKey("chapters.id"), nullable=True)
    episode_number = Column(Integer, nullable=True)  # 分集编号，用于分集对话持久化

    # 基本信息
    title = Column(String, nullable=False)  # 对话标题（自动生成或用户设置）
    status = Column(String, nullable=False, default="active")  # active, paused, completed, archived

    # 上下文追踪
    current_intent = Column(String, nullable=True)  # script, asset, render, qa, general
    context_json = Column(JSON, nullable=True, default=dict)  # 活跃上下文（实体引用等）

    # 统计信息
    message_count = Column(Integer, nullable=False, default=0)
    total_tokens_used = Column(Integer, nullable=False, default=0)

    # 关系
    project = relationship("Project", back_populates="conversations")
    messages = relationship("ConversationMessage", back_populates="conversation", cascade="all, delete-orphan")
    actions = relationship("ConversationAction", back_populates="conversation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Conversation {self.id} '{self.title}' status={self.status}>"
