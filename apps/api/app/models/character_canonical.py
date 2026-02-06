"""
CharacterCanonical Model - 角色基准资产（定妆照候选/选中）
"""
from sqlalchemy import Column, String, ForeignKey, Float, Enum as SQLEnum, Text, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid
import enum


class CanonicalStatus(str, enum.Enum):
    """Canonical 处理状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CharacterCanonical(Base, TimestampMixin):
    """
    角色基准资产模型
    
    存储角色定妆照的候选和最终选择结果
    """
    __tablename__ = "character_canonicals"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 关联章节
    chapter_id = Column(String(36), ForeignKey("chapters.id"), nullable=False)

    # 角色稳定 ID (如 ch_zhouyu, ch_xiaoqiao)
    character_id = Column(String(100), nullable=False, index=True)

    # 角色名称 (便于查询)
    character_name = Column(String(100), nullable=True)

    # 候选定妆照路径 (JSON 数组, MinIO 路径)
    # 格式: ["canon/characters/{chapterId}/{characterId}/cand_1.png", ...]
    candidate_paths = Column(JSON, default=list)

    # 选中的定妆照路径
    selected_path = Column(String(512), nullable=True)

    # 选优分数 (0.0 - 1.0)
    selected_score = Column(Float, nullable=True)

    # 选择原因 (LLM 或算法给出的理由)
    selection_reason = Column(Text, nullable=True)

    # 处理状态
    status = Column(
        SQLEnum(CanonicalStatus),
        default=CanonicalStatus.PENDING,
        nullable=False
    )

    # 错误信息
    error = Column(Text, nullable=True)

    # 生成配置 (可选, 记录 prompt/style 等)
    generation_config = Column(JSON, nullable=True)

    # 关系
    chapter = relationship("Chapter", back_populates="character_canonicals")

    # 唯一约束: 每个章节每个角色只有一条记录
    __table_args__ = (
        # 可选: UniqueConstraint('chapter_id', 'character_id', name='uq_chapter_character'),
    )

    def __repr__(self):
        return f"<CharacterCanonical {self.character_id} in {self.chapter_id}>"

    @property
    def candidates_count(self) -> int:
        """候选数量"""
        return len(self.candidate_paths) if self.candidate_paths else 0

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "chapter_id": self.chapter_id,
            "character_id": self.character_id,
            "character_name": self.character_name,
            "candidate_paths": self.candidate_paths or [],
            "candidates_count": self.candidates_count,
            "selected_path": self.selected_path,
            "selected_score": self.selected_score,
            "selection_reason": self.selection_reason,
            "status": self.status.value if self.status else None,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
