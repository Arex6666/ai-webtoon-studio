"""
ShotVersion Model - 镜头版本
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid


class ShotVersion(Base, TimestampMixin):
    """镜头版本模型 - 支持可回滚的版本控制"""
    __tablename__ = "shot_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    panel_id = Column(String(36), ForeignKey("panels.id"), nullable=False)

    # 版本号
    version_no = Column(Integer, nullable=False, default=1)

    # ShotSpec JSON (完整的镜头规格)
    shot_spec_json = Column(JSON, nullable=False, default=dict)

    # 可覆盖章节默认的风格配置
    style_profile_id = Column(String(36), nullable=True)

    # 提交信息
    commit_message = Column(Text, nullable=True)

    # 创建者
    created_by = Column(String(36), nullable=True)

    # 关系
    panel = relationship("Panel", back_populates="versions")

    def __repr__(self):
        return f"<ShotVersion {self.id}: Panel {self.panel_id} v{self.version_no}>"
