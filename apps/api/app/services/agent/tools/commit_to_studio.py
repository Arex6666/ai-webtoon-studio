"""commit_to_studio — slow; commits agent-mode work to Studio Workbench.

Wraps existing app.services.agent_commit.commit_orchestrator (B1 work).
For v1 metadata-first scaffolding, dispatched stub. Group 9 wires real call.
"""
import uuid

from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY


SCHEMA = {
    "type": "object",
    "properties": {
        "include_assets": {"type": "boolean", "default": True},
        "include_script": {"type": "boolean", "default": True},
        "include_panels": {"type": "boolean", "default": True},
    },
}


async def handle(args: dict, context: dict, db, tracer) -> dict:
    # TODO(B-1 Group 9): wire commit_orchestrator.commit_episode_to_studio(...)
    return {
        "dispatched": {
            "job_id": str(uuid.uuid4()),
            "eta_seconds": 30,
        },
        "note": "stub — real commit_orchestrator call lands in Group 9",
    }


tool = ToolDefinition(
    name="commit_to_studio",
    description="Commit the current episode's agent-mode artifacts (assets, script, panels) to Studio Workbench. Long-running.",
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id", "episode_number"),
    expected_duration="slow",
    read_only=False,
    side_effects=("writes:chapter", "writes:panels", "writes:assets"),
)
TOOL_REGISTRY.register(tool)
