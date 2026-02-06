"""
Export Model - 导出记录
"""
from sqlalchemy import Column, String, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid


class Export(Base, TimestampMixin):
    """导出记录模型"""
    __tablename__ = "exports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chapter_id = Column(String(36), ForeignKey("chapters.id"), nullable=False)

    # 导出类型: strip_png/micro_mp4/full_video
    type = Column(String(50), nullable=False)

    # 状态: queued/running/succeeded/failed
    state = Column(String(50), default="queued")

    # 设置: { "resolution": "1080x1920", "fps": 24, "subtitle_style": "..." }
    settings_json = Column(JSON, nullable=False, default=dict)

    # 输出路径
    output_uri = Column(String(512), nullable=True)

    # 关系
    chapter = relationship("Chapter", back_populates="exports")
    jobs = relationship("ExportJob", back_populates="export", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Export {self.id}: {self.type} ({self.state})>"
