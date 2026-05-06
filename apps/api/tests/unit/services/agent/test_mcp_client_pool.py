"""Unit tests for MCP client pool — isolation tests with fake clients."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.agent.mcp_client_pool import McpClientPool, _make_remote_handler


@pytest.mark.asyncio
async def test_remote_handler_forwards_to_client():
    client = MagicMock()
    client.call_tool = AsyncMock(return_value={"ok": True})
    h = _make_remote_handler(client, "ping")
    result = await h({"x": 1}, {}, db=None, tracer=None)
    assert result == {"ok": True}
    client.call_tool.assert_awaited_once_with("ping", {"x": 1})


@pytest.mark.asyncio
async def test_pool_disconnect_deregisters_tools():
    from app.services.agent.tool_registry import TOOL_REGISTRY, ToolDefinition

    pool = McpClientPool()
    fake_client = MagicMock()
    fake_client.close = AsyncMock()
    pool._clients["conn-1"] = fake_client
    pool._tool_names["conn-1"] = ["mcp_conn_1_ping"]

    async def _h(args, context, db, tracer): return None
    TOOL_REGISTRY.register(ToolDefinition(
        name="mcp_conn_1_ping", description="d", json_schema={},
        handler=_h,
    ))
    assert TOOL_REGISTRY.get("mcp_conn_1_ping") is not None

    await pool._disconnect("conn-1")
    assert "conn-1" not in pool._clients
    assert TOOL_REGISTRY.get("mcp_conn_1_ping") is None
