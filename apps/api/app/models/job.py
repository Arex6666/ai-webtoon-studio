"""
Job Model - 统一任务模型
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON, Float, DateTime
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
from datetime import datetime
import uuid


class Job(Base, TimestampMixin):
    """统一任务模型 - 支持 image/anchor/video/export"""
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # 任务类型: image_job, anchor_job, video_job, export_job
    type = Column(String(50), nullable=False)
    
    # 关联 ID
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True)
    chapter_id = Column(String(36), ForeignKey("chapters.id"), nullable=True)
    panel_id = Column(String(36), ForeignKey("panels.id"), nullable=True)
    clip_id = Column(String(36), nullable=True)  # 对于视频任务

    # Celery task id (AsyncResult.id) — used by cancel_job to revoke the running
    # task. Kept distinct from `id` (the internal Job UUID) because Celery's
    # control plane only knows tasks by their AsyncResult.id, not our DB pk.
    celery_task_id = Column(String(255), nullable=True, index=True)

    # 执行配置
    provider = Column(String(50), default="mock")
    attempt = Column(Integer, default=1)
    max_attempts = Column(Integer, default=3)

    # 状态: queued, running, succeeded, failed, needs_fix, canceled
    status = Column(String(50), default="queued")
    progress = Column(Float, default=0.0)
    eta_seconds = Column(Integer, nullable=True)

    # 时间戳
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    # 成本
    cost_estimated = Column(Float, default=0.0)
    cost_used = Column(Float, default=0.0)

    # 输入参数 JSON
    inputs_json = Column(JSON, nullable=False, default=dict)

    # 输出结果 JSON
    outputs_json = Column(JSON, nullable=True)

    # QA 结果 JSON
    qa_json = Column(JSON, nullable=True)

    # 错误信息 JSON
    error_json = Column(JSON, nullable=True)

    # 关系
    project = relationship("Project", back_populates="jobs")
    chapter = relationship("Chapter", back_populates="jobs")
    panel = relationship("Panel", back_populates="jobs")

    def __repr__(self):
        return f"<Job {self.id} type={self.type} status={self.status}>"

    def start(self):
        """开始执行"""
        self.status = "running"
        self.started_at = datetime.utcnow()

    def succeed(self, outputs: dict):
        """标记成功"""
        self.status = "succeeded"
        self.progress = 1.0
        self.outputs_json = outputs
        self.finished_at = datetime.utcnow()

    def fail(self, error: dict):
        """标记失败"""
        self.status = "failed"
        self.error_json = error
        self.finished_at = datetime.utcnow()

    def needs_fix(self, qa_result: dict):
        """标记需要修复"""
        self.status = "needs_fix"
        self.qa_json = qa_result
        self.finished_at = datetime.utcnow()

    def cancel(self):
        """取消任务"""
        self.status = "canceled"
        self.finished_at = datetime.utcnow()
