"""
Studio Model - 工作室/租户
"""
from sqlalchemy import Column, String, Text, JSON, Integer
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid


class Studio(Base, TimestampMixin):
    """工作室模型 - 多租户隔离"""
    __tablename__ = "studios"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # 配额策略
    quota_json = Column(JSON, nullable=False, default=dict)
    # 示例: { "max_concurrent_renders": 5, "max_storage_gb": 100, "max_projects": 50 }

    # 默认风格配置
    default_style_profile_id = Column(String(36), nullable=True)

    # 成员数量（快速统计）
    member_count = Column(Integer, default=1)

    # 状态
    status = Column(String(50), default="active")  # active/suspended/archived

    # 关系
    projects = relationship("Project", back_populates="studio", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Studio {self.id}: {self.name}>"
