"""generate_script — slow; dispatched to Celery for async script generation.

For v1 metadata-first scaffolding: returns a dispatched stub. Real Celery
wiring lands in Group 9 (agent runner) where the handler will:
1. Persist a Job row
2. send_task("app.workers.async_runner.run_script_generation_celery", ...)
3. Return {"dispatched": {"job_id": ..., "eta_seconds": ~60}}
"""
import uuid

from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY


SCHEMA = {
    "type": "object",
    "properties": {
        "story": {"type": "string", "description": "Story prompt or synopsis to generate panels from."},
        "panel_count": {"type": "integer", "minimum": 1, "maximum": 20, "default": 4},
    },
    "required": ["story"],
}


async def handle(args: dict, context: dict, db, tracer) -> dict:
    # TODO(B-1 Group 9): wire real Celery dispatch via app.celery_app.send_task
    # For now, return dispatched stub so the agent loop can flow through.
    job_id = str(uuid.uuid4())
    return {
        "dispatched": {
            "job_id": job_id,
            "eta_seconds": 60,
        },
        "note": "stub — real dispatch lands in Group 9",
    }


tool = ToolDefinition(
    name="generate_script",
    description="Generate a complete storyboard script (panels with camera, dialogue, action) from a story prompt. Long-running; dispatches a background job.",
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id", "episode_number"),
    expected_duration="slow",
    read_only=False,
    side_effects=("writes:chapter", "writes:panels"),
)
TOOL_REGISTRY.register(tool)
