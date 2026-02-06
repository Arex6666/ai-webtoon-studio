"""
RenderJob Model - 渲染任务
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON, Float, DateTime
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid
import enum
from datetime import datetime


class JobType(str, enum.Enum):
    """任务类型"""
    LAYER_GENERATION = "layer_generation"
    TYPESET = "typeset"
    COMPOSE = "compose"
    QA_CHECK = "qa_check"
    FULL_RENDER = "full_render"      # R0
    CHAR_CUTOUT = "char_cutout"      # R1
    BG_INPAINT = "bg_inpaint"        # R2
    FG_FX = "fg_fx"                  # R3


class JobStatus(str, enum.Enum):
    """任务状态"""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    NEEDS_FIX = "needs_fix"


class RenderJob(Base, TimestampMixin):
    """渲染任务模型"""
    __tablename__ = "render_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    shot_version_id = Column(String(36), nullable=True)
    panel_id = Column(String(36), ForeignKey("panels.id"), nullable=True)
    chapter_id = Column(String(36), nullable=True)

    # 引擎: comfyui / video_provider
    engine = Column(String(50), default="comfyui")

    # 渲染档位: fast/normal/hero
    tier = Column(String(50), default="normal")

    # 任务信息
    job_type = Column(String(50), nullable=False)
    status = Column(String(50), default="pending")
    priority = Column(Integer, default=0)

    # 幂等键
    idempotency_key = Column(String(255), nullable=True)

    # 进度
    progress = Column(Float, default=0)
    current_step = Column(String(255), nullable=True)

    # Payload JSON (ComfyUI workflow 或 provider payload)
    payload_json = Column(JSON, nullable=True)

    # 输入参数
    input_params = Column(JSON, nullable=False, default=dict)

    # 输出结果
    output_data = Column(JSON, nullable=True)
    result_url = Column(String(512), nullable=True)

    # 错误信息
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # 时间
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # 关系
    panel = relationship("Panel", back_populates="render_jobs")
    attempts = relationship("RenderAttempt", back_populates="render_job", cascade="all, delete-orphan")
    artifacts = relationship("Artifact", back_populates="render_job", cascade="all, delete-orphan")
    qa_reports = relationship("QAReport", back_populates="render_job", cascade="all, delete-orphan")
    fix_plans = relationship("FixPlan", back_populates="render_job", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<RenderJob {self.id}: {self.job_type} ({self.status})>"
