"""generate_script — parse a story prompt into structured beats and persist to the chapter.

Wires `ScriptPipelineService.task_parse` (apps/api/app/services/script_pipeline.py).
The pipeline factory ``create_pipeline()`` returns a service instance whose
``task_parse(script_text) -> ParseResult`` calls the configured LLM and
returns a structured ``ScriptIR`` (characters / scenes / beats).

Persistence: when a Chapter row matching ``project_id`` + ``episode_number``
(via ``Chapter.order_index``) is found, we store the raw story text in
``Chapter.script_raw``. Note the column is ``script_raw`` and the order
column is ``order_index`` (the original B-1 plan referenced ``script_text`` /
``order`` — those names do not exist on the model).

If no matching chapter is found we still return the parsed structure so the
caller can act on it; persistence is best-effort.
"""
from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY


SCHEMA = {
    "type": "object",
    "properties": {
        "story": {"type": "string", "description": "Story prompt or synopsis to generate panels from."},
        "panel_count": {"type": "integer", "minimum": 1, "maximum": 20, "default": 4},
    },
    "required": ["story"],
}


async def handle(args: dict, context: dict, db, tracer) -> dict:
    story = args.get("story", "")
    if not story:
        return {"error": "story required"}

    project_id = context["project_id"]
    episode_number = context["episode_number"]

    try:
        from app.services.script_pipeline import create_pipeline
        from app.models.chapter import Chapter

        pipeline = create_pipeline()
        result = await pipeline.task_parse(story)

        if not getattr(result, "success", False):
            return {
                "error": "task_parse failed",
                "details": list(getattr(result, "errors", []) or []),
            }

        # Persist raw story into the chapter row when one exists.
        chapter = None
        if db is not None:
            chapter = (
                db.query(Chapter)
                .filter(
                    Chapter.project_id == project_id,
                    Chapter.order_index == episode_number,
                )
                .first()
            )
        if chapter is not None:
            chapter.script_raw = story
            db.commit()

        ir = getattr(result, "script_ir", None)
        return {
            "success": True,
            "characters": [getattr(c, "name", str(c)) for c in getattr(ir, "characters", []) or []],
            "scenes": [getattr(s, "name", str(s)) for s in getattr(ir, "scenes", []) or []],
            "beat_count": len(getattr(ir, "beats", []) or []),
            "panel_count": args.get("panel_count", 4),
            "persisted": chapter is not None,
        }
    except Exception as e:  # noqa: BLE001 — surface failure to the agent loop
        return {"error": f"generate_script failed: {e!r}"}


tool = ToolDefinition(
    name="generate_script",
    description="Parse a story prompt into structured beats (characters, scenes, panels) and persist into the current episode's chapter row.",
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id", "episode_number"),
    # task_parse is a synchronous LLM round-trip (seconds), not Celery-dispatched.
    expected_duration="fast",
    read_only=False,
    side_effects=("writes:chapter",),
)
TOOL_REGISTRY.register(tool)
