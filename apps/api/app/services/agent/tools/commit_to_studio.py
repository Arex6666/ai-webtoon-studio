"""commit_to_studio — commits agent-mode work to Studio Workbench.

Wraps ``app.services.agent_commit.commit_orchestrator.commit_agent_to_studio``,
which:
  1. Idempotently looks up an existing chapter for (project_id, conversation_id,
     episode_number); short-circuits if found.
  2. Reads conversation messages for the configured ``panels``/``characters``/
     ``scenes``/``art_style`` cards (lean-payload enrichment) when any of those
     fields aren't supplied.
  3. Creates a Chapter row, syncs Asset rows for characters/scenes, and creates
     Panel rows with persisted preview keys.

The orchestrator is sync-await + DB-bound (no Celery dispatch). Total runtime
is dominated by ``image_fetcher.fetch_and_persist`` calls (one per
character / scene / panel that has a ``temp_image_url``). For typical episodes
that's seconds, so we mark the tool as ``"fast"``.

The handler builds a *lean* ``CommitToStudioRequest``: only ``conversation_id``
and ``episode_number`` are populated. The orchestrator then enriches the
request from conversation cards.

The tool's ``include_assets`` / ``include_script`` / ``include_panels`` args
are accepted for forward-compat but currently the orchestrator commits
everything as one atomic step — the flags are recorded in the response so
callers can see the requested scope.
"""
from __future__ import annotations

from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY


SCHEMA = {
    "type": "object",
    "properties": {
        "include_assets": {"type": "boolean", "default": True},
        "include_script": {"type": "boolean", "default": True},
        "include_panels": {"type": "boolean", "default": True},
    },
}


async def handle(args: dict, context: dict, db, tracer) -> dict:
    project_id = context.get("project_id")
    episode_number = context.get("episode_number")
    conversation_id = context.get("conversation_id")

    if not (project_id and episode_number and conversation_id):
        return {
            "error": (
                "commit_to_studio requires project_id, episode_number, and "
                "conversation_id in context"
            ),
        }

    include_assets = args.get("include_assets", True)
    include_script = args.get("include_script", True)
    include_panels = args.get("include_panels", True)

    try:
        from app.services.agent_commit.commit_orchestrator import commit_agent_to_studio
        from app.schemas.agent_commit import CommitToStudioRequest

        # Lean request: orchestrator pulls panels/characters/scenes/art_style
        # from conversation cards via enrich_request_from_conversation.
        req = CommitToStudioRequest(
            conversation_id=conversation_id,
            episode_number=int(episode_number),
        )

        result = await commit_agent_to_studio(db, project_id, req)
        # The orchestrator does not commit; the runner's outer transaction
        # ownership applies. We commit here because the agent runner does
        # NOT wrap individual tool calls in a transaction — each tool is
        # responsible for its own writes (matching refine_script.py's
        # convention).
        if db is not None:
            db.commit()

        chapter_id = getattr(result.chapter, "id", None) if result.chapter else None
        return {
            "success": True,
            "status": getattr(result, "status", "unknown"),
            "chapter_id": chapter_id,
            "character_count": getattr(result, "character_count", 0),
            "scene_count": getattr(result, "scene_count", 0),
            "panel_count": getattr(result, "panel_count", 0),
            "warnings": list(getattr(result, "warnings", []) or []),
            "payload_source": getattr(result, "payload_source", None),
            "requested_scope": {
                "include_assets": include_assets,
                "include_script": include_script,
                "include_panels": include_panels,
            },
        }
    except TypeError as e:
        # commit_agent_to_studio signature mismatch — treat as a wiring bug
        return {"error": f"commit_agent_to_studio signature mismatch: {e!r}"}
    except Exception as e:  # noqa: BLE001 — surface to agent loop
        if db is not None:
            try:
                db.rollback()
            except Exception:  # noqa: BLE001 — rollback best-effort
                pass
        return {"error": f"commit_to_studio failed: {e!r}"}


tool = ToolDefinition(
    name="commit_to_studio",
    description=(
        "Commit the current episode's agent-mode artifacts (assets, script, "
        "panels) to Studio Workbench. Creates a Chapter + Panels + Assets in a "
        "single DB transaction; idempotent on (project, conversation, episode)."
    ),
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id", "episode_number", "conversation_id"),
    expected_duration="fast",
    read_only=False,
    side_effects=("writes:chapter", "writes:panels", "writes:assets"),
)
TOOL_REGISTRY.register(tool)
