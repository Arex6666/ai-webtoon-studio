"""Bugs #7, #8: versions.py constructs VersionManager and calls its methods correctly.

Bug #7: ``versions.py`` constructed ``VersionManager(db)`` even though
``VersionManager.__init__`` takes no arguments — every request to a
``/versions/...`` endpoint raised ``TypeError`` before reaching any logic.

Bug #8: the same routes called ``vm.list_snapshots(..., entity_type=...)``
and ``vm.rollback_to(..., entity_type=...)``. Neither method accepts an
``entity_type`` kwarg, so even after Bug #7 was sidestepped the calls
would still raise ``TypeError``.

These tests use ``inspect`` rather than the live ``TestClient`` so they
remain meaningful even if the broader app graph is partially broken in
this PR (see ``_warmup_app_import`` below for the known pre-existing
import quirk).
"""
import inspect
import re


def _warmup_app_import() -> None:
    """Absorb pre-existing ImportError (subtitle_provider). Remove after task #9.

    See ``tests/unit/test_router_registration.py`` for the full story —
    the very first ``from app.main import app`` in a fresh interpreter
    raises ``ImportError`` due to a separate, unrelated bug. Subsequent
    imports succeed because Python caches the partial module.
    """
    try:
        from app.main import app  # noqa: F401
    except Exception:
        pass


_warmup_app_import()


from app.services.graph.version_manager import VersionManager  # noqa: E402
from app.api.routes import versions as versions_route  # noqa: E402


def test_version_manager_constructor_has_no_required_args():
    """Bug #7: route constructs VersionManager() with no args."""
    sig = inspect.signature(VersionManager.__init__)
    required = [
        n for n, p in sig.parameters.items()
        if n != "self" and p.default is inspect.Parameter.empty
    ]
    assert required == [], (
        f"VersionManager.__init__ has required params {required}; "
        f"the route's get_version_manager() must construct it without args."
    )


def test_route_does_not_pass_unsupported_kwargs_to_list_snapshots():
    """Bug #8: list_snapshots must not be called with kwargs it doesn't accept."""
    list_snapshots_sig = inspect.signature(VersionManager.list_snapshots)
    accepted = set(list_snapshots_sig.parameters.keys())
    src = inspect.getsource(versions_route)
    # Match the *call* on the manager (vm.list_snapshots(...)), not the
    # FastAPI route handler that happens to share the name.
    m = re.search(r"\.list_snapshots\(([^)]*)\)", src)
    assert m, "vm.list_snapshots call not found in versions.py"
    call_args = m.group(1)
    kwarg_names = re.findall(r"(\w+)\s*=", call_args)
    unsupported = [k for k in kwarg_names if k not in accepted]
    assert unsupported == [], (
        f"versions.py passes unsupported kwargs {unsupported} to "
        f"VersionManager.list_snapshots (accepts: {accepted})"
    )


def test_route_does_not_pass_unsupported_kwargs_to_rollback_to():
    """Bug #8: rollback_to must not be called with kwargs it doesn't accept."""
    rollback_to_sig = inspect.signature(VersionManager.rollback_to)
    accepted = set(rollback_to_sig.parameters.keys())
    src = inspect.getsource(versions_route)
    # Match the *call* on the manager (vm.rollback_to(...)), not any
    # similarly-named handler.
    m = re.search(r"\.rollback_to\(([^)]*)\)", src)
    assert m, "vm.rollback_to call not found in versions.py"
    call_args = m.group(1)
    kwarg_names = re.findall(r"(\w+)\s*=", call_args)
    unsupported = [k for k in kwarg_names if k not in accepted]
    assert unsupported == [], (
        f"versions.py passes unsupported kwargs {unsupported} to "
        f"VersionManager.rollback_to (accepts: {accepted})"
    )
