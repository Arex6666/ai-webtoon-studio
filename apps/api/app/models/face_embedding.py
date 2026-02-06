"""
FaceEmbedding Model - 人脸嵌入
"""
from sqlalchemy import Column, String, ForeignKey, Float, Integer
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid


class FaceEmbedding(Base, TimestampMixin):
    """人脸嵌入模型 - 角色一致性"""
    __tablename__ = "face_embeddings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 关联角色资产
    character_asset_id = Column(String(36), ForeignKey("assets.id"), nullable=False)

    # 可选: 关联 CharacterCanonical
    canonical_id = Column(String(36), ForeignKey("character_canonicals.id"), nullable=True)

    # 提供者 (insightface/arcface/etc)
    provider = Column(String(50), nullable=False, default="insightface")

    # 模型名称 (buffalo_l/buffalo_s/etc)
    model_name = Column(String(100), nullable=True, default="buffalo_l")

    # 模型哈希 (用于版本追踪)
    model_hash = Column(String(64), nullable=True)

    # 嵌入维度 (512/1024 等)
    dim = Column(Integer, nullable=False, default=512)

    # 嵌入文件路径 (MinIO/S3)
    embedding_path = Column(String(512), nullable=False)

    # 参考图路径
    reference_image_path = Column(String(512), nullable=True)

    # 质量分数
    quality_score = Column(Float, default=0.0)

    # 状态
    status = Column(String(50), default="active")  # active/archived

    # 关系
    character_asset = relationship("Asset", back_populates="face_embeddings")

    def __repr__(self):
        return f"<FaceEmbedding {self.id} for {self.character_asset_id}>"

    def to_dict(self):
        return {
            "id": self.id,
            "character_asset_id": self.character_asset_id,
            "canonical_id": self.canonical_id,
            "provider": self.provider,
            "model_name": self.model_name,
            "model_hash": self.model_hash,
            "dim": self.dim,
            "embedding_path": self.embedding_path,
            "reference_image_path": self.reference_image_path,
            "quality_score": self.quality_score,
            "status": self.status,
        }

