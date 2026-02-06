"""
Storyboard Draft Model (S3-02)

AI 分镜生成后先创建 Draft，用户预览确认后再应用到正式 panels。
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class StoryboardDraft(Base, TimestampMixin):
    """分镜草稿 - AI 生成的分镜在用户确认前存储在此"""
    __tablename__ = "storyboard_drafts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chapter_id = Column(String(36), ForeignKey("chapters.id"), nullable=False)
    job_id = Column(String(36), nullable=True)  # 关联的 RenderJob

    # 状态: pending, completed, applied, discarded
    status = Column(String(50), default="pending")
    version = Column(Integer, default=1)

    # Draft 内容 (JSON)
    panels_json = Column(JSON, nullable=True)      # 生成的 panels 列表
    characters_json = Column(JSON, nullable=True)  # 识别的角色
    scenes_json = Column(JSON, nullable=True)      # 识别的场景

    # LLM 原始输出 (用于调试)
    llm_raw_output = Column(Text, nullable=True)

    # 元信息
    script_snapshot = Column(Text, nullable=True)  # 生成时的剧本快照
    provider = Column(String(50), nullable=True)   # 使用的 LLM provider
    style_hint = Column(String(255), nullable=True)

    # 应用信息
    applied_at = Column(DateTime, nullable=True)
    applied_panels_count = Column(Integer, nullable=True)
    
    # 版本关联 (S3-04)
    script_version_on_create = Column(Integer, nullable=True)  # 创建时的 script 版本
    applied_as_storyboard_version = Column(Integer, nullable=True)  # 应用后的版本号

    # 统计
    generated_panels_count = Column(Integer, default=0)
    generated_characters_count = Column(Integer, default=0)
    generated_scenes_count = Column(Integer, default=0)
    
    # S4-01: 版本追溯
    schema_version = Column(String(50), default="storyboard_draft_v2")  # Schema 版本
    prompt_version = Column(String(50), default="pc_v1")  # 提示词合约版本
    script_digest = Column(String(64), nullable=True)  # 剧本 hash (MD5)
    analysis_digest = Column(String(64), nullable=True)  # ScriptAnalysis 的 digest

    # 关系
    chapter = relationship("Chapter", back_populates="storyboard_drafts")

    def __repr__(self):
        return f"<StoryboardDraft {self.id}: {self.status} ({self.generated_panels_count} panels)>"

    def to_dict(self):
        """转换为字典，用于 API 响应"""
        return {
            "id": self.id,
            "chapter_id": self.chapter_id,
            "job_id": self.job_id,
            "status": self.status,
            "version": self.version,
            "panels": self.panels_json or [],
            "characters": self.characters_json or [],
            "scenes": self.scenes_json or [],
            "generated_panels_count": self.generated_panels_count,
            "generated_characters_count": self.generated_characters_count,
            "generated_scenes_count": self.generated_scenes_count,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
