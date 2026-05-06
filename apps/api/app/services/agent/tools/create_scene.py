"""create_scene — slow; creates a scene asset and dispatches anchor generation."""
import uuid

from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY


SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
    },
    "required": ["name", "description"],
}


async def handle(args: dict, context: dict, db, tracer) -> dict:
    # TODO(B-1 Group 9): create Asset row, dispatch scene_anchor + control-map gen
    return {
        "asset_id": None,
        "dispatched": {
            "job_id": str(uuid.uuid4()),
            "eta_seconds": 60,
        },
        "name": args.get("name"),
        "note": "stub — Asset row insertion + anchor dispatch land in Group 9",
    }


tool = ToolDefinition(
    name="create_scene",
    description="Create a new scene asset and dispatch background anchor generation. Long-running.",
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id",),
    expected_duration="slow",
    read_only=False,
    side_effects=("writes:asset", "writes:scene_anchor"),
)
TOOL_REGISTRY.register(tool)
