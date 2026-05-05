"""Bugs #12, #19, #20: agent.py route correctness.

#12 — Partial image-gen failures in ``generate_full_episode_script`` were
silently swallowed by ``[r for r in results if isinstance(r, T)] or originals``,
hiding failures from callers and producing logs with no signal.

#19 — ``commit-to-studio`` ran ``getattr(project, "owner_id", None)`` to enforce
authz, but ``Project`` has no ``owner_id`` column, so the check was always
``None`` and silently no-op'd. Removed to avoid the false sense of security.

#20 — In the ``/episode1/script`` endpoint, ``result = Episode1Response(...)``
was followed by ``hasattr(result, "characters") and result.characters`` etc.
``Episode1Response`` only declares ``episodeTitle`` and ``scriptText``; the
guards were always False so the entire block was unreachable card-write code.
"""
import inspect
import re


# ---------------------------------------------------------------------------
# #20 — dead Episode1Response card writes
# ---------------------------------------------------------------------------


def test_episode1_response_dead_card_writes_removed():
    """Bug #20: Episode1Response has no characters/scenes/art_style fields;
    hasattr() guards in agent.py were always-False — must be removed."""
    from app.api.routes import agent
    src = inspect.getsource(agent)
    # The Episode1Response dead block specifically guards `result.characters`,
    # `result.scenes`, `result.art_style` — these guards are always False on
    # an Episode1Response and must be removed from the episode1 endpoint.
    # The full episode-script endpoint legitimately uses the same field names
    # on EpisodeScriptResponse, so we narrow the assertion to the episode1
    # function body via a sliced source range.
    src_episode1 = _slice_function_source(agent, "generate_episode1_script")
    assert src_episode1, "generate_episode1_script no longer importable from agent.py"
    assert 'hasattr(result, "characters") and result.characters' not in src_episode1
    assert 'hasattr(result, "scenes") and result.scenes' not in src_episode1
    assert 'hasattr(result, "art_style") and result.art_style' not in src_episode1


def _slice_function_source(module, fn_name: str) -> str:
    """Return source of `fn_name` in `module`, or full module source as
    fallback if the function is gone (also acceptable for the test)."""
    fn = getattr(module, fn_name, None)
    if fn is None:
        return ""
    try:
        return inspect.getsource(fn)
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# #19 — phantom owner_id authz check
# ---------------------------------------------------------------------------


def test_no_phantom_owner_id_check_in_commit_to_studio():
    """Bug #19: commit-to-studio must not pretend to enforce authz via missing field."""
    from app.api.routes import agent
    # Strip comment-only lines so a documenting TODO mentioning the dropped
    # call doesn't trip the assertion. Inline (`x = 1  # comment about
    # getattr(project, "owner_id"...)`) would still trip the test, but that
    # would be misleading documentation anyway.
    src_no_comments = "\n".join(
        line for line in inspect.getsource(agent).splitlines()
        if not line.lstrip().startswith("#")
    )
    assert 'getattr(project, "owner_id"' not in src_no_comments
    assert "getattr(project, 'owner_id'" not in src_no_comments


# ---------------------------------------------------------------------------
# #12 — silent partial image-gen failures
# ---------------------------------------------------------------------------


def test_partial_image_gen_logs_failures():
    """Bug #12: failures from asyncio.gather must surface in logs, not be silently
    swallowed by ``or characters`` / ``or scenes``."""
    from app.api.routes import agent
    src = inspect.getsource(agent)

    # The silent fallback ``or characters`` / ``or scenes`` after the gather
    # made any partial failure invisible — must be removed.
    assert "if isinstance(r, Character)] or characters" not in src, (
        "Silent ``or characters`` fallback still present — failed image gen "
        "is being masked by returning the original ungenerated list"
    )
    assert "if isinstance(r, Scene)] or scenes" not in src, (
        "Silent ``or scenes`` fallback still present — failed image gen "
        "is being masked by returning the original ungenerated list"
    )

    # And there must be at least one warning/error log in the gather region
    # that names image/character/scene generation failure.
    assert re.search(
        r"logger\.(warning|error|exception)\([^)]*(image|gen).*fail",
        src,
        re.IGNORECASE,
    ), "No warning log around image-gen failures — failures will be silent"
