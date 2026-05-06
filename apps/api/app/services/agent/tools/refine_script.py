"""refine_script — record user feedback on the current episode's script and run repair-loop validation on existing storyboard JSON.

Wires ``validate_and_repair_storyboard`` from
``apps/api/app/services/brain/repair/repair_loop.py``. Important — the actual
function signature differs from what the original B-1 plan assumed:

    async def validate_and_repair_storyboard(
        data: Dict[str, Any],
        script_text: str,
        duration_range: Tuple[float, float] = (1.5, 8.0),
        max_attempts: int = 3,
    ) -> Tuple[bool, Any, RepairPlan]

It does NOT take a free-form ``feedback`` string. It operates on a
structured StoryboardDraftV2 ``data`` dict and tries to repair validation
issues via the LLM. So we cannot use it as a "rewrite according to user
feedback" hook. Instead this tool:

1. Looks up the chapter (via ``project_id`` + ``episode_number``→
   ``Chapter.order_index``).
2. Records the user's feedback into ``Chapter.layout_json["pending_feedback"]``
   so a downstream director / regenerate step can act on it.
3. If a structured storyboard already exists in ``layout_json["storyboard"]``,
   runs ``validate_and_repair_storyboard`` over it as a best-effort
   integrity pass and stores the repaired JSON back.

Real "rewrite-on-feedback" behaviour requires a dedicated LLM call (similar
to ``ScriptPipelineService.task_parse``); that lands in a later phase. For
now this tool persists the feedback signal honestly and returns metadata
about what it did.
"""
import logging
from datetime import datetime

from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY


logger = logging.getLogger(__name__)


SCHEMA = {
    "type": "object",
    "properties": {
        "feedback": {"type": "string", "description": "User feedback on the current script."},
        "target_section": {"type": "string", "description": "Optional: panel range or scene name to focus on."},
    },
    "required": ["feedback"],
}


async def handle(args: dict, context: dict, db, tracer) -> dict:
    feedback = args.get("feedback", "")
    if not feedback:
        return {"error": "feedback required"}

    project_id = context["project_id"]
    episode_number = context["episode_number"]
    target_section = args.get("target_section")

    try:
        from app.models.chapter import Chapter
        from app.services.brain.repair.repair_loop import validate_and_repair_storyboard

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
        if chapter is None:
            return {
                "error": f"episode {episode_number} not found in project {project_id}",
            }

        # Record the feedback signal into layout_json for downstream consumers.
        layout = dict(chapter.layout_json or {})
        pending = list(layout.get("pending_feedback") or [])
        pending.append(
            {
                "feedback": feedback,
                "target_section": target_section,
                "received_at": datetime.utcnow().isoformat(),
            }
        )
        layout["pending_feedback"] = pending

        # Best-effort repair pass on the existing storyboard JSON if present.
        repair_outcome: dict = {"ran": False}
        storyboard = layout.get("storyboard")
        script_text = chapter.script_raw or ""
        if isinstance(storyboard, dict) and script_text:
            try:
                ok, repaired_data, plan = await validate_and_repair_storyboard(
                    data=storyboard,
                    script_text=script_text,
                )
                repair_outcome = {
                    "ran": True,
                    "ok": bool(ok),
                    "final_status": getattr(plan, "final_status", None),
                    "attempts_used": getattr(plan, "attempts_used", None),
                }
                # Persist repaired JSON when the loop produced a usable result.
                if ok and isinstance(repaired_data, dict):
                    layout["storyboard"] = repaired_data
                elif ok and hasattr(repaired_data, "model_dump"):
                    layout["storyboard"] = repaired_data.model_dump()
            except Exception as e:  # noqa: BLE001 — repair is best-effort
                logger.warning("refine_script: repair_loop raised: %r", e)
                repair_outcome = {"ran": True, "ok": False, "error": repr(e)}

        chapter.layout_json = layout
        db.commit()

        return {
            "success": True,
            "feedback_received": feedback,
            "target_section": target_section,
            "repair": repair_outcome,
            "note": (
                "Feedback recorded into chapter.layout_json.pending_feedback; "
                "free-form rewrite-on-feedback is not implemented yet — the "
                "repair pass only fixes validation issues on existing "
                "storyboard JSON."
            ),
        }
    except Exception as e:  # noqa: BLE001 — surface failure to the agent loop
        return {"error": f"refine_script failed: {e!r}"}


tool = ToolDefinition(
    name="refine_script",
    description="Record user feedback on the current episode's script and (when a storyboard JSON exists) run a validation/repair pass over it.",
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id", "episode_number"),
    expected_duration="fast",
    read_only=False,
    side_effects=("writes:chapter",),
)
TOOL_REGISTRY.register(tool)
