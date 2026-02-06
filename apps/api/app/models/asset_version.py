"""
AssetVersion Model - 资产版本
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid


class AssetVersion(Base, TimestampMixin):
    """资产版本模型"""
    __tablename__ = "asset_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    asset_id = Column(String(36), ForeignKey("assets.id"), nullable=False)

    # 版本号
    version_no = Column(Integer, nullable=False, default=1)

    # 资产清单 JSON
    # 示例: { "lora_path": "...", "reference_images": [...], "negative_template": "..." }
    manifest_json = Column(JSON, nullable=False, default=dict)

    # 向量ID (指向 pgvector)
    vector_id = Column(String(36), nullable=True)

    # 提交信息
    commit_message = Column(Text, nullable=True)

    # 关系
    asset = relationship("Asset", back_populates="versions")

    def __repr__(self):
        return f"<AssetVersion {self.id}: Asset {self.asset_id} v{self.version_no}>"
