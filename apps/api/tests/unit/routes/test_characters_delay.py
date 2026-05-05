"""Bug #9: characters.py must not pass db_session= to run_portrait_generation."""
import inspect


def test_no_db_session_kwarg_in_delay():
    from app.api.routes.assets import characters
    src = inspect.getsource(characters)
    assert "db_session=None" not in src
    # Stricter: no db_session= kwarg at all (assuming the file doesn't use db_session anywhere else)
    assert "db_session=" not in src, (
        "characters.py still references db_session as a kwarg somewhere"
    )


def test_delay_call_kwargs_match_task_signature():
    """Defensive: kwargs passed to .delay() must match the underlying task signature."""
    from app.api.routes.assets import characters as characters_route
    from app.workers.async_runner import run_portrait_generation

    # Get the task's underlying function signature
    wrapped = getattr(run_portrait_generation, "run", None) or run_portrait_generation
    try:
        sig = inspect.signature(wrapped)
        accepted = set(sig.parameters.keys())
    except (TypeError, ValueError):
        accepted = None

    if accepted is None:
        # Can't introspect; skip the strict check
        return

    src = inspect.getsource(characters_route)
    import re
    m = re.search(r"run_portrait_generation\.delay\(([^)]*)\)", src, re.DOTALL)
    assert m, ".delay() call not found in characters.py"
    call_args = m.group(1)
    kwarg_names = set(re.findall(r"(\w+)\s*=", call_args))
    # Drop 'self' if present (it's never passed via .delay)
    accepted -= {"self"}
    unsupported = kwarg_names - accepted
    assert unsupported == set(), (
        f"characters.py passes unsupported kwargs {unsupported} to "
        f"run_portrait_generation.delay (task accepts: {accepted})"
    )
