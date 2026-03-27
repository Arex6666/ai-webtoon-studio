"""
Media Persister — download external URLs and upload to MinIO.

Provider-agnostic utility. All AI-generated media (images, videos, audio)
should be persisted through this module so that the frontend never receives
temporary external URLs that expire.
"""
import uuid
import asyncio
import logging
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.core.storage import get_storage_client

logger = logging.getLogger(__name__)


class MediaPersistError(Exception):
    """Raised when media cannot be downloaded or uploaded to MinIO."""


# Content-type → file extension mapping
_CT_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/ogg": ".ogg",
}


def _ext_from_content_type(ct: str) -> str:
    """Map content-type to file extension."""
    base = ct.split(";")[0].strip().lower()
    return _CT_TO_EXT.get(base, ".bin")


def _ext_from_url(url: str) -> Optional[str]:
    """Extract extension from URL path, ignoring query params."""
    path = urlparse(url).path
    if "." in path.split("/")[-1]:
        ext = "." + path.split(".")[-1].lower()
        if len(ext) <= 5:  # reasonable extension length
            return ext
    return None


def _make_key(category: str, ext: str, filename: Optional[str] = None) -> str:
    """Build the MinIO storage key."""
    if filename:
        return f"generated/{category}/{filename}"
    return f"generated/{category}/{uuid.uuid4().hex}{ext}"


async def persist_media(
    url: str,
    category: str,
    content_type: Optional[str] = None,
    filename: Optional[str] = None,
) -> str:
    """
    Download from external URL → upload to MinIO → return storage key.

    Args:
        url: External URL to download (e.g. Volcengine signed URL)
        category: Storage category — "images", "videos", "audio"
        content_type: MIME type. Auto-detected from response if None.
        filename: Custom filename. Auto-generated UUID if None.

    Returns:
        MinIO storage key (e.g. "generated/videos/abc123.mp4")

    Raises:
        MediaPersistError: If download or upload fails.
    """
    storage = get_storage_client()
    if not storage.available:
        raise MediaPersistError("MinIO storage not available")

    try:
        # Stream download
        chunks = []
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=30.0)) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                # Auto-detect content type from response if not provided
                if content_type is None:
                    content_type = response.headers.get("content-type", "application/octet-stream")
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    chunks.append(chunk)

        data = b"".join(chunks)
        if not data:
            raise MediaPersistError(f"Downloaded 0 bytes from {url}")

        logger.info(f"[MediaPersist] Downloaded {len(data)} bytes from external URL")

    except httpx.HTTPError as e:
        raise MediaPersistError(f"Failed to download from {url}: {e}") from e

    # Determine extension
    ext = _ext_from_content_type(content_type) if content_type else _ext_from_url(url) or ".bin"
    target_key = _make_key(category, ext, filename)

    # Upload to MinIO (sync call in thread pool)
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            storage.upload_bytes_sync,
            target_key,
            data,
            content_type or "application/octet-stream",
        )
        logger.info(f"[MediaPersist] Uploaded to MinIO: {target_key}")
        return target_key
    except Exception as e:
        raise MediaPersistError(f"Failed to upload to MinIO: {e}") from e


async def persist_media_bytes(
    data: bytes,
    category: str,
    content_type: str,
    filename: Optional[str] = None,
) -> str:
    """
    Upload raw bytes to MinIO → return storage key.

    For local model outputs that return binary data instead of URLs.

    Args:
        data: Raw bytes to upload
        category: Storage category — "images", "videos", "audio"
        content_type: MIME type (required for bytes)
        filename: Custom filename. Auto-generated UUID if None.

    Returns:
        MinIO storage key (e.g. "generated/images/abc123.jpg")

    Raises:
        MediaPersistError: If upload fails.
    """
    storage = get_storage_client()
    if not storage.available:
        raise MediaPersistError("MinIO storage not available")

    ext = _ext_from_content_type(content_type)
    target_key = _make_key(category, ext, filename)

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            storage.upload_bytes_sync,
            target_key,
            data,
            content_type,
        )
        logger.info(f"[MediaPersist] Uploaded {len(data)} bytes to MinIO: {target_key}")
        return target_key
    except Exception as e:
        raise MediaPersistError(f"Failed to upload to MinIO: {e}") from e
