"""Tests for resolve_panel_preview_url — the re-sign-on-read helper added
alongside migration 021 (Panel.preview_key column)."""
from types import SimpleNamespace
from unittest.mock import patch

from app.services.storage.panel_preview import (
    resolve_panel_preview_url,
    DEFAULT_PRESIGN_TTL_SECONDS,
)


def _make_panel(*, preview_key=None, preview_url=None):
    """Build a stand-in Panel — SimpleNamespace mimics ORM attribute access
    without needing a database session or full SQLAlchemy model."""
    return SimpleNamespace(preview_key=preview_key, preview_url=preview_url)


def test_prefers_key_and_resigns():
    panel = _make_panel(
        preview_key="projects/p1/panels/p1.png",
        preview_url="https://stale.example.com/old.png?expires=long-ago",
    )
    fresh = "https://fresh.example.com/p1.png?X-Amz-Signature=abc"
    with patch(
        "app.services.storage.panel_preview.storage_client.get_url",
        return_value=fresh,
    ) as get_url:
        result = resolve_panel_preview_url(panel)
    assert result == fresh
    get_url.assert_called_once_with(
        "projects/p1/panels/p1.png", expires=DEFAULT_PRESIGN_TTL_SECONDS
    )


def test_custom_ttl_passed_through():
    panel = _make_panel(preview_key="key.png")
    with patch(
        "app.services.storage.panel_preview.storage_client.get_url",
        return_value="https://signed/",
    ) as get_url:
        resolve_panel_preview_url(panel, expires=120)
    get_url.assert_called_once_with("key.png", expires=120)


def test_falls_back_to_url_when_no_key():
    panel = _make_panel(preview_url="https://legacy.example.com/img.png")
    with patch(
        "app.services.storage.panel_preview.storage_client.get_url"
    ) as get_url:
        result = resolve_panel_preview_url(panel)
    assert result == "https://legacy.example.com/img.png"
    get_url.assert_not_called()


def test_returns_none_when_neither_set():
    panel = _make_panel()
    with patch(
        "app.services.storage.panel_preview.storage_client.get_url"
    ) as get_url:
        assert resolve_panel_preview_url(panel) is None
    get_url.assert_not_called()


def test_falls_back_to_url_when_storage_raises():
    panel = _make_panel(
        preview_key="key.png",
        preview_url="https://legacy.example.com/img.png",
    )
    with patch(
        "app.services.storage.panel_preview.storage_client.get_url",
        side_effect=RuntimeError("MinIO down"),
    ):
        result = resolve_panel_preview_url(panel)
    assert result == "https://legacy.example.com/img.png"


def test_falls_back_to_url_when_storage_returns_empty_string():
    """storage_client.get_url returns ``""`` when MinIO is unavailable.
    The helper must treat that as a miss and fall through to the legacy URL."""
    panel = _make_panel(
        preview_key="key.png",
        preview_url="https://legacy.example.com/img.png",
    )
    with patch(
        "app.services.storage.panel_preview.storage_client.get_url",
        return_value="",
    ):
        result = resolve_panel_preview_url(panel)
    assert result == "https://legacy.example.com/img.png"


def test_returns_none_when_storage_dead_and_no_legacy_url():
    panel = _make_panel(preview_key="key.png", preview_url=None)
    with patch(
        "app.services.storage.panel_preview.storage_client.get_url",
        return_value="",
    ):
        assert resolve_panel_preview_url(panel) is None
