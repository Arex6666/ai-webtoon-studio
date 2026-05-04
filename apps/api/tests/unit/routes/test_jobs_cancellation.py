"""Bugs #3 + #4: Timeline access via chapter, cancel_job uses real Celery task id."""
import inspect
import re


def _warmup_app_import():
    """Absorb pre-existing ImportError (subtitle_provider). Remove after task #9."""
    try:
        from app.main import app  # noqa: F401
    except Exception:
        pass


_warmup_app_import()


def test_no_module_accesses_timeline_project_id():
    """Bug #3: Timeline has no project_id; no production code may access it."""
    from app.api.routes import jobs as jobs_route
    from app.workers import video_worker

    for module in (jobs_route, video_worker):
        src = inspect.getsource(module)
        assert "timeline.project_id" not in src, (
            f"{module.__name__} still references non-existent Timeline.project_id"
        )


def test_cancel_job_revokes_celery_task_id_not_job_id():
    """Bug #4: cancel_job must revoke job.celery_task_id, not the internal job_id."""
    from app.api.routes import jobs as jobs_route

    src = inspect.getsource(jobs_route)
    # Find the .control.revoke(...) call. Args[0] must be celery_task_id (not job_id).
    m = re.search(r"control\.revoke\(\s*([^,)]+)", src)
    assert m, "No celery .control.revoke(...) call found in jobs.py"
    first_arg = m.group(1).strip()
    assert "celery_task_id" in first_arg, (
        f"control.revoke first arg is {first_arg!r}; expected something containing "
        f"'celery_task_id' (not the internal job id)"
    )


def test_job_model_has_celery_task_id_column():
    """Bug #4 (model side): Job must have a celery_task_id column."""
    from app.models.job import Job

    columns = {c.name for c in Job.__table__.columns}
    assert "celery_task_id" in columns, (
        f"Job model is missing celery_task_id column. Has: {columns}"
    )
