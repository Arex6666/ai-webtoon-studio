"""
Artifact Model - 渲染产物
"""
from sqlalchemy import Column, String, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid


class Artifact(Base, TimestampMixin):
    """渲染产物模型"""
    __tablename__ = "artifacts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    render_job_id = Column(String(36), ForeignKey("render_jobs.id"), nullable=False)

    # 产物类型: full/char/bg/fg/frames/video/manifest
    type = Column(String(50), nullable=False)

    # 文件路径 (MinIO/S3)
    uri = Column(String(512), nullable=False)

    # 元数据: { "width": 1024, "height": 1024, "hash": "...", "fps": 24, "frame_count": 120 }
    meta_json = Column(JSON, nullable=False, default=dict)

    # 关系
    render_job = relationship("RenderJob", back_populates="artifacts")

    def __repr__(self):
        return f"<Artifact {self.id}: {self.type}>"
