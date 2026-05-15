"""Phase E: BundleManifest.chapter_video is an optional additive field."""
from app.schemas.bundle_manifest import (
    BundleChapterVideo,
    BundleManifest,
    BundleChapterInfo,
    BundleProvenance,
)


def _minimal_manifest_kwargs():
    return dict(
        bundle_id="bundle-test",
        chapter=BundleChapterInfo(
            chapter_id="ch-1",
            chapter_title="t",
            project_id="p-1",
            panel_count=0,
        ),
        provenance=BundleProvenance(generated_at="2026-05-11T00:00:00Z"),
    )


def test_manifest_serialises_chapter_video_when_present():
    video = BundleChapterVideo(
        path="chapter_video/compose.mp4",
        source_compose_job_id="comp-1",
        duration_sec=12.0,
        clip_count=3,
        size_bytes=1024,
    )
    manifest = BundleManifest(**_minimal_manifest_kwargs(), chapter_video=video)
    data = manifest.model_dump()
    assert data["chapter_video"]["source_compose_job_id"] == "comp-1"
    assert data["chapter_video"]["path"] == "chapter_video/compose.mp4"
    assert data["chapter_video"]["clip_count"] == 3


def test_manifest_omits_or_nulls_chapter_video_when_none():
    """When no compose exists, chapter_video should serialise to null (Pydantic
    default with model_dump). Either absence or explicit null is acceptable
    for a backward-compatible additive field."""
    manifest = BundleManifest(**_minimal_manifest_kwargs())
    data = manifest.model_dump()
    # Field is present but None — that's how Pydantic handles Optional defaults
    assert data.get("chapter_video") is None
