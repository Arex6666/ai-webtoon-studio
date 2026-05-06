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
