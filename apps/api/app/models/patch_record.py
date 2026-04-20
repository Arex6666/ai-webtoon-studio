"""
PatchRecord Model - 变更记录 (E3: Persistent Version Tree)
"""
from sqlalchemy import Column, String, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid


class PatchRecord(Base, TimestampMixin):
    """变更记录模型 - 增量修改的持久化记录"""
    __tablename__ = "patch_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Entity reference
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(36), nullable=False)

    # Patch content
    patches_json = Column(JSON, nullable=False, default=list)  # List of patch operations
    summary = Column(Text, nullable=True)

    # Snapshot links
    before_snapshot_id = Column(String(36), ForeignKey("snapshots.id"), nullable=True)
    after_snapshot_id = Column(String(36), ForeignKey("snapshots.id"), nullable=True)

    # Relationships
    before_snapshot = relationship("Snapshot", foreign_keys=[before_snapshot_id])
    after_snapshot = relationship("Snapshot", foreign_keys=[after_snapshot_id])

    def __repr__(self):
        return f"<PatchRecord {self.id} entity={self.entity_type}/{self.entity_id}>"
