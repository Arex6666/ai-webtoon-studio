# C — Real Scene Anchor + Canny Control Map Generation

**Date**: 2026-05-06
**Status**: Draft (awaiting user review)
**Scope**: Replace the mock implementations in `services/scene/anchor_generator.py` and `services/scene/control_map_extractor.py` with real Doubao Seedream image generation + cv2-based canny extraction. Defer depth/lineart maps until ComfyUI rendering path is enabled.
**Estimated effort**: ~1 day (8 hours).
**Predecessor**: B-1 (chat-driven assets via agent_commit, doubao_image_provider already in use).
**Successor**: D (motion-comic video export) — independent.

---

## 1. Background

### Current state (mock land)

`services/scene/anchor_generator.py:113-129` — `_generate_mock` returns a fake path string after a 0.5s sleep. Real path `_generate_comfyui` is a TODO that falls back to mock with a warning.

`services/scene/control_map_extractor.py:55-71` — `_extract_mock` returns fake paths. Real path `_extract_controlnet` is a TODO that falls back to mock.

This means: when chat-driven asset creation triggers `create_scene` tool → `enqueue_scene_anchor_generation` → both calls return mock paths → DB stores fake URLs → **scene consistency feature is mostly theatre**.

### What works downstream

- `services/layer_factory/doubao_image_provider.py` (line 31) — Seedream 4.5 already wired and used for character portraits + panel generation, model `doubao-seedream-4-5-251128`. Uses ARK_API_KEY (configured in user's environment per Phase D).
- `services/scene_anchor/anchor_storage.py` — real MinIO storage, working code (B-1 era).
- `services/layer_factory/payload_builder.py` (lines 31-304) — does consume `scene_control_maps` to assemble ComfyUI workflows with depth + canny ControlNet nodes. **But ComfyUI path is currently not active (Doubao Seedream is the default panel renderer).**

### What "scene consistency" actually does today (post-implementation)

```
[scene description] → anchor generator → Seedream API → anchor PNG → MinIO

[panel render] → Seedream with reference_image_url=anchor_url → soft consistency
                 (canny map sits in MinIO, unused until ComfyUI is enabled)
```

When ComfyUI is later enabled (out-of-scope here), the canny map is already in place; depth + lineart will need to be added in a follow-up.

---

## 2. Goals

1. Replace `_generate_mock` with `_generate_doubao_seedream` — real Seedream API call, store result to MinIO.
2. Replace `_extract_mock` with `_extract_cv2` — real `cv2.Canny()` from anchor image, store to MinIO.
3. Keep mock providers reachable via `provider="mock"` for tests.
4. Update default providers in `retry_strategy.enqueue_scene_anchor_generation` so existing callers (storyboard.py, drafts.py, _assets_legacy.py, async_runner.py) automatically get real generation.
5. No changes to public API surface — `enqueue_scene_anchor_generation`, `generate_scene_anchor`, `extract_control_maps` signatures unchanged except provider default.
6. Pass full B-1 + new test suite green.

## 3. Non-goals

- Depth map extraction (defers to ComfyUI-path enable; needs `controlnet_aux` + ML model + GPU).
- Lineart extraction (same reason).
- ComfyUI integration (`_generate_comfyui` body) — out of scope; B-1's deployment Phase A territory.
- Frontend changes — scene anchor generation is backend-only flow triggered by chat tool / button.

---

## 4. Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│  retry_strategy.enqueue_scene_anchor_generation                    │
│  (existing — defaults change: anchor_provider/control_map_provider) │
└────────────────────────┬───────────────────────────────────────────┘
                         │
                ┌────────┴────────┐
                ▼                 ▼
┌────────────────────────┐  ┌────────────────────────────┐
│ generate_scene_anchor  │  │ extract_control_maps       │
│ provider="doubao" (NEW)│  │ provider="cv2" (NEW)       │
└────────┬───────────────┘  └────────┬───────────────────┘
         │                           │
         ▼                           ▼
┌────────────────────────┐  ┌────────────────────────────┐
│ doubao_image_provider  │  │ cv2.Canny + AnchorStorage  │
│ (existing Seedream)    │  │ canny only — depth/lineart │
└────────┬───────────────┘  │ explicitly skipped         │
         │                  └────────┬───────────────────┘
         ▼                           ▼
┌──────────────────────────────────────────────────────┐
│  AnchorStorage (MinIO)                                │
│   anchors/scenes/{scene_id}/anchor.png  (Seedream)   │
│   anchors/scenes/{scene_id}/canny.png   (cv2)        │
│   anchors/scenes/{scene_id}/metadata.json            │
└──────────────────────────────────────────────────────┘
```

---

## 5. Component Design

### 5.1 `_generate_doubao_seedream` (in `anchor_generator.py`)

```python
async def _generate_doubao_seedream(
    spec: SceneAnchorSpec,
    positive: str,
    negative: str,
    size: tuple[int, int],
    seed: int,
) -> AnchorResult:
    """Generate scene anchor via Doubao Seedream + re-store under AnchorStorage path."""
    from app.services.layer_factory.doubao_image_provider import (
        get_doubao_image_provider, DoubaoImageRequest, SEEDREAM_MODEL,
    )
    from app.services.scene_anchor.anchor_storage import get_anchor_storage
    from app.core.storage import get_storage_client

    provider = get_doubao_image_provider()
    if not provider.api_key:
        return AnchorResult(success=False, error="ARK_API_KEY / DOUBAO_API_KEY not configured")

    width, height = _enforce_seedream_min_pixels(size)

    req = DoubaoImageRequest(
        prompt=positive,
        negative_prompt=negative,
        width=width,
        height=height,
        seed=seed,
    )
    resp = await provider.generate(req)
    if not resp.success:
        return AnchorResult(success=False, error=resp.error or "Seedream generation failed")

    # Resolve image bytes — provider may have persisted under images/ prefix already.
    # We re-store under anchors/scenes/{scene_id}/anchor.png for the canonical scene path.
    image_bytes = resp.image_data
    if image_bytes is None and resp.image_url:
        # image_url is a MinIO storage key (post-persist) OR an http(s) URL (failed to persist).
        if resp.image_url.startswith(("http://", "https://")):
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(resp.image_url)
                r.raise_for_status()
                image_bytes = r.content
        else:
            sc = get_storage_client()
            image_bytes = await sc.download_bytes(resp.image_url)

    if not image_bytes:
        return AnchorResult(success=False, error="Seedream returned no image bytes or URL")

    storage = get_anchor_storage()
    paths = await storage.save_anchor(
        scene_id=spec.scene_id,
        anchor_image=image_bytes,
        control_maps={},  # filled in later by extract_control_maps
        metadata={
            "prompt": positive,
            "negative_prompt": negative,
            "seed": seed,
            "provider": "doubao-seedream",
            "model": SEEDREAM_MODEL,
            "size": [width, height],
        },
    )
    return AnchorResult(
        success=True,
        image_path=paths["anchor"],
        image_url=storage.get_anchor_url(spec.scene_id),
        meta={
            "seed": seed,
            "provider": "doubao-seedream",
            "model": SEEDREAM_MODEL,
            "prompt_hash": hash(positive),
        },
    )


def _enforce_seedream_min_pixels(size: tuple[int, int]) -> tuple[int, int]:
    """Seedream 4.5 requires ≥3,686,400 pixels (e.g. 1920×1920). Coerce small
    callers up to a 16:9-ish landscape default if too small."""
    width, height = size
    if width * height >= 3_686_400:
        return width, height
    # Default scene anchor: 2304×1632 = 3,760,128 pixels (~16:9, slight pad)
    return 2304, 1632
```

Replace `_generate_comfyui` reference in `generate_scene_anchor` dispatch table:
```python
elif provider == "doubao":
    return await _generate_doubao_seedream(spec, positive, negative, size, seed, output_dir)
elif provider == "comfyui":
    # Still TODO — ComfyUI is post-deployment work
    logger.warning("[SceneAnchor] ComfyUI not implemented, falling back to doubao")
    return await _generate_doubao_seedream(spec, positive, negative, size, seed, output_dir)
```

### 5.2 `_extract_cv2` (in `control_map_extractor.py`)

```python
async def _extract_cv2(
    anchor_image_path: str,
    scene_id: str,
    map_types: list[str],
) -> ControlMapResult:
    """Extract control maps via OpenCV. Currently supports only canny.

    depth + lineart are explicitly skipped — they require ML preprocessor models
    (controlnet_aux + torch) which are deferred until ComfyUI rendering is enabled.
    """
    import cv2
    import numpy as np
    from app.services.scene_anchor.anchor_storage import get_anchor_storage

    storage = get_anchor_storage()
    anchor_bytes = await storage.load_anchor_image(scene_id)
    if not anchor_bytes:
        return ControlMapResult(success=False, error=f"anchor image not found for {scene_id}")

    img_array = np.frombuffer(anchor_bytes, dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return ControlMapResult(success=False, error="failed to decode anchor image")

    result_maps: dict[str, str] = {}
    skipped: list[str] = []

    for map_type in map_types:
        if map_type == "canny":
            canny = cv2.Canny(img, 100, 200)
            ok, encoded = cv2.imencode(".png", canny)
            if not ok:
                logger.error("[ControlMap] cv2.imencode failed for canny")
                continue
            canny_bytes = encoded.tobytes()
            canny_path = await storage.save_control_map(scene_id, "canny", canny_bytes)
            result_maps["canny"] = canny_path
        elif map_type in ("depth", "lineart"):
            skipped.append(map_type)
            logger.info(f"[ControlMap] {map_type} skipped — needs ML preprocessor (deferred)")
        else:
            skipped.append(map_type)
            logger.warning(f"[ControlMap] unknown map_type: {map_type}")

    return ControlMapResult(
        success=True,
        maps=result_maps,
        meta={"provider": "cv2", "skipped": skipped, "thresholds": [100, 200]},
    )
```

Update dispatch in `extract_control_maps`:
```python
elif provider == "cv2":
    return await _extract_cv2(anchor_image_path, scene_id, map_types)
elif provider == "controlnet":
    # Still TODO — ControlNet preprocessors deferred
    logger.warning("[ControlMap] ControlNet not implemented, falling back to cv2 (canny only)")
    return await _extract_cv2(anchor_image_path, scene_id, map_types)
```

### 5.3 New public method on `AnchorStorage` (small refactor)

Avoid having `_extract_cv2` poke through `AnchorStorage` private helpers (`_get_control_map_path` + `_get_storage`). Add a public method:

```python
# scene_anchor/anchor_storage.py
async def save_control_map(self, scene_id: str, map_type: str, data: bytes) -> str:
    """Upload a single control map PNG to MinIO. Returns the storage path."""
    storage = self._get_storage()
    path = self._get_control_map_path(scene_id, map_type)
    await storage.upload_bytes(
        path=path,
        data=data,
        content_type="image/png",
    )
    logger.info(f"Saved {map_type} control map for scene {scene_id}")
    return path
```

Used by `_extract_cv2` (§5.2). The existing `save_anchor(...)` already uploads all maps in one call; `save_control_map` is for the "extract one at a time" flow.

### 5.4 `retry_strategy` defaults

```python
async def enqueue_scene_anchor_generation(
    scene_id: str,
    project_id: str,
    scene_name: str,
    location: Optional[str] = None,
    time_of_day: Optional[str] = None,
    mood: Optional[str] = None,
    anchor_provider: str = "doubao",          # was: provider="mock" — collapsed into one param
    control_map_provider: str = "cv2",         # NEW
    db_session=None,
) -> dict:
    ...
```

**Backwards compatibility**: the original signature was `provider: str = "mock"` (one param for both). Splitting into two is a breaking change for any caller passing `provider=...` keyword. Audit:
```bash
grep -rn "enqueue_scene_anchor_generation" apps/api/
```
Result is 4 callers (storyboard, drafts, _assets_legacy, async_runner). All pass it as a Celery task or kwarg without `provider=`, so the rename is safe. Any caller that did pass `provider="mock"` (none) would now need both params.

---

## 6. Data Flow (full happy path)

1. User in chat: "create a forest scene" → `create_scene` tool → inserts `Asset` row (scope=character/scene assets) → dispatches `run_scene_anchor_generation` Celery task with scene_id.
2. Celery worker calls `enqueue_scene_anchor_generation(scene_id, ..., anchor_provider="doubao", control_map_provider="cv2")`.
3. `enqueue_scene_anchor_generation` builds `SceneAnchorSpec`, marks scene status=generating, calls `generate_anchor_with_retry` (max 3 attempts).
4. `generate_anchor_with_retry` → `generate_scene_anchor(provider="doubao")` → `_generate_doubao_seedream`:
   - Calls `provider.generate(DoubaoImageRequest)` → ARK API → returns `image_url`
   - Downloads image bytes via httpx
   - Calls `AnchorStorage.save_anchor` → uploads PNG + metadata.json to MinIO
   - Returns `AnchorResult(success=True, image_path=<minio key>, image_url=<presigned URL>)`.
5. `enqueue_scene_anchor_generation` calls `extract_control_maps(provider="cv2")` → `_extract_cv2`:
   - Loads anchor bytes from MinIO
   - cv2.Canny → uploads `canny.png` to `anchors/scenes/{scene_id}/canny.png`
   - Returns `ControlMapResult(success=True, maps={"canny": <minio key>}, meta={skipped: ["depth", "lineart"]})`.
6. `_update_scene_anchor` writes back to `Asset.data_json`:
   ```json
   {
     "anchor_image_path": "anchors/scenes/abc/anchor.png",
     "anchor_status": "ready",
     "control_maps": {"canny": "anchors/scenes/abc/canny.png"},
     "control_map_status": "ready",
     "anchor_meta": {...}
   }
   ```
7. Emits `scene_anchor_ready` event.

When subsequent panel render uses this scene, it can pick up `data_json.anchor_image_path` to pass to Seedream as `reference_image_url` (separate flow, already wired).

---

## 7. Error Handling

| Failure | Path | Surface |
|---|---|---|
| ARK_API_KEY missing | `_generate_doubao_seedream` returns `AnchorResult(success=False, error="...")` | retry_strategy retries 3× then marks scene `failed` with error in DB |
| Seedream 429 / 5xx | `doubao_image_provider.generate` already retries internally | retry_strategy gets eventual `success=False` and retries again |
| Download URL 404 (Seedream returned bad URL) | `_download_image` raises HTTPError → outer `try/except` in `_generate_doubao_seedream` returns failure | same retry path |
| Storage upload IO error | `AnchorStorage.save_anchor` raises → propagates → retry_strategy catches | scene marked `failed` |
| Canny extraction throws | `_extract_cv2` returns `success=True, maps={}, meta={error: "..."}` | scene anchor still marked ready (canny optional); control_map_status='partial' |
| Anchor exists but `load_anchor_image` returns None (transient) | `_extract_cv2` returns `success=False, error="anchor image not found for {scene_id}"` | retry_strategy logs but does not mark scene failed (anchor itself is ready) |

Soft vs hard failure rule: **anchor failure = hard** (scene unusable); **canny failure = soft** (scene still usable for Seedream-style consistency).

---

## 8. Testing Strategy

### 8.1 Unit tests

**`tests/unit/services/scene/test_anchor_generator_doubao.py`** (~6 tests):
- `_generate_doubao_seedream` happy path — mock `get_doubao_image_provider().generate` to return `DoubaoImageResult(success=True, image_data=b"<png bytes>", image_url="images/abc.jpg")`; mock `AnchorStorage.save_anchor`; verify return shape + width/height passed correctly.
- API key missing — mock `provider.api_key` = `None`; verify `success=False, error="ARK_API_KEY..."`.
- Provider returns failure — mock `generate` to return `success=False`; verify graceful fail.
- image_data missing, image_url is MinIO key — mock storage_client.download_bytes; verify it's called and bytes are passed to save_anchor.
- image_data + image_url both missing — verify `success=False` with "no image bytes or URL".
- Verify dispatch in `generate_scene_anchor` — `provider="doubao"` routes to `_generate_doubao_seedream`; small `size` coerced up to ≥3,686,400 pixels.

**`tests/unit/services/scene/test_control_map_cv2.py`** (~5 tests):
- Happy path — generate a 32×32 PIL test image, encode to PNG bytes, mock `AnchorStorage.load_anchor_image` to return those bytes; verify `_extract_cv2` produces a canny PNG and uploads it.
- Anchor not found — mock load_anchor_image returns None → verify `success=False`.
- Bad image bytes — mock returns malformed bytes → verify `success=False, error="failed to decode..."`.
- depth/lineart skipped — request `["canny", "depth", "lineart"]`; verify only canny in `maps`, depth+lineart in `meta.skipped`.
- Unknown map type — request `["foo"]`; verify it's in `meta.skipped`.

### 8.2 Integration test

**`tests/integration/scene/test_anchor_e2e.py`** (1 test):
- In-memory SQLite, fakeredis (if needed), mocked `doubao_image_provider.generate` to return success, real cv2, real `AnchorStorage` against an in-memory MinIO substitute (or use `app.core.storage.MockObjectStore` if it exists; otherwise mock `_get_storage()` at AnchorStorage level).
- Call `enqueue_scene_anchor_generation(scene_id, ...)` end to end.
- Assert: `Asset.data_json["anchor_status"] == "ready"`, `data_json["control_maps"]["canny"]` is set, `_emit_anchor_ready` was called.

### 8.3 Static-source regression

**`tests/unit/services/scene/test_phase_c_real_impl.py`** (3 tests):
- `anchor_generator.py` source contains `from app.services.layer_factory.doubao_image_provider import` (not just `_generate_mock`).
- `control_map_extractor.py` source contains `import cv2` and a `cv2.Canny(` call site.
- `retry_strategy.py` `enqueue_scene_anchor_generation` defaults to `anchor_provider="doubao"` and `control_map_provider="cv2"`.

These guard against accidental revert to mock during refactors.

---

## 9. File Inventory

```
Modified (4):
apps/api/app/services/scene/anchor_generator.py            ~70 lines added
apps/api/app/services/scene/control_map_extractor.py       ~50 lines added
apps/api/app/services/scene/retry_strategy.py              ~5 lines: param split + defaults
apps/api/app/services/scene_anchor/anchor_storage.py       ~10 lines: public save_control_map

New tests (5 files):
apps/api/tests/unit/services/scene/__init__.py
apps/api/tests/unit/services/scene/test_anchor_generator_doubao.py
apps/api/tests/unit/services/scene/test_control_map_cv2.py
apps/api/tests/integration/scene/__init__.py
apps/api/tests/integration/scene/test_anchor_e2e.py
apps/api/tests/unit/services/scene/test_phase_c_real_impl.py
```

No new dependencies (cv2 + Seedream provider already present).

---

## 10. Acceptance Criteria

- [ ] `_generate_doubao_seedream` is called when `provider="doubao"` and produces a real PNG in MinIO.
- [ ] `_extract_cv2` is called when `provider="cv2"` and produces a canny PNG in MinIO.
- [ ] `enqueue_scene_anchor_generation` defaults route to real implementations.
- [ ] All 4 existing callers continue to work without modification.
- [ ] Mock providers still callable via explicit `provider="mock"` for tests.
- [ ] depth/lineart explicitly listed in `meta.skipped` (not silently absent).
- [ ] All new tests pass (~12 cases) + B-1 suite still green (160 cases).
- [ ] Soft-canny-failure does not block anchor readiness.

---

## 11. Known Limitations

- **No depth map** → ComfyUI-path renders with `payload_builder` will skip depth ControlNet node when consuming this scene (existing code path handles missing keys gracefully — `payload_builder.py:274` checks `if "depth" in scene_control_maps`).
- **No lineart** → same.
- **Canny thresholds (100, 200)** are not tuned per scene — may produce noisy or sparse edges depending on anchor content. Tune empirically when ComfyUI path is enabled and we see real downstream effect.
- **Default anchor size coerced to 2304×1632** when callers pass small sizes (Seedream 4.5 requires ≥3,686,400 pixels). Original `(768, 512)` default in `generate_scene_anchor` is treated as "the caller wants it small but Seedream forbids it" — silently bumped, with width/height in result `meta`. Callers that need exact dimensions must pass already-large sizes.
- **Provider-side double-persist**: Doubao provider already saves the generated image to `images/` prefix in MinIO; we re-save under `anchors/scenes/{scene_id}/anchor.png`. Net cost: one extra MinIO upload per scene + a small disk-doubling. Acceptable tradeoff for canonical anchor path.
- **Provider parameter rename** — `enqueue_scene_anchor_generation` had `provider: str = "mock"`; we split into `anchor_provider` + `control_map_provider`. Any external caller passing `provider=` (none observed in repo) would break.
- **No ComfyUI integration** — `_generate_comfyui` and `_extract_controlnet` paths still TODO; deferred until home-GPU deployment is online.
- **Seedream model lock** — uses `doubao-seedream-4-5-251128` (latest as of 2026-05). When ARK retires the model, update `doubao_image_provider.SEEDREAM_MODEL`.

---

## 12. Successor Work

When ComfyUI rendering is enabled (~part of B-1.5 deployment phase or separate "real GPU" project):
1. Add `controlnet_aux` + torch deps
2. Implement `_extract_depth` (depth_anything model) + `_extract_lineart` (lineart_anime preprocessor)
3. Add provider param `provider="controlnet_aux"` that uses ML models
4. Backfill control maps for existing scenes (one-time migration script)
5. Tune canny thresholds based on observed ControlNet behavior
