"""MCP server — exposes built-in tools to external MCP clients.

Defensive against mcp SDK API drift: imports are deferred and uses
getattr/hasattr where APIs may vary.

For external clients, every key in the tool's `requires_context` is lifted
into the JSON Schema as a required parameter, since external clients have
no implicit context.
"""
import json
import logging
from typing import Any

from app.services.agent.tool_registry import TOOL_REGISTRY, ToolDefinition

logger = logging.getLogger(__name__)


def build_mcp_server():
    """Construct the MCP Server with our tool catalog. Returns an mcp.server.Server.

    Late-imports the SDK so import-time failures don't break app boot.
    """
    from mcp.server import Server
    try:
        from mcp.types import Tool as McpTool, TextContent
    except ImportError:
        # SDK API drift — older versions had different module path
        from mcp import Tool as McpTool, TextContent

    server = Server("webtoon-studio")

    @server.list_tools()
    async def _list_tools() -> list:
        out: list = []
        for tool in TOOL_REGISTRY.all():
            # Skip tools that came from external MCP servers (avoid loops)
            if tool.source_skill_id and tool.source_skill_id.startswith("mcp:"):
                continue
            schema = _lift_context_to_schema(tool)
            out.append(McpTool(
                name=tool.name,
                description=tool.description,
                inputSchema=schema,
            ))
        return out

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict) -> list:
        tool = TOOL_REGISTRY.get(name)
        if not tool:
            return [TextContent(type="text", text=json.dumps({"error": f"tool not found: {name}"}))]

        # Lift context fields out of arguments
        context = {}
        args = dict(arguments)
        for k in tool.requires_context:
            if k not in args:
                return [TextContent(type="text", text=json.dumps({"error": f"missing required: {k}"}))]
            context[k] = args.pop(k)

        from app.db.database import SessionLocal
        from app.services.agent.trace import with_tracer
        async with with_tracer(conversation_id=None) as tracer:
            db = SessionLocal()
            try:
                result = await tool.handler(args, context, db, tracer)
            except Exception as e:
                logger.exception("MCP-inbound tool %s failed", name)
                result = {"error": f"tool execution failed: {e!r}"}
            finally:
                db.close()
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, default=str))]

    return server


def _lift_context_to_schema(tool: ToolDefinition) -> dict:
    """Promote tool.requires_context keys to JSON Schema required parameters.

    Internal tool: project_id from context (implicit).
    MCP-exposed: project_id required explicit arg.
    """
    base = dict(tool.json_schema or {"type": "object"})
    props = dict(base.get("properties", {}))
    required = list(base.get("required", []))

    for ctx_key in tool.requires_context:
        if ctx_key not in props:
            if ctx_key.endswith("_id"):
                props[ctx_key] = {"type": "string", "description": f"Required context: {ctx_key}"}
            elif ctx_key == "episode_number":
                props[ctx_key] = {"type": "integer", "description": "Required context: episode_number"}
            else:
                props[ctx_key] = {"type": "string", "description": f"Required context: {ctx_key}"}
        if ctx_key not in required:
            required.append(ctx_key)

    base["properties"] = props
    base["required"] = required
    return base
