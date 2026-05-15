"""Unit tests for BundleBuilder._fetch_chapter_video (Phase E)."""
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.export.bundle_builder import BundleBuilder
from app.services.export.bundle_models import BundleBuildContext


def _make_builder() -> BundleBuilder:
    ctx = BundleBuildContext(
        export_id="exp-1",
        job_id="job-1",
        chapter_id="ch-1",
    )
    builder = BundleBuilder(db=MagicMock(), context=ctx)
    builder.object_store = MagicMock()
    return builder


@pytest.mark.asyncio
async def test_fetch_chapter_video_creates_directory_and_calls_download(tmp_path):
    builder = _make_builder()
    # Capture download_to_file calls
    captured = {}

    async def fake_download(url_or_key, local_path):
        captured["url"] = url_or_key
        captured["path"] = local_path
        # Simulate writing the file so subsequent code can read it
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(b"FAKE_MP4")

    builder.object_store.download_to_file = fake_download

    await builder._fetch_chapter_video(str(tmp_path), "episode_videos/p/ep1/compose.mp4")

    assert captured["url"] == "episode_videos/p/ep1/compose.mp4"
    assert captured["path"] == os.path.join(str(tmp_path), "chapter_video", "compose.mp4")
    # Directory should have been created
    assert os.path.isdir(os.path.join(str(tmp_path), "chapter_video"))
    # File should exist with the bytes the fake wrote
    with open(captured["path"], "rb") as f:
        assert f.read() == b"FAKE_MP4"
