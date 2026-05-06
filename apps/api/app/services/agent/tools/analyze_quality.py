"""analyze_quality — fast read-only; runs image QA on a panel's current render."""
from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY


SCHEMA = {
    "type": "object",
    "properties": {},
}


async def handle(args: dict, context: dict, db, tracer) -> dict:
    panel_id = context.get("panel_id")
    if not panel_id:
        return {"error": "panel_id missing from context"}
    try:
        from app.services.qa.image_qa import ImageQAService
        service = ImageQAService()
        # ImageQAService API may vary; common shape: analyze(panel_id, db) or analyze(panel)
        if hasattr(service, "analyze_panel"):
            result = await service.analyze_panel(panel_id, db)
        elif hasattr(service, "analyze"):
            result = await service.analyze(panel_id, db)
        else:
            return {"error": "ImageQAService has no analyze_panel/analyze method"}
        return {
            "score": getattr(result, "score", None),
            "passed": getattr(result, "passed", None),
            "issues": getattr(result, "issues", []),
        }
    except Exception as e:
        return {"error": f"analyze_quality failed: {e!r}"}


tool = ToolDefinition(
    name="analyze_quality",
    description="Run automated QA on the current panel's rendered image. Returns score + issues. Read-only.",
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id", "panel_id"),
    expected_duration="fast",
    read_only=True,
)
TOOL_REGISTRY.register(tool)
