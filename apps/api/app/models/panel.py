"""
Panel Model - 分镜/镜头
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid


class Panel(Base, TimestampMixin):
    """分镜模型 (对应设计文档中的 Shot)"""
    __tablename__ = "panels"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chapter_id = Column(String(36), ForeignKey("chapters.id"), nullable=False)

    # 基本信息
    order_index = Column(Integer, default=0)
    title = Column(String(255), nullable=True)
    summary = Column(Text, nullable=True)

    # 时长 (视频用)
    duration_s = Column(Float, default=3.0)

    # 宽高比: 9:16 / 16:9 / 1:1
    aspect_ratio = Column(String(20), default="9:16")

    # PanelSpec JSON - Single Source of Truth
    spec_json = Column(JSON, nullable=False, default=dict)

    # 当前版本ID
    current_version_id = Column(String(36), nullable=True)

    # 渲染状态: draft/queued/running/needs_fix/rendered/typeset_done/exported
    render_status = Column(String(50), default="draft")

    # 当前使用的图层包 ID
    active_layer_pack_id = Column(String(36), nullable=True)

    # 预览 URL (legacy: presigned URL with finite TTL — kept for back-compat).
    preview_url = Column(String(512), nullable=True)
    # Raw storage key (e.g. MinIO object key) — readers re-sign on demand so
    # links don't expire. Prefer this over preview_url when set.
    preview_key = Column(String(512), nullable=True)


    # 嵌字状态
    typeset_status = Column(String(50), default="pending")  # pending/processing/completed/failed
    typeset_image_url = Column(String(512), nullable=True)
    
    # QA 评分
    qa_score = Column(Float, default=0.0)
    needs_manual_fix = Column(String(50), default="false")  # false/suggested/required
    
    # 警告数量（快速统计）
    warning_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    
    # 渲染级别
    render_tier = Column(String(50), default="normal")  # hero/normal/fast
    
    # 关系
    chapter = relationship("Chapter", back_populates="panels")
    render_jobs = relationship("RenderJob", back_populates="panel", cascade="all, delete-orphan")
    layer_packs = relationship("LayerPack", back_populates="panel", cascade="all, delete-orphan")
    versions = relationship("ShotVersion", back_populates="panel", cascade="all, delete-orphan")
    clips = relationship("Clip", back_populates="panel", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="panel", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Panel {self.id}>"
    
    @property
    def status_display(self) -> str:
        """获取显示状态"""
        status_map = {
            "draft": "草稿",
            "queued": "排队中",
            "rendering": "渲染中",
            "rendered": "已渲染",
            "needs_fix": "需修复",
            "approved": "已批准"
        }
        return status_map.get(self.render_status, self.render_status)
    
    def get_active_layer_pack(self):
        """获取当前激活的图层包"""
        if not self.active_layer_pack_id:
            return None
        for lp in self.layer_packs:
            if lp.id == self.active_layer_pack_id:
                return lp
        return None