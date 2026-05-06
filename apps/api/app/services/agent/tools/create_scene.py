"""create_scene — slow; creates a scene asset and dispatches anchor generation.

Two-step flow (mirrors POST /api/v1/assets/scenes/{id}/regenerate-anchor):

  1. INSERT a row into ``assets`` with type='scene', name, description,
     and ``data_json`` carrying location / time_of_day / mood hints
     parsed out of the description (best-effort; user can refine later).
     ``data_json.anchor_status`` is set to 'generating' immediately so
     the UI can show a spinner.
  2. Dispatch ``app.workers.async_runner.run_scene_anchor_generation``
     (Celery) which generates a SceneAnchor + ControlMaps via the
     ``scene_anchor`` services.

Returns the new asset_id + the Celery task id so callers can poll.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY


logger = logging.getLogger(__name__)


SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
        "location": {
            "type": "string",
            "description": "Optional location hint (e.g., 'forest', 'cafe').",
        },
        "time_of_day": {
            "type": "string",
            "description": (
                "Optional time-of-day hint (e.g., 'day', 'night', 'dusk')."
            ),
        },
        "mood": {
            "type": "string",
            "description": "Optional mood hint (e.g., 'calm', 'tense').",
        },
    },
    "required": ["name", "description"],
}


async def handle(args: dict, context: dict, db, tracer) -> dict:
    name = (args.get("name") or "").strip()
    description = args.get("description") or ""
    location: Optional[str] = args.get("location") or None
    time_of_day: Optional[str] = args.get("time_of_day") or None
    mood: Optional[str] = args.get("mood") or None
    project_id = context.get("project_id")

    if not name:
        return {"error": "create_scene requires non-empty 'name'"}
    if not project_id:
        return {"error": "create_scene requires project_id in context"}
    if db is None:
        return {"error": "create_scene requires a DB session"}

    try:
        from app.models.asset import Asset

        # Idempotency: reuse existing scene with same name (matches
        # asset_sync.sync_scene).
        existing = (
            db.query(Asset)
            .filter(
                Asset.project_id == project_id,
                Asset.type == "scene",
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
                "note": "Returning existing scene asset; no new dispatch.",
            }

        asset_id = str(uuid.uuid4())
        data_json = {
            "location": location or "",
            "time_of_day": time_of_day or "",
            "mood": mood or "",
            "anchor_status": "generating",
            "created_via": "agent_tool",
        }
        asset = Asset(
            id=asset_id,
            project_id=project_id,
            type="scene",
            name=name,
            description=description,
            data_json=data_json,
        )
        db.add(asset)
        db.commit()

        # Dispatch scene anchor generation. The Celery task wraps
        # ``enqueue_scene_anchor_generation`` which produces the anchor
        # image + ControlMaps via the scene_anchor service.
        from app.workers.async_runner import run_scene_anchor_generation

        celery_result = run_scene_anchor_generation.delay(
            scene_id=asset_id,
            project_id=project_id,
            scene_name=name,
            location=location,
            time_of_day=time_of_day,
            mood=mood,
            provider="mock",
            db_session=None,
        )

        return {
            "success": True,
            "asset_id": asset_id,
            "name": name,
            "status": "created",
            "dispatched": {
                "task_id": getattr(celery_result, "id", None),
                "celery_task": (
                    "app.workers.async_runner.run_scene_anchor_generation"
                ),
                "eta_seconds": 60,
            },
        }
    except Exception as e:  # noqa: BLE001 — surface to agent loop
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return {"error": f"create_scene failed: {e!r}"}


tool = ToolDefinition(
    name="create_scene",
    description=(
        "Create a new scene asset (with name, description, optional "
        "location/time_of_day/mood hints) and dispatch a SceneAnchor + "
        "ControlMap generation Celery task. Idempotent on "
        "(project_id, name)."
    ),
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id",),
    expected_duration="slow",
    read_only=False,
    side_effects=("writes:asset", "writes:scene_anchor"),
)
TOOL_REGISTRY.register(tool)
