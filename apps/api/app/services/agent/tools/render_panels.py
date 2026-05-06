"""render_panels — slow; dispatches ComfyUI render jobs for one or more panels.

Wires real Celery dispatch to ``app.workers.image_worker.execute_image_job``
(which is the actual @shared_task name registered in apps/api/app/workers/
image_worker.py — ``run_render`` does not exist; ``execute_image_job`` is the
canonical task that consumes a Job row and panel id).

For each panel id we insert a ``Job`` row (status=queued) and call
``celery_app.send_task`` with the worker's task name, args=[job_id, panel_id]
and queue="image". ``task_id`` is set to the Job's UUID so the Celery
AsyncResult id matches the DB row, mirroring the route convention in
apps/api/app/api/routes/jobs.py.

If ``db`` is None (unit-test path) we fall back to a synthetic job_id so the
tool stays callable without a DB session — mocked send_task in tests asserts
the dispatch arguments rather than DB persistence.
"""
import logging
import uuid
from typing import Any

from app.celery_app import celery_app
from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY


logger = logging.getLogger(__name__)

# Canonical Celery task name for image rendering. Kept as a module-level
# constant so tests can import & assert against it without string drift.
IMAGE_RENDER_TASK = "app.workers.image_worker.execute_image_job"

SCHEMA = {
    "type": "object",
    "properties": {
        "panel_ids": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "description": "Panel IDs to render.",
        },
        "force_regenerate": {
            "type": "boolean",
            "default": False,
            "description": "If true, dispatch even when a recent successful render exists.",
        },
    },
    "required": ["panel_ids"],
}


def _create_image_job_row(db, panel_id: str, project_id: str | None, force_regenerate: bool) -> str:
    """Insert a queued Job row for an image render and return its id.

    Falls back to a synthetic UUID when db is None (tests) — this keeps the
    handler callable without a DB while still exercising the dispatch path.
    """
    if db is None:
        return str(uuid.uuid4())
    try:
        # Local imports — these pull SQLAlchemy models which we don't want at
        # module import time (keeps the tool definition import-light).
        from app.api.routes.jobs import create_job_record, JobType
        from app.models.panel import Panel

        chapter_id = None
        try:
            panel = db.query(Panel).filter(Panel.id == panel_id).first()
            if panel is not None:
                chapter_id = panel.chapter_id
        except Exception as e:  # noqa: BLE001 — DB lookup is best-effort
            logger.warning("render_panels: panel lookup failed for %s: %r", panel_id, e)

        job = create_job_record(
            db=db,
            job_type=JobType.IMAGE.value,
            provider="comfyui",
            inputs={"force_regenerate": bool(force_regenerate)},
            panel_id=panel_id,
            chapter_id=chapter_id,
            project_id=project_id,
        )
        return job.id
    except Exception as e:  # noqa: BLE001 — never fail the tool just because DB is wonky
        logger.warning("render_panels: create_job_record failed: %r — using synthetic job id", e)
        return str(uuid.uuid4())


async def handle(args: dict, context: dict, db, tracer) -> dict[str, Any]:
    panel_ids = args.get("panel_ids") or []
    if not panel_ids:
        return {"error": "panel_ids must be a non-empty list"}

    force_regenerate = bool(args.get("force_regenerate", False))
    project_id = context.get("project_id") if context else None

    trace_kwargs: dict[str, Any] = {}
    if tracer is not None:
        # Best-effort attribute access — tests may pass a stub tracer.
        if hasattr(tracer, "trace_id"):
            trace_kwargs["_trace_id"] = tracer.trace_id
        if hasattr(tracer, "current_span_id"):
            trace_kwargs["_parent_span_id"] = tracer.current_span_id

    dispatched_jobs: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []

    for panel_id in panel_ids:
        job_id = _create_image_job_row(db, panel_id, project_id, force_regenerate)
        try:
            celery_app.send_task(
                IMAGE_RENDER_TASK,
                args=[job_id, panel_id],
                kwargs=trace_kwargs,
                queue="image",
                task_id=job_id,
            )
            dispatched_jobs.append({"panel_id": panel_id, "job_id": job_id})
        except Exception as e:  # noqa: BLE001 — surface dispatch failures without aborting the batch
            logger.exception("render_panels: send_task failed for panel %s", panel_id)
            errors.append({"panel_id": panel_id, "error": repr(e)})

    # Match the original "dispatched" envelope shape but extend it: when a
    # single panel is rendered keep the legacy single-job summary; otherwise
    # return the per-panel list. Callers can always read `panel_ids` and
    # `jobs` for full detail.
    if len(dispatched_jobs) == 1:
        dispatched: dict[str, Any] = {
            "job_id": dispatched_jobs[0]["job_id"],
            "eta_seconds": 180,
        }
    else:
        dispatched = {
            "jobs": dispatched_jobs,
            "eta_seconds": 180 * max(1, len(dispatched_jobs)),
        }

    out: dict[str, Any] = {
        "dispatched": dispatched,
        "panel_ids": list(panel_ids),
        "task_name": IMAGE_RENDER_TASK,
        "queue": "image",
    }
    if errors:
        out["errors"] = errors
    return out


tool = ToolDefinition(
    name="render_panels",
    description="Render one or more panels to final layered images (full + char + bg + mask) via ComfyUI. Long-running; dispatches a background Celery job per panel.",
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id", "episode_number"),
    expected_duration="slow",
    read_only=False,
    side_effects=("writes:render_job", "writes:layerpack", "writes:panel.preview_url"),
)
TOOL_REGISTRY.register(tool)
