"""
OutfitVariant Model - 服装变体（作为角色的子资源）
"""
from sqlalchemy import Column, String, Text, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid


class OutfitVariant(Base, TimestampMixin):
    """服装变体 - 作为 Character 的子资源"""
    __tablename__ = "outfit_variants"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    character_asset_id = Column(String(36), ForeignKey("assets.id"), nullable=False)

    # 服装信息
    outfit_name = Column(String(100), nullable=False)  # 如 "战袍", "便服"
    outfit_description = Column(Text, nullable=False)  # 详细描述
    garment_items = Column(JSON, default=list)  # ["上衣", "裤子", "鞋子"]
    colors = Column(JSON, default=list)  # 颜色列表
    materials = Column(JSON, default=list)  # 材质列表

    # 生成参数
    outfit_prompt = Column(Text, nullable=False)  # 完整的服装提示词

    # 参考图
    ref_image_path = Column(String(512), nullable=True)
    ref_image_status = Column(String(50), default="none")  # none|generating|ready|failed

    # 默认标记
    is_default = Column(Boolean, default=False)

    # 状态
    status = Column(String(50), default="pending")  # pending|ready|failed

    # 关系
    character_asset = relationship("Asset", back_populates="outfit_variants")

    def __repr__(self):
        return f"<OutfitVariant {self.id}: {self.outfit_name}>"
