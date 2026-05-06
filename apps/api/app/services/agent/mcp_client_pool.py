"""McpClientPool — manages outbound MCP client connections.

Loads active McpServerConnection rows at startup, opens a transport per row,
discovers tool list via the initialize handshake, and registers each tool to
TOOL_REGISTRY with name prefix `mcp_{conn_id_short}_`.

Health check: ping every 30s; failure → status=disconnected, tools deregistered.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.mcp_server_connection import McpServerConnection
from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY

logger = logging.getLogger(__name__)


class McpClientPool:
    """Process-wide MCP client connection pool."""

    def __init__(self):
        self._clients: dict[str, "McpClient"] = {}        # conn_id → client wrapper
        self._tool_names: dict[str, list[str]] = {}        # conn_id → registered tool names
        self._health_task: Optional[asyncio.Task] = None

    async def start(self, db: Session) -> None:
        """Connect to every persisted active connection."""
        rows = db.query(McpServerConnection).filter(
            McpServerConnection.status.in_(["connected", "disconnected"])
        ).all()
        for row in rows:
            try:
                await self._spawn_or_connect(db, row)
            except Exception as e:
                logger.warning("Failed to start MCP server connection %s: %s", row.name, e)
                row.status = "failed"
                row.last_error = str(e)
                try:
                    db.commit()
                except Exception:
                    db.rollback()
        self._health_task = asyncio.create_task(self._health_loop(db))

    async def stop(self) -> None:
        """Gracefully close all connections."""
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except (asyncio.CancelledError, Exception):
                pass
        for conn_id in list(self._clients.keys()):
            await self._disconnect(conn_id)

    async def reconnect(self, db: Session, conn_id: str) -> None:
        row = db.query(McpServerConnection).filter_by(id=conn_id).one()
        await self._disconnect(conn_id)
        await self._spawn_or_connect(db, row)

    async def _spawn_or_connect(self, db: Session, row: McpServerConnection) -> None:
        from app.services.agent.mcp_client_transports import open_client
        client = await open_client(row)
        capabilities = await client.initialize()
        tools = await client.list_tools()

        row.capabilities_json = {"tools": tools, **capabilities}
        row.status = "connected"
        row.last_connected_at = datetime.utcnow()
        row.last_error = None
        db.commit()

        self._clients[row.id] = client
        registered: list[str] = []
        for tool in tools:
            if not tool.get("name"):
                continue
            prefixed_name = f"mcp_{row.id[:8]}_{tool['name']}"
            tool_def = ToolDefinition(
                name=prefixed_name,
                description=tool.get("description") or tool["name"],
                json_schema=tool.get("inputSchema") or {"type": "object"},
                handler=_make_remote_handler(client, tool["name"]),
                requires_context=tuple(),
                expected_duration="slow",
                read_only=False,
                source_skill_id=f"mcp:{row.id}",
            )
            TOOL_REGISTRY.register(tool_def)
            registered.append(prefixed_name)
        self._tool_names[row.id] = registered
        logger.info("Connected MCP server %s; registered %d tools", row.name, len(registered))

    async def _disconnect(self, conn_id: str) -> None:
        client = self._clients.pop(conn_id, None)
        if client:
            try:
                await client.close()
            except Exception:
                pass
        for name in self._tool_names.pop(conn_id, []):
            TOOL_REGISTRY.deregister(name)

    async def _health_loop(self, db: Session) -> None:
        while True:
            try:
                await asyncio.sleep(30)
                for conn_id, client in list(self._clients.items()):
                    try:
                        await client.ping()
                    except Exception as e:
                        logger.warning("MCP %s ping failed: %s — disconnecting", conn_id, e)
                        await self._disconnect(conn_id)
                        row = db.query(McpServerConnection).filter_by(id=conn_id).one_or_none()
                        if row:
                            row.status = "disconnected"
                            row.last_error = str(e)
                            db.commit()
            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception("MCP health loop crashed")


def _make_remote_handler(client, tool_name: str):
    async def handler(args: dict, context: dict, db, tracer):
        return await client.call_tool(tool_name, args)
    return handler


# Singleton instance — initialized at app startup
MCP_CLIENT_POOL = McpClientPool()
