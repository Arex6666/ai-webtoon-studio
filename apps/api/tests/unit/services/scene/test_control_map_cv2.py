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

    save_call = fake_anchor_storage.save_control_map.call_args
    assert save_call.args[0] == "scene-1"
    assert save_call.args[1] == "canny"
    assert save_call.args[2][:8] == b"\x89PNG\r\n\x1a\n"


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
            map_types=None,
            provider="cv2",
        )

    assert result.success is True
    assert "canny" in result.maps
    assert sorted(result.meta["skipped"]) == ["depth", "lineart"]
