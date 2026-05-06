"""regenerate_asset_image — slow; regenerates a single character/scene asset's reference image.

Closes the episode-page TODO: '调用后端重新生成单个角色/场景图片'.

Dispatches the appropriate Celery task based on asset type:
  * ``character`` → ``app.workers.async_runner.run_portrait_generation``
  * ``scene``     → ``app.workers.async_runner.run_scene_anchor_generation``
  * other types   → not supported (returns an error)

This mirrors the existing HTTP routes
``/api/v1/assets/characters/{id}/regenerate-reference`` and
``/api/v1/assets/scenes/{id}/regenerate-anchor``. The Celery task IDs
are returned in the result so the frontend (or a follow-up tool call)
can poll status.

The ``prompt_override`` arg is accepted for forward-compat — neither
underlying task currently honours it. We pass it through in
``data_json`` so a future revision of the portrait/anchor pipelines
can pick it up.
"""
from __future__ import annotations

import logging

from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY


logger = logging.getLogger(__name__)


SCHEMA = {
    "type": "object",
    "properties": {
        "prompt_override": {
            "type": "string",
            "description": (
                "Optional prompt to use instead of the asset's stored "
                "prompt. Currently recorded in asset.data_json but the "
                "underlying portrait/anchor pipelines do not yet honour it."
            ),
        },
    },
}


async def handle(args: dict, context: dict, db, tracer) -> dict:
    asset_id = context.get("asset_id")
    project_id = context.get("project_id")
    prompt_override = args.get("prompt_override")

    if not asset_id:
        return {"error": "regenerate_asset_image requires asset_id in context"}
    if db is None:
        return {"error": "regenerate_asset_image requires a DB session"}

    try:
        from app.models.asset import Asset

        asset = db.query(Asset).filter(Asset.id == asset_id).first()
        if asset is None:
            return {"error": f"asset {asset_id} not found"}

        if project_id and asset.project_id != project_id:
            return {
                "error": (
                    f"asset {asset_id} belongs to project "
                    f"{asset.project_id!r}, not the active project "
                    f"{project_id!r}"
                ),
            }

        # Record the optional prompt override into data_json so a future
        # pipeline revision can read it.
        if prompt_override:
            data = dict(asset.data_json or {})
            data["prompt_override"] = prompt_override
            asset.data_json = data

        if asset.type == "character":
            asset.reference_image_status = "generating"
            db.commit()

            from app.workers.async_runner import run_portrait_generation
            data = asset.data_json or {}
            traits = data.get("appearance_traits", []) or []
            celery_result = run_portrait_generation.delay(
                character_id=asset.id,
                project_id=asset.project_id,
                character_name=asset.name,
                character_description=asset.description,
                appearance_traits=traits,
                provider="mock",
            )
            return {
                "success": True,
                "asset_id": asset_id,
                "asset_type": "character",
                "dispatched": {
                    "task_id": getattr(celery_result, "id", None),
                    "celery_task": (
                        "app.workers.async_runner.run_portrait_generation"
                    ),
                    "eta_seconds": 60,
                },
            }

        if asset.type == "scene":
            data = dict(asset.data_json or {})
            data["anchor_status"] = "generating"
            asset.data_json = data
            db.commit()

            from app.workers.async_runner import run_scene_anchor_generation
            celery_result = run_scene_anchor_generation.delay(
                scene_id=asset.id,
                project_id=asset.project_id,
                scene_name=asset.name,
                location=data.get("location"),
                time_of_day=data.get("time_of_day"),
                mood=data.get("mood"),
                provider="mock",
                db_session=None,
            )
            return {
                "success": True,
                "asset_id": asset_id,
                "asset_type": "scene",
                "dispatched": {
                    "task_id": getattr(celery_result, "id", None),
                    "celery_task": (
                        "app.workers.async_runner.run_scene_anchor_generation"
                    ),
                    "eta_seconds": 60,
                },
            }

        return {
            "error": (
                f"asset type {asset.type!r} not supported — "
                "only 'character' and 'scene' have regeneration pipelines"
            ),
        }
    except Exception as e:  # noqa: BLE001 — surface to agent loop
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return {"error": f"regenerate_asset_image failed: {e!r}"}


tool = ToolDefinition(
    name="regenerate_asset_image",
    description=(
        "Regenerate the reference image for a single character or scene "
        "asset. Long-running; dispatches a Celery task "
        "(run_portrait_generation for characters, "
        "run_scene_anchor_generation for scenes)."
    ),
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id", "asset_id"),
    expected_duration="slow",
    read_only=False,
    side_effects=("writes:asset.reference_image",),
)
TOOL_REGISTRY.register(tool)
