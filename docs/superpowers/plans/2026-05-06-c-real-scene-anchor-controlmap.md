# C — Real Scene Anchor + Canny Control Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace mock implementations in `services/scene/anchor_generator.py` and `services/scene/control_map_extractor.py` with real Doubao Seedream API calls + cv2-based canny extraction. Add a public `save_control_map` helper to `AnchorStorage`. Defer depth/lineart until ComfyUI rendering path is enabled.

**Architecture:** New `_generate_doubao_seedream` provider in anchor_generator wraps the existing `doubao_image_provider.DoubaoImageProvider`, downloads/copies bytes into the canonical anchor MinIO path. New `_extract_cv2` provider in control_map_extractor reads anchor from MinIO via AnchorStorage and uploads canny-only output. Both retain mock providers for tests.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, Doubao Seedream 4.5 (`doubao-seedream-4-5-251128`) via ARK_API_KEY, opencv-python (`cv2.Canny`), MinIO via existing `AnchorStorage`.

**Reference spec:** `docs/superpowers/specs/2026-05-06-c-real-scene-anchor-controlmap-design.md`.

**Estimated effort:** ~1 day (~13 tasks).

---

## Pre-flight

- [ ] **Step 0: Confirm starting state**

```bash
cd D:/ai-webtoon-studio
git status                          # working tree clean
git log --oneline -1                # 3cdd224 docs: C — real scene anchor + canny control map design spec
git rev-parse --abbrev-ref HEAD     # feat/b1e-legacy-deletion (or main if you've merged)
```

- [ ] **Step 0.1: Create C branch**

```bash
git checkout -b feat/c-real-scene-anchor
```

- [ ] **Step 0.2: Verify backend imports cleanly + B-1 tests still pass**

```bash
cd D:/ai-webtoon-studio/apps/api
py -3.13 -c "from app.main import app; print('main imports OK; routes:', len(app.routes))"
py -3.13 -m pytest tests/unit/services/agent tests/integration/agent 2>&1 | tail -3
```

Expected: imports clean; B-1 tests at 160 passed.

---

## Group 1: AnchorStorage helper

### Task 1.1: Add public `save_control_map` method to `AnchorStorage`

**Files:**
- Modify: `apps/api/app/services/scene_anchor/anchor_storage.py` — append a method after `save_anchor` (~line 110)
- Test: `apps/api/tests/unit/services/scene_anchor/test_save_control_map.py` (new)

- [ ] **Step 1: Create test directory + write the failing test**

`apps/api/tests/unit/services/scene_anchor/__init__.py` (empty file).

`apps/api/tests/unit/services/scene_anchor/test_save_control_map.py`:
```python
"""Test AnchorStorage.save_control_map for single-map upload (Phase C)."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.scene_anchor.anchor_storage import AnchorStorage


@pytest.mark.asyncio
async def test_save_control_map_uploads_to_correct_path():
    storage = AnchorStorage()
    fake_storage_client = MagicMock()
    fake_storage_client.upload_bytes = AsyncMock(return_value="ok")
    storage._storage = fake_storage_client

    path = await storage.save_control_map("scene-abc", "canny", b"<png bytes>")

    assert path == "anchors/scenes/scene-abc/canny.png"
    fake_storage_client.upload_bytes.assert_awaited_once_with(
        path="anchors/scenes/scene-abc/canny.png",
        data=b"<png bytes>",
        content_type="image/png",
    )


@pytest.mark.asyncio
async def test_save_control_map_supports_depth_lineart_paths():
    """Path generator handles all known control map types — even ones we don't extract today."""
    storage = AnchorStorage()
    fake_storage_client = MagicMock()
    fake_storage_client.upload_bytes = AsyncMock(return_value="ok")
    storage._storage = fake_storage_client

    for map_type in ("depth", "canny", "lineart"):
        path = await storage.save_control_map("scene-x", map_type, b"data")
        assert path == f"anchors/scenes/scene-x/{map_type}.png"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd D:/ai-webtoon-studio/apps/api
py -3.13 -m pytest tests/unit/services/scene_anchor/test_save_control_map.py -v
```

Expected: FAIL with `AttributeError: 'AnchorStorage' object has no attribute 'save_control_map'`.

- [ ] **Step 3: Implement the method**

In `apps/api/app/services/scene_anchor/anchor_storage.py`, find the `save_anchor` method (around line 48). Add this new method right after it (before `load_anchor_image`):

```python
    async def save_control_map(self, scene_id: str, map_type: str, data: bytes) -> str:
        """Upload a single control map PNG to MinIO. Returns the storage path.

        Used when control maps are extracted incrementally (one map at a time)
        rather than batched up-front. Counterpart to the all-in-one save_anchor.
        """
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

- [ ] **Step 4: Run test to verify it passes**

```bash
py -3.13 -m pytest tests/unit/services/scene_anchor/test_save_control_map.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/app/services/scene_anchor/anchor_storage.py apps/api/tests/unit/services/scene_anchor/__init__.py apps/api/tests/unit/services/scene_anchor/test_save_control_map.py
git commit -m "feat(api): AnchorStorage.save_control_map for incremental upload (C)"
```

---

## Group 2: Real anchor generation via Doubao Seedream

### Task 2.1: Test scaffolding — directory + helpers

**Files:**
- Create: `apps/api/tests/unit/services/scene/__init__.py` (empty)
- Create: `apps/api/tests/unit/services/scene/_helpers.py` (test fixture utilities)

- [ ] **Step 1: Create empty `__init__.py`**

```bash
mkdir -p D:/ai-webtoon-studio/apps/api/tests/unit/services/scene
type nul > D:/ai-webtoon-studio/apps/api/tests/unit/services/scene/__init__.py
```

(On macOS/Linux: `touch apps/api/tests/unit/services/scene/__init__.py`.)

- [ ] **Step 2: Create test helpers**

`apps/api/tests/unit/services/scene/_helpers.py`:
```python
"""Shared test fixtures for scene anchor tests."""
import io
import numpy as np
from PIL import Image


def make_test_png_bytes(width: int = 32, height: int = 32, color: str = "RGB") -> bytes:
    """Generate a tiny PNG image in-memory for tests."""
    img = Image.new(color, (width, height), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_grayscale_gradient_png(width: int = 64, height: int = 64) -> bytes:
    """Generate a PNG with a horizontal gradient — gives canny something to detect."""
    arr = np.zeros((height, width), dtype=np.uint8)
    for y in range(height):
        arr[y, :] = np.linspace(0, 255, width).astype(np.uint8)
    img = Image.fromarray(arr, mode="L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
```

- [ ] **Step 3: Smoke-test helpers**

```bash
cd D:/ai-webtoon-studio/apps/api
py -3.13 -c "
from tests.unit.services.scene._helpers import make_test_png_bytes, make_grayscale_gradient_png
b = make_test_png_bytes()
print('PNG bytes:', len(b), 'starts with:', b[:8])
b2 = make_grayscale_gradient_png()
print('Gradient PNG:', len(b2))
"
```

Expected: prints PNG byte counts (>0) and `\\x89PNG\\r\\n\\x1a\\n` magic bytes.

- [ ] **Step 4: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/tests/unit/services/scene/__init__.py apps/api/tests/unit/services/scene/_helpers.py
git commit -m "test(api): scene anchor test helpers (C)"
```

### Task 2.2: `_enforce_seedream_min_pixels` helper

**Files:**
- Modify: `apps/api/app/services/scene/anchor_generator.py` — add helper at module level
- Test: `apps/api/tests/unit/services/scene/test_anchor_generator_doubao.py` (new)

- [ ] **Step 1: Write the failing test**

`apps/api/tests/unit/services/scene/test_anchor_generator_doubao.py`:
```python
"""Tests for Doubao Seedream anchor generation (Phase C)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.scene.anchor_generator import (
    SceneAnchorSpec, _enforce_seedream_min_pixels, _generate_doubao_seedream,
    generate_scene_anchor,
)
from tests.unit.services.scene._helpers import make_test_png_bytes


def test_enforce_seedream_min_pixels_keeps_large_sizes():
    # Already satisfies 3,686,400-pixel minimum
    assert _enforce_seedream_min_pixels((1920, 1920)) == (1920, 1920)
    assert _enforce_seedream_min_pixels((2304, 1632)) == (2304, 1632)


def test_enforce_seedream_min_pixels_coerces_small_sizes():
    # 768×512 = 393,216 — way below 3,686,400; coerce to default
    assert _enforce_seedream_min_pixels((768, 512)) == (2304, 1632)
    assert _enforce_seedream_min_pixels((1024, 768)) == (2304, 1632)
```

- [ ] **Step 2: Run — expect failure**

```bash
cd D:/ai-webtoon-studio/apps/api
py -3.13 -m pytest tests/unit/services/scene/test_anchor_generator_doubao.py::test_enforce_seedream_min_pixels_keeps_large_sizes -v
```

Expected: FAIL with `ImportError: cannot import name '_enforce_seedream_min_pixels'`.

- [ ] **Step 3: Add helper to anchor_generator.py**

In `apps/api/app/services/scene/anchor_generator.py`, add this function at module level (after the existing `STYLE_PROFILES` dict, before `compose_anchor_prompt`):

```python
def _enforce_seedream_min_pixels(size: tuple[int, int]) -> tuple[int, int]:
    """Seedream 4.5 requires ≥3,686,400 pixels (e.g. 1920×1920). Small callers
    (e.g. legacy default 768×512) are bumped up to a 16:9-ish landscape default.

    Callers needing a specific aspect ratio should pass an already-large size.
    """
    width, height = size
    if width * height >= 3_686_400:
        return width, height
    # Default scene anchor: 2304×1632 = 3,760,128 pixels (~16:9, slight pad)
    return 2304, 1632
```

- [ ] **Step 4: Run tests — expect pass**

```bash
py -3.13 -m pytest tests/unit/services/scene/test_anchor_generator_doubao.py::test_enforce_seedream_min_pixels_keeps_large_sizes tests/unit/services/scene/test_anchor_generator_doubao.py::test_enforce_seedream_min_pixels_coerces_small_sizes -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/app/services/scene/anchor_generator.py apps/api/tests/unit/services/scene/test_anchor_generator_doubao.py
git commit -m "feat(api): _enforce_seedream_min_pixels helper (C)"
```

### Task 2.3: `_generate_doubao_seedream` happy path

**Files:**
- Modify: `apps/api/app/services/scene/anchor_generator.py` — add `_generate_doubao_seedream` async function
- Test: extend `apps/api/tests/unit/services/scene/test_anchor_generator_doubao.py`

- [ ] **Step 1: Append happy-path test**

Append to `tests/unit/services/scene/test_anchor_generator_doubao.py`:
```python
@pytest.mark.asyncio
async def test_generate_doubao_seedream_happy_path(monkeypatch):
    """Provider returns image_data → anchor written via AnchorStorage.save_anchor."""
    spec = SceneAnchorSpec(scene_id="scene-1", name="forest", location="enchanted forest")

    fake_provider = MagicMock()
    fake_provider.api_key = "test-key"
    fake_result = MagicMock(
        success=True,
        image_data=make_test_png_bytes(),
        image_url="images/abc.jpg",
        error=None,
    )
    fake_provider.generate = AsyncMock(return_value=fake_result)

    fake_anchor_storage = MagicMock()
    fake_anchor_storage.save_anchor = AsyncMock(
        return_value={"anchor": "anchors/scenes/scene-1/anchor.png"}
    )
    fake_anchor_storage.get_anchor_url = MagicMock(
        return_value="http://minio/anchors/scenes/scene-1/anchor.png"
    )

    with patch("app.services.layer_factory.doubao_image_provider.get_doubao_image_provider", return_value=fake_provider), \
         patch("app.services.scene_anchor.anchor_storage.get_anchor_storage", return_value=fake_anchor_storage):
        result = await _generate_doubao_seedream(
            spec=spec,
            positive="forest scene, daytime",
            negative="people",
            size=(1920, 1920),
            seed=12345,
        )

    assert result.success is True
    assert result.image_path == "anchors/scenes/scene-1/anchor.png"
    assert result.image_url == "http://minio/anchors/scenes/scene-1/anchor.png"
    assert result.meta["seed"] == 12345
    assert result.meta["provider"] == "doubao-seedream"

    # Provider was called with correct width/height (NOT a 'size' string)
    call_args = fake_provider.generate.call_args
    req = call_args.args[0] if call_args.args else call_args.kwargs.get("request")
    assert req.width == 1920
    assert req.height == 1920
    assert req.prompt == "forest scene, daytime"
    assert req.seed == 12345

    # save_anchor was called with the bytes from image_data
    save_call = fake_anchor_storage.save_anchor.call_args
    assert save_call.kwargs["scene_id"] == "scene-1"
    assert isinstance(save_call.kwargs["anchor_image"], bytes)
    assert save_call.kwargs["control_maps"] == {}
    assert save_call.kwargs["metadata"]["seed"] == 12345
```

- [ ] **Step 2: Run — expect failure**

```bash
py -3.13 -m pytest tests/unit/services/scene/test_anchor_generator_doubao.py::test_generate_doubao_seedream_happy_path -v
```

Expected: FAIL with `ImportError: cannot import name '_generate_doubao_seedream'`.

- [ ] **Step 3: Add `_generate_doubao_seedream` function**

In `apps/api/app/services/scene/anchor_generator.py`, **replace** the existing `_generate_comfyui` function (lines ~132-144) with:

```python
async def _generate_doubao_seedream(
    spec: SceneAnchorSpec,
    positive: str,
    negative: str,
    size: tuple[int, int],
    seed: int,
) -> AnchorResult:
    """Generate scene anchor via Doubao Seedream 4.5 + re-store under the
    canonical AnchorStorage path.

    The provider already persists the image under the `images/` MinIO prefix.
    We re-save under `anchors/scenes/{scene_id}/anchor.png` to give the scene
    its canonical address.
    """
    from app.services.layer_factory.doubao_image_provider import (
        get_doubao_image_provider, DoubaoImageRequest, SEEDREAM_MODEL,
    )
    from app.services.scene_anchor.anchor_storage import get_anchor_storage
    from app.core.storage import get_storage_client

    provider = get_doubao_image_provider()
    if not provider.api_key:
        return AnchorResult(
            success=False,
            error="ARK_API_KEY / DOUBAO_API_KEY not configured",
        )

    width, height = _enforce_seedream_min_pixels(size)

    req = DoubaoImageRequest(
        prompt=positive,
        negative_prompt=negative,
        width=width,
        height=height,
        seed=seed,
    )

    try:
        resp = await provider.generate(req)
    except Exception as e:
        logger.exception("[SceneAnchor] Seedream call raised")
        return AnchorResult(success=False, error=f"Seedream call raised: {e!r}")

    if not resp.success:
        return AnchorResult(
            success=False,
            error=resp.error or "Seedream generation failed",
        )

    # Resolve image bytes — provider may have persisted bytes inline OR returned
    # a storage key OR returned an http(s) URL (fallback when persist failed).
    image_bytes = resp.image_data
    if image_bytes is None and resp.image_url:
        if resp.image_url.startswith(("http://", "https://")):
            import httpx
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    r = await client.get(resp.image_url)
                    r.raise_for_status()
                    image_bytes = r.content
            except Exception as e:
                logger.exception("[SceneAnchor] Failed to download Seedream temp URL")
                return AnchorResult(success=False, error=f"download failed: {e!r}")
        else:
            try:
                sc = get_storage_client()
                image_bytes = await sc.download_bytes(resp.image_url)
            except Exception as e:
                logger.exception("[SceneAnchor] Failed to fetch persisted Seedream bytes")
                return AnchorResult(success=False, error=f"storage fetch failed: {e!r}")

    if not image_bytes:
        return AnchorResult(
            success=False,
            error="Seedream returned neither image_data nor a usable image_url",
        )

    storage = get_anchor_storage()
    paths = await storage.save_anchor(
        scene_id=spec.scene_id,
        anchor_image=image_bytes,
        control_maps={},
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
```

Also **update the dispatch table** in `generate_scene_anchor` (around line 105-110). Find:
```python
    if provider == "mock":
        return await _generate_mock(spec, seed)
    elif provider == "comfyui":
        return await _generate_comfyui(spec, positive, negative, size, seed, output_dir)
    else:
        return AnchorResult(success=False, error=f"Unknown provider: {provider}")
```

Replace with:
```python
    if provider == "mock":
        return await _generate_mock(spec, seed)
    elif provider == "doubao":
        return await _generate_doubao_seedream(spec, positive, negative, size, seed)
    elif provider == "comfyui":
        # ComfyUI path is deferred until home-GPU deployment (B-1 Phase A territory).
        # Fall through to Doubao for safety.
        logger.warning("[SceneAnchor] ComfyUI not implemented, falling back to doubao")
        return await _generate_doubao_seedream(spec, positive, negative, size, seed)
    else:
        return AnchorResult(success=False, error=f"Unknown provider: {provider}")
```

- [ ] **Step 4: Run — expect pass**

```bash
py -3.13 -m pytest tests/unit/services/scene/test_anchor_generator_doubao.py -v
```

Expected: 3 passed (the existing 2 plus the new happy path).

- [ ] **Step 5: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/app/services/scene/anchor_generator.py apps/api/tests/unit/services/scene/test_anchor_generator_doubao.py
git commit -m "feat(api): _generate_doubao_seedream — real anchor via Seedream (C)"
```

### Task 2.4: `_generate_doubao_seedream` failure paths

**Files:**
- Test: extend `apps/api/tests/unit/services/scene/test_anchor_generator_doubao.py`

- [ ] **Step 1: Append failure-path tests**

Append to `tests/unit/services/scene/test_anchor_generator_doubao.py`:
```python
@pytest.mark.asyncio
async def test_generate_doubao_seedream_no_api_key():
    spec = SceneAnchorSpec(scene_id="x", name="test")
    fake_provider = MagicMock()
    fake_provider.api_key = None

    with patch("app.services.layer_factory.doubao_image_provider.get_doubao_image_provider", return_value=fake_provider):
        result = await _generate_doubao_seedream(spec, "p", "n", (1920, 1920), 1)

    assert result.success is False
    assert "ARK_API_KEY" in result.error or "DOUBAO_API_KEY" in result.error


@pytest.mark.asyncio
async def test_generate_doubao_seedream_provider_failure():
    spec = SceneAnchorSpec(scene_id="x", name="test")
    fake_provider = MagicMock()
    fake_provider.api_key = "k"
    fake_provider.generate = AsyncMock(return_value=MagicMock(
        success=False, error="rate limited", error_code="429",
        image_data=None, image_url=None,
    ))

    with patch("app.services.layer_factory.doubao_image_provider.get_doubao_image_provider", return_value=fake_provider):
        result = await _generate_doubao_seedream(spec, "p", "n", (1920, 1920), 1)

    assert result.success is False
    assert "rate limited" in (result.error or "")


@pytest.mark.asyncio
async def test_generate_doubao_seedream_resolves_image_url_minio_key(monkeypatch):
    """When image_data is None but image_url is a MinIO key (no http://), fetch via storage."""
    spec = SceneAnchorSpec(scene_id="scene-1", name="test")

    fake_provider = MagicMock()
    fake_provider.api_key = "k"
    fake_provider.generate = AsyncMock(return_value=MagicMock(
        success=True, image_data=None, image_url="images/persisted.jpg", error=None,
    ))

    fake_sc = MagicMock()
    fake_sc.download_bytes = AsyncMock(return_value=make_test_png_bytes())

    fake_anchor_storage = MagicMock()
    fake_anchor_storage.save_anchor = AsyncMock(return_value={"anchor": "anchors/scenes/scene-1/anchor.png"})
    fake_anchor_storage.get_anchor_url = MagicMock(return_value="http://minio/anchor.png")

    with patch("app.services.layer_factory.doubao_image_provider.get_doubao_image_provider", return_value=fake_provider), \
         patch("app.services.scene_anchor.anchor_storage.get_anchor_storage", return_value=fake_anchor_storage), \
         patch("app.core.storage.get_storage_client", return_value=fake_sc):
        result = await _generate_doubao_seedream(spec, "p", "n", (1920, 1920), 1)

    assert result.success is True
    fake_sc.download_bytes.assert_awaited_once_with("images/persisted.jpg")


@pytest.mark.asyncio
async def test_generate_doubao_seedream_no_bytes_no_url():
    spec = SceneAnchorSpec(scene_id="x", name="test")
    fake_provider = MagicMock()
    fake_provider.api_key = "k"
    fake_provider.generate = AsyncMock(return_value=MagicMock(
        success=True, image_data=None, image_url=None, error=None,
    ))

    with patch("app.services.layer_factory.doubao_image_provider.get_doubao_image_provider", return_value=fake_provider):
        result = await _generate_doubao_seedream(spec, "p", "n", (1920, 1920), 1)

    assert result.success is False
    assert "image_data" in result.error or "image_url" in result.error or "neither" in result.error.lower()
```

- [ ] **Step 2: Run all anchor tests**

```bash
py -3.13 -m pytest tests/unit/services/scene/test_anchor_generator_doubao.py -v
```

Expected: 7 passed (3 from prior tasks + 4 failure-path).

- [ ] **Step 3: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/tests/unit/services/scene/test_anchor_generator_doubao.py
git commit -m "test(api): _generate_doubao_seedream failure paths (C)"
```

### Task 2.5: Dispatch — `provider=\"doubao\"` route + small-size coerce

**Files:**
- Test: extend `apps/api/tests/unit/services/scene/test_anchor_generator_doubao.py`

- [ ] **Step 1: Append dispatch tests**

```python
@pytest.mark.asyncio
async def test_generate_scene_anchor_dispatches_to_doubao_when_provider_doubao(monkeypatch):
    """Verifies the provider="doubao" path actually calls _generate_doubao_seedream."""
    called = {}

    async def fake_doubao(spec, positive, negative, size, seed):
        called["called"] = True
        called["size"] = size
        return MagicMock(success=True, image_path="x", image_url="y", meta={})

    monkeypatch.setattr(
        "app.services.scene.anchor_generator._generate_doubao_seedream",
        fake_doubao,
    )

    spec = SceneAnchorSpec(scene_id="scene-1", name="t")
    result = await generate_scene_anchor(spec, provider="doubao", size=(1920, 1920), seed=1)

    assert called.get("called") is True
    assert called["size"] == (1920, 1920)
    assert result.success is True


@pytest.mark.asyncio
async def test_generate_scene_anchor_small_size_coerced_through_dispatch(monkeypatch):
    """Even when caller passes the legacy default (768, 512), the size that
    reaches Seedream API is coerced to ≥3,686,400 pixels (in _enforce helper)."""
    captured = {}

    fake_provider = MagicMock()
    fake_provider.api_key = "k"

    async def fake_generate(req):
        captured["width"] = req.width
        captured["height"] = req.height
        return MagicMock(
            success=True, image_data=make_test_png_bytes(), image_url="x",
        )

    fake_provider.generate = fake_generate

    fake_anchor_storage = MagicMock()
    fake_anchor_storage.save_anchor = AsyncMock(return_value={"anchor": "anchors/scenes/scene-1/anchor.png"})
    fake_anchor_storage.get_anchor_url = MagicMock(return_value="http://x")

    with patch("app.services.layer_factory.doubao_image_provider.get_doubao_image_provider", return_value=fake_provider), \
         patch("app.services.scene_anchor.anchor_storage.get_anchor_storage", return_value=fake_anchor_storage):
        spec = SceneAnchorSpec(scene_id="scene-1", name="t")
        # Passing tiny size — should be bumped
        await generate_scene_anchor(spec, provider="doubao", size=(768, 512), seed=1)

    # 768×512 = 393,216 → coerced to 2304×1632 (or any ≥3,686,400)
    assert captured["width"] * captured["height"] >= 3_686_400
```

- [ ] **Step 2: Run**

```bash
py -3.13 -m pytest tests/unit/services/scene/test_anchor_generator_doubao.py -v
```

Expected: 9 passed.

- [ ] **Step 3: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/tests/unit/services/scene/test_anchor_generator_doubao.py
git commit -m "test(api): generate_scene_anchor dispatch + size coercion (C)"
```

---

## Group 3: Real canny extraction via cv2

### Task 3.1: `_extract_cv2` happy path

**Files:**
- Modify: `apps/api/app/services/scene/control_map_extractor.py`
- Test: `apps/api/tests/unit/services/scene/test_control_map_cv2.py` (new)

- [ ] **Step 1: Write the failing test**

`apps/api/tests/unit/services/scene/test_control_map_cv2.py`:
```python
"""Tests for cv2-based control map extraction (Phase C)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.scene.control_map_extractor import _extract_cv2, extract_control_maps
from tests.unit.services.scene._helpers import make_grayscale_gradient_png


@pytest.mark.asyncio
async def test_extract_cv2_canny_happy_path():
    """Real cv2 canny on a real test PNG → uploads via save_control_map."""
    fake_anchor_storage = MagicMock()
    fake_anchor_storage.load_anchor_image = AsyncMock(
        return_value=make_grayscale_gradient_png()
    )
    fake_anchor_storage.save_control_map = AsyncMock(
        return_value="anchors/scenes/scene-1/canny.png"
    )

    with patch("app.services.scene_anchor.anchor_storage.get_anchor_storage", return_value=fake_anchor_storage):
        result = await _extract_cv2("any/path", "scene-1", ["canny"])

    assert result.success is True
    assert result.maps == {"canny": "anchors/scenes/scene-1/canny.png"}
    assert result.meta["provider"] == "cv2"
    assert result.meta["skipped"] == []
    assert result.meta["thresholds"] == [100, 200]

    # save_control_map was called with PNG bytes
    save_call = fake_anchor_storage.save_control_map.call_args
    assert save_call.args[0] == "scene-1"
    assert save_call.args[1] == "canny"
    assert save_call.args[2][:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic bytes


@pytest.mark.asyncio
async def test_extract_cv2_anchor_not_found():
    fake_anchor_storage = MagicMock()
    fake_anchor_storage.load_anchor_image = AsyncMock(return_value=None)

    with patch("app.services.scene_anchor.anchor_storage.get_anchor_storage", return_value=fake_anchor_storage):
        result = await _extract_cv2("any/path", "scene-x", ["canny"])

    assert result.success is False
    assert "not found" in result.error


@pytest.mark.asyncio
async def test_extract_cv2_bad_image_bytes():
    fake_anchor_storage = MagicMock()
    fake_anchor_storage.load_anchor_image = AsyncMock(return_value=b"not a real image")

    with patch("app.services.scene_anchor.anchor_storage.get_anchor_storage", return_value=fake_anchor_storage):
        result = await _extract_cv2("any/path", "scene-x", ["canny"])

    assert result.success is False
    assert "decode" in result.error


@pytest.mark.asyncio
async def test_extract_cv2_skips_depth_and_lineart():
    fake_anchor_storage = MagicMock()
    fake_anchor_storage.load_anchor_image = AsyncMock(
        return_value=make_grayscale_gradient_png()
    )
    fake_anchor_storage.save_control_map = AsyncMock(
        return_value="anchors/scenes/scene-1/canny.png"
    )

    with patch("app.services.scene_anchor.anchor_storage.get_anchor_storage", return_value=fake_anchor_storage):
        result = await _extract_cv2(
            "any/path", "scene-1", ["canny", "depth", "lineart"]
        )

    assert result.success is True
    assert "canny" in result.maps
    assert "depth" not in result.maps
    assert "lineart" not in result.maps
    assert sorted(result.meta["skipped"]) == ["depth", "lineart"]


@pytest.mark.asyncio
async def test_extract_cv2_unknown_map_type():
    fake_anchor_storage = MagicMock()
    fake_anchor_storage.load_anchor_image = AsyncMock(
        return_value=make_grayscale_gradient_png()
    )
    fake_anchor_storage.save_control_map = AsyncMock(return_value="x")

    with patch("app.services.scene_anchor.anchor_storage.get_anchor_storage", return_value=fake_anchor_storage):
        result = await _extract_cv2("any/path", "scene-1", ["foo", "canny"])

    assert result.success is True
    assert "canny" in result.maps
    assert "foo" in result.meta["skipped"]
```

- [ ] **Step 2: Run — expect failure**

```bash
py -3.13 -m pytest tests/unit/services/scene/test_control_map_cv2.py -v
```

Expected: FAIL with `ImportError: cannot import name '_extract_cv2'`.

- [ ] **Step 3: Implement `_extract_cv2`**

In `apps/api/app/services/scene/control_map_extractor.py`, **replace** `_extract_controlnet` (lines 74-83) with `_extract_cv2`:

```python
async def _extract_cv2(
    anchor_image_path: str,
    scene_id: str,
    map_types: list[str],
) -> ControlMapResult:
    """Extract control maps via OpenCV. Currently supports only canny.

    depth + lineart are explicitly skipped — they require ML preprocessor models
    (controlnet_aux + torch + GPU) which are deferred until ComfyUI rendering
    is enabled.
    """
    import cv2
    import numpy as np
    from app.services.scene_anchor.anchor_storage import get_anchor_storage

    storage = get_anchor_storage()
    anchor_bytes = await storage.load_anchor_image(scene_id)
    if not anchor_bytes:
        return ControlMapResult(
            success=False,
            error=f"anchor image not found for {scene_id}",
        )

    img_array = np.frombuffer(anchor_bytes, dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return ControlMapResult(
            success=False,
            error="failed to decode anchor image",
        )

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
            canny_path = await storage.save_control_map(
                scene_id, "canny", canny_bytes
            )
            result_maps["canny"] = canny_path
        elif map_type in ("depth", "lineart"):
            skipped.append(map_type)
            logger.info(
                f"[ControlMap] {map_type} skipped — needs ML preprocessor (deferred)"
            )
        else:
            skipped.append(map_type)
            logger.warning(f"[ControlMap] unknown map_type: {map_type}")

    return ControlMapResult(
        success=True,
        maps=result_maps,
        meta={"provider": "cv2", "skipped": skipped, "thresholds": [100, 200]},
    )
```

Also **update the dispatch table** in `extract_control_maps` (lines 47-52). Replace:
```python
    if provider == "mock":
        return await _extract_mock(scene_id, map_types)
    elif provider == "controlnet":
        return await _extract_controlnet(anchor_image_path, scene_id, map_types)
    else:
        return ControlMapResult(success=False, error=f"Unknown provider: {provider}")
```

With:
```python
    if provider == "mock":
        return await _extract_mock(scene_id, map_types)
    elif provider == "cv2":
        return await _extract_cv2(anchor_image_path, scene_id, map_types)
    elif provider == "controlnet":
        # ControlNet preprocessor stack (depth/lineart via controlnet_aux) is deferred.
        # Fall through to cv2 for canny-only support.
        logger.warning("[ControlMap] ControlNet not implemented, falling back to cv2 (canny only)")
        return await _extract_cv2(anchor_image_path, scene_id, map_types)
    else:
        return ControlMapResult(success=False, error=f"Unknown provider: {provider}")
```

- [ ] **Step 4: Run — expect pass**

```bash
py -3.13 -m pytest tests/unit/services/scene/test_control_map_cv2.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/app/services/scene/control_map_extractor.py apps/api/tests/unit/services/scene/test_control_map_cv2.py
git commit -m "feat(api): _extract_cv2 — real canny extraction via OpenCV (C)"
```

### Task 3.2: Dispatch — `provider="cv2"` route

**Files:**
- Test: extend `apps/api/tests/unit/services/scene/test_control_map_cv2.py`

- [ ] **Step 1: Append dispatch test**

```python
@pytest.mark.asyncio
async def test_extract_control_maps_dispatches_to_cv2(monkeypatch):
    called = {}

    async def fake_cv2(anchor_path, scene_id, map_types):
        called["called"] = True
        called["map_types"] = map_types
        return MagicMock(success=True, maps={"canny": "x"}, meta={})

    monkeypatch.setattr(
        "app.services.scene.control_map_extractor._extract_cv2",
        fake_cv2,
    )

    result = await extract_control_maps(
        anchor_image_path="any/path",
        scene_id="scene-1",
        map_types=["canny"],
        provider="cv2",
    )

    assert called.get("called") is True
    assert result.success is True


@pytest.mark.asyncio
async def test_extract_control_maps_default_full_set():
    """When map_types is None, defaults to all SUPPORTED_MAP_TYPES."""
    fake_anchor_storage = MagicMock()
    fake_anchor_storage.load_anchor_image = AsyncMock(
        return_value=make_grayscale_gradient_png()
    )
    fake_anchor_storage.save_control_map = AsyncMock(return_value="x")

    with patch("app.services.scene_anchor.anchor_storage.get_anchor_storage", return_value=fake_anchor_storage):
        result = await extract_control_maps(
            anchor_image_path="any/path",
            scene_id="scene-1",
            map_types=None,  # → defaults to ["depth", "lineart", "canny"]
            provider="cv2",
        )

    assert result.success is True
    assert "canny" in result.maps
    # depth + lineart should both be in skipped
    assert sorted(result.meta["skipped"]) == ["depth", "lineart"]
```

- [ ] **Step 2: Run**

```bash
py -3.13 -m pytest tests/unit/services/scene/test_control_map_cv2.py -v
```

Expected: 7 passed.

- [ ] **Step 3: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/tests/unit/services/scene/test_control_map_cv2.py
git commit -m "test(api): extract_control_maps cv2 dispatch + default map_types (C)"
```

---

## Group 4: Wire defaults into retry_strategy

### Task 4.1: Split `provider` param + new defaults

**Files:**
- Modify: `apps/api/app/services/scene/retry_strategy.py`
- Test: `apps/api/tests/unit/services/scene/test_retry_strategy_defaults.py` (new)

- [ ] **Step 1: Audit current callers (no changes yet)**

```bash
cd D:/ai-webtoon-studio
grep -n "enqueue_scene_anchor_generation" apps/api/app/ -r --include="*.py"
```

Expected: 4 results
- `app/api/routes/chapters/storyboard.py:467`
- `app/api/routes/drafts.py:638`
- `app/api/routes/_assets_legacy.py:398`
- `app/workers/async_runner.py:43` (the actual celery task wrapper)

For each, look at the call site and confirm it does NOT pass `provider=...`:
```bash
grep -B 1 -A 5 "enqueue_scene_anchor_generation" apps/api/app/api/routes/chapters/storyboard.py
grep -B 1 -A 5 "enqueue_scene_anchor_generation" apps/api/app/api/routes/drafts.py
grep -B 1 -A 5 "enqueue_scene_anchor_generation" apps/api/app/api/routes/_assets_legacy.py
grep -B 1 -A 5 "enqueue_scene_anchor_generation" apps/api/app/workers/async_runner.py
```

If any call site passes `provider="..."`, you'll need to migrate it (update to either `anchor_provider=...` or remove if it was passing `"mock"` for tests). Write any required migration into Step 3 below.

- [ ] **Step 2: Write the failing test**

`apps/api/tests/unit/services/scene/test_retry_strategy_defaults.py`:
```python
"""Verify retry_strategy defaults route to real implementations (Phase C)."""
import inspect

from app.services.scene import retry_strategy


def test_enqueue_default_anchor_provider_is_doubao():
    sig = inspect.signature(retry_strategy.enqueue_scene_anchor_generation)
    assert sig.parameters["anchor_provider"].default == "doubao"


def test_enqueue_default_control_map_provider_is_cv2():
    sig = inspect.signature(retry_strategy.enqueue_scene_anchor_generation)
    assert sig.parameters["control_map_provider"].default == "cv2"


def test_enqueue_no_longer_has_legacy_provider_param():
    """Old single 'provider' kwarg should be gone — split into two."""
    sig = inspect.signature(retry_strategy.enqueue_scene_anchor_generation)
    assert "provider" not in sig.parameters
```

- [ ] **Step 3: Run — expect failure**

```bash
cd D:/ai-webtoon-studio/apps/api
py -3.13 -m pytest tests/unit/services/scene/test_retry_strategy_defaults.py -v
```

Expected: 3 FAILs (current sig still has `provider` not split).

- [ ] **Step 4: Update `enqueue_scene_anchor_generation`**

In `apps/api/app/services/scene/retry_strategy.py`, find the function (line ~56). Replace its signature + body's provider usage:

**Current (line 56-66):**
```python
async def enqueue_scene_anchor_generation(
    scene_id: str,
    project_id: str,
    scene_name: str,
    location: Optional[str] = None,
    time_of_day: Optional[str] = None,
    mood: Optional[str] = None,
    provider: str = "mock",
    db_session = None
) -> dict:
```

**New:**
```python
async def enqueue_scene_anchor_generation(
    scene_id: str,
    project_id: str,
    scene_name: str,
    location: Optional[str] = None,
    time_of_day: Optional[str] = None,
    mood: Optional[str] = None,
    anchor_provider: str = "doubao",
    control_map_provider: str = "cv2",
    db_session = None,
) -> dict:
```

Then in the body, find the two places that use `provider`:

**Line ~95-98 (anchor generation call):**
```python
        success, anchor_path, meta = await generate_anchor_with_retry(
            spec=spec,
            provider=provider
        )
```

Change to:
```python
        success, anchor_path, meta = await generate_anchor_with_retry(
            spec=spec,
            provider=anchor_provider,
        )
```

**Line ~106-110 (control map extraction):**
```python
        control_result = await extract_control_maps(
            anchor_image_path=anchor_path,
            scene_id=scene_id,
            provider=provider
        )
```

Change to:
```python
        control_result = await extract_control_maps(
            anchor_image_path=anchor_path,
            scene_id=scene_id,
            provider=control_map_provider,
        )
```

- [ ] **Step 5: Run tests — expect pass**

```bash
py -3.13 -m pytest tests/unit/services/scene/test_retry_strategy_defaults.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Verify no callers pass legacy `provider=` kwarg**

```bash
cd D:/ai-webtoon-studio
grep -rn "enqueue_scene_anchor_generation.*provider=" apps/api/ --include="*.py"
```

Expected: empty (no caller passes `provider=`).

If a result appears, edit that caller — drop the `provider=` kwarg or rewrite to `anchor_provider=...`. Then re-run tests.

- [ ] **Step 7: Smoke-test app imports**

```bash
cd apps/api
py -3.13 -c "from app.main import app; print('main imports OK; routes:', len(app.routes))"
```

Expected: clean import.

- [ ] **Step 8: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/app/services/scene/retry_strategy.py apps/api/tests/unit/services/scene/test_retry_strategy_defaults.py
git commit -m "feat(api): retry_strategy split provider→anchor/control_map (defaults: doubao + cv2) (C)"
```

---

## Group 5: Static-source regression

### Task 5.1: Phase C real-impl regression test

**Files:**
- Create: `apps/api/tests/unit/services/scene/test_phase_c_real_impl.py`

- [ ] **Step 1: Write the test**

```python
"""Static-source regression: Phase C real implementations are live (not stubbed back to mock)."""
import inspect

from app.services.scene import anchor_generator, control_map_extractor, retry_strategy


def test_anchor_generator_imports_doubao_provider():
    """The doubao provider import must appear inside _generate_doubao_seedream."""
    src = inspect.getsource(anchor_generator)
    assert "from app.services.layer_factory.doubao_image_provider import" in src, \
        "anchor_generator no longer imports doubao_image_provider — Phase C regressed to mock"


def test_anchor_generator_has_doubao_function():
    assert hasattr(anchor_generator, "_generate_doubao_seedream"), \
        "anchor_generator missing _generate_doubao_seedream — Phase C regressed"


def test_anchor_generator_dispatches_doubao_provider():
    src = inspect.getsource(anchor_generator.generate_scene_anchor)
    assert 'provider == "doubao"' in src, \
        "generate_scene_anchor no longer routes 'doubao' provider — Phase C regressed"


def test_control_map_extractor_uses_cv2():
    src = inspect.getsource(control_map_extractor)
    assert "import cv2" in src
    assert "cv2.Canny(" in src, \
        "control_map_extractor no longer calls cv2.Canny — Phase C regressed"


def test_control_map_extractor_dispatches_cv2_provider():
    src = inspect.getsource(control_map_extractor.extract_control_maps)
    assert 'provider == "cv2"' in src, \
        "extract_control_maps no longer routes 'cv2' provider — Phase C regressed"


def test_retry_strategy_defaults_doubao_and_cv2():
    sig = inspect.signature(retry_strategy.enqueue_scene_anchor_generation)
    assert sig.parameters["anchor_provider"].default == "doubao"
    assert sig.parameters["control_map_provider"].default == "cv2"
```

- [ ] **Step 2: Run**

```bash
cd D:/ai-webtoon-studio/apps/api
py -3.13 -m pytest tests/unit/services/scene/test_phase_c_real_impl.py -v
```

Expected: 6 passed.

- [ ] **Step 3: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/tests/unit/services/scene/test_phase_c_real_impl.py
git commit -m "test(api): static-source regression for Phase C real impl (C)"
```

---

## Group 6: Integration test

### Task 6.1: End-to-end anchor + canny flow

**Files:**
- Create: `apps/api/tests/integration/scene/__init__.py` (empty)
- Create: `apps/api/tests/integration/scene/test_anchor_e2e.py`

- [ ] **Step 1: Create empty __init__**

```bash
mkdir -p D:/ai-webtoon-studio/apps/api/tests/integration/scene
type nul > D:/ai-webtoon-studio/apps/api/tests/integration/scene/__init__.py
```

- [ ] **Step 2: Write integration test**

`apps/api/tests/integration/scene/test_anchor_e2e.py`:
```python
"""End-to-end: enqueue_scene_anchor_generation with mocked Seedream + real cv2 + in-memory storage.

Verifies the full pipeline: spec → anchor (Seedream mock) → cv2 canny → AnchorStorage uploads.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401 — register all models
from app.models.base import Base
from app.models.asset import Asset, AssetType
from tests.unit.services.scene._helpers import make_grayscale_gradient_png


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    sess = Session()
    yield sess
    sess.close()


@pytest.mark.asyncio
async def test_anchor_e2e_doubao_then_canny(db_session):
    """End-to-end: anchor generated via mocked Seedream, canny extracted via real cv2,
    Asset.data_json updated with both paths."""
    project_id = "test-project"
    scene_id = "scene-1"

    # Insert minimal Asset row so _update_scene_status / _update_scene_anchor have something to update
    asset = Asset(
        id=scene_id,
        project_id=project_id,
        name="forest",
        type=AssetType.SCENE if hasattr(AssetType, "SCENE") else "scene",
        description="enchanted forest",
        data_json={},
    )
    db_session.add(asset)
    db_session.commit()

    # In-memory anchor storage that mimics the real one.
    # AnchorStorage uses _get_storage() under the hood; we patch get_anchor_storage to a
    # MagicMock that performs in-memory upload + retrieval.
    in_memory: dict[str, bytes] = {}

    def make_fake_storage():
        s = MagicMock()
        s._storage = MagicMock()
        async def upload(path, data, content_type=None):
            in_memory[path] = data
            return path
        async def download(path):
            return in_memory.get(path)

        async def save_anchor(scene_id, anchor_image, control_maps, metadata=None):
            anchor_path = f"anchors/scenes/{scene_id}/anchor.png"
            in_memory[anchor_path] = anchor_image
            return {"anchor": anchor_path}

        async def load_anchor_image(scene_id):
            return in_memory.get(f"anchors/scenes/{scene_id}/anchor.png")

        async def save_control_map(scene_id, map_type, data):
            path = f"anchors/scenes/{scene_id}/{map_type}.png"
            in_memory[path] = data
            return path

        s.save_anchor = save_anchor
        s.load_anchor_image = load_anchor_image
        s.save_control_map = save_control_map
        s.get_anchor_url = MagicMock(return_value="http://test/anchor.png")
        return s

    fake_storage = make_fake_storage()

    # Mock Doubao Seedream provider
    fake_provider = MagicMock()
    fake_provider.api_key = "test-key"
    fake_provider.generate = AsyncMock(return_value=MagicMock(
        success=True,
        image_data=make_grayscale_gradient_png(64, 64),
        image_url="images/test.jpg",
        error=None,
    ))

    # Patch get_anchor_storage at the import sites used by both modules
    with patch("app.services.scene.anchor_generator.get_anchor_storage", return_value=fake_storage, create=True), \
         patch("app.services.scene_anchor.anchor_storage.get_anchor_storage", return_value=fake_storage), \
         patch("app.services.layer_factory.doubao_image_provider.get_doubao_image_provider", return_value=fake_provider):

        from app.services.scene.retry_strategy import enqueue_scene_anchor_generation

        result = await enqueue_scene_anchor_generation(
            scene_id=scene_id,
            project_id=project_id,
            scene_name="forest",
            location="enchanted forest",
            time_of_day="day",
            mood="calm",
            db_session=db_session,
        )

    # Top-level result
    assert result["success"] is True, f"flow failed: {result.get('error')}"
    assert result["anchor_path"] == f"anchors/scenes/{scene_id}/anchor.png"
    assert result["control_maps"]["canny"] == f"anchors/scenes/{scene_id}/canny.png"

    # In-memory storage saw both PNGs
    assert f"anchors/scenes/{scene_id}/anchor.png" in in_memory
    assert f"anchors/scenes/{scene_id}/canny.png" in in_memory
    canny_bytes = in_memory[f"anchors/scenes/{scene_id}/canny.png"]
    assert canny_bytes[:8] == b"\x89PNG\r\n\x1a\n"  # canny output is a real PNG

    # DB state was updated
    db_session.refresh(asset)
    data = asset.data_json
    assert data["anchor_status"] == "ready"
    assert data["control_map_status"] == "ready"
    assert data["control_maps"]["canny"] == f"anchors/scenes/{scene_id}/canny.png"
```

- [ ] **Step 3: Run**

```bash
cd D:/ai-webtoon-studio/apps/api
py -3.13 -m pytest tests/integration/scene/test_anchor_e2e.py -v
```

Expected: 1 passed.

If it fails on `_update_scene_anchor` because `Asset` lookup fails — the fixture inserts the row but the inner `_update_scene_status` / `_update_scene_anchor` may use a different db session. Common fix: pass `db_session=db_session` correctly (already done in test). If `Asset.data_json` is None, the `or {}` fallback in retry_strategy handles it. Re-read the inner logic if a real bug surfaces.

- [ ] **Step 4: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/tests/integration/scene/__init__.py apps/api/tests/integration/scene/test_anchor_e2e.py
git commit -m "test(api): e2e anchor + canny via mocked Seedream + real cv2 (C)"
```

---

## Group 7: Final Verification

### Task 7.1: Run full B-1 + C test suite

- [ ] **Step 1: Run**

```bash
cd D:/ai-webtoon-studio/apps/api
py -3.13 -m pytest \
    tests/unit/services/agent \
    tests/unit/services/agent/skills \
    tests/unit/services/agent/tools \
    tests/unit/services/scene \
    tests/unit/services/scene_anchor \
    tests/unit/test_migration_022.py \
    tests/unit/core/test_logging.py \
    tests/unit/workers/test_trace_decorator.py \
    tests/unit/routes/test_b1_routes_registered.py \
    tests/unit/routes/test_episode_endpoints_delegate.py \
    tests/unit/test_phase_e_deletions.py \
    tests/integration/agent \
    tests/integration/scene \
    2>&1 | tail -3
```

Expected: ~178 passed (160 from B-1 + ~18 new from C).

### Task 7.2: Verify scene anchor tool dispatches doubao now

When B-1 chat-driven `create_scene` tool runs, it dispatches `run_scene_anchor_generation` (Celery task in `app/workers/async_runner.py`). After Group 4, that path uses real Doubao + cv2 by default.

- [ ] **Step 1: Read async_runner to confirm**

```bash
cd D:/ai-webtoon-studio/apps/api
grep -B 2 -A 12 "run_scene_anchor_generation\b" app/workers/async_runner.py
```

Expected: the celery task wraps `enqueue_scene_anchor_generation(...)` without `provider=`. After Group 4, it picks up the new defaults automatically. **No code change needed.**

If you find the wrapper passes `provider="mock"`, edit it: replace with no kwarg (so defaults apply), or split into `anchor_provider`/`control_map_provider` if you want explicit control. Commit any such fix:

```bash
git add apps/api/app/workers/async_runner.py
git commit -m "fix(api): drop legacy provider= kwarg in run_scene_anchor_generation (C)"
```

### Task 7.3: PR + merge prep

After the verification suite is green:

```bash
cd D:/ai-webtoon-studio
git log --oneline feat/b1e-legacy-deletion..feat/c-real-scene-anchor
git diff --stat feat/b1e-legacy-deletion..feat/c-real-scene-anchor
```

Expected: ~9 commits, ~3 source files modified + ~6 test files added.

Optional PR creation:
```bash
git push -u origin feat/c-real-scene-anchor
gh pr create --base main --title "C: real scene anchor (Doubao Seedream) + canny (cv2)" --body "$(cat <<'EOF'
## Summary
- Replace mock implementations in services/scene/anchor_generator.py and control_map_extractor.py
- Anchor: real Doubao Seedream API call via existing doubao_image_provider; output stored under canonical AnchorStorage path
- Canny: real cv2.Canny extraction from anchor; uploaded via new AnchorStorage.save_control_map helper
- depth + lineart: explicitly deferred until ComfyUI rendering path enabled (require controlnet_aux + torch + GPU)
- retry_strategy default providers: doubao (anchor) + cv2 (control maps)

## Test plan
- [x] B-1 + C unit suite green (~178 cases)
- [x] Integration test exercises full anchor → canny → MinIO → DB update flow
- [x] Static-source regression guards against revert to mock
- [ ] Manual smoke: trigger create_scene tool from chat, observe Asset.data_json updates with real paths

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review

**Spec coverage check** (each spec section maps to tasks):
- §1 Background — N/A (background only)
- §2 Goals — Tasks 2.3 (anchor real), 3.1 (canny real), 1.1 (save_control_map), 4.1 (defaults), 5.1 (regression)
- §3 Non-goals — N/A (explicitly out)
- §4 Architecture — Tasks 2.3 + 3.1 + 4.1 implement the depicted flow
- §5.1 _generate_doubao_seedream — Tasks 2.2 (helper) + 2.3 (impl) + 2.4 (failure paths) + 2.5 (dispatch)
- §5.2 _extract_cv2 — Tasks 3.1 + 3.2
- §5.3 save_control_map — Task 1.1
- §5.4 retry_strategy defaults — Task 4.1
- §6 Data flow — covered by integration Task 6.1
- §7 Error handling — Tasks 2.4 (Doubao failure modes) + 3.1 (anchor not found / bad bytes)
- §8 Testing strategy — Tasks 2.x, 3.x, 5.1, 6.1
- §9 File inventory — Pre-flight + every implementation task lists exact paths
- §10 Acceptance criteria — Task 7.1 verifies; static-source 5.1 guards
- §11 Known limitations — documented in spec; no plan tasks needed
- §12 Successor work — N/A (out of scope)

**Placeholder scan:** No "TBD", "fill in later", or "similar to Task N" patterns. Every code block has complete content. The Task 7.2 fallback edit (if `async_runner.py` has legacy `provider=` kwarg) gives explicit fix instructions.

**Type consistency:**
- `_enforce_seedream_min_pixels` returns `tuple[int, int]` — used identically in Task 2.2 (definition) + Task 2.3 (calls it).
- `DoubaoImageRequest` fields `prompt`/`negative_prompt`/`width`/`height`/`seed` match real provider verified during spec self-review.
- `DoubaoImageResult` fields `success`/`image_data`/`image_url`/`error` match real provider.
- `SEEDREAM_MODEL` imported as constant from `doubao_image_provider` — same name used everywhere.
- `AnchorStorage.save_control_map(scene_id, map_type, data) -> str` — Task 1.1 defines, Tasks 3.1 + 6.1 consume.
- `AnchorResult` / `ControlMapResult` Pydantic models unchanged from existing code.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-06-c-real-scene-anchor-controlmap.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
