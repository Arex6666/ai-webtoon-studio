content = """\"\"\"
Panel Model - 分镜
\"\"\"
from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid


class Panel(Base, TimestampMixin):
    \"\"\"分镜模型\"\"\"
    __tablename__ = "panels"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chapter_id = Column(String(36), ForeignKey("chapters.id"), nullable=False)
    
    order_index = Column(Integer, default=0)
    title = Column(String(255), nullable=True)
    summary = Column(Text, nullable=True)
    spec_json = Column(JSON, nullable=False, default=dict)
    render_status = Column(String(50), default="draft")
    active_layer_pack_id = Column(String(36), nullable=True)
    preview_url = Column(String(512), nullable=True)
    typeset_status = Column(String(50), default="pending")
    typeset_image_url = Column(String(512), nullable=True)
    qa_score = Column(Float, default=0.0)
    needs_manual_fix = Column(String(50), default="false")
    warning_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    render_tier = Column(String(50), default="normal")
    
    chapter = relationship("Chapter", back_populates="panels")
    render_jobs = relationship("RenderJob", back_populates="panel", cascade="all, delete-orphan")
    layer_packs = relationship("LayerPack", back_populates="panel", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Panel {self.id}>"
"""
with open('app/models/panel.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed!")
