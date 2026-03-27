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
