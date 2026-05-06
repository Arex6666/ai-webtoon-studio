"""refine_script — fast; refines an existing script with user feedback.

Stub for v1 scaffolding. Group 9 (runner) wires synchronous repair_loop call.
"""
from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY


SCHEMA = {
    "type": "object",
    "properties": {
        "feedback": {"type": "string", "description": "User feedback on the current script."},
        "target_section": {"type": "string", "description": "Optional: panel range or scene name to focus on."},
    },
    "required": ["feedback"],
}


async def handle(args: dict, context: dict, db, tracer) -> dict:
    # TODO(B-1 Group 9): wire repair_loop call
    return {
        "refined": False,
        "feedback_received": args.get("feedback", ""),
        "note": "stub — real refine logic lands in Group 9",
    }


tool = ToolDefinition(
    name="refine_script",
    description="Refine the current episode's script based on user feedback (re-roll dialogue, tighten pacing, change tone, etc).",
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id", "episode_number"),
    expected_duration="fast",
    read_only=False,
    side_effects=("writes:chapter",),
)
TOOL_REGISTRY.register(tool)
