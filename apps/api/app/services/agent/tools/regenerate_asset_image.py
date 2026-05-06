"""regenerate_asset_image — slow; regenerates a single character/scene asset's reference image.

Closes the episode-page TODO: '调用后端重新生成单个角色/场景图片'.
"""
import uuid

from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY


SCHEMA = {
    "type": "object",
    "properties": {
        "prompt_override": {"type": "string", "description": "Optional prompt to use instead of the asset's stored prompt."},
    },
}


async def handle(args: dict, context: dict, db, tracer) -> dict:
    # context must include asset_id (per requires_context)
    asset_id = context.get("asset_id")
    # TODO(B-1 Group 9): wire image_worker dispatch with optional prompt override
    return {
        "dispatched": {
            "job_id": str(uuid.uuid4()),
            "eta_seconds": 60,
        },
        "asset_id": asset_id,
        "note": "stub — real dispatch lands in Group 9",
    }


tool = ToolDefinition(
    name="regenerate_asset_image",
    description="Regenerate the reference image for a single character or scene asset. Long-running; dispatches a background job.",
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id", "asset_id"),
    expected_duration="slow",
    read_only=False,
    side_effects=("writes:asset.reference_image",),
)
TOOL_REGISTRY.register(tool)
