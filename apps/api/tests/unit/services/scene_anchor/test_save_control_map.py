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
