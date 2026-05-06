"""
ConversationAction Model - 对话触发的动作模型
"""
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
import uuid

from app.models.base import Base, TimestampMixin


class ConversationAction(Base, TimestampMixin):
    """对话触发的动作"""
    __tablename__ = "conversation_actions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    message_id = Column(String, ForeignKey("conversation_messages.id"), nullable=False)

    # 动作详情
    action_type = Column(String, nullable=False)  # create_asset, generate_storyboard, render_panel, analyze_quality
    action_params_json = Column(JSON, nullable=True, default=dict)  # 动作参数

    # 执行追踪
    status = Column(String, nullable=False, default="pending")  # pending, running, completed, failed, dispatched
    job_id = Column(String, ForeignKey("jobs.id"), nullable=True)  # 关联的Job（如果有）— Celery 派发亦走此字段
    result_json = Column(JSON, nullable=True, default=dict)  # 执行结果
    error_json = Column(JSON, nullable=True, default=dict)  # 错误信息

    # B-1 tracing + skill provenance
    trace_id = Column(String(64), nullable=True, index=True)
    skill_id = Column(String(64), nullable=True, index=True)
    # skill_id values: "builtin" | "mcp:{conn_id}" | "skill:{install_id}"

    # 关系
    conversation = relationship("Conversation", back_populates="actions")
    message = relationship("ConversationMessage", back_populates="triggered_actions")
    job = relationship("Job", foreign_keys=[job_id])

    def __repr__(self):
        return f"<ConversationAction {self.id} type={self.action_type} status={self.status}>"
