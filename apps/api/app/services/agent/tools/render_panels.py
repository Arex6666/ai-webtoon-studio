"""render_panels — slow; dispatches ComfyUI render jobs for one or more panels."""
import uuid

from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY


SCHEMA = {
    "type": "object",
    "properties": {
        "panel_ids": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "description": "Panel IDs to render.",
        },
        "force_regenerate": {"type": "boolean", "default": False},
    },
    "required": ["panel_ids"],
}


async def handle(args: dict, context: dict, db, tracer) -> dict:
    panel_ids = args.get("panel_ids", [])
    # TODO(B-1 Group 9): wire celery_app.send_task("app.workers.image_worker.run_render", ...)
    return {
        "dispatched": {
            "job_id": str(uuid.uuid4()),
            "eta_seconds": 180,
        },
        "panel_ids": panel_ids,
        "note": "stub — real Celery dispatch lands in Group 9",
    }


tool = ToolDefinition(
    name="render_panels",
    description="Render one or more panels to final layered images (full + char + bg + mask) via ComfyUI. Long-running; dispatches a background job per panel.",
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id", "episode_number"),
    expected_duration="slow",
    read_only=False,
    side_effects=("writes:render_job", "writes:layerpack", "writes:panel.preview_url"),
)
TOOL_REGISTRY.register(tool)
