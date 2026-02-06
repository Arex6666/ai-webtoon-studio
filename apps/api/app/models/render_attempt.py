"""
RenderAttempt Model - 渲染尝试记录
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.models.base import Base
import uuid
from datetime import datetime


class RenderAttempt(Base):
    """渲染尝试记录 - 追踪每次渲染尝试"""
    __tablename__ = "render_attempts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    render_job_id = Column(String(36), ForeignKey("render_jobs.id"), nullable=False)

    # 尝试次数
    attempt_no = Column(Integer, nullable=False, default=1)

    # 时间
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

    # 错误类型
    # oom/kernel/provider_timeout/prompt_invalid/qa_low
    error_type = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)

    # 日志路径
    logs_path = Column(String(512), nullable=True)

    # 关系
    render_job = relationship("RenderJob", back_populates="attempts")

    def __repr__(self):
        return f"<RenderAttempt {self.id}: Job {self.render_job_id} #{self.attempt_no}>"
