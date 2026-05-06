"""SkillInstallation - 已安装的 skill 包"""
import uuid
from sqlalchemy import Column, String, DateTime, Text, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSON

from app.models.base import Base, TimestampMixin


class SkillInstallation(Base, TimestampMixin):
    """已安装的 skill 包（builtin、本地、URL、git、mcp_only 五种来源）"""
    __tablename__ = "skill_installations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    name = Column(String(128), nullable=False, index=True)
    version = Column(String(32), nullable=False)

    source_type = Column(String(16), nullable=False)
    # values: builtin | local | url | git | mcp_only
    source_url = Column(String(512), nullable=True)
    install_path = Column(String(512), nullable=True)

    manifest_json = Column(JSON, nullable=False)

    status = Column(String(16), nullable=False, default="active")
    # values: installing | active | disabled | failed | uninstalled
    failure_reason = Column(Text, nullable=True)

    scope = Column(String(16), nullable=False, default="global")
    # values: global | project
    project_id = Column(String, nullable=True, index=True)

    installed_at = Column(DateTime, nullable=False)
    last_loaded_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("name", "scope", "project_id", name="uq_skill_name_scope"),
        Index("idx_skill_status_scope", "status", "scope"),
    )

    def __repr__(self):
        return f"<SkillInstallation {self.name}@{self.version} status={self.status}>"
