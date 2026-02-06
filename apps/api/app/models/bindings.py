"""
Bindings Model - 章节资产绑定
"""
from sqlalchemy import Column, String, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid


class ChapterBindings(Base, TimestampMixin):
    """章节资产绑定模型"""
    __tablename__ = "chapter_bindings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chapter_id = Column(String(36), ForeignKey("chapters.id"), nullable=False, unique=True)

    # 绑定的资产 ID 列表
    identity_asset_ids = Column(JSON, nullable=False, default=list)  # 角色资产
    scene_asset_ids = Column(JSON, nullable=False, default=list)     # 场景资产
    anchor_ids = Column(JSON, nullable=False, default=list)          # 控制图锚点

    # 风格档案
    style_profile_id = Column(String(36), nullable=True)

    # QA 配置 JSON
    qa_config_json = Column(JSON, nullable=True, default=lambda: {
        "threshold": 0.75,
        "max_issues": 3
    })

    # 重试策略 JSON
    retry_policy_json = Column(JSON, nullable=True, default=lambda: {
        "max_attempts": 3,
        "provider_chain": ["kling", "tongyi", "doubao", "mock"],
        "budget": {"max_cost": 50.0, "cost_used": 0.0}
    })

    # 关系
    chapter = relationship("Chapter", back_populates="bindings")

    def __repr__(self):
        return f"<ChapterBindings chapter={self.chapter_id}>"
