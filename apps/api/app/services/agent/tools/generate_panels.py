"""generate_panels — slow; generates panel images via Doubao for the current episode.

Reads the latest ``art_style`` / ``characters`` / ``scenes`` cards and the
``panels`` card for ``episode_number`` from the active conversation, then
runs the same orchestration the
``/agent/episode/{N}/generate-panels`` HTTP endpoint uses.

Implementation is in
``app.services.agent_commit.panel_generation.generate_panels_for_episode``.
The handler is sync-await (not Celery-dispatched), so the agent runner
blocks here until generation finishes; the tool is therefore marked
``expected_duration="slow"`` (typical wall time 30–90s for a 6–10 panel
episode).

A ``conversation_id`` is required in context — the runner injects it
automatically. ``force_regenerate`` is accepted for forward-compat.
"""
from __future__ import annotations

from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY


SCHEMA = {
    "type": "object",
    "properties": {
        "force_regenerate": {
            "type": "boolean",
            "default": False,
            "description": (
                "Regenerate even if panels already have images. Currently a "
                "no-op (always regenerates) — future revision will short-"
                "circuit on existing keys."
            ),
        },
    },
}


async def handle(args: dict, context: dict, db, tracer) -> dict:
    project_id = context.get("project_id")
    episode_number = context.get("episode_number")
    conversation_id = context.get("conversation_id")
    force_regenerate = bool(args.get("force_regenerate", False))

    if not (project_id and episode_number and conversation_id):
        return {
            "error": (
                "generate_panels requires project_id, episode_number, and "
                "conversation_id in context"
            ),
        }
    if db is None:
        return {"error": "generate_panels requires a DB session"}

    try:
        from app.services.agent_commit.panel_generation import (
            generate_panels_for_episode,
        )

        result = await generate_panels_for_episode(
            db=db,
            project_id=project_id,
            episode_number=int(episode_number),
            conversation_id=conversation_id,
            force_regenerate=force_regenerate,
        )
        # Forward the helper's structured result.
        return {
            "success": True,
            "panel_count": result.get("panel_count", 0),
            "success_count": result.get("success_count", 0),
            "panels": result.get("panels", []),
            "warnings": result.get("warnings", []),
        }
    except Exception as e:  # noqa: BLE001 — surface to agent loop
        return {"error": f"generate_panels failed: {e!r}"}


tool = ToolDefinition(
    name="generate_panels",
    description=(
        "Generate panel preview images for the current episode using the "
        "configured Doubao image-gen pipeline. Reads art_style / characters "
        "/ scenes / panels cards from the conversation. Long-running "
        "(30–90s typical)."
    ),
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id", "episode_number", "conversation_id"),
    expected_duration="slow",
    read_only=False,
    side_effects=("writes:panel.preview_url", "writes:panel.preview_key"),
)
TOOL_REGISTRY.register(tool)
