"""
Snapshot Model - 版本快照 (E3: Persistent Version Tree)
"""
from sqlalchemy import Column, String, Text, ForeignKey, JSON, Index, DateTime
from app.models.base import Base, TimestampMixin
from sqlalchemy.orm import relationship, backref
import uuid


class Snapshot(Base, TimestampMixin):
    """版本快照模型 - 持久化的实体版本"""
    __tablename__ = "snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Entity reference
    entity_type = Column(String(50), nullable=False)  # storyboard|panel|template|asset
    entity_id = Column(String(36), nullable=False)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True)
    chapter_id = Column(String(36), ForeignKey("chapters.id"), nullable=True)

    # Tree structure
    parent_id = Column(String(36), ForeignKey("snapshots.id"), nullable=True)

    # Snapshot metadata
    snapshot_type = Column(String(30), nullable=False, default="auto")  # auto|manual|before_patch|milestone
    data_json = Column(JSON, nullable=False, default=dict)
    content_hash = Column(String(64), nullable=True)  # SHA-256 of data for dedup
    reason = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)

    # Relationships
    parent = relationship("Snapshot", remote_side=[id], backref="children")
    project = relationship("Project", backref=backref("snapshots", cascade="all, delete-orphan"))
    chapter = relationship("Chapter", backref=backref("snapshots", cascade="all, delete-orphan"))

    __table_args__ = (
        Index("ix_snapshots_entity_lookup", "entity_type", "entity_id", "created_at"),
    )

    def __repr__(self):
        return f"<Snapshot {self.id} entity={self.entity_type}/{self.entity_id} type={self.snapshot_type}>"
