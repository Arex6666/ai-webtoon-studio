"""End-to-end Phase E bundle build with in-memory SQLite + patched object_store.

Verifies the full pipeline produces a valid zip that includes the D motion-comic
MP4 when a succeeded compose job exists for the chapter's order_index, and
gracefully omits it when no compose exists.
"""
import asyncio
import io
import json
import os
import zipfile
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401 — register all models
from app.models import Chapter, Panel, LayerPack, Job, Project
from app.models.base import Base
from app.schemas.bundle_manifest import BundleManifest
from app.services.export.bundle_builder import BundleBuilder
from app.services.export.bundle_models import BundleBuildContext


def _drive_build(builder: BundleBuilder):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(builder.build())
    finally:
        loop.close()


def _seed_chapter(db, chapter_id="ch-1", project_id="p-1", order_index=3):
    """Insert a minimal project + chapter + one panel + one LayerPack."""
    # Create project
    project = Project(id=project_id, name="Test Project")
    db.add(project)

    # Chapter
    chapter = Chapter(
        id=chapter_id,
        project_id=project_id,
        title="Test Chapter",
        order_index=order_index,
        layout_json={},
        status="storyboarded",
    )
    db.add(chapter)

    # Panel
    panel = Panel(
        id="panel-1",
        chapter_id=chapter_id,
        order_index=0,
        spec_json={"shot": {"durationSec": 3.0}},
        render_status="completed",
        qa_score=0.85,
    )
    db.add(panel)

    # LayerPack
    layerpack = LayerPack(
        id="lp-1",
        panel_id="panel-1",
        status="completed",
        file_full="images/panel1/full.png",
        full_url="images/panel1/full.png",
    )
    db.add(layerpack)
    panel.active_layer_pack_id = "lp-1"

    db.commit()
    return chapter, panel, layerpack


def _seed_compose_job(db, project_id="p-1", episode_number=3):
    """Insert a succeeded episode_video_compose Job matching the chapter."""
    job = Job(
        id="comp-1",
        type="episode_video_compose",
        project_id=project_id,
        provider="ffmpeg",
        status="succeeded",
        progress=1.0,
        finished_at=datetime.utcnow(),
        inputs_json={"episode_number": episode_number, "expected_clip_count": 3},
        outputs_json={
            "video_url": "episode_videos/p-1/ep3/compose_comp-1.mp4",
            "duration_sec": 12.0,
            "clip_count": 3,
            "size_bytes": 1024,
        },
    )
    db.add(job)
    db.commit()
    return job


def _make_in_memory_object_store(in_memory: dict):
    """Build a MagicMock object_store that uses in_memory as backing storage."""
    store = MagicMock()

    async def fake_download_to_file(url_or_key, local_path):
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        data = in_memory.get(url_or_key, b"FAKE_BYTES_FOR_" + url_or_key.encode())
        with open(local_path, "wb") as f:
            f.write(data)

    async def fake_upload_file(local_path, target_key, content_type=None):
        with open(local_path, "rb") as f:
            in_memory[target_key] = f.read()
        return f"http://test/{target_key}"

    store.download_to_file = fake_download_to_file
    store.upload_file = fake_upload_file
    return store


def test_e2e_bundle_includes_chapter_video_when_compose_exists(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    chapter, panel, layerpack = _seed_chapter(db, order_index=3)
    _seed_compose_job(db, episode_number=3)

    in_memory = {
        "images/panel1/full.png": b"FAKE_PNG_BYTES",
        "episode_videos/p-1/ep3/compose_comp-1.mp4": b"FAKE_COMPOSE_MP4",
    }
    object_store = _make_in_memory_object_store(in_memory)

    ctx = BundleBuildContext(
        export_id="exp-1",
        job_id="job-1",
        chapter_id=chapter.id,
    )
    builder = BundleBuilder(db=db, context=ctx)
    builder.object_store = object_store

    result = _drive_build(builder)

    assert result.success is True, f"Build failed: {result.error_message}"

    # Find the uploaded zip in in_memory
    zip_keys = [k for k in in_memory if k.endswith(".zip")]
    assert len(zip_keys) == 1
    zip_bytes = in_memory[zip_keys[0]]

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        # Required root files
        assert "manifest.json" in names
        assert "chapter.json" in names
        assert "assets.json" in names
        assert "provenance/jobs.json" in names
        # Phase E addition
        assert "chapter_video/compose.mp4" in names
        assert zf.read("chapter_video/compose.mp4") == b"FAKE_COMPOSE_MP4"
        # Manifest parses with chapter_video set
        manifest_data = json.loads(zf.read("manifest.json"))
        manifest = BundleManifest(**manifest_data)
        assert manifest.chapter_video is not None
        assert manifest.chapter_video.source_compose_job_id == "comp-1"
        assert manifest.chapter_video.path == "chapter_video/compose.mp4"

    db.close()


def test_e2e_bundle_omits_chapter_video_when_no_compose(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    chapter, panel, layerpack = _seed_chapter(db, order_index=3)
    # NO compose job inserted

    in_memory = {"images/panel1/full.png": b"FAKE_PNG_BYTES"}
    object_store = _make_in_memory_object_store(in_memory)

    ctx = BundleBuildContext(
        export_id="exp-2",
        job_id="job-2",
        chapter_id=chapter.id,
    )
    builder = BundleBuilder(db=db, context=ctx)
    builder.object_store = object_store

    result = _drive_build(builder)

    assert result.success is True

    zip_keys = [k for k in in_memory if k.endswith(".zip")]
    assert len(zip_keys) == 1
    zip_bytes = in_memory[zip_keys[0]]

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        # chapter_video MUST be absent
        assert not any(n.startswith("chapter_video/") for n in names)
        # Manifest still parses; chapter_video is None
        manifest_data = json.loads(zf.read("manifest.json"))
        manifest = BundleManifest(**manifest_data)
        assert manifest.chapter_video is None

    db.close()
