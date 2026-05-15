"""Phase E: AssetLockResolver returns an empty spec without raising for empty input."""
from unittest.mock import MagicMock

from app.services.export.asset_lock_resolver import AssetLockResolver
from app.services.export.bundle_models import ChapterSnapshot
from app.schemas.bundle_manifest import AssetsLockSpec


def test_resolver_returns_empty_spec_for_empty_panel_plans():
    db = MagicMock()
    resolver = AssetLockResolver(db)

    snap = ChapterSnapshot(
        chapter_id="ch-1",
        project_id="p-1",
        title="t",
        version=1,
        panels=[],
    )
    spec = resolver.resolve(snap, [])

    assert isinstance(spec, AssetsLockSpec)
    assert spec.chapter_id == "ch-1"
    assert spec.models == []
    assert spec.loras == []
    assert spec.face_embeddings == []
    assert spec.scene_anchors == []
    assert spec.total_assets == 0
