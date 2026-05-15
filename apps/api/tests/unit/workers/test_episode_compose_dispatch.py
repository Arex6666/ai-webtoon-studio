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
