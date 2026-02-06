"""
SceneAnchor Model - 场景锚点
"""
from sqlalchemy import Column, String, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid


class SceneAnchor(Base, TimestampMixin):
    """场景锚点模型 - 场景一致性"""
    __tablename__ = "scene_anchors"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 关联场景资产
    scene_asset_id = Column(String(36), ForeignKey("assets.id"), nullable=False)

    # 基准背景图路径
    bg_anchor_path = Column(String(512), nullable=False)

    # 控制图路径集合
    # { "depth": "...", "lineart": "...", "canny": "...", "pose": "..." }
    control_maps = Column(JSON, nullable=False, default=dict)

    # 透视/视角信息
    perspective_json = Column(JSON, nullable=True)

    # 状态
    status = Column(String(50), default="active")

    # 关系
    scene_asset = relationship("Asset", back_populates="scene_anchors")

    def __repr__(self):
        return f"<SceneAnchor {self.id} for {self.scene_asset_id}>"
