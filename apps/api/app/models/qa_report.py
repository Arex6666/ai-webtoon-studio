"""
QAReport Model - QA报告
"""
from sqlalchemy import Column, String, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid


class QAReport(Base, TimestampMixin):
    """QA报告模型 - 质量评估结果"""
    __tablename__ = "qa_reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    render_job_id = Column(String(36), ForeignKey("render_jobs.id"), nullable=False)

    # 总分 0-100
    score = Column(Float, nullable=False, default=0.0)

    # 检查项详情
    # { "face_sim": 0.95, "style_shift": 0.1, "text_readability": 0.9, ... }
    checks_json = Column(JSON, nullable=False, default=dict)

    # 是否通过
    passed = Column(String(10), default="false")

    # 关系
    render_job = relationship("RenderJob", back_populates="qa_reports")

    def __repr__(self):
        return f"<QAReport {self.id}: score={self.score}>"
