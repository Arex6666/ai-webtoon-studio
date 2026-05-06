"""analyze_script — fast read-only; parses a script string into structured beats."""
from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY


SCHEMA = {
    "type": "object",
    "properties": {
        "script_text": {"type": "string", "description": "Script text to parse. If omitted, parses the current episode's stored script."},
    },
}


async def handle(args: dict, context: dict, db, tracer) -> dict:
    script_text = args.get("script_text")
    if not script_text:
        # Group 9 runner will pull current episode's stored script when arg is absent.
        return {
            "parsed": False,
            "note": "stub — current-episode lookup lands in Group 9",
        }
    # Use existing ScriptPipelineService for actual parse
    try:
        from app.services.script_pipeline import ScriptPipelineService
        svc = ScriptPipelineService()
        result = await svc.task_parse(script_text)
        return {
            "parsed": True,
            "characters": [c.name for c in getattr(result.script_ir, "characters", [])],
            "scenes": [s.name for s in getattr(result.script_ir, "scenes", [])],
            "beat_count": len(getattr(result.script_ir, "beats", [])),
        }
    except Exception as e:
        return {"parsed": False, "error": str(e)}


tool = ToolDefinition(
    name="analyze_script",
    description="Parse a script (provided or from the current episode) and extract characters, scenes, and beat count. Read-only.",
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id", "episode_number"),
    expected_duration="fast",
    read_only=True,
)
TOOL_REGISTRY.register(tool)
