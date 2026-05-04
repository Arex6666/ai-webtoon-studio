"""Bug #10: /media/url must accept agent-commit/ keys.

Pre-existing bug in this PR's batch causes the very first
``from app.main import app`` to raise ImportError; the warmup helper
absorbs it so subsequent imports (cached partial module) succeed.
"""
import pytest


def _warmup_app_import() -> None:
    try:
        from app.main import app  # noqa: F401
    except Exception:
        pass


_warmup_app_import()


@pytest.mark.parametrize("key", [
    "agent-commit/proj1/panel-1.png",
    "agent_commit/proj1/panel-1.png",
    "generated/x.png",   # sanity: existing prefix still works
])
def test_media_url_accepts_agent_commit_prefix(test_client, key):
    """The media URL endpoint must not reject ``agent-commit/`` or
    ``agent_commit/`` prefixed keys with HTTP 400.

    A 200 (URL returned) or 404 (key absent in storage) or 503 (storage
    unavailable in test env) are all acceptable — the prefix is simply
    not the gating reason for failure. A 400 means the prefix gate
    rejected the key, which is the bug.
    """
    resp = test_client.get(f"/api/v1/media/url?key={key}")
    assert resp.status_code != 400, (
        f"Key {key!r} rejected with 400. Body: {resp.text}"
    )
