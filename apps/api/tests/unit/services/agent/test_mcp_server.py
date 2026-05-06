from app.services.agent.mcp_server import _lift_context_to_schema
from app.services.agent.tool_registry import ToolDefinition


async def _h(*args, **kwargs):
    return None


def test_lift_adds_context_keys_as_required():
    t = ToolDefinition(
        name="x", description="d",
        json_schema={"type": "object", "properties": {"k": {"type": "string"}}, "required": ["k"]},
        handler=_h,
        requires_context=("project_id", "episode_number"),
    )
    schema = _lift_context_to_schema(t)
    assert "project_id" in schema["properties"]
    assert "episode_number" in schema["properties"]
    assert schema["properties"]["project_id"]["type"] == "string"
    assert schema["properties"]["episode_number"]["type"] == "integer"
    assert "project_id" in schema["required"]
    assert "episode_number" in schema["required"]
    assert "k" in schema["required"]   # original required preserved


def test_lift_handles_no_existing_schema():
    t = ToolDefinition(
        name="x", description="d", json_schema={}, handler=_h,
        requires_context=("project_id",),
    )
    schema = _lift_context_to_schema(t)
    assert "project_id" in schema["required"]


def test_lift_no_context_no_change():
    t = ToolDefinition(
        name="x", description="d",
        json_schema={"type": "object", "properties": {"a": {"type": "string"}}},
        handler=_h,
    )
    schema = _lift_context_to_schema(t)
    assert schema["properties"] == {"a": {"type": "string"}}
    assert schema.get("required", []) == []


def test_build_mcp_server_smoke():
    from app.services.agent.mcp_server import build_mcp_server
    server = build_mcp_server()
    assert server is not None
    assert hasattr(server, "list_tools")
    assert hasattr(server, "call_tool")
