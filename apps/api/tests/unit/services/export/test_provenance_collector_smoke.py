"""Phase E: ProvenanceCollector returns an empty spec without raising when no jobs exist."""
from unittest.mock import MagicMock

from app.services.export.provenance_collector import ProvenanceCollector
from app.services.export.bundle_models import ChapterSnapshot
from app.schemas.bundle_manifest import ProvenanceJobsSpec


def test_collector_returns_empty_spec_when_no_jobs():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    collector = ProvenanceCollector(db)

    snap = ChapterSnapshot(
        chapter_id="ch-1",
        project_id="p-1",
        title="t",
        version=1,
        panels=[],
    )
    spec = collector.collect(snap, [])

    assert isinstance(spec, ProvenanceJobsSpec)
    assert spec.chapter_id == "ch-1"
    assert spec.jobs == []
    assert spec.total_jobs == 0
