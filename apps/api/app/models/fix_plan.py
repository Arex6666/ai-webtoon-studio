"""
FixPlan Model - 修复计划
"""
from sqlalchemy import Column, String, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base, TimestampMixin
import uuid


class FixPlan(Base, TimestampMixin):
    """修复计划模型 - 自动返工策略"""
    __tablename__ = "fix_plans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    render_job_id = Column(String(36), ForeignKey("render_jobs.id"), nullable=False)

    # 修复策略 JSON
    # { "action": "change_seed", "params": { "new_seed": 12345 } }
    # { "action": "enhance_faceid", "params": { "weight": 1.2 } }
    # { "action": "partial_inpaint", "params": { "mask_region": "face" } }
    plan_json = Column(JSON, nullable=False, default=dict)

    # 状态: pending/applied/ignored
    status = Column(String(50), default="pending")

    # 关系
    render_job = relationship("RenderJob", back_populates="fix_plans")

    def __repr__(self):
        return f"<FixPlan {self.id}: {self.status}>"
