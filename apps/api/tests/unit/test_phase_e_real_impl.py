"""Static-source regression: Phase E real implementations are live (not stubbed out)."""
import inspect

from app.services.export import bundle_builder
from app.schemas.bundle_manifest import BundleManifest


def test_bundle_builder_passes_assets_lock_to_write_root():
    src = inspect.getsource(bundle_builder.BundleBuilder.build)
    assert "assets_lock=" in src, \
        "BundleBuilder.build() no longer passes assets_lock= — Phase E bug fix regressed"


def test_bundle_builder_passes_provenance_jobs_to_write_root():
    src = inspect.getsource(bundle_builder.BundleBuilder.build)
    assert "provenance_jobs=" in src, \
        "BundleBuilder.build() no longer passes provenance_jobs= — Phase E bug fix regressed"


def test_bundle_builder_calls_gate_validate_or_raise():
    src = inspect.getsource(bundle_builder.BundleBuilder.build)
    assert "validate_or_raise" in src, \
        "BundleBuilder.build() no longer calls the export gate — Phase E bug fix regressed"


def test_bundle_builder_has_collect_chapter_video_helper():
    assert hasattr(bundle_builder.BundleBuilder, "_collect_chapter_video"), \
        "BundleBuilder._collect_chapter_video missing — Phase E D integration regressed"


def test_bundle_builder_has_fetch_chapter_video_helper():
    assert hasattr(bundle_builder.BundleBuilder, "_fetch_chapter_video"), \
        "BundleBuilder._fetch_chapter_video missing — Phase E D integration regressed"


def test_manifest_has_chapter_video_field():
    assert "chapter_video" in BundleManifest.model_fields, \
        "BundleManifest.chapter_video field missing — Phase E schema regressed"
