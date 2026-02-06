"""
ExportJob Model - 导出任务
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid


class ExportJob(Base, TimestampMixin):
    """导出任务模型"""
    __tablename__ = "export_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    export_id = Column(String(36), ForeignKey("exports.id"), nullable=False)

    # 尝试次数
    attempt_count = Column(Integer, default=0)

    # 日志路径
    logs_path = Column(String(512), nullable=True)

    # 错误信息
    error_message = Column(Text, nullable=True)

    # 关系
    export = relationship("Export", back_populates="jobs")

    def __repr__(self):
        return f"<ExportJob {self.id}>"
