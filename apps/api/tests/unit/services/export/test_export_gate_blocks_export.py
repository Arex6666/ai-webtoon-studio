"""Phase E: confirm ExportGate.validate_or_raise() surfaces as BundleBuildResult(success=False, error_code='GATE_REJECTED')."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.export.bundle_builder import BundleBuilder
from app.services.export.bundle_models import (
    BundleBuildContext,
    ChapterSnapshot,
)
from app.services.export.bundle_errors import GateRejectedError


def _drive_build(builder: BundleBuilder):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(builder.build())
    finally:
        loop.close()


def _make_builder_with_stubs() -> BundleBuilder:
    ctx = BundleBuildContext(
        export_id="exp-1",
        job_id="job-1",
        chapter_id="ch-1",
    )
    db = MagicMock()
    builder = BundleBuilder(db=db, context=ctx)
    builder.object_store = MagicMock()
    snap = ChapterSnapshot(
        chapter_id="ch-1", project_id="p-1", title="t", version=1, panels=[],
    )
    builder.collect_chapter_snapshot = MagicMock(return_value=snap)
    builder.resolve_panel_artifacts = MagicMock()
    builder.fetch_files_to_staging = AsyncMock()
    builder.write_panel_folder = MagicMock()
    builder.upload_panel_previews = AsyncMock()
    builder.write_bundle_root_files = MagicMock()
    builder.zip_and_upload = AsyncMock(return_value=("x", "y", 1))
    return builder


def test_gate_failure_returns_result_with_error_code_GATE_REJECTED():
    builder = _make_builder_with_stubs()
    gate_instance = MagicMock()
    gate_instance.validate_or_raise.side_effect = GateRejectedError(
        reason="Missing required files: ['0001']",
        gate_result={"missing_required": ["0001"]},
    )

    with patch("app.services.export.bundle_builder.AssetLockResolver"), \
         patch("app.services.export.bundle_builder.ProvenanceCollector"), \
         patch.object(builder, "_collect_chapter_video", return_value=None), \
         patch("app.services.export.bundle_builder.ExportGate", return_value=gate_instance):
        result = _drive_build(builder)

    assert result.success is False
    assert result.error_code == "GATE_REJECTED"
    assert "Missing required files" in result.error_message
    # write_bundle_root_files should NOT have been called after gate rejection
    builder.write_bundle_root_files.assert_not_called()


def test_gate_passes_when_all_panels_have_full_image():
    """Happy path: gate passes → build proceeds to write_bundle_root_files."""
    builder = _make_builder_with_stubs()
    gate_instance = MagicMock()
    # validate_or_raise returns silently (no exception) → gate passed
    gate_instance.validate_or_raise.return_value = MagicMock(passed=True)

    with patch("app.services.export.bundle_builder.AssetLockResolver"), \
         patch("app.services.export.bundle_builder.ProvenanceCollector"), \
         patch.object(builder, "_collect_chapter_video", return_value=None), \
         patch("app.services.export.bundle_builder.ExportGate", return_value=gate_instance):
        result = _drive_build(builder)

    assert result.success is True
    builder.write_bundle_root_files.assert_called_once()
