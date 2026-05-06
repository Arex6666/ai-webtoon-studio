"""McpServerConnection - 出向连接的外部 MCP server"""
import uuid
from sqlalchemy import Column, String, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import JSON

from app.models.base import Base, TimestampMixin


class McpServerConnection(Base, TimestampMixin):
    """已配置的外部 MCP server 连接"""
    __tablename__ = "mcp_server_connections"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    name = Column(String(128), nullable=False)

    transport = Column(String(16), nullable=False)
    # values: stdio | sse | streamable_http
    command = Column(String(512), nullable=True)        # stdio
    args_json = Column(JSON, nullable=True)             # stdio argv list
    url = Column(String(512), nullable=True)            # sse / streamable_http
    env_json = Column(JSON, nullable=True)              # env vars passed (stdio)

    skill_id = Column(String, nullable=True, index=True)
    # Non-null if this connection belongs to a mcp-wrapped skill

    status = Column(String(16), nullable=False, default="disconnected")
    # values: connected | disconnected | failed
    last_connected_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    capabilities_json = Column(JSON, nullable=True)
    # Cached server capabilities (tool list, resources, prompts) from initialize handshake

    scope = Column(String(16), nullable=False, default="global")
    project_id = Column(String, nullable=True, index=True)

    __table_args__ = (
        Index("idx_mcp_status", "status"),
    )

    def __repr__(self):
        return f"<McpServerConnection {self.name} {self.transport} status={self.status}>"
