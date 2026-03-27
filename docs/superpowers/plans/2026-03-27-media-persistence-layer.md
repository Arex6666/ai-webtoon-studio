# Media Persistence Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure all AI-generated media (images, videos) is persisted to MinIO and served via on-demand presigned URLs, eliminating expired external URL errors.

**Architecture:** A new `media_persister` utility handles download-from-external-URL and upload-to-MinIO as a single reusable function. All providers call it instead of implementing their own persistence. A new `/api/v1/media/url` endpoint generates fresh presigned URLs on demand. Frontend components use a `useMediaUrl` hook to resolve storage keys into displayable URLs.

**Tech Stack:** Python (httpx, minio), FastAPI, React (Next.js), TypeScript

**Spec:** `docs/superpowers/specs/2026-03-27-media-persistence-layer-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `apps/api/app/services/storage/media_persister.py` | Create | `persist_media()` and `persist_media_bytes()` — download external URLs and upload to MinIO |
| `apps/api/app/services/storage/object_store.py` | Modify | Fix SSL default to read from `MINIO_SECURE` env var |
| `apps/api/app/services/storage/__init__.py` | Modify | Export new `persist_media` functions |
| `apps/api/app/api/routes/media.py` | Create | `GET /api/v1/media/url?key=...` presigned URL endpoint |
| `apps/api/app/main.py` | Modify | Register media router |
| `apps/api/app/services/layer_factory/doubao_image_provider.py` | Modify | Replace inline download+upload with `persist_media` |
| `apps/api/app/services/video/doubao_video_provider.py` | Modify | Add `persist_media` call in `get_result()` |
| `apps/api/app/services/video/tongyi_video_provider.py` | Modify | Add `persist_media` call in `get_result()` |
| `apps/web/src/lib/api/media.ts` | Create | `getMediaUrl()` API call + `useMediaUrl()` React hook |
| `apps/web/src/components/studio/center/PanelCard.tsx` | Modify | Use `useMediaUrl` for panel image |
| `apps/web/src/components/agent/VideoCard.tsx` | Modify | Use `useMediaUrl` for video thumbnail and link |
| `apps/api/tests/unit/storage/test_media_persister.py` | Create | Unit tests for media persister |

---

### Task 1: Fix ObjectStore SSL Default

**Files:**
- Modify: `apps/api/app/services/storage/object_store.py:19-31`

This is the likely root cause of images not being stored. `ObjectStore` defaults `use_ssl=True` but local MinIO runs on HTTP.

- [ ] **Step 1: Fix the SSL default**

In `apps/api/app/services/storage/object_store.py`, change the `__init__` method:

```python
# Replace this:
    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket: Optional[str] = None,
        use_ssl: bool = True
    ):
        self.endpoint = endpoint or os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY", "minioadmin")
        self.bucket = bucket or os.getenv("MINIO_BUCKET", "webtoon-studio")
        self.use_ssl = use_ssl

# With this:
    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket: Optional[str] = None,
        use_ssl: Optional[bool] = None
    ):
        self.endpoint = endpoint or os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY", "minioadmin")
        self.bucket = bucket or os.getenv("MINIO_BUCKET", "webtoon-studio")
        if use_ssl is not None:
            self.use_ssl = use_ssl
        else:
            self.use_ssl = os.getenv("MINIO_SECURE", "false").lower() == "true"
```

- [ ] **Step 2: Commit**

```bash
cd apps/api
git add app/services/storage/object_store.py
git commit -m "fix: read MINIO_SECURE from env in ObjectStore instead of defaulting to True"
```

---

### Task 2: Create Media Persister Utility

**Files:**
- Create: `apps/api/app/services/storage/media_persister.py`
- Modify: `apps/api/app/services/storage/__init__.py`
- Create: `apps/api/tests/unit/storage/test_media_persister.py`

- [ ] **Step 1: Create the test file**

Create `apps/api/tests/unit/storage/test_media_persister.py`:

```python
"""Tests for media_persister utility."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.storage.media_persister import (
    persist_media,
    persist_media_bytes,
    MediaPersistError,
    _ext_from_content_type,
)


def test_ext_from_content_type():
    assert _ext_from_content_type("image/jpeg") == ".jpg"
    assert _ext_from_content_type("image/png") == ".png"
    assert _ext_from_content_type("video/mp4") == ".mp4"
    assert _ext_from_content_type("audio/mpeg") == ".mp3"
    assert _ext_from_content_type("application/octet-stream") == ".bin"
    assert _ext_from_content_type("unknown/type") == ".bin"


@pytest.mark.asyncio
async def test_persist_media_bytes_uploads_and_returns_key():
    mock_storage = MagicMock()
    mock_storage.available = True
    mock_storage.upload_bytes_sync = MagicMock(side_effect=lambda path, data, ct: path)

    with patch("app.services.storage.media_persister.get_storage_client", return_value=mock_storage):
        key = await persist_media_bytes(b"fake-image-data", "images", "image/jpeg")

    assert key.startswith("generated/images/")
    assert key.endswith(".jpg")
    mock_storage.upload_bytes_sync.assert_called_once()
    call_args = mock_storage.upload_bytes_sync.call_args
    assert call_args[0][1] == b"fake-image-data"
    assert call_args[0][2] == "image/jpeg"


@pytest.mark.asyncio
async def test_persist_media_bytes_custom_filename():
    mock_storage = MagicMock()
    mock_storage.available = True
    mock_storage.upload_bytes_sync = MagicMock(side_effect=lambda path, data, ct: path)

    with patch("app.services.storage.media_persister.get_storage_client", return_value=mock_storage):
        key = await persist_media_bytes(b"data", "videos", "video/mp4", filename="my-clip.mp4")

    assert key == "generated/videos/my-clip.mp4"


@pytest.mark.asyncio
async def test_persist_media_bytes_raises_when_storage_unavailable():
    mock_storage = MagicMock()
    mock_storage.available = False

    with patch("app.services.storage.media_persister.get_storage_client", return_value=mock_storage):
        with pytest.raises(MediaPersistError, match="MinIO storage not available"):
            await persist_media_bytes(b"data", "images", "image/jpeg")


@pytest.mark.asyncio
async def test_persist_media_downloads_and_uploads():
    mock_storage = MagicMock()
    mock_storage.available = True
    mock_storage.upload_bytes_sync = MagicMock(side_effect=lambda path, data, ct: path)

    fake_response = AsyncMock()
    fake_response.status_code = 200
    fake_response.headers = {"content-type": "image/jpeg"}
    fake_response.aiter_bytes = lambda chunk_size=8192: _async_iter([b"chunk1", b"chunk2"])
    fake_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=fake_response)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_client.stream = MagicMock(return_value=mock_stream_ctx)

    with patch("app.services.storage.media_persister.get_storage_client", return_value=mock_storage):
        with patch("app.services.storage.media_persister.httpx.AsyncClient", return_value=mock_client):
            key = await persist_media("https://example.com/temp.jpg", "images")

    assert key.startswith("generated/images/")
    assert key.endswith(".jpg")
    mock_storage.upload_bytes_sync.assert_called_once()


async def _async_iter(items):
    for item in items:
        yield item
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/api
python -m pytest tests/unit/storage/test_media_persister.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.storage.media_persister'`

- [ ] **Step 3: Create the media persister module**

Create `apps/api/app/services/storage/media_persister.py`:

```python
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
```

- [ ] **Step 4: Update storage `__init__.py`**

In `apps/api/app/services/storage/__init__.py`, add exports:

```python
"""
Storage Services
"""
from .object_store import ObjectStore, get_object_store
from .media_persister import persist_media, persist_media_bytes, MediaPersistError

__all__ = [
    "ObjectStore", "get_object_store",
    "persist_media", "persist_media_bytes", "MediaPersistError",
]
```

- [ ] **Step 5: Create `tests/unit/storage/__init__.py` if needed, then run tests**

```bash
cd apps/api
mkdir -p tests/unit/storage
touch tests/unit/storage/__init__.py
python -m pytest tests/unit/storage/test_media_persister.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd apps/api
git add app/services/storage/media_persister.py app/services/storage/__init__.py tests/unit/storage/
git commit -m "feat: add media_persister utility for persisting external URLs to MinIO"
```

---

### Task 3: Create Presigned URL Endpoint

**Files:**
- Create: `apps/api/app/api/routes/media.py`
- Modify: `apps/api/app/main.py:21,178`

- [ ] **Step 1: Create the media route**

Create `apps/api/app/api/routes/media.py`:

```python
"""
Media URL endpoint — generates fresh presigned URLs for MinIO storage keys.
"""
from fastapi import APIRouter, HTTPException, Query

from app.core.storage import get_storage_client

router = APIRouter()

ALLOWED_PREFIXES = ("generated/", "panels/", "exports/", "assets/")


@router.get("/media/url")
def get_media_url(
    key: str = Query(..., description="MinIO storage key"),
    expires: int = Query(3600, ge=60, le=86400, description="URL expiry in seconds"),
):
    """
    Generate a fresh presigned URL for a MinIO storage key.

    Returns:
        {"url": "http://...", "expires_in": 3600}
    """
    if not any(key.startswith(p) for p in ALLOWED_PREFIXES):
        raise HTTPException(status_code=400, detail=f"Invalid storage key prefix. Allowed: {ALLOWED_PREFIXES}")

    storage = get_storage_client()
    if not storage.available:
        raise HTTPException(status_code=503, detail="Storage service unavailable")

    if not storage.exists(key):
        raise HTTPException(status_code=404, detail="File not found in storage")

    url = storage.get_url(key, expires=expires)
    return {"url": url, "expires_in": expires}
```

- [ ] **Step 2: Register in main.py**

In `apps/api/app/main.py`, add the import and router registration:

Add to the import line (line 21):
```python
from app.api.routes import projects, chapters, panels, assets, render, typeset, compose, auth, identity, scene_anchor, brain, qa, ws, studios, exports, shot_versions, jobs, timeline, bindings, analytics, release, layerpacks, generate, templates, drafts, batch_render, script_pipeline, automation, asset_autobuild, props, conversations, faceid, export_strip, agent, providers, episode_video, media
```

Add after line 178 (after episode_video router):
```python
# Media URL (presigned URL generation)
app.include_router(media.router, prefix="/api/v1", tags=["媒体"])
```

- [ ] **Step 3: Commit**

```bash
cd apps/api
git add app/api/routes/media.py app/main.py
git commit -m "feat: add /api/v1/media/url endpoint for presigned URL generation"
```

---

### Task 4: Update DoubaoImageProvider to Use persist_media

**Files:**
- Modify: `apps/api/app/services/layer_factory/doubao_image_provider.py:238-274`

- [ ] **Step 1: Replace inline download+upload block**

In `apps/api/app/services/layer_factory/doubao_image_provider.py`, replace the imports at the top — change:

```python
from app.services.storage import get_object_store
```

to:

```python
from app.services.storage.media_persister import persist_media, persist_media_bytes, MediaPersistError
```

Then replace lines 238-274 (the `# ==== 下载临时图片并上传到 MinIO 获取永久 URL ====` block and the return) with:

```python
            # ==== 持久化到 MinIO ====
            storage_key = None
            try:
                if image_data:
                    storage_key = await persist_media_bytes(image_data, "images", "image/jpeg")
                elif temp_image_url:
                    storage_key = await persist_media(temp_image_url, "images", "image/jpeg")
            except MediaPersistError as e:
                logger.warning(f"[DoubaoImage] Failed to persist image: {e}, using temp URL")

            generation_time = int((time.time() - start_time) * 1000)
            # Use storage key if persisted, otherwise fall back to temp URL
            result_url = storage_key or temp_image_url

            logger.info(f"[DoubaoImage] Success! URL/key: {result_url[:80]}...")

            return DoubaoImageResult(
                success=True,
                image_url=result_url,
                image_data=image_data,
                seed=seed_used,
                cost=0.1,
                generation_time_ms=generation_time,
            )
```

- [ ] **Step 2: Verify no import errors**

```bash
cd apps/api
python -c "from app.services.layer_factory.doubao_image_provider import DoubaoImageProvider; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd apps/api
git add app/services/layer_factory/doubao_image_provider.py
git commit -m "refactor: use persist_media in DoubaoImageProvider instead of inline upload"
```

---

### Task 5: Update DoubaoVideoProvider to Use persist_media

**Files:**
- Modify: `apps/api/app/services/video/doubao_video_provider.py:180-232`

- [ ] **Step 1: Add import and persist logic in get_result()**

At the top of the file, add the import:

```python
from app.services.storage.media_persister import persist_media, MediaPersistError
```

In the `get_result()` method, replace lines 206-223 (the success return block) with:

```python
            # 提取视频 URL
            output = task_data.get("output", {})
            video_url = output.get("video_url") or task_data.get("video_url")

            # 提取预览
            preview_url = output.get("cover_url") or output.get("preview_url")

            # 持久化到 MinIO
            try:
                if video_url:
                    video_url = await persist_media(video_url, "videos", "video/mp4")
                if preview_url:
                    preview_url = await persist_media(preview_url, "images", "image/jpeg")
            except MediaPersistError as e:
                logger.warning(f"[DoubaoVideo] Failed to persist media: {e}")

            return VideoResult(
                success=True,
                video_url=video_url,
                preview_url=preview_url,
                frames=[],
                duration_sec=output.get("duration", 5),
                seed=output.get("seed"),
                provider=self.provider_name,
                cost=0.5,
            )
```

- [ ] **Step 2: Verify no import errors**

```bash
cd apps/api
python -c "from app.services.video.doubao_video_provider import DoubaoVideoProvider; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd apps/api
git add app/services/video/doubao_video_provider.py
git commit -m "feat: persist Doubao video results to MinIO via media_persister"
```

---

### Task 6: Update TongyiVideoProvider to Use persist_media

**Files:**
- Modify: `apps/api/app/services/video/tongyi_video_provider.py:202-256`

- [ ] **Step 1: Add import and persist logic in get_result()**

At the top of the file, add the import:

```python
from app.services.storage.media_persister import persist_media, MediaPersistError
```

In the `get_result()` method, replace lines 227-247 (from `# 提取视频 URL` to the success return) with:

```python
            # 提取视频 URL
            video_url = output.get("video_url")

            # 提取预览帧（如果有）
            preview_url = None
            frames = []

            # 持久化到 MinIO
            try:
                if video_url:
                    video_url = await persist_media(video_url, "videos", "video/mp4")
            except MediaPersistError as e:
                logger.warning(f"[TongyiVideo] Failed to persist media: {e}")

            # 计算费用（根据分辨率和时长估算）
            usage = data.get("usage", {})
            cost = usage.get("video_count", 1) * 0.5

            return VideoResult(
                success=True,
                video_url=video_url,
                preview_url=preview_url,
                frames=frames,
                duration_sec=output.get("duration", 5),
                seed=output.get("seed"),
                provider=self.provider_name,
                cost=cost,
            )
```

- [ ] **Step 2: Verify no import errors**

```bash
cd apps/api
python -c "from app.services.video.tongyi_video_provider import TongyiVideoProvider; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd apps/api
git add app/services/video/tongyi_video_provider.py
git commit -m "feat: persist Tongyi video results to MinIO via media_persister"
```

---

### Task 7: Create Frontend Media URL Utility and Hook

**Files:**
- Create: `apps/web/src/lib/api/media.ts`

- [ ] **Step 1: Create the media utility**

Create `apps/web/src/lib/api/media.ts`:

```typescript
/**
 * Media URL utilities — resolves MinIO storage keys to presigned URLs.
 */
import { useState, useEffect } from 'react'
import { apiGet } from './client'

/**
 * Check if a string is a storage key (not a full URL).
 */
export function isStorageKey(value: string): boolean {
  return !value.startsWith('http://') && !value.startsWith('https://') && !value.startsWith('data:')
}

/**
 * Fetch a fresh presigned URL for a MinIO storage key.
 */
export async function getMediaUrl(storageKey: string): Promise<string> {
  const resp = await apiGet<{ url: string; expires_in: number }>(
    `/api/v1/media/url?key=${encodeURIComponent(storageKey)}`
  )
  return resp.url
}

/**
 * React hook that resolves a storage key or URL to a displayable URL.
 *
 * - If `keyOrUrl` is already a full URL (http/https/data), returns it as-is.
 * - If `keyOrUrl` is a storage key, fetches a presigned URL from the backend.
 * - Returns `null` while loading or if `keyOrUrl` is null/undefined.
 */
export function useMediaUrl(keyOrUrl: string | null | undefined): string | null {
  const [url, setUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!keyOrUrl) {
      setUrl(null)
      return
    }

    if (!isStorageKey(keyOrUrl)) {
      // Already a full URL, use directly
      setUrl(keyOrUrl)
      return
    }

    // Fetch presigned URL
    let cancelled = false
    getMediaUrl(keyOrUrl)
      .then((presignedUrl) => {
        if (!cancelled) setUrl(presignedUrl)
      })
      .catch((err) => {
        console.error('[useMediaUrl] Failed to resolve storage key:', keyOrUrl, err)
        if (!cancelled) setUrl(null)
      })

    return () => { cancelled = true }
  }, [keyOrUrl])

  return url
}
```

- [ ] **Step 2: Commit**

```bash
cd apps/web
git add src/lib/api/media.ts
git commit -m "feat: add useMediaUrl hook and getMediaUrl utility for presigned URLs"
```

---

### Task 8: Update PanelCard to Use useMediaUrl

**Files:**
- Modify: `apps/web/src/components/studio/center/PanelCard.tsx`

- [ ] **Step 1: Add import and apply hook**

At the top of `PanelCard.tsx`, add:

```typescript
import { useMediaUrl } from '@/lib/api/media'
```

Inside the component function, before the JSX return, add:

```typescript
const resolvedPreviewUrl = useMediaUrl(panel.previewUrl)
```

Then in the JSX, replace `panel.previewUrl` with `resolvedPreviewUrl`:

```tsx
{/* Change this: */}
{panel.previewUrl ? (
  <img src={panel.previewUrl} ...

{/* To this: */}
{resolvedPreviewUrl ? (
  <img src={resolvedPreviewUrl} ...
```

There are two places where `panel.previewUrl` is used as an img src — the thumbnail (around line 150) and possibly elsewhere. Change all img `src` usages to `resolvedPreviewUrl`. Keep the truthiness check (`resolvedPreviewUrl ?`) as-is.

- [ ] **Step 2: Verify build**

```bash
cd apps/web
npx next lint src/components/studio/center/PanelCard.tsx
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
cd apps/web
git add src/components/studio/center/PanelCard.tsx
git commit -m "feat: use useMediaUrl hook in PanelCard for presigned image URLs"
```

---

### Task 9: Update VideoCard to Use useMediaUrl

**Files:**
- Modify: `apps/web/src/components/agent/VideoCard.tsx`

- [ ] **Step 1: Add import**

At the top of `VideoCard.tsx`, add:

```typescript
import { useMediaUrl } from '@/lib/api/media'
```

The VideoCard renders a list of jobs, each with `job.video_url` and `job.image_url`. Since the hook can't be called inside a loop directly, create a small wrapper component for each job row. Alternatively, since the main video URLs are set per-job, add resolution at the list level.

The simplest approach: create a `VideoJobRow` subcomponent that uses the hook:

Add before the main component:

```typescript
function VideoJobRow({ job }: { job: { job_id: string; video_url?: string; image_url?: string; status: string; progress: number; panel_index: number; error?: string } }) {
  const resolvedVideoUrl = useMediaUrl(job.video_url ?? null)
  const resolvedImageUrl = useMediaUrl(job.image_url ?? null)

  return (
    // ... same JSX as the current job row, but using resolvedVideoUrl and resolvedImageUrl
    // instead of job.video_url and job.image_url
  )
}
```

Then in the `.map()` loop, replace the inline JSX with `<VideoJobRow job={job} key={job.job_id} />`.

Note: Copy the exact existing JSX from the current job row (lines 323-374) into `VideoJobRow`, replacing:
- `job.video_url` → `resolvedVideoUrl` (in the `<a href=...>`)
- `job.image_url` → `resolvedImageUrl` (in the `<img src=...>`)

- [ ] **Step 2: Verify build**

```bash
cd apps/web
npx next lint src/components/agent/VideoCard.tsx
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
cd apps/web
git add src/components/agent/VideoCard.tsx
git commit -m "feat: use useMediaUrl hook in VideoCard for presigned video/image URLs"
```

---

### Task 10: Run All Tests and Verify Build

- [ ] **Step 1: Run backend tests**

```bash
cd apps/api
python -m pytest tests/unit/storage/test_media_persister.py -v
```

Expected: All tests pass.

- [ ] **Step 2: Run frontend build**

```bash
cd apps/web
npm run build
```

Expected: Build succeeds with no errors.

- [ ] **Step 3: Final commit if any fixes needed**

If any fixes were needed, commit them:

```bash
git add -A
git commit -m "fix: address build/test issues in media persistence layer"
```
