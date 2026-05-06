"""
ConversationMessage Model - 对话消息模型
"""
from sqlalchemy import Column, String, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
import uuid

from app.models.base import Base, TimestampMixin


class ConversationMessage(Base, TimestampMixin):
    """对话消息"""
    __tablename__ = "conversation_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)

    # 消息内容
    role = Column(String, nullable=False)  # user, assistant, system, tool
    content = Column(Text, nullable=False)
    content_type = Column(String, nullable=False, default="text")  # text, image, asset_preview, panel_preview

    # 元数据
    intent = Column(String, nullable=True)  # 检测到的意图
    entities_json = Column(JSON, nullable=True, default=dict)  # 提取的实体（角色、场景等）
    tool_calls_json = Column(JSON, nullable=True, default=list)  # 智能体调用的工具
    tool_results_json = Column(JSON, nullable=True, default=list)  # 工具执行结果

    # LLM追踪
    model_used = Column(String, nullable=True)  # 使用的模型
    tokens_used = Column(Integer, nullable=False, default=0)
    latency_ms = Column(Integer, nullable=True)  # 响应延迟（毫秒）

    # B-1 tracing + finish reason
    trace_id = Column(String(64), nullable=True, index=True)
    finish_reason = Column(String(32), nullable=True)
    # finish_reason values: stop | tool_calls | length | content_filter | error

    # 关系
    conversation = relationship("Conversation", back_populates="messages")
    triggered_actions = relationship("ConversationAction", back_populates="message")

    def __repr__(self):
        return f"<ConversationMessage {self.id} role={self.role} intent={self.intent}>"
