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
