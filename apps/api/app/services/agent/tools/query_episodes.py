"""query_episodes — list chapters (episodes) for a project."""
from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY
from app.models.chapter import Chapter


SCHEMA = {
    "type": "object",
    "properties": {
        "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 100},
    },
}


async def handle(args: dict, context: dict, db, tracer) -> dict:
    project_id = context["project_id"]
    chapters = (
        db.query(Chapter)
        .filter(Chapter.project_id == project_id)
        .order_by(Chapter.order)
        .limit(args.get("limit", 100))
        .all()
    )
    return {
        "count": len(chapters),
        "episodes": [
            {
                "id": c.id,
                "title": c.title,
                "order": c.order,
                "status": getattr(c, "status", None),
            }
            for c in chapters
        ],
    }


tool = ToolDefinition(
    name="query_episodes",
    description="List episodes (chapters) in the current project ordered by sequence.",
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id",),
    expected_duration="fast",
    read_only=True,
)
TOOL_REGISTRY.register(tool)
