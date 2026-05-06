"""create_character — slow; creates a character asset and dispatches portrait generation.

Two-step flow (mirrors POST /api/v1/assets/characters/{id}/regenerate-reference):

  1. INSERT a row into ``assets`` with type='character', name, description,
     and an ``appearance_traits`` list parsed from the agent-supplied
     ``appearance`` string. ``reference_image_status`` is set to
     'generating' immediately so the UI can show a spinner.
  2. Dispatch ``app.workers.async_runner.run_portrait_generation`` (Celery)
     to do the actual portrait + FaceID extraction work asynchronously.

Returns the new asset_id + the Celery task id so callers can poll.
"""
from __future__ import annotations

import logging
import uuid

from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY


logger = logging.getLogger(__name__)


SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
        "appearance": {
            "type": "string",
            "description": (
                "Detailed visual description for portrait generation. "
                "Comma-separated traits are split into appearance_traits."
            ),
        },
    },
    "required": ["name", "description", "appearance"],
}


def _split_traits(appearance: str) -> list[str]:
    """Split a free-form appearance string into a traits list.

    Splits on commas, semicolons, and Chinese full-width commas. Empty
    pieces dropped.
    """
    if not appearance:
        return []
    cleaned = (
        appearance.replace("，", ",")
        .replace("；", ";")
        .replace(";", ",")
    )
    return [t.strip() for t in cleaned.split(",") if t.strip()]


async def handle(args: dict, context: dict, db, tracer) -> dict:
    name = (args.get("name") or "").strip()
    description = args.get("description") or ""
    appearance = args.get("appearance") or ""
    project_id = context.get("project_id")

    if not name:
        return {"error": "create_character requires non-empty 'name'"}
    if not project_id:
        return {"error": "create_character requires project_id in context"}
    if db is None:
        return {"error": "create_character requires a DB session"}

    try:
        from app.models.asset import Asset

        # Idempotency: if a character with this name already exists in
        # the project, reuse it (matches asset_sync.sync_character).
        existing = (
            db.query(Asset)
            .filter(
                Asset.project_id == project_id,
                Asset.type == "character",
                Asset.name == name,
            )
            .first()
        )
        if existing is not None:
            return {
                "success": True,
                "asset_id": existing.id,
                "name": name,
                "status": "already_exists",
                "note": "Returning existing character asset; no new dispatch.",
            }

        traits = _split_traits(appearance)
        asset_id = str(uuid.uuid4())
        asset = Asset(
            id=asset_id,
            project_id=project_id,
            type="character",
            name=name,
            description=description,
            data_json={
                "appearance": appearance,
                "appearance_traits": traits,
                "created_via": "agent_tool",
            },
            reference_image_status="generating",
        )
        db.add(asset)
        db.commit()

        # Dispatch portrait generation. The Celery task is the same one
        # the /assets/characters/{id}/regenerate-reference HTTP route
        # dispatches.
        from app.workers.async_runner import run_portrait_generation

        celery_result = run_portrait_generation.delay(
            character_id=asset_id,
            project_id=project_id,
            character_name=name,
            character_description=description,
            appearance_traits=traits,
            provider="mock",
        )

        return {
            "success": True,
            "asset_id": asset_id,
            "name": name,
            "status": "created",
            "dispatched": {
                "task_id": getattr(celery_result, "id", None),
                "celery_task": (
                    "app.workers.async_runner.run_portrait_generation"
                ),
                "eta_seconds": 90,
            },
        }
    except Exception as e:  # noqa: BLE001 — surface to agent loop
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return {"error": f"create_character failed: {e!r}"}


tool = ToolDefinition(
    name="create_character",
    description=(
        "Create a new character asset (with name, description, "
        "appearance) and dispatch a portrait-generation Celery task. "
        "Idempotent on (project_id, name)."
    ),
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id",),
    expected_duration="slow",
    read_only=False,
    side_effects=("writes:asset", "writes:asset.reference_image"),
)
TOOL_REGISTRY.register(tool)
