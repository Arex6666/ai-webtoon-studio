"""query_panels — list panels for a given episode."""
from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY
from app.models.panel import Panel
from app.models.chapter import Chapter


SCHEMA = {
    "type": "object",
    "properties": {
        "episode_number": {
            "type": "integer",
            "description": "If omitted, uses episode_number from context.",
        },
    },
}


async def handle(args: dict, context: dict, db, tracer) -> dict:
    project_id = context["project_id"]
    ep = args.get("episode_number") or context.get("episode_number")
    if ep is None:
        return {"error": "episode_number required (in args or context)"}
    chapter = (
        db.query(Chapter)
        .filter(Chapter.project_id == project_id, Chapter.order == ep)
        .first()
    )
    if not chapter:
        return {"count": 0, "panels": []}
    panels = (
        db.query(Panel)
        .filter(Panel.chapter_id == chapter.id)
        .order_by(Panel.order)
        .all()
    )
    return {
        "count": len(panels),
        "panels": [
            {
                "id": p.id,
                "order": p.order,
                "preview_url": getattr(p, "preview_url", None),
            }
            for p in panels
        ],
    }


tool = ToolDefinition(
    name="query_panels",
    description="List panels in a given episode of the current project.",
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id",),
    expected_duration="fast",
    read_only=True,
)
TOOL_REGISTRY.register(tool)
