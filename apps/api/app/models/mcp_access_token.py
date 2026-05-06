"""McpAccessToken - 入向 MCP 客户端鉴权 token"""
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSON

from app.models.base import Base, TimestampMixin


class McpAccessToken(Base, TimestampMixin):
    """外部 MCP 客户端鉴权 token（明文只显示一次，存 SHA-256 hash）"""
    __tablename__ = "mcp_access_tokens"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    # SHA-256 hex digest of plaintext token; plaintext returned only at creation
    name = Column(String(128), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    scopes_json = Column(JSON, nullable=False)
    # Example: {"projects": ["p1", "p2"], "tools": ["query_*", "render_panels"]}

    expires_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_mcp_token_user", "user_id"),
    )

    def __repr__(self):
        return f"<McpAccessToken {self.name} user={self.user_id}>"
