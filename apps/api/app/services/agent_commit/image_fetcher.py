"""Download a remote image and store it in MinIO, returning the storage key."""
from __future__ import annotations

import logging
import mimetypes
import uuid
from typing import Optional

import httpx

from app.core.storage import storage_client

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 20 * 1024 * 1024
DEFAULT_TIMEOUT_S = 15.0


class ImageFetchError(Exception):
    pass


async def fetch_and_persist(
    url: str,
    *,
    project_id: str,
    asset_type: str,
    name_hint: str,
) -> str:
    """Download `url`, upload to MinIO under a deterministic key, return the key.

    Raises ImageFetchError on any failure.
    """
    if not url:
        raise ImageFetchError("empty url")

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_S, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.content
            if len(data) > MAX_IMAGE_BYTES:
                raise ImageFetchError(f"image exceeds {MAX_IMAGE_BYTES} bytes")
            content_type = resp.headers.get("content-type", "image/png").split(";")[0].strip()
    except ImageFetchError:
        raise
    except Exception as e:
        raise ImageFetchError(f"download failed: {e}") from e

    ext = mimetypes.guess_extension(content_type) or ".png"
    safe_hint = "".join(c if c.isalnum() else "_" for c in name_hint)[:40]
    key = f"agent-commit/{project_id}/{asset_type}/{safe_hint}-{uuid.uuid4().hex[:8]}{ext}"

    try:
        await storage_client.upload_bytes(key, data, content_type=content_type)
    except Exception as e:
        raise ImageFetchError(f"minio upload failed: {e}") from e

    return key
