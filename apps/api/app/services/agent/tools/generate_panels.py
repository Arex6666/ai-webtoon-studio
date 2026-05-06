"""generate_panels — slow; generates panel images via Doubao or ComfyUI for current episode."""
import uuid

from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY


SCHEMA = {
    "type": "object",
    "properties": {
        "force_regenerate": {"type": "boolean", "default": False, "description": "Regenerate even if panels already have images."},
    },
}


async def handle(args: dict, context: dict, db, tracer) -> dict:
    # TODO(B-1 Group 9): wire Celery dispatch (Doubao image-gen pipeline)
    return {
        "dispatched": {
            "job_id": str(uuid.uuid4()),
            "eta_seconds": 90,
        },
        "note": "stub — real dispatch lands in Group 9",
    }


tool = ToolDefinition(
    name="generate_panels",
    description="Generate panel preview images for the current episode using the configured image-gen pipeline. Long-running; dispatches a background job.",
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id", "episode_number"),
    expected_duration="slow",
    read_only=False,
    side_effects=("writes:panel.preview_url", "writes:panel.preview_key"),
)
TOOL_REGISTRY.register(tool)
