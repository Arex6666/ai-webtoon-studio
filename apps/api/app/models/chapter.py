"""
Chapter Model - 章节
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid


class Chapter(Base, TimestampMixin):
    """章节模型"""
    __tablename__ = "chapters"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    order_index = Column(Integer, default=0)

    # 原始脚本文本
    script_raw = Column(Text, nullable=True)

    # ChapterLayout JSON - Single Source of Truth
    layout_json = Column(JSON, nullable=False, default=dict)

    # 章节状态: draft/storyboarded/rendering/exported
    status = Column(String(50), default="draft")

    # 导出状态 (保留兼容)
    export_status = Column(String(50), default="draft")
    exported_url = Column(String(512), nullable=True)

    # 版本控制 (S3-04)
    script_version = Column(Integer, default=0)
    storyboard_version = Column(Integer, default=0)
    
    # 资产锁定 (S3-06)
    assets_lock_json = Column(JSON, nullable=True)
    
    # 时间轴 (P0-TL-01)
    timeline_json = Column(JSON, nullable=True)

    # 关系
    project = relationship("Project", back_populates="chapters")
    panels = relationship("Panel", back_populates="chapter", cascade="all, delete-orphan")
    revisions = relationship("Revision", back_populates="chapter", cascade="all, delete-orphan")
    exports = relationship("Export", back_populates="chapter", cascade="all, delete-orphan")
    storyboard_drafts = relationship("StoryboardDraft", back_populates="chapter", cascade="all, delete-orphan")
    character_canonicals = relationship("CharacterCanonical", back_populates="chapter", cascade="all, delete-orphan")
    bindings = relationship("ChapterBindings", back_populates="chapter", cascade="all, delete-orphan", uselist=False)
    timeline = relationship("Timeline", back_populates="chapter", cascade="all, delete-orphan", uselist=False)
    jobs = relationship("Job", back_populates="chapter", cascade="all, delete-orphan")
    asset_relations = relationship("AssetRelation", back_populates="chapter", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Chapter {self.id}: {self.title}>"
