"""Static-source regression — episode endpoints must delegate to new tools (B-1 Phase C).

These tests use ``inspect.getsource`` on ``app/api/routes/agent.py`` to verify
that the intended endpoints reference the corresponding tool handler imports.
They guard against accidental reverts of the Phase C delegation refactors
introduced by Batch 4 (Group 2).

Coverage:
- /agent/episode/{N}/script           → generate_script tool import
- /agent/episode/{N}/script/stream    → inherits via _generate_episode_script_core
                                         (same module reference still asserted)
- /agent/episode/{N}/refine           → refine_script tool import
- /agent/episode/{N}/generate-panels  → panel_generation helper (Batch 3)

Notes:
- ``/agent/episode/{N}/render`` does not exist in agent.py — there is no
  Phase C task for it (the render-trigger lives elsewhere via
  /generate-panels). Test omitted.
- The /script and /refine endpoints intentionally only delegate the
  side-effect (chapter persistence / feedback recording) to the tool while
  retaining their own LLM-driven richer response shapes. The tests therefore
  only assert *import presence*, not full delegation.
"""
import inspect


def test_script_or_stream_endpoint_imports_generate_script_tool():
    """At least one of the script endpoints (non-streaming or streaming) must
    reference ``app.services.agent.tools.generate_script``."""
    from app.api.routes import agent

    src = inspect.getsource(agent)
    assert (
        "app.services.agent.tools.generate_script" in src
        or "agent.tools.generate_script" in src
    ), "neither /script nor /script/stream endpoint references the generate_script tool"


def test_refine_endpoint_imports_refine_script_tool():
    """/refine endpoint must reference ``app.services.agent.tools.refine_script``."""
    from app.api.routes import agent

    src = inspect.getsource(agent)
    assert (
        "app.services.agent.tools.refine_script" in src
        or "agent.tools.refine_script" in src
    ), "/refine endpoint does not reference the refine_script tool"


def test_generate_panels_endpoint_uses_new_helper():
    """/generate-panels must use the panel_generation helper introduced in Batch 3."""
    from app.api.routes import agent

    src = inspect.getsource(agent)
    assert (
        "panel_generation" in src
        or "generate_panels_for_episode" in src
        or "generate_panel_images_for_payload" in src
    ), "/generate-panels endpoint does not reference the panel_generation helper"
