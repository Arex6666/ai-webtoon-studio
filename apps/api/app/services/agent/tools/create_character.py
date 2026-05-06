"""create_character — slow; creates a character asset and dispatches portrait generation."""
import uuid

from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY


SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
        "appearance": {"type": "string", "description": "Detailed visual description for portrait generation."},
    },
    "required": ["name", "description", "appearance"],
}


async def handle(args: dict, context: dict, db, tracer) -> dict:
    # TODO(B-1 Group 9): create Asset row, dispatch canonical_generator + portrait gen
    job_id = str(uuid.uuid4())
    return {
        "asset_id": None,   # Group 9 fills in real id after Asset row insert
        "dispatched": {
            "job_id": job_id,
            "eta_seconds": 90,
        },
        "name": args.get("name"),
        "note": "stub — Asset row insertion + canonical/portrait dispatch land in Group 9",
    }


tool = ToolDefinition(
    name="create_character",
    description="Create a new character asset (with name, description, appearance) and dispatch a portrait-generation job. Long-running.",
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id",),
    expected_duration="slow",
    read_only=False,
    side_effects=("writes:asset", "writes:asset.reference_image"),
)
TOOL_REGISTRY.register(tool)
