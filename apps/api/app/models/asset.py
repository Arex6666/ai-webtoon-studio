"""
Asset Model - 资产（角色、场景、气泡样式、风格配置）
"""
from sqlalchemy import Column, String, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid
import enum


class AssetType(str, enum.Enum):
    """资产类型"""
    CHARACTER = "character"     # 角色
    SCENE = "scene"            # 场景/背景
    BUBBLE_STYLE = "bubble"    # 气泡样式
    STYLE_PROFILE = "style"    # 风格配置
    EFFECT = "effect"          # 特效
    PROP = "prop"              # 道具


class Asset(Base, TimestampMixin):
    """资产模型"""
    __tablename__ = "assets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)

    # 基本信息
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)  # AssetType
    description = Column(Text, nullable=True)
    tags = Column(JSON, nullable=False, default=list)

    # 缩略图
    thumbnail_url = Column(String(512), nullable=True)

    # 当前版本ID
    current_version_id = Column(String(36), nullable=True)

    # 资产数据 JSON
    data_json = Column(JSON, nullable=False, default=dict)

    # 状态
    status = Column(String(50), default="active")
    
    # S5-01: 角色参考图自动生成
    reference_image_path = Column(String(512), nullable=True)
    reference_image_status = Column(String(50), default="none")  # none|generating|ready|failed
    reference_image_meta = Column(JSON, nullable=True)  # {seed, model, prompt_hash, style_id}

    # 关系
    project = relationship("Project", back_populates="assets")
    versions = relationship("AssetVersion", back_populates="asset", cascade="all, delete-orphan")
    face_embeddings = relationship("FaceEmbedding", back_populates="character_asset", cascade="all, delete-orphan")
    scene_anchors = relationship("SceneAnchor", back_populates="scene_asset", cascade="all, delete-orphan")
    outfit_variants = relationship("OutfitVariant", back_populates="character_asset", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Asset {self.id}: {self.name} ({self.type})>"
