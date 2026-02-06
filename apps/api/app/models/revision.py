"""
Revision Model - 版本记录
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship
from app.models.base import Base
import uuid
from datetime import datetime


class Revision(Base):
    """版本记录模型 - 用于跟踪 JSON 变更历史"""
    __tablename__ = "revisions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chapter_id = Column(String(36), ForeignKey("chapters.id"), nullable=False)
    
    # 版本号
    revision_number = Column(Integer, nullable=False)
    
    # 变更类型
    change_type = Column(String(50), nullable=False)  # layout/panel_spec/manual
    target_id = Column(String(36), nullable=True)  # panel_id 如果是 panel 级别变更
    
    # 快照
    snapshot_json = Column(JSON, nullable=False)  # 变更前的 JSON 快照
    
    # 元数据
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(String(36), nullable=True)  # user_id
    
    # 关系
    chapter = relationship("Chapter", back_populates="revisions")
    
    def __repr__(self):
        return f"<Revision {self.id}: Chapter {self.chapter_id} v{self.revision_number}>"
