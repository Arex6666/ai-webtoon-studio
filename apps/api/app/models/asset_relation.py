"""
AssetRelation Model - 资产关系图谱
"""
from sqlalchemy import Column, String, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid


class RelationType:
    """关系类型"""
    WEARS = "wears"              # Character → OutfitVariant
    HOLDS = "holds"              # Character → PropAsset (hand_prop)
    APPEARS_IN = "appears_in"    # Character → Scene
    CONTAINS = "contains"        # Scene → PropAsset (set_dressing)
    INTERACTS_WITH = "interacts_with"  # Character → PropAsset (动作关联)


class AssetRelation(Base, TimestampMixin):
    """资产关系图谱"""
    __tablename__ = "asset_relations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chapter_id = Column(String(36), ForeignKey("chapters.id"), nullable=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)

    # 关系类型
    relation_type = Column(String(50), nullable=False)
    # wears, holds, appears_in, contains, interacts_with

    # 主体
    subject_id = Column(String(36), nullable=False)
    subject_type = Column(String(50), nullable=False)  # character|scene|prop

    # 客体
    object_id = Column(String(36), nullable=False)
    object_type = Column(String(50), nullable=False)  # character|scene|prop|outfit

    # 元数据 (metadata 是 SQLAlchemy 保留属性名，使用 relation_metadata)
    relation_metadata = Column(JSON, default=dict)  # 额外信息，如频率、重要性、panel_ids

    # 关系
    chapter = relationship("Chapter", back_populates="asset_relations")
    project = relationship("Project", back_populates="asset_relations")

    def __repr__(self):
        return f"<AssetRelation {self.subject_type}:{self.subject_id} -{self.relation_type}-> {self.object_type}:{self.object_id}>"
