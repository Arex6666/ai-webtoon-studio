"""
LayerPack Model - 图层包
渲染输出的结构化存储
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON, Float, DateTime
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid
from datetime import datetime


class LayerPack(Base, TimestampMixin):
    """图层包模型 - 存储渲染输出"""
    __tablename__ = "layer_packs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    panel_id = Column(String(36), ForeignKey("panels.id"), nullable=False)
    
    # A01 规范字段
    attempt = Column(Integer, default=1)
    manifest_url = Column(String(512), nullable=True)
    full_url = Column(String(512), nullable=True)  # 完整图 URL (便捷访问)
    generation_params = Column(JSON, nullable=True)  # 生成参数摘要
    
    # 版本控制
    version = Column(Integer, default=1)
    parent_id = Column(String(36), ForeignKey("layer_packs.id"), nullable=True)
    is_active = Column(String(10), default="true")  # 当前激活版本
    
    # 图层文件路径 (MinIO)
    file_full = Column(String(512), nullable=True)       # 完整合成图
    file_char = Column(String(512), nullable=True)       # 角色层
    file_bg = Column(String(512), nullable=True)         # 背景层
    file_fg = Column(String(512), nullable=True)         # 前景层
    file_mask = Column(String(512), nullable=True)       # 遮罩层
    file_depth = Column(String(512), nullable=True)      # 深度图
    file_lineart = Column(String(512), nullable=True)    # 线稿
    
    # 额外文件 JSON
    extra_files = Column(JSON, nullable=False, default=dict)
    
    # 尺寸
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    
    # 边界框信息
    bbox_json = Column(JSON, nullable=False, default=dict)
    
    # 生成参数 (保留兼容)
    params_json = Column(JSON, nullable=False, default=dict)
    
    # QA 结果
    qa_score = Column(Float, default=0.0)
    qa_passed = Column(String(10), default="false")
    qa_json = Column(JSON, nullable=False, default=dict)
    
    # 状态
    status = Column(String(50), default="completed")  # generating/completed/failed
    
    # 元数据
    metadata_json = Column(JSON, nullable=False, default=dict)
    
    # 关系
    panel = relationship("Panel", back_populates="layer_packs")
    parent = relationship("LayerPack", remote_side=[id], backref="children")
    
    def __repr__(self):
        return f"<LayerPack {self.id} for Panel {self.panel_id}>"
    
    def to_meta_dict(self) -> dict:
        """转换为 LayerPackMeta 格式"""
        return {
            "layerpack_id": self.id,
            "panel_id": self.panel_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "files": {
                "full": self.file_full,
                "char": self.file_char,
                "bg": self.file_bg,
                "fg": self.file_fg,
                "mask": self.file_mask,
                "depth": self.file_depth,
                "lineart": self.file_lineart,
                "extras": self.extra_files or {}
            },
            "bbox": self.bbox_json or {},
            "params": self.params_json or {},
            "qa": {
                "score": self.qa_score,
                "passed": self.qa_passed == "true",
                **(self.qa_json or {})
            },
            "width": self.width,
            "height": self.height,
            "status": self.status,
            "version": self.version,
            "parent_id": self.parent_id,
            "metadata": self.metadata_json or {}
        }
