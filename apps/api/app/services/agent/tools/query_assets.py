"""query_assets — list assets in a project, filtered by type/name."""
from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY
from app.models.asset import Asset, AssetType


SCHEMA = {
    "type": "object",
    "properties": {
        "asset_type": {
            "type": "string",
            "enum": ["character", "scene", "prop", "style", "bubble", "effect"],
            "description": "Filter by asset type. Omit for all types.",
        },
        "name_contains": {"type": "string", "description": "Case-insensitive substring filter on asset name."},
        "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
    },
}


async def handle(args: dict, context: dict, db, tracer) -> dict:
    project_id = context["project_id"]
    q = db.query(Asset).filter(Asset.project_id == project_id)
    if args.get("asset_type"):
        try:
            q = q.filter(Asset.type == AssetType(args["asset_type"]))
        except ValueError:
            return {"error": f"unknown asset_type: {args['asset_type']}"}
    if args.get("name_contains"):
        q = q.filter(Asset.name.ilike(f"%{args['name_contains']}%"))
    rows = q.limit(args.get("limit", 50)).all()
    return {
        "count": len(rows),
        "assets": [
            {
                "id": a.id,
                "name": a.name,
                "type": a.type.value if hasattr(a.type, "value") else str(a.type),
                "description": a.description,
            }
            for a in rows
        ],
    }


tool = ToolDefinition(
    name="query_assets",
    description="List assets in the current project. Optionally filter by type (character/scene/prop/style) or name substring.",
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id",),
    expected_duration="fast",
    read_only=True,
)
TOOL_REGISTRY.register(tool)
