"""update_panel_camera — fast; updates a panel's camera params directly."""
from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY


SCHEMA = {
    "type": "object",
    "properties": {
        "camera_angle": {"type": "string", "description": "e.g. 'eye-level', 'low', 'high', 'Dutch'"},
        "shot_type": {"type": "string", "description": "e.g. 'wide', 'medium', 'close-up', 'over-the-shoulder'"},
    },
}


async def handle(args: dict, context: dict, db, tracer) -> dict:
    panel_id = context.get("panel_id")
    if not panel_id:
        return {"error": "panel_id missing from context"}
    if db is None:
        return {"error": "db session not provided"}
    if not args:
        return {"error": "at least one of camera_angle or shot_type must be provided"}
    try:
        from app.models.panel import Panel
        panel = db.query(Panel).filter(Panel.id == panel_id).first()
        if not panel:
            return {"error": f"panel {panel_id} not found"}
        updated = []
        if args.get("camera_angle") is not None:
            for attr in ("camera_angle", "camera"):
                if hasattr(panel, attr):
                    setattr(panel, attr, args["camera_angle"])
                    updated.append(attr)
                    break
        if args.get("shot_type") is not None:
            for attr in ("shot_type", "shot"):
                if hasattr(panel, attr):
                    setattr(panel, attr, args["shot_type"])
                    updated.append(attr)
                    break
        if not updated:
            return {"error": "Panel model has no camera_angle/camera/shot_type/shot fields"}
        db.commit()
        return {"updated": True, "panel_id": panel_id, "fields_changed": updated}
    except Exception as e:
        db.rollback()
        return {"error": f"update_panel_camera failed: {e!r}"}


tool = ToolDefinition(
    name="update_panel_camera",
    description="Update a single panel's camera angle and/or shot type. Fast direct update.",
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id", "panel_id"),
    expected_duration="fast",
    read_only=False,
    side_effects=("writes:panel.camera",),
)
TOOL_REGISTRY.register(tool)
