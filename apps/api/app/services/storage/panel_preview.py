"""Resolve a Panel's preview URL from its raw storage key.

Migration 021 added Panel.preview_key (the raw storage key) so callers can
re-sign on every read instead of caching a presigned URL with a finite TTL on
Panel.preview_url. This module centralizes the prefer-key-over-url logic plus
the storage-failure fallback.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from app.core.storage import storage_client

if TYPE_CHECKING:
    from app.models.panel import Panel


DEFAULT_PRESIGN_TTL_SECONDS = 3600


def resolve_panel_preview_url(
    panel: "Panel",
    expires: int = DEFAULT_PRESIGN_TTL_SECONDS,
) -> Optional[str]:
    """Return a fresh presigned URL for the panel's preview image.

    Prefers ``panel.preview_key`` (re-signed on every call so it never
    expires). Falls back to the legacy ``panel.preview_url`` field for rows
    that pre-date migration 021 or were written by code paths that don't yet
    populate ``preview_key`` (e.g. the ComfyUI render worker). Returns
    ``None`` when neither field is populated.
    """
    key = getattr(panel, "preview_key", None)
    if key:
        try:
            signed = storage_client.get_url(key, expires=expires)
            if signed:
                return signed
        except Exception:
            # Storage unreachable — fall through to legacy URL field.
            pass
    legacy = getattr(panel, "preview_url", None)
    return legacy or None
