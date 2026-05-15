"""Unit tests for compose dispatch helper (Phase D)."""
import pytest
from unittest.mock import MagicMock, patch

from app.services.video.compose_dispatch import _maybe_enqueue_episode_compose
from tests.unit.workers._episode_helpers import make_episode_video_job, make_compose_job


@pytest.mark.asyncio
async def test_dispatch_all_succeeded_enqueues_compose():
    siblings = [
        make_episode_video_job("c0", "p1", 1, 0, status="succeeded"),
        make_episode_video_job("c1", "p1", 1, 1, status="succeeded"),
        make_episode_video_job("c2", "p1", 1, 2, status="succeeded"),
    ]
    db = MagicMock()
    db.query.return_value.filter.return_value.all.side_effect = [siblings, []]
    db.add = MagicMock()
    db.commit = MagicMock()

    with patch("app.services.video.compose_dispatch.execute_episode_compose") as fake_task:
        fake_task.delay = MagicMock()
        result = _maybe_enqueue_episode_compose(db, "p1", 1)

    assert isinstance(result, str)
    assert len(result) == 36  # UUID
    added_job = db.add.call_args.args[0]
    assert added_job.type == "episode_video_compose"
    assert added_job.project_id == "p1"
    assert added_job.provider == "ffmpeg"
    assert added_job.inputs_json == {"episode_number": 1, "expected_clip_count": 3}
    db.commit.assert_called_once()
    fake_task.delay.assert_called_once_with(result)


@pytest.mark.asyncio
async def test_dispatch_no_siblings_returns_none():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    db.add = MagicMock()

    result = _maybe_enqueue_episode_compose(db, "p1", 1)

    assert result is None
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_pending_sibling_skips():
    siblings = [
        make_episode_video_job("c0", "p1", 1, 0, status="succeeded"),
        make_episode_video_job("c1", "p1", 1, 1, status="running"),
    ]
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = siblings
    db.add = MagicMock()

    result = _maybe_enqueue_episode_compose(db, "p1", 1)

    assert result is None
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_failed_sibling_skips():
    siblings = [
        make_episode_video_job("c0", "p1", 1, 0, status="succeeded"),
        make_episode_video_job("c1", "p1", 1, 1, status="failed"),
    ]
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = siblings
    db.add = MagicMock()

    result = _maybe_enqueue_episode_compose(db, "p1", 1)

    assert result is None
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_filters_by_episode_number():
    """Siblings from other episodes must not influence the decision."""
    siblings = [
        make_episode_video_job("c0", "p1", 1, 0, status="succeeded"),
        make_episode_video_job("c1", "p1", 2, 0, status="failed"),
    ]
    db = MagicMock()
    db.query.return_value.filter.return_value.all.side_effect = [siblings, []]
    db.add = MagicMock()

    with patch("app.services.video.compose_dispatch.execute_episode_compose") as fake_task:
        fake_task.delay = MagicMock()
        result = _maybe_enqueue_episode_compose(db, "p1", 1)

    assert result is not None  # ep 1 alone has 1 succeeded → enqueues


@pytest.mark.asyncio
async def test_dispatch_existing_queued_compose_dedups():
    siblings = [
        make_episode_video_job("c0", "p1", 1, 0, status="succeeded"),
    ]
    existing_compose = [make_compose_job("comp0", "p1", 1, status="queued")]
    db = MagicMock()
    db.query.return_value.filter.return_value.all.side_effect = [siblings, existing_compose]
    db.add = MagicMock()

    result = _maybe_enqueue_episode_compose(db, "p1", 1)

    assert result is None
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_existing_running_compose_dedups():
    siblings = [make_episode_video_job("c0", "p1", 1, 0, status="succeeded")]
    existing = [make_compose_job("comp0", "p1", 1, status="running")]
    db = MagicMock()
    db.query.return_value.filter.return_value.all.side_effect = [siblings, existing]
    db.add = MagicMock()

    result = _maybe_enqueue_episode_compose(db, "p1", 1)

    assert result is None


@pytest.mark.asyncio
async def test_dispatch_existing_succeeded_compose_dedups():
    siblings = [make_episode_video_job("c0", "p1", 1, 0, status="succeeded")]
    existing = [make_compose_job("comp0", "p1", 1, status="succeeded")]
    db = MagicMock()
    db.query.return_value.filter.return_value.all.side_effect = [siblings, existing]
    db.add = MagicMock()

    result = _maybe_enqueue_episode_compose(db, "p1", 1)

    assert result is None


@pytest.mark.asyncio
async def test_dispatch_failed_compose_does_not_dedup():
    """A prior failed compose must NOT block re-trigger when clips are still all good."""
    siblings = [make_episode_video_job("c0", "p1", 1, 0, status="succeeded")]
    # existing_compose list is empty because the helper's status filter excludes 'failed'
    db = MagicMock()
    db.query.return_value.filter.return_value.all.side_effect = [siblings, []]
    db.add = MagicMock()

    with patch("app.services.video.compose_dispatch.execute_episode_compose") as fake_task:
        fake_task.delay = MagicMock()
        result = _maybe_enqueue_episode_compose(db, "p1", 1)

    assert result is not None  # new enqueue allowed


@pytest.mark.asyncio
async def test_dispatch_integrity_error_returns_none():
    """Race: another worker inserted first. Helper must roll back and return None."""
    from sqlalchemy.exc import IntegrityError

    siblings = [make_episode_video_job("c0", "p1", 1, 0, status="succeeded")]
    db = MagicMock()
    db.query.return_value.filter.return_value.all.side_effect = [siblings, []]
    db.add = MagicMock()
    db.commit = MagicMock(side_effect=IntegrityError("test", {}, Exception()))
    db.rollback = MagicMock()

    with patch("app.services.video.compose_dispatch.execute_episode_compose") as fake_task:
        fake_task.delay = MagicMock()
        result = _maybe_enqueue_episode_compose(db, "p1", 1)

    assert result is None
    db.rollback.assert_called_once()
    fake_task.delay.assert_not_called()
