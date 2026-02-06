"""
Template Model - 模板/风格包
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid


class Template(Base, TimestampMixin):
    """模板模型 - 风格包/角色包/场景包"""
    __tablename__ = "templates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # 基本信息
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    thumbnail_url = Column(String(512), nullable=True)
    
    # 分类
    category = Column(String(50), default="general")  # general, character, scene, style
    tags = Column(JSON, default=list)
    
    # 归属
    studio_id = Column(String(36), ForeignKey("studios.id"), nullable=True)
    is_public = Column(String(10), default="false")  # 是否公开
    
    # 模板内容
    # 风格档案
    style_profile = Column(JSON, nullable=False, default=lambda: {
        "art_style": "anime",
        "color_palette": "vibrant",
        "lighting": "soft",
        "texture": "smooth",
    })
    
    # 默认渲染参数
    render_params = Column(JSON, nullable=False, default=lambda: {
        "width": 1080,
        "height": 1920,
        "steps": 20,
        "sampler": "euler",
        "scheduler": "normal",
        "cfg_scale": 7.0,
    })
    
    # 默认提示词
    prompt_template = Column(JSON, nullable=False, default=lambda: {
        "positive_prefix": "masterpiece, best quality, ",
        "positive_suffix": "",
        "negative_prompt": "low quality, blurry, watermark",
    })
    
    # 关联资产 ID
    identity_asset_ids = Column(JSON, default=list)  # 角色资产
    scene_asset_ids = Column(JSON, default=list)     # 场景资产
    anchor_ids = Column(JSON, default=list)          # 控制图锚点
    
    # 使用统计
    use_count = Column(Integer, default=0)
    
    # 关系
    studio = relationship("Studio", backref="templates")

    def __repr__(self):
        return f"<Template {self.id}: {self.name}>"
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "thumbnail_url": self.thumbnail_url,
            "category": self.category,
            "tags": self.tags or [],
            "style_profile": self.style_profile or {},
            "render_params": self.render_params or {},
            "prompt_template": self.prompt_template or {},
            "identity_asset_ids": self.identity_asset_ids or [],
            "scene_asset_ids": self.scene_asset_ids or [],
            "anchor_ids": self.anchor_ids or [],
            "use_count": self.use_count,
            "is_public": self.is_public == "true",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
