# D — Motion-Comic Video Compose Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stitch the per-panel Doubao Seedance video clips already produced by `episode_video_worker` into one MP4 per episode, with ffmpeg `concat` running in a new Celery worker auto-triggered when all sibling clips have succeeded.

**Architecture:** A new `episode_compose_worker` Celery task downloads sibling clips from MinIO, runs `ffmpeg -f concat -c copy`, uploads the result back to MinIO, and emits compose WebSocket events. Auto-trigger lives in `episode_video_worker` and delegates to a new unit-testable `compose_dispatch._maybe_enqueue_episode_compose` helper. Dedup is enforced via a partial unique index on `jobs` (Postgres) plus an in-Python pre-check for SQLite compatibility. Source clip job IDs are resolved at compose-run time (latest succeeded per `image_index`) so a clip retried after compose enqueue still flows in.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, Alembic, Celery, ffmpeg (subprocess), pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-05-11-d-motion-comic-video-compose-design.md`

---

## Pre-flight

- [ ] **Step 1: Confirm current branch**

```bash
cd D:/ai-webtoon-studio
git rev-parse --abbrev-ref HEAD
```

Expected: `feat/d-motion-comic-compose`. If not, `git checkout feat/d-motion-comic-compose`.

- [ ] **Step 2: Confirm the spec is in place**

```bash
ls docs/superpowers/specs/2026-05-11-d-motion-comic-video-compose-design.md
```

Expected: file exists.

- [ ] **Step 3: Confirm Python interpreter**

```bash
py -3.13 -c "import fastapi, sqlalchemy, celery; print('deps OK')"
```

Expected: `deps OK`. (Per memory: `py -3.13` is the project interpreter.)

- [ ] **Step 4: Confirm current head revision**

```bash
cd apps/api
py -3.13 -m alembic heads
```

Expected: includes `022_unified_agent_runner`. The new D migration revises from this.

---

## Group 1: Dispatch helper

### Task 1.1: Test scaffolding — shared fixtures

**Files:**
- Create: `apps/api/tests/unit/workers/_episode_helpers.py`

- [ ] **Step 1: Write the helper module**

```python
"""Shared fixtures for episode_compose unit tests (Phase D).

Provides factories for Job rows in canonical states so each test can describe
its scenario in one or two lines.
"""
from datetime import datetime, timedelta
from typing import Optional

from app.models import Job


def make_episode_video_job(
    job_id: str,
    project_id: str,
    episode_number: int,
    image_index: int,
    status: str = "succeeded",
    video_url: Optional[str] = "images/clip.mp4",
    finished_at: Optional[datetime] = None,
) -> Job:
    """Build an episode_video Job row in any lifecycle state."""
    return Job(
        id=job_id,
        type="episode_video",
        project_id=project_id,
        status=status,
        progress=1.0 if status == "succeeded" else 0.0,
        finished_at=finished_at or (datetime.utcnow() if status == "succeeded" else None),
        inputs_json={
            "episode_number": episode_number,
            "image_index": image_index,
            "image_url": f"images/panel_{image_index}.png",
        },
        outputs_json=(
            {"video_url": video_url, "duration_sec": 5.0}
            if status == "succeeded" and video_url else None
        ),
    )


def make_compose_job(
    job_id: str,
    project_id: str,
    episode_number: int,
    status: str = "queued",
    expected_clip_count: int = 3,
) -> Job:
    return Job(
        id=job_id,
        type="episode_video_compose",
        project_id=project_id,
        provider="ffmpeg",
        status=status,
        inputs_json={
            "episode_number": episode_number,
            "expected_clip_count": expected_clip_count,
        },
    )


def time_offset(seconds: int) -> datetime:
    """Helper to build distinct finished_at values for ordering tests."""
    return datetime.utcnow() + timedelta(seconds=seconds)
```

- [ ] **Step 2: Confirm no test runs against this file**

It's a helper, not a test file. Pytest only collects `test_*` and `*_test.py`. The leading underscore in `_episode_helpers.py` also signals "private."

- [ ] **Step 3: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/tests/unit/workers/_episode_helpers.py
git commit -m "test(api): episode compose test helpers (D)"
```

### Task 1.2: `_maybe_enqueue_episode_compose` happy path

**Files:**
- Create: `apps/api/app/services/video/compose_dispatch.py`
- Test: `apps/api/tests/unit/workers/test_episode_compose_dispatch.py` (new)

- [ ] **Step 1: Write the failing test**

`apps/api/tests/unit/workers/test_episode_compose_dispatch.py`:

```python
"""Unit tests for compose dispatch helper (Phase D)."""
import pytest
from unittest.mock import MagicMock, patch

from app.services.video.compose_dispatch import _maybe_enqueue_episode_compose
from tests.unit.workers._episode_helpers import make_episode_video_job, make_compose_job


def _fake_db_with_jobs(jobs):
    """Return a MagicMock db session whose .query(Job).filter(...).all() returns `jobs`."""
    db = MagicMock()
    # Make .query(...).filter(...).all() yield the full list — tests then assert
    # the helper's in-Python filtering of episode_number / status.
    db.query.return_value.filter.return_value.all.return_value = jobs
    db.add = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    return db


@pytest.mark.asyncio
async def test_dispatch_all_succeeded_enqueues_compose():
    siblings = [
        make_episode_video_job("c0", "p1", 1, 0, status="succeeded"),
        make_episode_video_job("c1", "p1", 1, 1, status="succeeded"),
        make_episode_video_job("c2", "p1", 1, 2, status="succeeded"),
    ]
    db = MagicMock()
    # Helper makes TWO queries: siblings then existing composes. Order matters.
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
```

- [ ] **Step 2: Run — expect ImportError**

```bash
cd D:/ai-webtoon-studio/apps/api
py -3.13 -m pytest tests/unit/workers/test_episode_compose_dispatch.py -v
```

Expected: FAIL with `ImportError: cannot import name '_maybe_enqueue_episode_compose'`.

- [ ] **Step 3: Implement minimal helper**

`apps/api/app/services/video/compose_dispatch.py` (new):

```python
"""Phase D: compose dispatch — decides when to enqueue an episode_video_compose job.

Called from episode_video_worker on the success path of each per-panel clip.
Lives in services/ (not workers/) so it stays unit-testable without Celery.
"""
import logging
import uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError

from app.models import Job
from app.workers.episode_compose_worker import execute_episode_compose

logger = logging.getLogger(__name__)


def _maybe_enqueue_episode_compose(
    db,
    project_id: str,
    episode_number: int,
) -> Optional[str]:
    """Check sibling state; enqueue compose if all clips succeeded.

    Returns new compose job_id on enqueue, None otherwise.
    Strict policy: every sibling clip must be 'succeeded' before compose fires.
    """
    siblings_query = (
        db.query(Job)
        .filter(
            Job.type == "episode_video",
            Job.project_id == project_id,
        )
        .all()
    )
    siblings = [
        j for j in siblings_query
        if (j.inputs_json or {}).get("episode_number") == episode_number
    ]
    if not siblings:
        return None

    if any(j.status != "succeeded" for j in siblings):
        return None

    existing_query = (
        db.query(Job)
        .filter(
            Job.type == "episode_video_compose",
            Job.project_id == project_id,
            Job.status.in_(["queued", "running", "succeeded"]),
        )
        .all()
    )
    existing = [
        j for j in existing_query
        if (j.inputs_json or {}).get("episode_number") == episode_number
    ]
    if existing:
        return None

    compose_job_id = str(uuid.uuid4())
    job = Job(
        id=compose_job_id,
        type="episode_video_compose",
        provider="ffmpeg",
        project_id=project_id,
        status="queued",
        inputs_json={
            "episode_number": episode_number,
            "expected_clip_count": len(siblings),
        },
    )
    try:
        db.add(job)
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.info(
            "[ComposeDispatch] dedup race lost for project=%s ep=%s",
            project_id, episode_number,
        )
        return None

    execute_episode_compose.delay(compose_job_id)
    logger.info(
        "[ComposeDispatch] enqueued compose %s for project=%s ep=%s clips=%d",
        compose_job_id, project_id, episode_number, len(siblings),
    )
    return compose_job_id
```

This import will fail at module load until Task 3.2 creates the worker. To unblock the test, we stub the worker module first:

`apps/api/app/workers/episode_compose_worker.py` (new — minimal stub):

```python
"""Phase D: episode compose worker (stub, full impl in Task 3.2)."""
from celery import shared_task


@shared_task(bind=True, name="app.workers.episode_compose_worker.execute_episode_compose")
def execute_episode_compose(self, job_id: str):
    raise NotImplementedError("Filled in by Task 3.2")
```

- [ ] **Step 4: Run — expect pass**

```bash
py -3.13 -m pytest tests/unit/workers/test_episode_compose_dispatch.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/app/services/video/compose_dispatch.py \
        apps/api/app/workers/episode_compose_worker.py \
        apps/api/tests/unit/workers/test_episode_compose_dispatch.py
git commit -m "feat(api): _maybe_enqueue_episode_compose helper + worker stub (D)"
```

### Task 1.3: Skip cases — pending / failed sibling / no siblings

**Files:**
- Test: extend `apps/api/tests/unit/workers/test_episode_compose_dispatch.py`

- [ ] **Step 1: Append three failing tests**

```python
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
        make_episode_video_job("c1", "p1", 1, 1, status="running"),  # not done
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
        make_episode_video_job("c1", "p1", 1, 1, status="failed"),  # strict policy
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
        make_episode_video_job("c1", "p1", 2, 0, status="failed"),  # other ep
    ]
    db = MagicMock()
    db.query.return_value.filter.return_value.all.side_effect = [siblings, []]
    db.add = MagicMock()

    with patch("app.services.video.compose_dispatch.execute_episode_compose") as fake_task:
        fake_task.delay = MagicMock()
        result = _maybe_enqueue_episode_compose(db, "p1", 1)

    assert result is not None  # ep 1 alone has 1 succeeded → enqueues
```

- [ ] **Step 2: Run — expect 4 pass total now (1 from 1.2 + 4 new = 5)**

Wait — the existing test from 1.2 is one. Plus 4 new. = 5 total.

```bash
py -3.13 -m pytest tests/unit/workers/test_episode_compose_dispatch.py -v
```

Expected: 5 passed.

- [ ] **Step 3: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/tests/unit/workers/test_episode_compose_dispatch.py
git commit -m "test(api): compose dispatch skip cases (D)"
```

### Task 1.4: Dedup — existing compose blocks new enqueue

**Files:**
- Test: extend `apps/api/tests/unit/workers/test_episode_compose_dispatch.py`

- [ ] **Step 1: Append dedup tests**

```python
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
```

- [ ] **Step 2: Run — expect 10 pass (5 prior + 5 new)**

```bash
py -3.13 -m pytest tests/unit/workers/test_episode_compose_dispatch.py -v
```

Expected: 10 passed.

- [ ] **Step 3: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/tests/unit/workers/test_episode_compose_dispatch.py
git commit -m "test(api): compose dispatch dedup + race handling (D)"
```

---

## Group 2: Migration + dedup unique index

### Task 2.1: Alembic migration — partial unique index

**Files:**
- Create: `apps/api/migrations/versions/023_episode_compose_dedup_index.py`

- [ ] **Step 1: Write the migration**

```python
"""023 episode_video_compose dedup index — Phase D

Adds a partial unique index on (project_id, inputs_json->>'episode_number')
where type='episode_video_compose' and status in ('queued','running','succeeded').
Failed rows are excluded so retries can create new compose jobs.

Postgres-only enforcement; SQLite test path uses an in-Python pre-check inside
_maybe_enqueue_episode_compose. Detect dialect to skip the index on SQLite,
which does not support partial indexes with JSON expressions.

Revision ID: 023_episode_compose_dedup
Revises: 022_unified_agent_runner
Create Date: 2026-05-11
"""
from alembic import op


revision = "023_episode_compose_dedup"
down_revision = "022_unified_agent_runner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite: no-op. The in-Python pre-check in compose_dispatch handles dedup.
        return
    op.execute(
        """
        CREATE UNIQUE INDEX uq_episode_compose_inflight
        ON jobs (project_id, ((inputs_json->>'episode_number')::int))
        WHERE type = 'episode_video_compose'
          AND status IN ('queued', 'running', 'succeeded')
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS uq_episode_compose_inflight")
```

- [ ] **Step 2: Apply migration locally**

```bash
cd D:/ai-webtoon-studio/apps/api
py -3.13 -m alembic upgrade head
```

Expected: clean output, no errors. (SQLite path is a no-op.)

- [ ] **Step 3: Verify head**

```bash
py -3.13 -m alembic heads
```

Expected: `023_episode_compose_dedup (head)`.

- [ ] **Step 4: Verify downgrade is reversible**

```bash
py -3.13 -m alembic downgrade -1
py -3.13 -m alembic upgrade head
```

Expected: both clean. Leaves DB at head.

- [ ] **Step 5: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/migrations/versions/023_episode_compose_dedup_index.py
git commit -m "feat(api): migration — episode_video_compose dedup unique index (D)"
```

---

## Group 3: Compose worker

### Task 3.1: Worker happy path — 3 clips → ffmpeg → upload

**Files:**
- Modify: `apps/api/app/workers/episode_compose_worker.py` (replace stub)
- Test: `apps/api/tests/unit/workers/test_episode_compose_worker.py` (new)

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for episode_compose_worker (Phase D)."""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.unit.workers._episode_helpers import (
    make_episode_video_job,
    make_compose_job,
    time_offset,
)


@pytest.mark.asyncio
async def test_compose_happy_path_three_clips(tmp_path, monkeypatch):
    """3 succeeded clips → download → ffmpeg concat → upload → status=succeeded."""
    # Force the worker to use tmp_path as the temp dir root (otherwise the
    # worker would create dirs under the system TEMP, harder to clean up).
    monkeypatch.setenv("EPISODE_COMPOSE_TMP_ROOT", str(tmp_path))

    project_id = "p1"
    ep_num = 1
    compose_job = make_compose_job("comp-1", project_id, ep_num, status="queued", expected_clip_count=3)
    siblings = [
        make_episode_video_job("c0", project_id, ep_num, 0, status="succeeded",
                                video_url="images/c0.mp4", finished_at=time_offset(0)),
        make_episode_video_job("c1", project_id, ep_num, 1, status="succeeded",
                                video_url="images/c1.mp4", finished_at=time_offset(1)),
        make_episode_video_job("c2", project_id, ep_num, 2, status="succeeded",
                                video_url="images/c2.mp4", finished_at=time_offset(2)),
    ]

    # The worker uses a real SessionLocal; we patch the query result instead of
    # spinning up SQLite. Two distinct queries: load Job, then siblings.
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = compose_job
    db.query.return_value.filter.return_value.all.return_value = siblings

    # Storage mocks
    fake_storage = MagicMock()
    fake_storage.download_bytes = AsyncMock(side_effect=[b"clip0", b"clip1", b"clip2"])
    fake_storage.upload_bytes = AsyncMock(return_value=None)

    # Patch subprocess.run to a fake that writes a fake output.mp4 file
    def fake_subprocess(cmd, *args, **kwargs):
        # cmd will be a list ending in output.mp4 path
        output_path = cmd[-1]
        with open(output_path, "wb") as f:
            f.write(b"fake_output_mp4_bytes")
        return MagicMock(returncode=0, stderr=b"", stdout=b"")

    with patch("app.workers.episode_compose_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_compose_worker.get_storage_client", return_value=fake_storage), \
         patch("app.workers.episode_compose_worker.subprocess.run", side_effect=fake_subprocess) as sp_mock:

        from app.workers.episode_compose_worker import _execute_compose_sync
        result = _execute_compose_sync("comp-1")

    assert result["success"] is True
    assert compose_job.status == "succeeded"
    assert compose_job.outputs_json["clip_count"] == 3
    assert compose_job.outputs_json["video_url"].startswith(f"episode_videos/{project_id}/ep{ep_num}/compose_")

    # subprocess.run called with ffmpeg concat flags
    invoked_cmd = sp_mock.call_args.args[0]
    assert invoked_cmd[0] == "ffmpeg"
    assert "-f" in invoked_cmd and "concat" in invoked_cmd
    assert "-safe" in invoked_cmd
    assert "-c" in invoked_cmd and "copy" in invoked_cmd

    # Three downloads, one upload of the stitched output
    assert fake_storage.download_bytes.await_count == 3
    fake_storage.upload_bytes.assert_awaited_once()
```

- [ ] **Step 2: Run — expect failure (NotImplementedError or AttributeError)**

```bash
cd D:/ai-webtoon-studio/apps/api
py -3.13 -m pytest tests/unit/workers/test_episode_compose_worker.py::test_compose_happy_path_three_clips -v
```

Expected: FAIL (cannot import `_execute_compose_sync` or stub raises `NotImplementedError`).

- [ ] **Step 3: Replace the worker stub with the full implementation**

`apps/api/app/workers/episode_compose_worker.py` (full replacement):

```python
"""Phase D: episode_video_compose worker.

Reads sibling episode_video Job rows, downloads succeeded clip MP4s,
stitches them with ffmpeg concat, uploads the result to MinIO, updates
the Job row, and emits compose WebSocket events.
"""
import asyncio
import logging
import os
import subprocess
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

from celery import shared_task

from app.db.database import SessionLocal
from app.models import Job
from app.core.storage import get_storage_client

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async function from sync Celery context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def _resolve_latest_succeeded_clips(db, project_id: str, episode_number: int) -> List[Job]:
    """Return one Job per image_index, picking the latest succeeded by finished_at."""
    all_succeeded = (
        db.query(Job)
        .filter(
            Job.type == "episode_video",
            Job.project_id == project_id,
            Job.status == "succeeded",
        )
        .all()
    )
    matching = [
        j for j in all_succeeded
        if (j.inputs_json or {}).get("episode_number") == episode_number
    ]
    # Group by image_index, keep latest finished_at
    latest_by_index: dict[int, Job] = {}
    for j in matching:
        idx = (j.inputs_json or {}).get("image_index")
        if idx is None:
            continue
        prior = latest_by_index.get(idx)
        if prior is None or (j.finished_at or datetime.min) > (prior.finished_at or datetime.min):
            latest_by_index[idx] = j
    return [latest_by_index[i] for i in sorted(latest_by_index.keys())]


def _execute_compose_sync(job_id: str) -> dict:
    """Body of execute_episode_compose, split out so unit tests can drive it.

    Returns: {"success": bool, "error"?: str}
    """
    db = SessionLocal()
    compose_job = None
    work_dir = None
    try:
        compose_job = db.query(Job).filter(Job.id == job_id).first()
        if compose_job is None:
            return {"success": False, "error": "compose job not found"}

        compose_job.status = "running"
        compose_job.started_at = datetime.utcnow()
        compose_job.progress = 0.0
        db.commit()

        project_id = compose_job.project_id
        episode_number = (compose_job.inputs_json or {}).get("episode_number")
        expected = (compose_job.inputs_json or {}).get("expected_clip_count", 0)

        clips = _resolve_latest_succeeded_clips(db, project_id, episode_number)
        if len(clips) < expected:
            return _fail_job(
                db, compose_job,
                code="MISSING_CLIPS",
                message=f"expected {expected} clips, found {len(clips)}",
            )

        # Set up working directory
        tmp_root = os.environ.get("EPISODE_COMPOSE_TMP_ROOT") or tempfile.gettempdir()
        work_dir = Path(tmp_root) / f"episode-compose-{job_id}"
        work_dir.mkdir(parents=True, exist_ok=True)

        storage = get_storage_client()
        clip_paths: List[Path] = []
        for i, clip in enumerate(clips):
            key = (clip.outputs_json or {}).get("video_url")
            if not key:
                return _fail_job(
                    db, compose_job,
                    code="MISSING_CLIPS",
                    message=f"clip index {i} has no video_url",
                )
            try:
                data = _run_async(storage.download_bytes(key))
            except Exception as e:
                return _fail_job(
                    db, compose_job,
                    code="DOWNLOAD_FAILED",
                    message=f"failed to download clip {i} ({key}): {e!r}",
                )
            if not data:
                return _fail_job(
                    db, compose_job,
                    code="DOWNLOAD_FAILED",
                    message=f"clip {i} returned empty bytes",
                )
            clip_path = work_dir / f"clip_{i:03d}.mp4"
            clip_path.write_bytes(data)
            clip_paths.append(clip_path)

            compose_job.progress = 0.5 * ((i + 1) / len(clips))
            db.commit()

        # Build concat list
        list_file = work_dir / "concat_list.txt"
        list_file.write_text(
            "\n".join(f"file '{p.name}'" for p in clip_paths),
            encoding="utf-8",
        )

        # Run ffmpeg
        output_path = work_dir / "output.mp4"
        compose_job.progress = 0.5
        db.commit()

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(output_path),
        ]
        try:
            result = subprocess.run(
                cmd,
                cwd=str(work_dir),
                capture_output=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            return _fail_job(
                db, compose_job,
                code="FFMPEG_FAILED",
                message="ffmpeg timed out after 300s",
            )

        if result.returncode != 0:
            return _fail_job(
                db, compose_job,
                code="FFMPEG_FAILED",
                message=f"ffmpeg exit {result.returncode}",
                ffmpeg_stderr=result.stderr.decode("utf-8", errors="replace")[:4000],
            )

        compose_job.progress = 0.9
        db.commit()

        # Upload
        output_bytes = output_path.read_bytes()
        output_key = f"episode_videos/{project_id}/ep{episode_number}/compose_{job_id}.mp4"
        try:
            _run_async(storage.upload_bytes(
                path=output_key,
                data=output_bytes,
                content_type="video/mp4",
            ))
        except Exception as e:
            return _fail_job(
                db, compose_job,
                code="UPLOAD_FAILED",
                message=f"upload to {output_key} failed: {e!r}",
            )

        compose_job.status = "succeeded"
        compose_job.progress = 1.0
        compose_job.outputs_json = {
            "video_url": output_key,
            "size_bytes": len(output_bytes),
            "clip_count": len(clips),
            # duration_sec is best-effort: sum of source clips' duration metadata
            "duration_sec": sum(
                (c.outputs_json or {}).get("duration_sec", 0.0) for c in clips
            ),
        }
        compose_job.finished_at = datetime.utcnow()
        db.commit()

        return {"success": True, "video_url": output_key}

    except Exception as e:
        logger.exception("[EpisodeCompose] unexpected error in job %s", job_id)
        if compose_job is not None:
            return _fail_job(db, compose_job, code="UNEXPECTED", message=repr(e))
        return {"success": False, "error": repr(e)}
    finally:
        db.close()
        if work_dir and work_dir.exists():
            try:
                import shutil
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                logger.warning("[EpisodeCompose] cleanup failed for %s", work_dir)


def _fail_job(db, job: Job, code: str, message: str, **extra) -> dict:
    job.status = "failed"
    job.progress = 0.0
    job.error_json = {"code": code, "message": message, **extra}
    job.finished_at = datetime.utcnow()
    db.commit()
    logger.error("[EpisodeCompose] job %s failed: %s — %s", job.id, code, message)
    return {"success": False, "error": message, "code": code}


@shared_task(bind=True, name="app.workers.episode_compose_worker.execute_episode_compose")
def execute_episode_compose(self, job_id: str):
    return _execute_compose_sync(job_id)
```

- [ ] **Step 4: Run — expect pass**

```bash
py -3.13 -m pytest tests/unit/workers/test_episode_compose_worker.py::test_compose_happy_path_three_clips -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/app/workers/episode_compose_worker.py \
        apps/api/tests/unit/workers/test_episode_compose_worker.py
git commit -m "feat(api): episode_compose_worker — ffmpeg concat happy path (D)"
```

### Task 3.2: Worker — latest-succeeded-per-index resolution

**Files:**
- Test: extend `apps/api/tests/unit/workers/test_episode_compose_worker.py`

- [ ] **Step 1: Append the test**

```python
@pytest.mark.asyncio
async def test_compose_resolves_latest_succeeded_per_image_index(tmp_path, monkeypatch):
    """Two succeeded clips at index 0 → the latest finished_at wins."""
    monkeypatch.setenv("EPISODE_COMPOSE_TMP_ROOT", str(tmp_path))

    project_id = "p1"
    compose_job = make_compose_job("comp-x", project_id, 1, status="queued", expected_clip_count=2)

    siblings = [
        # Index 0: two succeeded entries — newer one wins
        make_episode_video_job("old0", project_id, 1, 0, status="succeeded",
                                video_url="images/old0.mp4", finished_at=time_offset(0)),
        make_episode_video_job("new0", project_id, 1, 0, status="succeeded",
                                video_url="images/new0.mp4", finished_at=time_offset(60)),
        # Index 1: single succeeded
        make_episode_video_job("a1", project_id, 1, 1, status="succeeded",
                                video_url="images/a1.mp4", finished_at=time_offset(10)),
    ]

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = compose_job
    db.query.return_value.filter.return_value.all.return_value = siblings

    downloaded_keys = []

    fake_storage = MagicMock()
    async def fake_download(key):
        downloaded_keys.append(key)
        return b"clip-bytes"
    fake_storage.download_bytes = fake_download
    fake_storage.upload_bytes = AsyncMock(return_value=None)

    def fake_subprocess(cmd, *args, **kwargs):
        output_path = cmd[-1]
        with open(output_path, "wb") as f:
            f.write(b"ok")
        return MagicMock(returncode=0, stderr=b"", stdout=b"")

    with patch("app.workers.episode_compose_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_compose_worker.get_storage_client", return_value=fake_storage), \
         patch("app.workers.episode_compose_worker.subprocess.run", side_effect=fake_subprocess):

        from app.workers.episode_compose_worker import _execute_compose_sync
        result = _execute_compose_sync("comp-x")

    assert result["success"] is True
    # Latest-per-index resolved correctly: new0 for index 0, a1 for index 1
    assert downloaded_keys == ["images/new0.mp4", "images/a1.mp4"]
```

- [ ] **Step 2: Run — expect 2 pass**

```bash
py -3.13 -m pytest tests/unit/workers/test_episode_compose_worker.py -v
```

Expected: 2 passed.

- [ ] **Step 3: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/tests/unit/workers/test_episode_compose_worker.py
git commit -m "test(api): compose worker resolves latest-succeeded-per-index (D)"
```

### Task 3.3: Worker — failure paths

**Files:**
- Test: extend `apps/api/tests/unit/workers/test_episode_compose_worker.py`

- [ ] **Step 1: Append four failure tests**

```python
@pytest.mark.asyncio
async def test_compose_missing_clips_fails(tmp_path, monkeypatch):
    """expected_clip_count = 3 but only 2 succeeded clips found → MISSING_CLIPS."""
    monkeypatch.setenv("EPISODE_COMPOSE_TMP_ROOT", str(tmp_path))

    compose_job = make_compose_job("comp-m", "p1", 1, expected_clip_count=3)
    siblings = [
        make_episode_video_job("c0", "p1", 1, 0, status="succeeded", finished_at=time_offset(0)),
        make_episode_video_job("c1", "p1", 1, 1, status="succeeded", finished_at=time_offset(0)),
        # index 2 missing
    ]

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = compose_job
    db.query.return_value.filter.return_value.all.return_value = siblings

    with patch("app.workers.episode_compose_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_compose_worker.get_storage_client"), \
         patch("app.workers.episode_compose_worker.subprocess.run"):
        from app.workers.episode_compose_worker import _execute_compose_sync
        result = _execute_compose_sync("comp-m")

    assert result["success"] is False
    assert result["code"] == "MISSING_CLIPS"
    assert compose_job.status == "failed"
    assert compose_job.error_json["code"] == "MISSING_CLIPS"


@pytest.mark.asyncio
async def test_compose_download_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("EPISODE_COMPOSE_TMP_ROOT", str(tmp_path))

    compose_job = make_compose_job("comp-d", "p1", 1, expected_clip_count=1)
    siblings = [
        make_episode_video_job("c0", "p1", 1, 0, status="succeeded",
                                video_url="images/c0.mp4", finished_at=time_offset(0)),
    ]

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = compose_job
    db.query.return_value.filter.return_value.all.return_value = siblings

    fake_storage = MagicMock()
    fake_storage.download_bytes = AsyncMock(side_effect=RuntimeError("network down"))

    with patch("app.workers.episode_compose_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_compose_worker.get_storage_client", return_value=fake_storage):
        from app.workers.episode_compose_worker import _execute_compose_sync
        result = _execute_compose_sync("comp-d")

    assert result["success"] is False
    assert result["code"] == "DOWNLOAD_FAILED"


@pytest.mark.asyncio
async def test_compose_ffmpeg_failure_captures_stderr(tmp_path, monkeypatch):
    monkeypatch.setenv("EPISODE_COMPOSE_TMP_ROOT", str(tmp_path))

    compose_job = make_compose_job("comp-f", "p1", 1, expected_clip_count=1)
    siblings = [
        make_episode_video_job("c0", "p1", 1, 0, status="succeeded",
                                video_url="images/c0.mp4", finished_at=time_offset(0)),
    ]
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = compose_job
    db.query.return_value.filter.return_value.all.return_value = siblings

    fake_storage = MagicMock()
    fake_storage.download_bytes = AsyncMock(return_value=b"clip")

    def fake_subprocess(cmd, *args, **kwargs):
        return MagicMock(returncode=1, stderr=b"ffmpeg: codec mismatch", stdout=b"")

    with patch("app.workers.episode_compose_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_compose_worker.get_storage_client", return_value=fake_storage), \
         patch("app.workers.episode_compose_worker.subprocess.run", side_effect=fake_subprocess):
        from app.workers.episode_compose_worker import _execute_compose_sync
        result = _execute_compose_sync("comp-f")

    assert result["success"] is False
    assert result["code"] == "FFMPEG_FAILED"
    assert "codec mismatch" in compose_job.error_json["ffmpeg_stderr"]


@pytest.mark.asyncio
async def test_compose_upload_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("EPISODE_COMPOSE_TMP_ROOT", str(tmp_path))

    compose_job = make_compose_job("comp-u", "p1", 1, expected_clip_count=1)
    siblings = [
        make_episode_video_job("c0", "p1", 1, 0, status="succeeded",
                                video_url="images/c0.mp4", finished_at=time_offset(0)),
    ]
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = compose_job
    db.query.return_value.filter.return_value.all.return_value = siblings

    fake_storage = MagicMock()
    fake_storage.download_bytes = AsyncMock(return_value=b"clip")
    fake_storage.upload_bytes = AsyncMock(side_effect=RuntimeError("S3 down"))

    def fake_subprocess(cmd, *args, **kwargs):
        output_path = cmd[-1]
        with open(output_path, "wb") as f:
            f.write(b"out")
        return MagicMock(returncode=0, stderr=b"", stdout=b"")

    with patch("app.workers.episode_compose_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_compose_worker.get_storage_client", return_value=fake_storage), \
         patch("app.workers.episode_compose_worker.subprocess.run", side_effect=fake_subprocess):
        from app.workers.episode_compose_worker import _execute_compose_sync
        result = _execute_compose_sync("comp-u")

    assert result["success"] is False
    assert result["code"] == "UPLOAD_FAILED"
```

- [ ] **Step 2: Run — expect 6 pass total**

```bash
py -3.13 -m pytest tests/unit/workers/test_episode_compose_worker.py -v
```

Expected: 6 passed (2 prior + 4 new).

- [ ] **Step 3: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/tests/unit/workers/test_episode_compose_worker.py
git commit -m "test(api): compose worker failure paths — missing/download/ffmpeg/upload (D)"
```

### Task 3.4: Worker — concat list contents + subprocess invocation

**Files:**
- Test: extend `apps/api/tests/unit/workers/test_episode_compose_worker.py`

- [ ] **Step 1: Append the test**

```python
@pytest.mark.asyncio
async def test_compose_concat_list_contents(tmp_path, monkeypatch):
    """Verify the concat list file written before ffmpeg lists clips in image_index order."""
    monkeypatch.setenv("EPISODE_COMPOSE_TMP_ROOT", str(tmp_path))

    compose_job = make_compose_job("comp-cl", "p1", 1, expected_clip_count=3)
    siblings = [
        make_episode_video_job("c2", "p1", 1, 2, status="succeeded",
                                video_url="images/c2.mp4", finished_at=time_offset(0)),
        make_episode_video_job("c0", "p1", 1, 0, status="succeeded",
                                video_url="images/c0.mp4", finished_at=time_offset(0)),
        make_episode_video_job("c1", "p1", 1, 1, status="succeeded",
                                video_url="images/c1.mp4", finished_at=time_offset(0)),
    ]

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = compose_job
    db.query.return_value.filter.return_value.all.return_value = siblings

    fake_storage = MagicMock()
    fake_storage.download_bytes = AsyncMock(return_value=b"clip")
    fake_storage.upload_bytes = AsyncMock(return_value=None)

    list_contents = {}
    def fake_subprocess(cmd, *args, **kwargs):
        # Read the concat list file from the -i argument
        i_idx = cmd.index("-i")
        list_file = cmd[i_idx + 1]
        with open(list_file, "r", encoding="utf-8") as f:
            list_contents["text"] = f.read()
        output_path = cmd[-1]
        with open(output_path, "wb") as f:
            f.write(b"ok")
        return MagicMock(returncode=0, stderr=b"", stdout=b"")

    with patch("app.workers.episode_compose_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_compose_worker.get_storage_client", return_value=fake_storage), \
         patch("app.workers.episode_compose_worker.subprocess.run", side_effect=fake_subprocess):
        from app.workers.episode_compose_worker import _execute_compose_sync
        result = _execute_compose_sync("comp-cl")

    assert result["success"] is True
    text = list_contents["text"]
    # Index ascending order: 0,1,2 → clip_000, clip_001, clip_002
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    assert lines == ["file 'clip_000.mp4'", "file 'clip_001.mp4'", "file 'clip_002.mp4'"]
```

- [ ] **Step 2: Run — expect 7 pass**

```bash
py -3.13 -m pytest tests/unit/workers/test_episode_compose_worker.py -v
```

Expected: 7 passed.

- [ ] **Step 3: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/tests/unit/workers/test_episode_compose_worker.py
git commit -m "test(api): compose worker concat list ordering (D)"
```

---

## Group 4: Wire trigger into existing worker

### Task 4.1: Hook compose dispatch into `episode_video_worker` success path

**Files:**
- Modify: `apps/api/app/workers/episode_video_worker.py`
- Test: `apps/api/tests/unit/workers/test_episode_video_dispatch_hook.py` (new)

- [ ] **Step 1: Write the failing test**

```python
"""Verify the auto-trigger hook fires (or skips correctly) at clip success."""
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_episode_video_success_calls_compose_dispatch(monkeypatch):
    """When a clip job succeeds, the dispatch helper is invoked exactly once."""
    # Drive the success-path code by patching everything else inside the task.
    fake_job = MagicMock()
    fake_job.id = "v1"
    fake_job.project_id = "p1"
    fake_job.inputs_json = {"episode_number": 1, "image_index": 0}

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = fake_job

    fake_provider = MagicMock()
    fake_provider.generate = MagicMock()  # patched below at run_async

    fake_result = MagicMock(
        success=True, video_url="x", preview_url="x", duration_sec=5.0,
        provider="doubao", seed=0, cost=0.0,
    )

    with patch("app.workers.episode_video_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_video_worker.get_video_provider", return_value=fake_provider), \
         patch("app.workers.episode_video_worker.run_async", return_value=fake_result), \
         patch("app.workers.episode_video_worker._maybe_enqueue_episode_compose") as dispatch_mock:

        from app.workers.episode_video_worker import generate_episode_video_task
        # Call via the underlying function (skip celery .delay() invocation)
        generate_episode_video_task.run(
            job_id="v1",
            image_url="images/in.png",
            motion_prompt="x",
            duration_sec=3.0,
            provider_name="doubao",
        )

    dispatch_mock.assert_called_once_with(db, "p1", 1)


@pytest.mark.asyncio
async def test_episode_video_failure_does_not_call_dispatch(monkeypatch):
    """On clip failure, dispatch must NOT be called — strict policy."""
    fake_job = MagicMock()
    fake_job.id = "v2"
    fake_job.project_id = "p1"
    fake_job.inputs_json = {"episode_number": 1, "image_index": 0}

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = fake_job

    fake_provider = MagicMock()
    fake_result = MagicMock(success=False, error="boom", error_code="X")

    with patch("app.workers.episode_video_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_video_worker.get_video_provider", return_value=fake_provider), \
         patch("app.workers.episode_video_worker.run_async", return_value=fake_result), \
         patch("app.workers.episode_video_worker._maybe_enqueue_episode_compose") as dispatch_mock:

        from app.workers.episode_video_worker import generate_episode_video_task
        generate_episode_video_task.run(
            job_id="v2",
            image_url="images/in.png",
            motion_prompt="x",
            duration_sec=3.0,
            provider_name="doubao",
        )

    dispatch_mock.assert_not_called()


@pytest.mark.asyncio
async def test_episode_video_dispatch_error_does_not_fail_clip(monkeypatch):
    """If dispatch helper raises, clip status must still be 'succeeded'."""
    fake_job = MagicMock()
    fake_job.id = "v3"
    fake_job.project_id = "p1"
    fake_job.inputs_json = {"episode_number": 1, "image_index": 0}

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = fake_job

    fake_provider = MagicMock()
    fake_result = MagicMock(success=True, video_url="x", preview_url="x",
                             duration_sec=5.0, provider="doubao", seed=0, cost=0.0)

    with patch("app.workers.episode_video_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_video_worker.get_video_provider", return_value=fake_provider), \
         patch("app.workers.episode_video_worker.run_async", return_value=fake_result), \
         patch("app.workers.episode_video_worker._maybe_enqueue_episode_compose",
               side_effect=RuntimeError("dispatch helper crash")):

        from app.workers.episode_video_worker import generate_episode_video_task
        ret = generate_episode_video_task.run(
            job_id="v3",
            image_url="images/in.png",
            motion_prompt="x",
            duration_sec=3.0,
            provider_name="doubao",
        )

    # Clip succeeded despite the dispatch error
    assert ret["success"] is True
    assert fake_job.status == "succeeded"
```

- [ ] **Step 2: Run — expect failure (no import)**

```bash
cd D:/ai-webtoon-studio/apps/api
py -3.13 -m pytest tests/unit/workers/test_episode_video_dispatch_hook.py -v
```

Expected: FAIL — `_maybe_enqueue_episode_compose` not importable from `episode_video_worker` yet.

- [ ] **Step 3: Modify `episode_video_worker.py`**

In `apps/api/app/workers/episode_video_worker.py`, add the import near the top (after existing imports):

```python
from app.services.video.compose_dispatch import _maybe_enqueue_episode_compose
```

Then locate the success block (around lines 149-166) — after `db.commit()` at line 163, append:

```python
            # Phase D: auto-trigger episode compose if all siblings succeeded.
            # Compose dispatch failure must NOT fail the clip job — the clip succeeded.
            try:
                episode_num = (job.inputs_json or {}).get("episode_number")
                if job.project_id and episode_num is not None:
                    _maybe_enqueue_episode_compose(db, job.project_id, episode_num)
            except Exception:
                logger.exception("[EpisodeVideoWorker] compose dispatch check failed")
```

So the full success block now reads:

```python
        if result.success:
            outputs = {
                "video_url": result.video_url,
                "preview_url": result.preview_url or result.video_url,
                "duration_sec": result.duration_sec,
                "provider": result.provider,
                "seed": result.seed,
            }

            job.status = "succeeded"
            job.progress = 1.0
            job.outputs_json = outputs
            job.finished_at = datetime.utcnow()
            job.cost_used = result.cost
            db.commit()

            # Phase D: auto-trigger episode compose if all siblings succeeded.
            # Compose dispatch failure must NOT fail the clip job — the clip succeeded.
            try:
                episode_num = (job.inputs_json or {}).get("episode_number")
                if job.project_id and episode_num is not None:
                    _maybe_enqueue_episode_compose(db, job.project_id, episode_num)
            except Exception:
                logger.exception("[EpisodeVideoWorker] compose dispatch check failed")

            logger.info(f"[EpisodeVideoWorker] Job {job_id} completed: {result.video_url}")
            return {"success": True, "outputs": outputs}
        else:
            raise Exception(result.error or "Video generation failed")
```

- [ ] **Step 4: Run — expect 3 pass**

```bash
py -3.13 -m pytest tests/unit/workers/test_episode_video_dispatch_hook.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/app/workers/episode_video_worker.py \
        apps/api/tests/unit/workers/test_episode_video_dispatch_hook.py
git commit -m "feat(api): wire compose dispatch hook into episode_video_worker (D)"
```

---

## Group 5: API routes

### Task 5.1: GET `/episode/compose-jobs/{job_id}` status endpoint

**Files:**
- Modify: `apps/api/app/api/routes/episode_video.py`
- Test: `apps/api/tests/unit/routes/test_episode_compose_routes.py` (new)

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for the Phase D compose API endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


@pytest.fixture
def fake_db():
    db = MagicMock()
    return db


def _override_get_db(client, fake_db):
    from app.db.database import get_db
    from app.main import app
    app.dependency_overrides[get_db] = lambda: fake_db
    yield
    app.dependency_overrides.clear()


def test_get_compose_job_status_succeeded(client, fake_db):
    from app.models import Job
    job = MagicMock(spec=Job)
    job.id = "comp-1"
    job.status = "succeeded"
    job.progress = 1.0
    job.outputs_json = {"video_url": "episode_videos/p1/ep1/compose_comp-1.mp4",
                         "clip_count": 3, "duration_sec": 15.0}
    job.error_json = None
    fake_db.query.return_value.filter.return_value.first.return_value = job

    from app.db.database import get_db
    from app.main import app
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        resp = client.get("/episode/compose-jobs/comp-1")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["job_id"] == "comp-1"
    assert body["status"] == "succeeded"
    assert body["video_url"].endswith("compose_comp-1.mp4")
    assert body["clip_count"] == 3


def test_get_compose_job_status_404(client, fake_db):
    fake_db.query.return_value.filter.return_value.first.return_value = None

    from app.db.database import get_db
    from app.main import app
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        resp = client.get("/episode/compose-jobs/nope")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404
```

- [ ] **Step 2: Run — expect 404 from missing route**

```bash
cd D:/ai-webtoon-studio/apps/api
py -3.13 -m pytest tests/unit/routes/test_episode_compose_routes.py -v
```

Expected: FAIL. Route doesn't exist yet.

- [ ] **Step 3: Add the route to `episode_video.py`**

In `apps/api/app/api/routes/episode_video.py`, append after the existing routes (after line 223):

```python
class ComposeJobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    video_url: Optional[str] = None
    clip_count: Optional[int] = None
    duration_sec: Optional[float] = None
    error: Optional[str] = None


@router.get("/episode/compose-jobs/{job_id}", response_model=ComposeJobStatusResponse)
async def get_compose_job_status(
    job_id: str,
    db: Session = Depends(get_db),
):
    """Phase D: status of an episode_video_compose job."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Compose job not found")
    outputs = job.outputs_json or {}
    return ComposeJobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        video_url=outputs.get("video_url"),
        clip_count=outputs.get("clip_count"),
        duration_sec=outputs.get("duration_sec"),
        error=(job.error_json or {}).get("message") if job.error_json else None,
    )
```

- [ ] **Step 4: Run — expect 2 pass**

```bash
py -3.13 -m pytest tests/unit/routes/test_episode_compose_routes.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/app/api/routes/episode_video.py \
        apps/api/tests/unit/routes/test_episode_compose_routes.py
git commit -m "feat(api): GET /episode/compose-jobs/{id} status endpoint (D)"
```

### Task 5.2: POST `/episode/{N}/compose-video/retry`

**Files:**
- Modify: `apps/api/app/api/routes/episode_video.py`
- Test: extend `apps/api/tests/unit/routes/test_episode_compose_routes.py`

- [ ] **Step 1: Append the failing tests**

```python
def test_retry_endpoint_requires_all_clips_succeeded(client, fake_db):
    """If any sibling clip is not 'succeeded', 409."""
    from tests.unit.workers._episode_helpers import make_episode_video_job

    siblings = [
        make_episode_video_job("c0", "p1", 1, 0, status="succeeded"),
        make_episode_video_job("c1", "p1", 1, 1, status="failed"),
    ]
    fake_db.query.return_value.filter.return_value.all.return_value = siblings

    from app.db.database import get_db
    from app.main import app
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        resp = client.post("/episode/1/compose-video/retry", json={"project_id": "p1"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 409


def test_retry_endpoint_creates_new_compose_bypassing_dedup(client, fake_db):
    """All clips succeeded + a prior succeeded compose exists → retry STILL creates a new one."""
    from tests.unit.workers._episode_helpers import make_episode_video_job, make_compose_job

    siblings = [make_episode_video_job("c0", "p1", 1, 0, status="succeeded")]
    # Even though one succeeded compose already exists, retry bypasses the dedup check
    existing = [make_compose_job("old-comp", "p1", 1, status="succeeded")]
    fake_db.query.return_value.filter.return_value.all.side_effect = [siblings, existing]
    fake_db.add = MagicMock()
    fake_db.commit = MagicMock()

    from app.db.database import get_db
    from app.main import app
    app.dependency_overrides[get_db] = lambda: fake_db
    try:
        with patch("app.api.routes.episode_video.execute_episode_compose") as fake_task:
            fake_task.delay = MagicMock()
            resp = client.post("/episode/1/compose-video/retry", json={"project_id": "p1"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert "job_id" in body
    assert body["status"] == "queued"
    fake_db.add.assert_called_once()
```

- [ ] **Step 2: Run — expect failure (route missing)**

```bash
py -3.13 -m pytest tests/unit/routes/test_episode_compose_routes.py -v
```

Expected: FAIL on the two new tests (404).

- [ ] **Step 3: Add the retry route**

In `apps/api/app/api/routes/episode_video.py`, add near the new ComposeJobStatusResponse:

```python
class ComposeRetryRequest(BaseModel):
    project_id: str


class ComposeRetryResponse(BaseModel):
    job_id: str
    status: str


@router.post("/episode/{episode_num}/compose-video/retry", response_model=ComposeRetryResponse)
async def retry_episode_compose(
    episode_num: int,
    request: ComposeRetryRequest,
    db: Session = Depends(get_db),
):
    """Phase D: manually enqueue a fresh compose for an episode.

    Used when compose itself failed but every per-panel clip is still 'succeeded'.
    Bypasses the dedup check (returns a new job_id even if a prior succeeded
    compose row exists), but still enforces the all-clips-succeeded rule.
    """
    # Pull siblings — must all be 'succeeded'
    candidates = db.query(Job).filter(
        Job.type == "episode_video",
        Job.project_id == request.project_id,
    ).all()
    siblings = [
        j for j in candidates
        if (j.inputs_json or {}).get("episode_number") == episode_num
    ]
    if not siblings:
        raise HTTPException(status_code=404, detail="No per-panel clips for episode")
    if any(j.status != "succeeded" for j in siblings):
        raise HTTPException(
            status_code=409,
            detail="Cannot compose: one or more sibling clips are not 'succeeded'",
        )

    compose_job_id = str(uuid.uuid4())
    job = Job(
        id=compose_job_id,
        type="episode_video_compose",
        provider="ffmpeg",
        project_id=request.project_id,
        status="queued",
        inputs_json={
            "episode_number": episode_num,
            "expected_clip_count": len(siblings),
        },
    )
    db.add(job)
    db.commit()

    from app.workers.episode_compose_worker import execute_episode_compose
    execute_episode_compose.delay(compose_job_id)

    logger.info(
        "[EpisodeCompose] retry enqueued %s for project=%s ep=%s clips=%d",
        compose_job_id, request.project_id, episode_num, len(siblings),
    )
    return ComposeRetryResponse(job_id=compose_job_id, status="queued")
```

- [ ] **Step 4: Run — expect 4 pass**

```bash
py -3.13 -m pytest tests/unit/routes/test_episode_compose_routes.py -v
```

Expected: 4 passed (2 prior + 2 new).

- [ ] **Step 5: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/app/api/routes/episode_video.py \
        apps/api/tests/unit/routes/test_episode_compose_routes.py
git commit -m "feat(api): POST /episode/{N}/compose-video/retry (D)"
```

---

## Group 6: WebSocket events

### Task 6.1: Compose WS event emission

**Files:**
- Modify: `apps/api/app/workers/episode_compose_worker.py`
- Test: `apps/api/tests/unit/workers/test_episode_compose_ws_events.py` (new)

- [ ] **Step 1: Write the failing test**

```python
"""Verify compose worker emits the expected WS events at each stage (Phase D)."""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from tests.unit.workers._episode_helpers import (
    make_episode_video_job,
    make_compose_job,
    time_offset,
)


@pytest.mark.asyncio
async def test_compose_emits_events_on_success(tmp_path, monkeypatch):
    monkeypatch.setenv("EPISODE_COMPOSE_TMP_ROOT", str(tmp_path))

    compose_job = make_compose_job("comp-ws", "p1", 1, expected_clip_count=2)
    siblings = [
        make_episode_video_job("c0", "p1", 1, 0, status="succeeded",
                                video_url="images/c0.mp4", finished_at=time_offset(0)),
        make_episode_video_job("c1", "p1", 1, 1, status="succeeded",
                                video_url="images/c1.mp4", finished_at=time_offset(0)),
    ]

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = compose_job
    db.query.return_value.filter.return_value.all.return_value = siblings

    fake_storage = MagicMock()
    fake_storage.download_bytes = AsyncMock(return_value=b"clip")
    fake_storage.upload_bytes = AsyncMock(return_value=None)

    def fake_subprocess(cmd, *args, **kwargs):
        output_path = cmd[-1]
        with open(output_path, "wb") as f:
            f.write(b"ok")
        return MagicMock(returncode=0, stderr=b"", stdout=b"")

    emitted_events = []

    def fake_emit(project_id, episode_number, event_type, data):
        emitted_events.append({"event": event_type, "data": data,
                                "project_id": project_id, "episode_number": episode_number})

    with patch("app.workers.episode_compose_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_compose_worker.get_storage_client", return_value=fake_storage), \
         patch("app.workers.episode_compose_worker.subprocess.run", side_effect=fake_subprocess), \
         patch("app.workers.episode_compose_worker._push_episode_compose_update", side_effect=fake_emit):

        from app.workers.episode_compose_worker import _execute_compose_sync
        _execute_compose_sync("comp-ws")

    event_types = [e["event"] for e in emitted_events]
    # Required events: created (or progress: downloading_clips at 0), running_ffmpeg, uploading, done
    assert "episode_compose_progress" in event_types
    assert "episode_compose_done" in event_types
    # Final event contains video_url
    done_event = next(e for e in emitted_events if e["event"] == "episode_compose_done")
    assert "video_url" in done_event["data"]
    assert done_event["data"]["clip_count"] == 2


@pytest.mark.asyncio
async def test_compose_emits_failed_event_on_ffmpeg_error(tmp_path, monkeypatch):
    monkeypatch.setenv("EPISODE_COMPOSE_TMP_ROOT", str(tmp_path))

    compose_job = make_compose_job("comp-wsf", "p1", 1, expected_clip_count=1)
    siblings = [
        make_episode_video_job("c0", "p1", 1, 0, status="succeeded",
                                video_url="images/c0.mp4", finished_at=time_offset(0)),
    ]
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = compose_job
    db.query.return_value.filter.return_value.all.return_value = siblings

    fake_storage = MagicMock()
    fake_storage.download_bytes = AsyncMock(return_value=b"clip")

    def fake_subprocess(cmd, *args, **kwargs):
        return MagicMock(returncode=1, stderr=b"boom", stdout=b"")

    emitted = []
    def fake_emit(project_id, episode_number, event_type, data):
        emitted.append((event_type, data))

    with patch("app.workers.episode_compose_worker.SessionLocal", return_value=db), \
         patch("app.workers.episode_compose_worker.get_storage_client", return_value=fake_storage), \
         patch("app.workers.episode_compose_worker.subprocess.run", side_effect=fake_subprocess), \
         patch("app.workers.episode_compose_worker._push_episode_compose_update", side_effect=fake_emit):

        from app.workers.episode_compose_worker import _execute_compose_sync
        _execute_compose_sync("comp-wsf")

    failed_events = [e for e in emitted if e[0] == "episode_compose_failed"]
    assert len(failed_events) == 1
    assert failed_events[0][1]["error_code"] == "FFMPEG_FAILED"
```

- [ ] **Step 2: Run — expect failure (emit helper not defined yet)**

```bash
py -3.13 -m pytest tests/unit/workers/test_episode_compose_ws_events.py -v
```

Expected: FAIL — `_push_episode_compose_update` not importable.

- [ ] **Step 3: Add the emit helper + call it from the worker**

In `apps/api/app/workers/episode_compose_worker.py`, add after the imports:

```python
def _push_episode_compose_update(
    project_id: str,
    episode_number: int,
    event_type: str,
    data: dict,
) -> None:
    """Push a compose-stage WS event by reusing the chapter pub-sub channel.

    Uses project_id as the routing key (frontends interested in compose events
    subscribe with chapter_id=project_id). Failures are swallowed — WS publish
    must never break the worker.
    """
    try:
        from app.api.routes.ws import push_chapter_update
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                push_chapter_update(
                    project_id,
                    event_type,
                    {
                        "project_id": project_id,
                        "episode_number": episode_number,
                        **data,
                    },
                )
            )
        finally:
            loop.close()
    except Exception:
        logger.warning("[EpisodeCompose] WS publish failed", exc_info=True)
```

Then sprinkle emit calls into the worker at key stages. Replace the worker's progress updates with these (note: progress was already being computed; just adding emits):

In `_execute_compose_sync`, after the worker starts (after `compose_job.status = "running"` block):

```python
        _push_episode_compose_update(
            project_id, episode_number, "episode_compose_created",
            {"job_id": job_id, "expected_clip_count": expected},
        )
```

Inside the clip download loop, after each `compose_job.progress = 0.5 * ((i + 1) / len(clips))`:

```python
            _push_episode_compose_update(
                project_id, episode_number, "episode_compose_progress",
                {"job_id": job_id, "progress": compose_job.progress,
                 "stage": "downloading_clips"},
            )
```

Before the `subprocess.run` call:

```python
        _push_episode_compose_update(
            project_id, episode_number, "episode_compose_progress",
            {"job_id": job_id, "progress": 0.5, "stage": "running_ffmpeg"},
        )
```

After ffmpeg succeeds, before upload:

```python
        _push_episode_compose_update(
            project_id, episode_number, "episode_compose_progress",
            {"job_id": job_id, "progress": 0.9, "stage": "uploading"},
        )
```

After the final commit on success, just before `return {"success": True, ...}`:

```python
        _push_episode_compose_update(
            project_id, episode_number, "episode_compose_done",
            {
                "job_id": job_id,
                "video_url": output_key,
                "duration_sec": compose_job.outputs_json["duration_sec"],
                "clip_count": len(clips),
            },
        )
```

Inside `_fail_job`, append before the return:

```python
    # Emit a compose_failed event (best-effort — failures here are swallowed).
    try:
        proj = job.project_id
        ep = (job.inputs_json or {}).get("episode_number")
        if proj and ep is not None:
            _push_episode_compose_update(
                proj, ep, "episode_compose_failed",
                {"job_id": job.id, "error_code": code, "message": message},
            )
    except Exception:
        logger.warning("[EpisodeCompose] failed-event emit raised", exc_info=True)
```

- [ ] **Step 4: Run — expect 2 pass**

```bash
py -3.13 -m pytest tests/unit/workers/test_episode_compose_ws_events.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Run full compose worker suite to verify no regressions**

```bash
py -3.13 -m pytest tests/unit/workers/test_episode_compose_worker.py tests/unit/workers/test_episode_compose_ws_events.py tests/unit/workers/test_episode_compose_dispatch.py tests/unit/workers/test_episode_video_dispatch_hook.py -v
```

Expected: 22 passed (10 dispatch + 7 worker + 3 dispatch hook + 2 ws).

- [ ] **Step 6: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/app/workers/episode_compose_worker.py \
        apps/api/tests/unit/workers/test_episode_compose_ws_events.py
git commit -m "feat(api): compose worker emits WS events at each stage (D)"
```

---

## Group 7: Celery registration + static-source regression

### Task 7.1: Register `episode_compose_worker` in celery_app

**Files:**
- Modify: `apps/api/app/celery_app.py`

- [ ] **Step 1: Find the worker imports list**

```bash
cd D:/ai-webtoon-studio
grep -n "episode_video_worker" apps/api/app/celery_app.py
```

Expected output: lines ~20 (imports) and ~61 (queue routing).

- [ ] **Step 2: Edit `celery_app.py`**

Find the `include=[...]` list (around line 17–22). Add `"app.workers.episode_compose_worker"` after `episode_video_worker`:

```python
        "app.workers.image_worker",
        "app.workers.anchor_worker",
        "app.workers.video_worker",
        "app.workers.episode_video_worker",
        "app.workers.episode_compose_worker",
        "app.workers.export_worker",
```

Find the `task_routes` mapping (around line 58–62). Route compose tasks to the `video` queue:

```python
        "app.workers.video_worker.*": {"queue": "video"},
        "app.workers.episode_video_worker.*": {"queue": "video"},
        "app.workers.episode_compose_worker.*": {"queue": "video"},
        "app.workers.export_worker.*": {"queue": "export"},
```

- [ ] **Step 3: Smoke-test celery app import**

```bash
cd D:/ai-webtoon-studio/apps/api
py -3.13 -c "from app.celery_app import celery_app; print('tasks:', sorted(t for t in celery_app.tasks if 'episode' in t))"
```

Expected: includes `app.workers.episode_compose_worker.execute_episode_compose` in the output.

- [ ] **Step 4: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/app/celery_app.py
git commit -m "chore(api): register episode_compose_worker in celery_app (D)"
```

### Task 7.2: Phase D real-impl static-source regression test

**Files:**
- Create: `apps/api/tests/unit/test_phase_d_real_impl.py`

- [ ] **Step 1: Write the test**

```python
"""Static-source regression: Phase D real implementations are live (not stubbed)."""
import inspect

from app.workers import episode_compose_worker, episode_video_worker
from app.services.video import compose_dispatch
from app.api.routes import episode_video as episode_video_routes


def test_compose_worker_uses_ffmpeg():
    src = inspect.getsource(episode_compose_worker)
    assert "import subprocess" in src
    assert '"ffmpeg"' in src or "'ffmpeg'" in src
    assert "concat" in src
    assert "-c" in src and "copy" in src


def test_compose_dispatch_helper_exists():
    assert hasattr(compose_dispatch, "_maybe_enqueue_episode_compose")


def test_episode_video_worker_calls_dispatch_on_success():
    src = inspect.getsource(episode_video_worker.generate_episode_video_task)
    assert "_maybe_enqueue_episode_compose" in src, \
        "episode_video_worker no longer hooks into compose dispatch — Phase D regressed"


def test_retry_endpoint_route_exists():
    src = inspect.getsource(episode_video_routes)
    assert "/compose-video/retry" in src
    assert "ComposeRetryRequest" in src


def test_compose_status_route_exists():
    src = inspect.getsource(episode_video_routes)
    assert "/episode/compose-jobs/" in src
    assert "ComposeJobStatusResponse" in src
```

- [ ] **Step 2: Run — expect pass**

```bash
cd D:/ai-webtoon-studio/apps/api
py -3.13 -m pytest tests/unit/test_phase_d_real_impl.py -v
```

Expected: 5 passed.

- [ ] **Step 3: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/tests/unit/test_phase_d_real_impl.py
git commit -m "test(api): static-source regression for Phase D real impl (D)"
```

---

## Group 8: Integration test

### Task 8.1: End-to-end compose flow with in-memory storage

**Files:**
- Create: `apps/api/tests/integration/video/__init__.py` (empty)
- Create: `apps/api/tests/integration/video/test_episode_compose_e2e.py`

- [ ] **Step 1: Create the package marker**

```bash
cd D:/ai-webtoon-studio
type nul > apps/api/tests/integration/video/__init__.py
```

(On macOS/Linux: `touch apps/api/tests/integration/video/__init__.py`.)

- [ ] **Step 2: Write the e2e test**

`apps/api/tests/integration/video/test_episode_compose_e2e.py`:

```python
"""End-to-end Phase D compose flow.

Inserts three succeeded episode_video Job rows into an in-memory SQLite DB,
invokes the dispatch helper, then runs the compose worker synchronously with
a patched ffmpeg and in-memory storage. Verifies a compose Job row is created,
ffmpeg is invoked with the correct concat list, the final MP4 is uploaded to
the canonical MinIO path, and Job.outputs_json is populated correctly.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401 — register all models
from app.models.base import Base
from app.models import Job


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    sess = Session()
    yield sess
    sess.close()


@pytest.mark.asyncio
async def test_e2e_dispatch_then_compose(db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("EPISODE_COMPOSE_TMP_ROOT", str(tmp_path))

    project_id = "proj-e2e"
    episode_num = 7

    # Insert 3 succeeded clip jobs
    from datetime import datetime
    for i in range(3):
        db_session.add(Job(
            id=f"clip-{i}",
            type="episode_video",
            project_id=project_id,
            status="succeeded",
            progress=1.0,
            finished_at=datetime.utcnow(),
            inputs_json={"episode_number": episode_num, "image_index": i,
                          "image_url": f"images/p{i}.png"},
            outputs_json={"video_url": f"images/clip_{i}.mp4", "duration_sec": 4.0},
        ))
    db_session.commit()

    in_memory: dict[str, bytes] = {}

    fake_storage = MagicMock()
    async def fake_download(key):
        # Inject some bytes (worker writes them to /tmp; ffmpeg is patched anyway)
        in_memory.setdefault(key, b"clip_bytes_" + key.encode())
        return in_memory[key]
    async def fake_upload(path, data, content_type=None):
        in_memory[path] = data
        return None
    fake_storage.download_bytes = fake_download
    fake_storage.upload_bytes = fake_upload

    def fake_subprocess(cmd, *args, **kwargs):
        # Write a recognizable bytes blob to output.mp4
        output_path = cmd[-1]
        with open(output_path, "wb") as f:
            f.write(b"E2E_FINAL_MP4")
        return MagicMock(returncode=0, stderr=b"", stdout=b"")

    from app.services.video.compose_dispatch import _maybe_enqueue_episode_compose
    from app.workers.episode_compose_worker import _execute_compose_sync

    # Step 1: dispatch should create a compose job
    with patch("app.services.video.compose_dispatch.execute_episode_compose") as fake_task:
        fake_task.delay = MagicMock()
        compose_job_id = _maybe_enqueue_episode_compose(db_session, project_id, episode_num)

    assert compose_job_id is not None
    compose_job = db_session.query(Job).filter(Job.id == compose_job_id).first()
    assert compose_job is not None
    assert compose_job.status == "queued"
    assert compose_job.inputs_json["expected_clip_count"] == 3

    # Step 2: drive the compose worker synchronously
    with patch("app.workers.episode_compose_worker.SessionLocal", return_value=db_session), \
         patch("app.workers.episode_compose_worker.get_storage_client", return_value=fake_storage), \
         patch("app.workers.episode_compose_worker.subprocess.run", side_effect=fake_subprocess), \
         patch("app.workers.episode_compose_worker._push_episode_compose_update"):
        result = _execute_compose_sync(compose_job_id)

    assert result["success"] is True

    # Final state: compose job succeeded, MP4 in in-memory storage
    db_session.refresh(compose_job)
    assert compose_job.status == "succeeded"
    assert compose_job.outputs_json["clip_count"] == 3
    out_key = compose_job.outputs_json["video_url"]
    assert out_key == f"episode_videos/{project_id}/ep{episode_num}/compose_{compose_job_id}.mp4"
    assert in_memory[out_key] == b"E2E_FINAL_MP4"

    # The compose row should be in the DB; dispatch should now dedup
    with patch("app.services.video.compose_dispatch.execute_episode_compose") as fake_task:
        fake_task.delay = MagicMock()
        second_id = _maybe_enqueue_episode_compose(db_session, project_id, episode_num)
    assert second_id is None  # dedup against succeeded compose
```

- [ ] **Step 3: Run — expect pass**

```bash
cd D:/ai-webtoon-studio/apps/api
py -3.13 -m pytest tests/integration/video/test_episode_compose_e2e.py -v
```

Expected: 1 passed.

If the test fails with a JSON-column mutation issue similar to the bug found during C's e2e (SQLAlchemy's identity-based JSON change detection silently drops in-place mutations), check whether the compose worker uses `dict(...)` when reading-modifying-writing `outputs_json` / `error_json`. The Task 3.1 worker assigns fresh dicts via `compose_job.outputs_json = {...}` and `compose_job.error_json = {...}`, so this should not regress.

- [ ] **Step 4: Commit**

```bash
cd D:/ai-webtoon-studio
git add apps/api/tests/integration/video/__init__.py \
        apps/api/tests/integration/video/test_episode_compose_e2e.py
git commit -m "test(api): e2e compose flow with in-memory storage (D)"
```

---

## Group 9: Final Verification

### Task 9.1: Run full B-1 + C + D test suite

- [ ] **Step 1: Run**

```bash
cd D:/ai-webtoon-studio/apps/api
py -3.13 -m pytest \
    tests/unit/services/agent \
    tests/unit/services/scene \
    tests/unit/services/scene_anchor \
    tests/unit/services/video \
    tests/unit/test_migration_022.py \
    tests/unit/core/test_logging.py \
    tests/unit/workers \
    tests/unit/routes/test_b1_routes_registered.py \
    tests/unit/routes/test_episode_endpoints_delegate.py \
    tests/unit/routes/test_episode_compose_routes.py \
    tests/unit/test_phase_e_deletions.py \
    tests/unit/test_phase_d_real_impl.py \
    tests/integration/agent \
    tests/integration/scene \
    tests/integration/video \
    2>&1 | tail -3
```

Expected: ~210+ passed (188 from B-1 + C, ~22 new from D).

If any test fails, fix in place and re-run before proceeding.

### Task 9.2: Smoke-test app boot

```bash
cd D:/ai-webtoon-studio/apps/api
py -3.13 -c "from app.main import app; print('imports OK; routes:', len(app.routes))"
py -3.13 -c "from app.workers.episode_compose_worker import execute_episode_compose, _execute_compose_sync; print('compose worker imports OK')"
py -3.13 -c "from app.services.video.compose_dispatch import _maybe_enqueue_episode_compose; print('dispatch imports OK')"
```

Expected: all three print successfully; route count rises by ~2 (compose-jobs/{id} and compose-video/retry).

### Task 9.3: PR + merge prep

- [ ] **Step 1: Confirm commits on branch**

```bash
cd D:/ai-webtoon-studio
git log --oneline feat/c-real-scene-anchor..feat/d-motion-comic-compose
```

Expected: ~17 commits — one per task.

- [ ] **Step 2: Diff summary**

```bash
git diff --stat feat/c-real-scene-anchor..feat/d-motion-comic-compose
```

Expected: roughly 6–8 source files modified + 5–7 new test files.

- [ ] **Step 3: Push branch**

```bash
git push -u origin feat/d-motion-comic-compose
```

- [ ] **Step 4: Optional — create PR**

The C PR (#3) is still open against `main`. Choose:
- **Stack on C:** target the PR against `feat/c-real-scene-anchor` (D's base) so the diff is small and focused on D scope.
- **Roll into the same PR:** if C hasn't merged yet and the team prefers one big PR, merge feat/d-motion-comic-compose into feat/c-real-scene-anchor and push to update PR #3.

Either choice is mechanical from here. The plan does not prescribe one; ask the user.

---

## Summary

- **Files created:** 8 source/test files
  - `apps/api/app/services/video/compose_dispatch.py`
  - `apps/api/app/workers/episode_compose_worker.py`
  - `apps/api/migrations/versions/023_episode_compose_dedup_index.py`
  - `apps/api/tests/unit/workers/_episode_helpers.py`
  - `apps/api/tests/unit/workers/test_episode_compose_dispatch.py`
  - `apps/api/tests/unit/workers/test_episode_compose_worker.py`
  - `apps/api/tests/unit/workers/test_episode_compose_ws_events.py`
  - `apps/api/tests/unit/workers/test_episode_video_dispatch_hook.py`
  - `apps/api/tests/unit/routes/test_episode_compose_routes.py`
  - `apps/api/tests/unit/test_phase_d_real_impl.py`
  - `apps/api/tests/integration/video/__init__.py`
  - `apps/api/tests/integration/video/test_episode_compose_e2e.py`

- **Files modified:** 3
  - `apps/api/app/workers/episode_video_worker.py` — auto-trigger hook
  - `apps/api/app/api/routes/episode_video.py` — two new routes
  - `apps/api/app/celery_app.py` — register new worker module

- **Tasks:** 17 task commits.
- **New routes:** 2 (`GET /episode/compose-jobs/{job_id}`, `POST /episode/{N}/compose-video/retry`).
- **New WS events:** 4 (`episode_compose_created`, `episode_compose_progress`, `episode_compose_done`, `episode_compose_failed`).

## Test plan

- [x] Unit: dispatch helper covers happy path, all skip cases, dedup, race handling — 10 tests.
- [x] Unit: compose worker covers happy path, latest-per-index resolution, four failure paths, concat list ordering — 7 tests.
- [x] Unit: WS event emission — 2 tests.
- [x] Unit: auto-trigger hook in episode_video_worker — 3 tests.
- [x] Unit: API routes (compose status + retry) — 4 tests.
- [x] Static-source regression: 5 tests to prevent silent rollback.
- [x] Integration: full e2e dispatch → compose flow with in-memory storage — 1 test.
- [x] Migration: upgrade + downgrade cycle clean on SQLite (Postgres index is no-op there).
- [ ] Manual smoke: run a real episode through the pipeline against production Doubao + MinIO + ffmpeg binary; confirm a playable MP4 lands at the expected MinIO key.

## Self-Review

**Spec coverage:**
- ✅ Architecture (Section 2 of spec): worker + dispatch helper + auto-trigger — Tasks 3.1, 1.2, 4.1.
- ✅ Data model (Section 3): `Job(type='episode_video_compose')` reuse + migration — Tasks 1.2, 2.1.
- ✅ Compose worker pipeline (Section 4): download → ffmpeg concat → upload, all error codes — Tasks 3.1–3.4.
- ✅ Auto-trigger hook (Section 5): episode_video_worker change + helper — Tasks 1.2, 4.1.
- ✅ API + WebSocket (Section 6): two endpoints + four WS events — Tasks 5.1, 5.2, 6.1.
- ✅ Testing strategy (Section 7): all named test files implemented — Tasks 1.x, 3.x, 4.1, 5.x, 6.1, 7.2, 8.1.

**Placeholder scan:** no TBD / TODO / "similar to" patterns in any task body. Every code step has complete code.

**Type/signature consistency:**
- `_maybe_enqueue_episode_compose(db, project_id, episode_number)` — same arity in dispatch test (1.2), retry route handwriting (5.2), e2e test (8.1).
- `_execute_compose_sync(job_id)` — same signature in worker (3.1), worker tests (3.2–3.4, 6.1), e2e (8.1).
- `_push_episode_compose_update(project_id, episode_number, event_type, data)` — same signature in worker (6.1), tests (6.1).
- Compose Job row schema (`type`, `provider`, `inputs_json.episode_number`, `inputs_json.expected_clip_count`, `outputs_json.video_url`, `outputs_json.clip_count`, `outputs_json.duration_sec`) — consistent across dispatch test, worker test, route test, e2e test.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-11-d-motion-comic-video-compose.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Same workflow that drove the C implementation to completion.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
