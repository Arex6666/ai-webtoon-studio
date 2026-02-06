"""
Project Model - 项目
"""
from sqlalchemy import Column, String, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid


class Project(Base, TimestampMixin):
    """项目模型"""
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 工作室关联
    studio_id = Column(String(36), ForeignKey("studios.id"), nullable=True)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    cover_image = Column(String(512), nullable=True)
    is_archived = Column(Boolean, default=False)

    # 默认风格配置
    default_style_profile_id = Column(String(36), nullable=True)

    # 项目创建方式: agent / workbench
    creation_method = Column(String(32), default="agent", nullable=False)

    # 目标平台: douyin/webtoon/horizontal
    target_platform = Column(String(50), default="webtoon")

    # 默认分辨率
    default_resolution = Column(String(50), default="1080x1920")

    # 默认渲染档位
    default_render_tier = Column(String(50), default="normal")

    # 关系
    studio = relationship("Studio", back_populates="projects")
    chapters = relationship("Chapter", back_populates="project", cascade="all, delete-orphan")
    assets = relationship("Asset", back_populates="project", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="project", cascade="all, delete-orphan")
    prop_assets = relationship("PropAsset", back_populates="project", cascade="all, delete-orphan")
    asset_relations = relationship("AssetRelation", back_populates="project", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="project", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Project {self.id}: {self.name}>"
