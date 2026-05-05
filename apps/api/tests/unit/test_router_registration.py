"""Verify critical routers are registered on the FastAPI app.

Bug #1: qa_fix, versions, voices, music routers were never registered in
main.py, leaving the E5 NeedsFix workflow API and several others
unreachable.

Bug #6: chapters/automation.py dispatched a non-existent Celery task name
(``app.workers.image_worker.execute_render_job``). The real task is
``app.workers.async_runner.execute_render_job_celery``.
"""
import inspect
import re

import pytest


# Each entry: (label, substring that must appear in at least one route path).
# Substrings include the ``/api/v1/`` prefix to avoid false positives from
# other routers whose paths contain the same word (e.g. ``/shot-versions``
# contains the word ``versions`` but is unrelated to the versions router).
@pytest.mark.parametrize(
    "label,substring",
    [
        ("qa_fix", "/api/v1/qa-fix"),
        ("versions", "/api/v1/versions"),
        ("voices", "/api/v1/voices"),
        ("music", "/api/v1/music"),
    ],
)
def test_router_registered(test_client, label, substring):
    paths = [getattr(r, "path", "") for r in test_client.app.routes]
    assert any(substring in p for p in paths), (
        f"No route path contains {substring!r} (router {label!r} not registered). "
        f"Registered paths: {paths}"
    )


def test_confirm_assets_dispatches_existing_task():
    """Bug #6: dispatch must reference a real Celery task name AND match its arity.

    The original bug shipped the right task name but only one positional arg,
    while the wrapper needed two. This test asserts both: name is registered,
    and the args= list length matches the task's parameter count (excluding
    self for bound tasks).
    """
    import app.workers.async_runner  # noqa: F401
    from app.celery_app import celery_app
    from app.api.routes.chapters import automation as ca

    src = inspect.getsource(ca)
    m = re.search(
        r"send_task\(\s*['\"]([^'\"]+)['\"]\s*,\s*args\s*=\s*\[([^\]]*)\]",
        src,
    )
    assert m, "send_task call with args=[...] not found in automation.py"
    dispatched, args_literal = m.group(1), m.group(2)

    registered = set(celery_app.tasks.keys())
    assert dispatched in registered, (
        f"Dispatched task {dispatched!r} is not a registered Celery task. "
        f"Candidate render/job tasks: "
        f"{sorted(t for t in registered if 'render' in t or 'job' in t)}"
    )

    task_func = celery_app.tasks[dispatched].run
    sig = inspect.signature(task_func)
    expected_arity = len(sig.parameters)

    # Count comma-separated args in the dispatched call. Strip whitespace and
    # ignore an empty literal (args=[]).
    dispatched_args = [a.strip() for a in args_literal.split(",") if a.strip()]
    assert len(dispatched_args) == expected_arity, (
        f"Dispatched {dispatched!r} with {len(dispatched_args)} positional "
        f"args ({dispatched_args!r}) but task expects {expected_arity} "
        f"({list(sig.parameters)!r})"
    )
