"""suggest_fixes — fast read-only; produces a FixPlan for a failing-QA panel."""
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
        from app.services.qa.fix_plan_generator import FixPlanGenerator
        gen = FixPlanGenerator()
        if hasattr(gen, "generate_for_panel"):
            plan = await gen.generate_for_panel(panel_id, db)
        elif hasattr(gen, "generate"):
            plan = await gen.generate(panel_id, db)
        else:
            return {"error": "FixPlanGenerator has no generate/generate_for_panel method"}
        # Try to coerce to dict — plan may be a dataclass or pydantic model
        if hasattr(plan, "model_dump"):
            return {"fix_plan": plan.model_dump()}
        if hasattr(plan, "dict"):
            return {"fix_plan": plan.dict()}
        if hasattr(plan, "__dict__"):
            return {"fix_plan": dict(plan.__dict__)}
        return {"fix_plan": str(plan)}
    except Exception as e:
        return {"error": f"suggest_fixes failed: {e!r}"}


tool = ToolDefinition(
    name="suggest_fixes",
    description="Suggest a fix plan (re-seed, boost FaceID weight, inpaint, etc.) for a panel that failed QA. Read-only.",
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id", "panel_id"),
    expected_duration="fast",
    read_only=True,
)
TOOL_REGISTRY.register(tool)
