"""Unit tests for BundleBuilder._collect_chapter_video (Phase E)."""
from unittest.mock import MagicMock

from app.services.export.bundle_builder import BundleBuilder
from app.services.export.bundle_models import (
    ChapterSnapshot,
    BundleBuildContext,
)
from app.schemas.bundle_manifest import BundleChapterVideo
from tests.unit.services.export._helpers import (
    make_chapter,
    make_compose_job,
    time_offset,
)


def _make_builder(db) -> BundleBuilder:
    ctx = BundleBuildContext(
        export_id="exp-1",
        job_id="job-1",
        chapter_id="ch-1",
    )
    return BundleBuilder(db=db, context=ctx)


def _make_snapshot(chapter_id="ch-1", project_id="p-1") -> ChapterSnapshot:
    return ChapterSnapshot(
        chapter_id=chapter_id,
        project_id=project_id,
        title="t",
        version=1,
        panels=[],
        style_profile_snapshot=None,
    )


def test_returns_none_when_no_compose_job_exists():
    chapter = make_chapter(order_index=3)
    db = MagicMock()
    # 1st query (Chapter) returns chapter; 2nd query (Job) returns []
    db.query.return_value.filter.return_value.first.return_value = chapter
    db.query.return_value.filter.return_value.all.return_value = []

    builder = _make_builder(db)
    result = builder._collect_chapter_video(_make_snapshot())

    assert result is None


def test_returns_none_when_chapter_order_index_is_none():
    chapter = make_chapter(order_index=None)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = chapter

    builder = _make_builder(db)
    result = builder._collect_chapter_video(_make_snapshot())

    assert result is None


def test_picks_latest_succeeded_compose_by_finished_at():
    chapter = make_chapter(order_index=3)
    older = make_compose_job(
        "old", "p-1", 3,
        video_url="episode_videos/p-1/ep3/old.mp4",
        finished_at=time_offset(0),
    )
    newer = make_compose_job(
        "new", "p-1", 3,
        video_url="episode_videos/p-1/ep3/new.mp4",
        finished_at=time_offset(60),
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = chapter
    db.query.return_value.filter.return_value.all.return_value = [older, newer]

    builder = _make_builder(db)
    result = builder._collect_chapter_video(_make_snapshot())

    assert result is not None
    info, video_url = result
    assert isinstance(info, BundleChapterVideo)
    assert info.source_compose_job_id == "new"
    assert video_url == "episode_videos/p-1/ep3/new.mp4"


def test_matches_only_jobs_for_correct_project_and_episode_number():
    """A compose for the same project but different episode_number must NOT match."""
    chapter = make_chapter(order_index=3, project_id="p-1")
    wrong_episode = make_compose_job("wrong", "p-1", 2, finished_at=time_offset(0))
    right = make_compose_job(
        "right", "p-1", 3,
        video_url="episode_videos/p-1/ep3/right.mp4",
        finished_at=time_offset(0),
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = chapter
    db.query.return_value.filter.return_value.all.return_value = [wrong_episode, right]

    builder = _make_builder(db)
    result = builder._collect_chapter_video(_make_snapshot())

    assert result is not None
    info, _ = result
    assert info.source_compose_job_id == "right"
