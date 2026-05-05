"""Bugs #14, #15: commit_orchestrator data-handling correctness.

#14 — Panel.preview_url was assigned a raw MinIO storage key from
``fetch_and_persist`` instead of a URL. The frontend renders ``preview_url``
directly as an ``<img src>`` so storing a key produces broken images.

#15 — ``order_index=agent_panel.order if agent_panel.order else idx`` is a
truthy check that overwrites a legitimate ``order=0`` with the loop index.
Must use ``is not None``.
"""
import inspect


def test_order_zero_preserved():
    """Bug #15: order=0 must be preserved, not overwritten with idx via truthy check."""
    from app.services.agent_commit import commit_orchestrator
    src = inspect.getsource(commit_orchestrator)
    assert "agent_panel.order if agent_panel.order else" not in src, (
        "Truthy/falsy check on order=0 still present — use `is not None` instead"
    )


def test_preview_url_is_url_not_raw_key():
    """Bug #14: Panel.preview_url must be a URL, not a raw MinIO key."""
    from app.services.agent_commit import commit_orchestrator
    src = inspect.getsource(commit_orchestrator)
    # The buggy form was: preview_url=preview_key (raw assignment).
    # Fixed form converts the key to a presigned URL via storage helper before
    # assigning.
    assert "preview_url=preview_key" not in src, (
        "preview_url is still being assigned a raw storage key — convert via "
        "storage_client.get_url(key) first"
    )
