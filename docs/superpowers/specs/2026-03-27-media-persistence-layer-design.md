# Media Persistence Layer Design

> **Date:** 2026-03-27
> **Status:** Approved
> **Problem:** AI-generated media (images, videos) served via temporary signed URLs from cloud providers (Volcengine/Aliyun) that expire in 24-72h, causing 403 errors on the frontend.

## Problem Analysis

### Current State

| Media Type | Provider | Stored to MinIO? | Issue |
|------------|----------|-------------------|-------|
| Image | Doubao Seedream | Code exists but fails silently | `ObjectStore` defaults `use_ssl=True`, local MinIO is HTTP → upload fails, falls back to temp URL |
| Video | Doubao (即梦) | No | `get_result()` returns temp URL directly, no download/upload logic |
| Video | Tongyi (通义万相) | No | Same as Doubao video |
| Audio | Doubao TTS | Yes | Base64 decode → upload to MinIO, working correctly |

### Root Causes

1. **Video providers have no persistence logic** — `DoubaoVideoProvider.get_result()` and `TongyiVideoProvider.get_result()` return external temp URLs directly.
2. **ObjectStore SSL misconfiguration** — `ObjectStore.__init__` defaults `use_ssl=True`, but local MinIO runs on HTTP port 9000. This causes the image provider's upload to silently fail, falling back to the temp URL.
3. **No unified persistence pattern** — Each provider implements (or doesn't implement) its own download+upload logic. No reusable utility.
4. **Frontend displays raw URLs** — No mechanism to refresh expired URLs or translate storage keys to fresh presigned URLs.

## Design

### 1. Media Persister Utility

**New file:** `apps/api/app/services/storage/media_persister.py`

A single, provider-agnostic utility for persisting any external media to MinIO.

```python
async def persist_media(
    url: str,
    category: str,            # "images", "videos", "audio"
    content_type: str = None,  # auto-detected if None
    filename: str = None,      # auto-generated UUID if None
) -> str:
    """
    Download external URL → upload to MinIO → return storage key.

    Returns:
        MinIO storage key (e.g. "generated/videos/abc123.mp4")
    Raises:
        MediaPersistError on download or upload failure (no silent fallback)
    """

async def persist_media_bytes(
    data: bytes,
    category: str,
    content_type: str,
    filename: str = None,
) -> str:
    """
    Upload raw bytes to MinIO → return storage key.
    For local model outputs that return binary data instead of URLs.
    """
```

**Storage path convention:** `generated/{category}/{uuid}.{ext}`

**Key design decisions:**
- Returns **storage key**, not full URL. URLs are generated on-demand via presigned endpoint.
- **No silent fallback** — if persistence fails, raises `MediaPersistError`. Callers decide how to handle.
- Streaming download via `httpx` for large video files (not `requests.get` which loads everything into memory).
- Content-type auto-detection from URL extension and HTTP response headers.
- Uses `StorageClient` (from `app.core.storage`) for MinIO operations — it has `upload_bytes_sync`, `get_url` (presigned), and auto-creates bucket. `ObjectStore` is a higher-level wrapper; `persist_media` works at the core level for reliability.

### 2. Fix ObjectStore SSL Default

**File:** `apps/api/app/services/storage/object_store.py`

Change `__init__` parameter `use_ssl` default from `True` to reading from `settings.MINIO_SECURE` (which defaults to `False`).

```python
# Before
def __init__(self, ..., use_ssl: bool = True):

# After
def __init__(self, ..., use_ssl: bool = None):
    self.use_ssl = use_ssl if use_ssl is not None else (os.getenv("MINIO_SECURE", "false").lower() == "true")
```

This is the likely root cause of images not being stored — the MinIO client tries HTTPS on an HTTP endpoint and silently fails.

### 3. Update Providers to Use `persist_media`

#### DoubaoImageProvider (`doubao_image_provider.py`)

Replace inline download+upload block (lines 238-266) with:

```python
from app.services.storage.media_persister import persist_media, persist_media_bytes

# If we have image bytes (b64 response), use persist_media_bytes
# If we have a temp URL, use persist_media
if image_data:
    storage_key = await persist_media_bytes(image_data, "images", "image/jpeg")
elif temp_image_url:
    storage_key = await persist_media(temp_image_url, "images", "image/jpeg")
```

#### DoubaoVideoProvider (`doubao_video_provider.py`)

In `get_result()`, after extracting `video_url` from API response:

```python
from app.services.storage.media_persister import persist_media

if video_url:
    storage_key = await persist_media(video_url, "videos", "video/mp4")
    video_url = storage_key  # store key, not temp URL

# Also persist preview_url if present
if preview_url:
    preview_key = await persist_media(preview_url, "images", "image/jpeg")
    preview_url = preview_key
```

#### TongyiVideoProvider (`tongyi_video_provider.py`)

Same pattern as DoubaoVideoProvider.

#### DoubaoTTS (`tts_provider.py`)

Already working. Optionally refactor to use `persist_media_bytes` for consistency, but not required.

### 4. Presigned URL Endpoint

**New file:** `apps/api/app/api/routes/media.py`

```
GET /api/media/url?key={storage_key}
```

- Takes a MinIO storage key
- Returns a JSON response with a fresh presigned URL (1 hour expiry)
- Response: `{ "url": "http://localhost:9000/bucket/...", "expires_in": 3600 }`

**Security:** Validate that the key starts with allowed prefixes (`generated/`, `panels/`, `exports/`, `assets/`). Reject arbitrary paths.

**Register in `main.py`:** Add `media_router` to the FastAPI app.

### 5. Frontend Adaptation

#### New utility: `apps/web/src/lib/api/media.ts`

```typescript
export async function getMediaUrl(storageKey: string): Promise<string> {
  const resp = await apiGet<{ url: string }>(`/api/media/url?key=${encodeURIComponent(storageKey)}`);
  return resp.url;
}
```

#### Component updates

Components that display media (`PanelCard`, `VideoCard`, etc.) need to:
1. Check if the URL is a storage key (not starting with `http`) or an external URL
2. If storage key → call `getMediaUrl()` to get a presigned URL
3. Use the presigned URL for display

A helper hook `useMediaUrl(keyOrUrl)` can encapsulate this:

```typescript
function useMediaUrl(keyOrUrl: string | null): string | null {
  // If already a full URL, return as-is (backwards compatible)
  // If a storage key, fetch presigned URL via /api/media/url
}
```

## Files Changed

| File | Change Type | Description |
|------|------------|-------------|
| `services/storage/media_persister.py` | **New** | Universal persist_media / persist_media_bytes |
| `services/storage/object_store.py` | **Fix** | SSL default from settings |
| `services/storage/__init__.py` | **Edit** | Export new functions |
| `services/layer_factory/doubao_image_provider.py` | **Edit** | Replace inline upload with persist_media |
| `services/video/doubao_video_provider.py` | **Edit** | Add persist_media call in get_result |
| `services/video/tongyi_video_provider.py` | **Edit** | Add persist_media call in get_result |
| `api/routes/media.py` | **New** | Presigned URL endpoint |
| `app/main.py` | **Edit** | Register media router |
| `web/src/lib/api/media.ts` | **New** | getMediaUrl + useMediaUrl hook |
| `web/src/lib/api/services.ts` | **Edit** | Export media utilities |
| `web/src/components/studio/center/PanelCard.tsx` | **Edit** | Use useMediaUrl for images |
| `web/src/components/agent/VideoCard.tsx` | **Edit** | Use useMediaUrl for videos |

## Data Flow (After)

```
Provider API response
  → temp URL or bytes
  → persist_media() / persist_media_bytes()
    → httpx stream download (if URL)
    → MinIO upload
    → return storage key (e.g. "generated/videos/abc.mp4")
  → store key in database
  → API returns key to frontend
  → frontend calls GET /api/media/url?key=...
  → receives 1h presigned URL
  → renders media
```

## Non-Goals

- Migrating existing expired URLs in the database (old data is already lost)
- Changing the audio pipeline (already working)
- CDN or public bucket access (can be added later)
- Frontend-side URL caching with TTL (future optimization)
