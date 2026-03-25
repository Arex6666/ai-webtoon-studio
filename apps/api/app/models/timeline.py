"""
Timeline Model - 时间轴
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid


class Timeline(Base, TimestampMixin):
    """章节时间轴模型"""
    __tablename__ = "timelines"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chapter_id = Column(String(36), ForeignKey("chapters.id"), nullable=False, unique=True)

    # 时间轴设置 JSON
    settings_json = Column(JSON, nullable=False, default=lambda: {
        "fps_default": 8,
        "aspect": "9:16",
        "export_preset": "webtoon_vertical"
    })

    # 关系
    chapter = relationship("Chapter", back_populates="timeline")
    clips = relationship("Clip", back_populates="timeline", cascade="all, delete-orphan", order_by="Clip.order_index")

    def __repr__(self):
        return f"<Timeline chapter={self.chapter_id}>"


class Clip(Base, TimestampMixin):
    """视频片段模型"""
    __tablename__ = "clips"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timeline_id = Column(String(36), ForeignKey("timelines.id"), nullable=False)
    panel_id = Column(String(36), ForeignKey("panels.id"), nullable=False)

    # 顺序
    order_index = Column(Integer, default=0)

    # 视频属性
    duration_sec = Column(Float, default=3.0)
    fps = Column(Integer, default=8)

    # 生成配置
    provider = Column(String(50), default="mock")
    motion_prompt = Column(Text, nullable=True)
    motion_mode = Column(String(50), default="single_keyframe")  # single_keyframe/dual_keyframe/image2video
    negative = Column(Text, nullable=True)
    seed = Column(Integer, nullable=True)

    # 关键帧引用
    start_frame_layerpack_id = Column(String(36), nullable=True)
    end_frame_layerpack_id = Column(String(36), nullable=True)

    # 状态
    status = Column(String(50), default="Draft")  # Draft/Queued/Running/Rendered/Failed
    progress = Column(Float, default=0.0)

    # 输出
    output_json = Column(JSON, nullable=True, default=lambda: {
        "video_url": None,
        "preview_url": None,
        "frames": []
    })

    # 关系
    timeline = relationship("Timeline", back_populates="clips")
    panel = relationship("Panel", back_populates="clips")

    def __repr__(self):
        return f"<Clip {self.id} panel={self.panel_id}>"
