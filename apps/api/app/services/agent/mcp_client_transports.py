"""MCP client transport selection — stdio, sse, streamable_http.

Wraps Anthropic mcp SDK's client primitives behind a uniform McpClient interface.
Defensive against minor SDK API drift — if a transport import fails, raises a
clear error so the pool can mark the connection as failed instead of crashing.
"""
import logging
from typing import Optional

from app.models.mcp_server_connection import McpServerConnection

logger = logging.getLogger(__name__)


class McpClient:
    """Uniform interface around an MCP ClientSession."""

    def __init__(self, session, connect_cm, transport: str):
        self._session = session
        self._connect_cm = connect_cm
        self._transport = transport

    async def initialize(self) -> dict:
        result = await self._session.initialize()
        proto_ver = getattr(result, "protocolVersion", None) or getattr(result, "protocol_version", None)
        info = getattr(result, "serverInfo", None) or getattr(result, "server_info", None)
        return {
            "protocol_version": proto_ver,
            "server_info": {
                "name": getattr(info, "name", None) if info else None,
                "version": getattr(info, "version", None) if info else None,
            },
        }

    async def list_tools(self) -> list[dict]:
        result = await self._session.list_tools()
        out = []
        for t in getattr(result, "tools", []):
            out.append({
                "name": getattr(t, "name", None),
                "description": getattr(t, "description", None),
                "inputSchema": getattr(t, "inputSchema", None) or getattr(t, "input_schema", None) or {"type": "object"},
            })
        return out

    async def call_tool(self, name: str, args: dict) -> dict:
        result = await self._session.call_tool(name, args)
        content = []
        for c in getattr(result, "content", []):
            content.append(self._content_to_dict(c))
        return {"content": content, "is_error": getattr(result, "isError", False)}

    async def ping(self) -> None:
        # MCP SDK exposes send_ping in some versions; tolerate absence
        if hasattr(self._session, "send_ping"):
            await self._session.send_ping()
        elif hasattr(self._session, "ping"):
            await self._session.ping()
        # else: silent — not all transports support ping; rely on call_tool errors

    async def close(self) -> None:
        try:
            await self._connect_cm.__aexit__(None, None, None)
        except Exception:
            pass

    @staticmethod
    def _content_to_dict(c) -> dict:
        if hasattr(c, "text"):
            return {"type": "text", "text": c.text}
        if hasattr(c, "data"):
            return {"type": "image", "data": c.data, "mimeType": getattr(c, "mimeType", None)}
        return {"type": "unknown", "raw": str(c)}


async def open_client(row: McpServerConnection) -> McpClient:
    """Open an MCP connection using the row's transport config."""
    if row.transport == "stdio":
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        params = StdioServerParameters(
            command=row.command,
            args=list(row.args_json or []),
            env=dict(row.env_json or {}),
        )
        cm = stdio_client(params)
    elif row.transport == "sse":
        from mcp import ClientSession
        from mcp.client.sse import sse_client
        cm = sse_client(row.url)
    elif row.transport == "streamable_http":
        from mcp import ClientSession
        try:
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError:
            from mcp.client.streamablehttp import streamablehttp_client
        cm = streamablehttp_client(row.url)
    else:
        raise ValueError(f"Unknown MCP transport: {row.transport}")

    streams = await cm.__aenter__()
    if row.transport == "streamable_http":
        # Newer SDK: returns 3-tuple (read, write, _)
        if isinstance(streams, tuple) and len(streams) >= 2:
            read_stream, write_stream = streams[0], streams[1]
        else:
            read_stream, write_stream = streams
    else:
        read_stream, write_stream = streams
    session = ClientSession(read_stream, write_stream)
    await session.__aenter__()
    return McpClient(session, cm, row.transport)
