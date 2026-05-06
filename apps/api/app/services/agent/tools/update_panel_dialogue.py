"""update_panel_dialogue — fast; updates a panel's dialogue text directly."""
from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY


SCHEMA = {
    "type": "object",
    "properties": {
        "dialogue": {"type": "string", "description": "New dialogue text for the panel."},
    },
    "required": ["dialogue"],
}


async def handle(args: dict, context: dict, db, tracer) -> dict:
    panel_id = context.get("panel_id")
    if not panel_id:
        return {"error": "panel_id missing from context"}
    if db is None:
        return {"error": "db session not provided"}
    try:
        from app.models.panel import Panel
        panel = db.query(Panel).filter(Panel.id == panel_id).first()
        if not panel:
            return {"error": f"panel {panel_id} not found"}
        # Try common dialogue field names — codebase may use any of these
        new_dialogue = args["dialogue"]
        if hasattr(panel, "dialogue"):
            panel.dialogue = new_dialogue
        elif hasattr(panel, "dialogue_text"):
            panel.dialogue_text = new_dialogue
        elif hasattr(panel, "speech"):
            panel.speech = new_dialogue
        else:
            return {"error": "Panel model has no dialogue/dialogue_text/speech field"}
        db.commit()
        return {"updated": True, "panel_id": panel_id}
    except Exception as e:
        db.rollback()
        return {"error": f"update_panel_dialogue failed: {e!r}"}


tool = ToolDefinition(
    name="update_panel_dialogue",
    description="Replace the dialogue text on a single panel. Fast direct update.",
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id", "panel_id"),
    expected_duration="fast",
    read_only=False,
    side_effects=("writes:panel.dialogue",),
)
TOOL_REGISTRY.register(tool)
