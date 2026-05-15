"""Phase E bug-fix tests: build() must wire AssetLockResolver / ProvenanceCollector /
ExportGate / chapter video into write_bundle_root_files."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.export.bundle_builder import BundleBuilder
from app.services.export.bundle_models import (
    BundleBuildContext,
    ChapterSnapshot,
    PanelArtifactPlan,
)


def _drive_build(builder: BundleBuilder):
    """Run the async build() to completion in a fresh loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(builder.build())
    finally:
        loop.close()


def _make_builder_with_stubs(tmp_path):
    """Construct a BundleBuilder whose I/O is fully stubbed.

    All the heavy steps (collect_chapter_snapshot, resolve_panel_artifacts,
    fetch_files_to_staging, write_panel_folder, upload_panel_previews,
    write_bundle_root_files, zip_and_upload) are patched on the instance so we
    can assert what build() passes to them without spinning up real DB/MinIO.
    """
    ctx = BundleBuildContext(
        export_id="exp-1",
        job_id="job-1",
        chapter_id="ch-1",
    )
    db = MagicMock()
    builder = BundleBuilder(db=db, context=ctx)
    builder.object_store = MagicMock()

    # Step 1
    snap = ChapterSnapshot(
        chapter_id="ch-1", project_id="p-1", title="t", version=1, panels=[],
    )
    builder.collect_chapter_snapshot = MagicMock(return_value=snap)

    # Steps 2-4 are no-ops — empty panel list
    builder.resolve_panel_artifacts = MagicMock()
    builder.fetch_files_to_staging = AsyncMock()
    builder.write_panel_folder = MagicMock()
    builder.upload_panel_previews = AsyncMock()

    # Step 5: capture kwargs
    builder.write_bundle_root_files = MagicMock(return_value=MagicMock(
        qa_summary=None,
    ))

    # Step 6
    builder.zip_and_upload = AsyncMock(return_value=("http://x/bundle.zip", "http://x/m.json", 1234))

    return builder


def test_build_calls_write_bundle_root_files_with_assets_lock(tmp_path, monkeypatch):
    builder = _make_builder_with_stubs(tmp_path)

    fake_assets = MagicMock()
    fake_provenance = MagicMock()

    with patch("app.services.export.bundle_builder.AssetLockResolver") as fake_resolver_cls, \
         patch("app.services.export.bundle_builder.ProvenanceCollector") as fake_collector_cls, \
         patch.object(builder, "_collect_chapter_video", return_value=None), \
         patch("app.services.export.bundle_builder.ExportGate"):
        fake_resolver_cls.return_value.resolve.return_value = fake_assets
        fake_collector_cls.return_value.collect.return_value = fake_provenance

        _drive_build(builder)

    call = builder.write_bundle_root_files.call_args
    assert call.kwargs.get("assets_lock") is fake_assets


def test_build_calls_write_bundle_root_files_with_provenance_jobs(tmp_path):
    builder = _make_builder_with_stubs(tmp_path)

    fake_assets = MagicMock()
    fake_provenance = MagicMock()

    with patch("app.services.export.bundle_builder.AssetLockResolver") as fake_resolver_cls, \
         patch("app.services.export.bundle_builder.ProvenanceCollector") as fake_collector_cls, \
         patch.object(builder, "_collect_chapter_video", return_value=None), \
         patch("app.services.export.bundle_builder.ExportGate"):
        fake_resolver_cls.return_value.resolve.return_value = fake_assets
        fake_collector_cls.return_value.collect.return_value = fake_provenance

        _drive_build(builder)

    call = builder.write_bundle_root_files.call_args
    assert call.kwargs.get("provenance_jobs") is fake_provenance


def test_build_calls_gate_validate_or_raise_before_root_files():
    builder = _make_builder_with_stubs(None)

    gate_instance = MagicMock()

    with patch("app.services.export.bundle_builder.AssetLockResolver"), \
         patch("app.services.export.bundle_builder.ProvenanceCollector"), \
         patch.object(builder, "_collect_chapter_video", return_value=None), \
         patch("app.services.export.bundle_builder.ExportGate", return_value=gate_instance):

        _drive_build(builder)

    gate_instance.validate_or_raise.assert_called_once()
    # And it must have been called before write_bundle_root_files
    # (MagicMock records call order; check both were called and gate first)
    assert gate_instance.validate_or_raise.call_count == 1
    assert builder.write_bundle_root_files.call_count == 1


def test_build_passes_chapter_video_kwarg_when_present():
    builder = _make_builder_with_stubs(None)

    from app.schemas.bundle_manifest import BundleChapterVideo
    fake_video_info = BundleChapterVideo(
        path="chapter_video/compose.mp4",
        source_compose_job_id="comp-1",
    )

    with patch("app.services.export.bundle_builder.AssetLockResolver"), \
         patch("app.services.export.bundle_builder.ProvenanceCollector"), \
         patch.object(builder, "_collect_chapter_video", return_value=(fake_video_info, "images/c.mp4")), \
         patch.object(builder, "_fetch_chapter_video", new=AsyncMock()), \
         patch("app.services.export.bundle_builder.ExportGate"):

        _drive_build(builder)

    call = builder.write_bundle_root_files.call_args
    assert call.kwargs.get("chapter_video") is fake_video_info


def test_build_skips_chapter_video_when_download_fails():
    """Silent-skip: if _fetch_chapter_video raises, build() must still succeed
    and chapter_video kwarg must be None."""
    builder = _make_builder_with_stubs(None)

    from app.schemas.bundle_manifest import BundleChapterVideo
    fake_video_info = BundleChapterVideo(
        path="chapter_video/compose.mp4",
        source_compose_job_id="comp-1",
    )

    async def boom(*a, **kw):
        raise RuntimeError("MinIO unreachable")

    with patch("app.services.export.bundle_builder.AssetLockResolver"), \
         patch("app.services.export.bundle_builder.ProvenanceCollector"), \
         patch.object(builder, "_collect_chapter_video", return_value=(fake_video_info, "images/c.mp4")), \
         patch.object(builder, "_fetch_chapter_video", new=AsyncMock(side_effect=RuntimeError("boom"))), \
         patch("app.services.export.bundle_builder.ExportGate"):

        result = _drive_build(builder)

    assert result.success is True
    call = builder.write_bundle_root_files.call_args
    assert call.kwargs.get("chapter_video") is None
