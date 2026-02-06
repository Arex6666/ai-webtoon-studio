"""
PropAsset Model - 物品资产（手持物品、场景陈设）
"""
from sqlalchemy import Column, String, Text, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid


class PropCategory:
    """物品分类"""
    HAND_PROP = "hand_prop"      # 手持物品（如：剑、书、手机）
    SET_DRESSING = "set_dressing"  # 场景陈设（如：桌子、椅子、灯）


class PropAsset(Base, TimestampMixin):
    """物品资产模型 - HandProp 和 SetDressing"""
    __tablename__ = "prop_assets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)

    # 基本信息
    canonical_name = Column(String(100), nullable=False, index=True)
    aliases = Column(JSON, default=list)  # 别名列表
    category = Column(String(50), nullable=False)  # hand_prop | set_dressing

    # 视觉描述
    visual_brief = Column(Text, nullable=True)  # 简要描述
    material = Column(String(100), nullable=True)  # 材质
    colors = Column(JSON, default=list)  # 颜色列表
    shape = Column(String(100), nullable=True)  # 形状
    key_features = Column(JSON, default=list)  # 关键特征

    # 生成参数
    default_prompt_tokens = Column(JSON, default=list)  # 默认提示词

    # 参考图
    ref_image_paths = Column(JSON, default=list)  # 候选参考图
    ref_image_status = Column(String(50), default="none")  # none|generating|ready|failed

    # 特征提取
    embedding_path = Column(String(512), nullable=True)  # CLIP/DINOv2 embedding

    # 状态
    status = Column(String(50), default="pending")  # pending|ready|failed

    # 关系
    project = relationship("Project", back_populates="prop_assets")

    def __repr__(self):
        return f"<PropAsset {self.id}: {self.canonical_name} ({self.category})>"
