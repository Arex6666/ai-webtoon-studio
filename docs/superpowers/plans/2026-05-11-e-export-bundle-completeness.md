# E — Export Bundle Completeness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the two real bugs in `BundleBuilder.build()`, integrate D's motion-comic MP4 into the bundle, and add the unit + integration tests the export pipeline has never had.

**Architecture:** Two surgical fixes to `BundleBuilder.build()` (wire collector results into `write_bundle_root_files`; call `ExportGate.validate_or_raise`); two new private helpers (`_collect_chapter_video`, `_fetch_chapter_video`) that find and download the D compose MP4 by chapter `order_index` convention; one additive field on `BundleManifest` (`chapter_video: Optional[BundleChapterVideo]`); ~18 new tests for the previously untested export subsystem.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, Pydantic v2, pytest, in-memory SQLite for integration.

**Spec:** `docs/superpowers/specs/2026-05-11-e-export-bundle-completeness-design.md`

---

## Pre-flight

- [ ] **Step 1: Confirm current branch**

```bash
cd D:/ai-webtoon-studio
git rev-parse --abbrev-ref HEAD
```

Expected: `feat/e-export-bundle-completeness`. If not, `git checkout feat/e-export-bundle-completeness`.

- [ ] **Step 2: Confirm the spec is in place**

```bash
ls docs/superpowers/specs/2026-05-11-e-export-bundle-completeness-design.md
```

Expected: file exists.

- [ ] **Step 3: Confirm Python interpreter**

```bash
py -3.13 -c "import fastapi, sqlalchemy, pydantic; print('deps OK')"
```

Expected: `deps OK`. (Per project memory: `py -3.13` is the project interpreter.)

- [ ] **Step 4: Sanity-check the prior C+D suite still passes**

```bash
cd /d/ai-webtoon-studio/apps/api
py -3.13 -m pytest tests/unit/workers tests/integration/video tests/integration/scene tests/unit/services/scene tests/unit/services/scene_anchor 2>&1 | tail -3
```

Expected: all passed (no regressions introduced by branch state).

---

## Group 1: Manifest schema — `chapter_video` field

### Task 1.1: Add `BundleChapterVideo` + optional `BundleManifest.chapter_video`

**Files:**
- Modify: `apps/api/app/schemas/bundle_manifest.py`
- Test: `apps/api/tests/unit/services/export/test_bundle_manifest_chapter_video_field.py` (new)
- Create: `apps/api/tests/unit/services/export/__init__.py` (empty)

- [ ] **Step 1: Create the test package marker**

```bash
cd /d/ai-webtoon-studio
mkdir -p apps/api/tests/unit/services/export
type nul > apps/api/tests/unit/services/export/__init__.py
```

(On macOS/Linux: `touch apps/api/tests/unit/services/export/__init__.py`.)

- [ ] **Step 2: Write the failing test**

`apps/api/tests/unit/services/export/test_bundle_manifest_chapter_video_field.py`:

```python
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
```

- [ ] **Step 3: Run — expect ImportError**

```bash
cd /d/ai-webtoon-studio/apps/api
py -3.13 -m pytest tests/unit/services/export/test_bundle_manifest_chapter_video_field.py -v
```

Expected: FAIL with `ImportError: cannot import name 'BundleChapterVideo' from 'app.schemas.bundle_manifest'`.

- [ ] **Step 4: Implement the schema additions**

In `apps/api/app/schemas/bundle_manifest.py`, **insert** the new model definition just above `class BundleManifest(BaseModel):` (around line 73):

```python
class BundleChapterVideo(BaseModel):
    """Phase E: reference to the D motion-comic MP4 for this chapter."""
    path: str = Field("chapter_video/compose.mp4", description="路径（相对 bundle 根目录）")
    source_compose_job_id: str = Field(..., description="产生此视频的 episode_video_compose Job ID")
    duration_sec: Optional[float] = Field(None, description="时长秒数（来自 compose Job outputs）")
    clip_count: Optional[int] = Field(None, description="参与拼接的 clip 数量")
    size_bytes: Optional[int] = Field(None, description="最终 MP4 字节数")
```

Then **add** one field to `BundleManifest` (insert near the other Optional fields, after `qa_summary`):

```python
    # Phase E: D motion-comic video reference (optional — present only when a
    # succeeded episode_video_compose exists for this chapter's order_index)
    chapter_video: Optional["BundleChapterVideo"] = None
```

- [ ] **Step 5: Run — expect pass**

```bash
py -3.13 -m pytest tests/unit/services/export/test_bundle_manifest_chapter_video_field.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
cd /d/ai-webtoon-studio
git add apps/api/app/schemas/bundle_manifest.py \
        apps/api/tests/unit/services/export/__init__.py \
        apps/api/tests/unit/services/export/test_bundle_manifest_chapter_video_field.py
git commit -m "feat(api): BundleManifest.chapter_video optional field (E)"
```

---

## Group 2: Shared test helpers

### Task 2.1: Factory helpers for export tests

**Files:**
- Create: `apps/api/tests/unit/services/export/_helpers.py`

- [ ] **Step 1: Write the helper module**

`apps/api/tests/unit/services/export/_helpers.py`:

```python
"""Shared fixtures for export bundle unit tests (Phase E)."""
from datetime import datetime, timedelta
from typing import Optional

from app.models import Chapter, Job, Panel, LayerPack


def make_chapter(
    chapter_id: str = "ch-1",
    project_id: str = "p-1",
    title: str = "Test Chapter",
    order_index: int = 1,
) -> Chapter:
    return Chapter(
        id=chapter_id,
        project_id=project_id,
        title=title,
        order_index=order_index,
        layout_json={},
        status="storyboarded",
    )


def make_compose_job(
    job_id: str,
    project_id: str,
    episode_number: int,
    status: str = "succeeded",
    video_url: Optional[str] = "episode_videos/p-1/ep1/compose_x.mp4",
    duration_sec: float = 12.0,
    clip_count: int = 3,
    size_bytes: int = 4096,
    finished_at: Optional[datetime] = None,
) -> Job:
    return Job(
        id=job_id,
        type="episode_video_compose",
        project_id=project_id,
        provider="ffmpeg",
        status=status,
        progress=1.0 if status == "succeeded" else 0.0,
        finished_at=finished_at or (datetime.utcnow() if status == "succeeded" else None),
        inputs_json={"episode_number": episode_number, "expected_clip_count": clip_count},
        outputs_json=(
            {
                "video_url": video_url,
                "duration_sec": duration_sec,
                "clip_count": clip_count,
                "size_bytes": size_bytes,
            } if status == "succeeded" and video_url else None
        ),
    )


def time_offset(seconds: int) -> datetime:
    return datetime.utcnow() + timedelta(seconds=seconds)
```

- [ ] **Step 2: Sanity check — file is a private helper, not collected as tests**

The leading underscore in `_helpers.py` plus the absence of `test_` prefix mean pytest won't collect it. No assertion needed.

- [ ] **Step 3: Commit**

```bash
cd /d/ai-webtoon-studio
git add apps/api/tests/unit/services/export/_helpers.py
git commit -m "test(api): export bundle test helpers (E)"
```

---

## Group 3: `_collect_chapter_video` helper

### Task 3.1: Add helper + 4 unit tests

**Files:**
- Modify: `apps/api/app/services/export/bundle_builder.py`
- Test: `apps/api/tests/unit/services/export/test_collect_chapter_video.py` (new)

- [ ] **Step 1: Write the failing test**

`apps/api/tests/unit/services/export/test_collect_chapter_video.py`:

```python
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
```

- [ ] **Step 2: Run — expect failure (no helper)**

```bash
cd /d/ai-webtoon-studio/apps/api
py -3.13 -m pytest tests/unit/services/export/test_collect_chapter_video.py -v
```

Expected: FAIL — `AttributeError: 'BundleBuilder' object has no attribute '_collect_chapter_video'`.

- [ ] **Step 3: Implement the helper**

In `apps/api/app/services/export/bundle_builder.py`:

Update the imports at the top of the file. Replace:

```python
from app.models import Chapter, Panel, LayerPack, Job, RenderJob
from app.schemas.bundle_manifest import (
    BundleManifest, BundlePanelEntry, BundleChapterInfo, 
    BundleProvenance, BundleQASummary, ChapterJsonSpec, PanelJsonSpec,
    AssetsLockSpec, ProvenanceJobsSpec
)
```

With (one new import added):

```python
from app.models import Chapter, Panel, LayerPack, Job, RenderJob
from app.schemas.bundle_manifest import (
    BundleManifest, BundlePanelEntry, BundleChapterInfo, 
    BundleProvenance, BundleQASummary, ChapterJsonSpec, PanelJsonSpec,
    AssetsLockSpec, ProvenanceJobsSpec, BundleChapterVideo,
)
```

Then **add** the helper as a method on `BundleBuilder`. Insert it just before `# ==================== Step 5: 写入根目录文件 ====================` (around line 388):

```python
    # ==================== Step 4.6: Phase E — chapter video ====================

    def _collect_chapter_video(
        self, chapter_snapshot: ChapterSnapshot
    ) -> Optional[tuple[BundleChapterVideo, str]]:
        """Phase E: find the D compose job whose episode_number matches this
        chapter's order_index. Returns (manifest_entry, minio_video_url) or
        None. Picks the most recent succeeded compose if multiple exist.
        """
        chapter = self.db.query(Chapter).filter(
            Chapter.id == chapter_snapshot.chapter_id
        ).first()
        if chapter is None or chapter.order_index is None:
            return None

        candidates = (
            self.db.query(Job)
            .filter(
                Job.type == "episode_video_compose",
                Job.project_id == chapter_snapshot.project_id,
                Job.status == "succeeded",
            )
            .all()
        )
        matching = [
            j for j in candidates
            if (j.inputs_json or {}).get("episode_number") == chapter.order_index
        ]
        if not matching:
            return None

        latest = max(matching, key=lambda j: j.finished_at or datetime.min)
        outputs = latest.outputs_json or {}
        video_url = outputs.get("video_url")
        if not video_url:
            return None

        info = BundleChapterVideo(
            path="chapter_video/compose.mp4",
            source_compose_job_id=latest.id,
            duration_sec=outputs.get("duration_sec"),
            clip_count=outputs.get("clip_count"),
            size_bytes=outputs.get("size_bytes"),
        )
        return info, video_url
```

- [ ] **Step 4: Run — expect 4 pass**

```bash
py -3.13 -m pytest tests/unit/services/export/test_collect_chapter_video.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd /d/ai-webtoon-studio
git add apps/api/app/services/export/bundle_builder.py \
        apps/api/tests/unit/services/export/test_collect_chapter_video.py
git commit -m "feat(api): BundleBuilder._collect_chapter_video helper (E)"
```

---

## Group 4: `_fetch_chapter_video` helper

### Task 4.1: Add fetch helper + silent-skip test

**Files:**
- Modify: `apps/api/app/services/export/bundle_builder.py`
- Test: `apps/api/tests/unit/services/export/test_fetch_chapter_video.py` (new)

- [ ] **Step 1: Write the failing test**

`apps/api/tests/unit/services/export/test_fetch_chapter_video.py`:

```python
"""Unit tests for BundleBuilder._fetch_chapter_video (Phase E)."""
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.export.bundle_builder import BundleBuilder
from app.services.export.bundle_models import BundleBuildContext


def _make_builder() -> BundleBuilder:
    ctx = BundleBuildContext(
        export_id="exp-1",
        job_id="job-1",
        chapter_id="ch-1",
    )
    builder = BundleBuilder(db=MagicMock(), context=ctx)
    builder.object_store = MagicMock()
    return builder


@pytest.mark.asyncio
async def test_fetch_chapter_video_creates_directory_and_calls_download(tmp_path):
    builder = _make_builder()
    # Capture download_to_file calls
    captured = {}

    async def fake_download(url_or_key, local_path):
        captured["url"] = url_or_key
        captured["path"] = local_path
        # Simulate writing the file so subsequent code can read it
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(b"FAKE_MP4")

    builder.object_store.download_to_file = fake_download

    await builder._fetch_chapter_video(str(tmp_path), "episode_videos/p/ep1/compose.mp4")

    assert captured["url"] == "episode_videos/p/ep1/compose.mp4"
    assert captured["path"] == os.path.join(str(tmp_path), "chapter_video", "compose.mp4")
    # Directory should have been created
    assert os.path.isdir(os.path.join(str(tmp_path), "chapter_video"))
    # File should exist with the bytes the fake wrote
    with open(captured["path"], "rb") as f:
        assert f.read() == b"FAKE_MP4"
```

- [ ] **Step 2: Run — expect failure (no helper)**

```bash
cd /d/ai-webtoon-studio/apps/api
py -3.13 -m pytest tests/unit/services/export/test_fetch_chapter_video.py -v
```

Expected: FAIL — `AttributeError: 'BundleBuilder' object has no attribute '_fetch_chapter_video'`.

- [ ] **Step 3: Implement the helper**

In `apps/api/app/services/export/bundle_builder.py`, **append** to the Phase E section you started in Task 3.1 (just below `_collect_chapter_video`):

```python
    async def _fetch_chapter_video(
        self, staging_dir: str, video_url: str
    ) -> None:
        """Phase E: download the chapter compose MP4 into the staging directory.

        Caller is responsible for handling exceptions — the silent-skip policy
        lives at the build() call site, not here, so this helper stays simple
        and testable.
        """
        target_dir = os.path.join(staging_dir, "chapter_video")
        os.makedirs(target_dir, exist_ok=True)
        target_path = os.path.join(target_dir, "compose.mp4")
        await self.object_store.download_to_file(video_url, target_path)
        logger.info(f"[Bundle] Downloaded chapter video to {target_path}")
```

- [ ] **Step 4: Run — expect 1 pass**

```bash
py -3.13 -m pytest tests/unit/services/export/test_fetch_chapter_video.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
cd /d/ai-webtoon-studio
git add apps/api/app/services/export/bundle_builder.py \
        apps/api/tests/unit/services/export/test_fetch_chapter_video.py
git commit -m "feat(api): BundleBuilder._fetch_chapter_video helper (E)"
```

---

## Group 5: Wire collectors + gate + chapter video into `build()`

### Task 5.1: Test that `build()` calls `write_bundle_root_files` with all three new kwargs

**Files:**
- Test: `apps/api/tests/unit/services/export/test_build_wires_collectors.py` (new)
- Modify: `apps/api/app/services/export/bundle_builder.py` (`build()` method)
- Modify: `apps/api/app/services/export/bundle_builder.py` (`write_bundle_root_files` signature — add `chapter_video=` kwarg)

- [ ] **Step 1: Write the failing test**

`apps/api/tests/unit/services/export/test_build_wires_collectors.py`:

```python
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
```

- [ ] **Step 2: Run — expect failure (kwargs not passed yet)**

```bash
cd /d/ai-webtoon-studio/apps/api
py -3.13 -m pytest tests/unit/services/export/test_build_wires_collectors.py -v
```

Expected: ~5 FAILures — kwargs missing in `write_bundle_root_files` call.

- [ ] **Step 3: Update `write_bundle_root_files` signature**

In `apps/api/app/services/export/bundle_builder.py`, around line 390, update the `write_bundle_root_files` method signature to accept the new `chapter_video=` kwarg.

**Current signature (lines ~390-397):**

```python
    def write_bundle_root_files(
        self,
        staging_dir: str,
        chapter_snapshot: ChapterSnapshot,
        panel_plans: List[PanelArtifactPlan],
        assets_lock: Optional[AssetsLockSpec] = None,
        provenance_jobs: Optional[ProvenanceJobsSpec] = None
    ) -> BundleManifest:
```

**New signature:**

```python
    def write_bundle_root_files(
        self,
        staging_dir: str,
        chapter_snapshot: ChapterSnapshot,
        panel_plans: List[PanelArtifactPlan],
        assets_lock: Optional[AssetsLockSpec] = None,
        provenance_jobs: Optional[ProvenanceJobsSpec] = None,
        chapter_video: Optional[BundleChapterVideo] = None,
    ) -> BundleManifest:
```

Then inside the method body, find the `BundleManifest(...)` constructor call (around line 459). Add `chapter_video=chapter_video,` to the kwargs (after `provenance=...`):

```python
        manifest = BundleManifest(
            spec_version=self.SPEC_VERSION,
            bundle_id=bundle_id,
            chapter=BundleChapterInfo(
                chapter_id=chapter_snapshot.chapter_id,
                chapter_title=chapter_snapshot.title,
                chapter_version=chapter_snapshot.version,
                project_id=chapter_snapshot.project_id,
                panel_count=chapter_snapshot.panel_count,
                total_duration_sec=chapter_snapshot.total_duration_sec
            ),
            panels=panel_entries,
            qa_summary=qa_summary,
            provenance=BundleProvenance(
                generated_at=now.isoformat(),
                export_job_id=self.context.job_id,
                bundle_spec_version=self.SPEC_VERSION
            ),
            chapter_video=chapter_video,
        )
```

- [ ] **Step 4: Update `build()` to call collectors, gate, and chapter video**

In `apps/api/app/services/export/bundle_builder.py`, add imports for the collector classes near the top (after the existing service imports). Find:

```python
from app.services.export.bundle_models import (
    ChapterSnapshot, PanelSnapshot, PanelArtifactPlan, 
    BundleBuildContext, BundleBuildResult, GateCheckResult
)
from app.services.export.bundle_errors import (
    BundleBuildError, MissingArtifactError, CorruptManifestError,
    ChapterNotFoundError, NoPanelsError, NoLayerPackError
)
```

**Replace with** (add three new imports):

```python
from app.services.export.bundle_models import (
    ChapterSnapshot, PanelSnapshot, PanelArtifactPlan, 
    BundleBuildContext, BundleBuildResult, GateCheckResult
)
from app.services.export.bundle_errors import (
    BundleBuildError, MissingArtifactError, CorruptManifestError,
    ChapterNotFoundError, NoPanelsError, NoLayerPackError
)
from app.services.export.asset_lock_resolver import AssetLockResolver
from app.services.export.provenance_collector import ProvenanceCollector
from app.services.export.export_gate import ExportGate
```

Then **modify `build()`** (around lines 599-700). Find the block:

```python
            # Step 4.5: 上传预览图
            self.context.report_progress("packaging", 0.65, "Uploading previews...")
            await self.upload_panel_previews(staging_dir, panel_plans)
            
            # Step 5: 写入根目录文件
            self.context.report_progress("packaging", 0.7, "Generating bundle files...")
            manifest = self.write_bundle_root_files(
                staging_dir, 
                chapter_snapshot, 
                panel_plans
            )
```

**Replace with:**

```python
            # Step 4.5: 上传预览图
            self.context.report_progress("packaging", 0.65, "Uploading previews...")
            await self.upload_panel_previews(staging_dir, panel_plans)

            # Step 4.6 (Phase E): collect assets lock, provenance, chapter video
            self.context.report_progress("packaging", 0.67, "Collecting assets and provenance...")
            assets_lock = AssetLockResolver(self.db).resolve(chapter_snapshot, panel_plans)
            provenance_jobs = ProvenanceCollector(self.db).collect(chapter_snapshot, panel_plans)

            chapter_video_info = None
            chapter_video_result = self._collect_chapter_video(chapter_snapshot)
            if chapter_video_result is not None:
                chapter_video_info, video_url = chapter_video_result
                try:
                    await self._fetch_chapter_video(staging_dir, video_url)
                except Exception as e:
                    logger.warning(
                        f"[Bundle] chapter_video download failed: {e}; bundling without video"
                    )
                    chapter_video_info = None

            # Step 4.7 (Phase E): export gate
            self.context.report_progress("packaging", 0.68, "Running export gate...")
            ExportGate(self.db).validate_or_raise(
                chapter_snapshot, panel_plans, allow_qa_failure=True
            )

            # Step 5: 写入根目录文件
            self.context.report_progress("packaging", 0.7, "Generating bundle files...")
            manifest = self.write_bundle_root_files(
                staging_dir,
                chapter_snapshot,
                panel_plans,
                assets_lock=assets_lock,
                provenance_jobs=provenance_jobs,
                chapter_video=chapter_video_info,
            )
```

- [ ] **Step 5: Run — expect 5 pass**

```bash
py -3.13 -m pytest tests/unit/services/export/test_build_wires_collectors.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
cd /d/ai-webtoon-studio
git add apps/api/app/services/export/bundle_builder.py \
        apps/api/tests/unit/services/export/test_build_wires_collectors.py
git commit -m "fix(api): wire AssetLockResolver + ProvenanceCollector + ExportGate + chapter_video into BundleBuilder.build (E)"
```

---

## Group 6: Gate enforcement test

### Task 6.1: Verify gate failure surfaces as `GATE_REJECTED` BundleBuildResult

**Files:**
- Test: `apps/api/tests/unit/services/export/test_export_gate_blocks_export.py` (new)

- [ ] **Step 1: Write the failing test**

`apps/api/tests/unit/services/export/test_export_gate_blocks_export.py`:

```python
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
```

- [ ] **Step 2: Run — expect 2 pass (gate is already wired by Task 5.1)**

```bash
py -3.13 -m pytest tests/unit/services/export/test_export_gate_blocks_export.py -v
```

Expected: 2 passed.

- [ ] **Step 3: Commit**

```bash
cd /d/ai-webtoon-studio
git add apps/api/tests/unit/services/export/test_export_gate_blocks_export.py
git commit -m "test(api): gate rejection surfaces as GATE_REJECTED BundleBuildResult (E)"
```

---

## Group 7: Collector smoke tests

### Task 7.1: AssetLockResolver + ProvenanceCollector empty-input smoke

**Files:**
- Test: `apps/api/tests/unit/services/export/test_asset_lock_resolver_smoke.py` (new)
- Test: `apps/api/tests/unit/services/export/test_provenance_collector_smoke.py` (new)

- [ ] **Step 1: Write `test_asset_lock_resolver_smoke.py`**

```python
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
```

- [ ] **Step 2: Write `test_provenance_collector_smoke.py`**

```python
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
```

- [ ] **Step 3: Run both — expect 2 pass**

```bash
cd /d/ai-webtoon-studio/apps/api
py -3.13 -m pytest tests/unit/services/export/test_asset_lock_resolver_smoke.py \
                   tests/unit/services/export/test_provenance_collector_smoke.py -v
```

Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
cd /d/ai-webtoon-studio
git add apps/api/tests/unit/services/export/test_asset_lock_resolver_smoke.py \
        apps/api/tests/unit/services/export/test_provenance_collector_smoke.py
git commit -m "test(api): collector smoke tests for AssetLockResolver + ProvenanceCollector (E)"
```

---

## Group 8: Static-source regression

### Task 8.1: Phase E real-impl regression test

**Files:**
- Create: `apps/api/tests/unit/test_phase_e_real_impl.py`

- [ ] **Step 1: Write the test**

```python
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
```

- [ ] **Step 2: Run — expect 6 pass**

```bash
cd /d/ai-webtoon-studio/apps/api
py -3.13 -m pytest tests/unit/test_phase_e_real_impl.py -v
```

Expected: 6 passed.

- [ ] **Step 3: Commit**

```bash
cd /d/ai-webtoon-studio
git add apps/api/tests/unit/test_phase_e_real_impl.py
git commit -m "test(api): static-source regression for Phase E real impl (E)"
```

---

## Group 9: Integration e2e

### Task 9.1: End-to-end bundle build with in-memory storage

**Files:**
- Create: `apps/api/tests/integration/export/__init__.py` (empty)
- Create: `apps/api/tests/integration/export/test_bundle_e2e.py`

- [ ] **Step 1: Create the package marker**

```bash
cd /d/ai-webtoon-studio
mkdir -p apps/api/tests/integration/export
type nul > apps/api/tests/integration/export/__init__.py
```

(On macOS/Linux: `touch apps/api/tests/integration/export/__init__.py`.)

- [ ] **Step 2: Write the e2e test**

`apps/api/tests/integration/export/test_bundle_e2e.py`:

```python
"""End-to-end Phase E bundle build with in-memory SQLite + patched object_store.

Verifies the full pipeline produces a valid zip that includes the D motion-comic
MP4 when a succeeded compose job exists for the chapter's order_index, and
gracefully omits it when no compose exists.
"""
import asyncio
import io
import json
import os
import zipfile
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401 — register all models
from app.models import Chapter, Panel, LayerPack, Job, Project
from app.models.base import Base
from app.schemas.bundle_manifest import BundleManifest
from app.services.export.bundle_builder import BundleBuilder
from app.services.export.bundle_models import BundleBuildContext


def _drive_build(builder: BundleBuilder):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(builder.build())
    finally:
        loop.close()


def _seed_chapter(db, chapter_id="ch-1", project_id="p-1", order_index=3):
    """Insert a minimal project + chapter + one panel + one LayerPack."""
    # Create project
    project = Project(id=project_id, name="Test Project")
    db.add(project)

    # Chapter
    chapter = Chapter(
        id=chapter_id,
        project_id=project_id,
        title="Test Chapter",
        order_index=order_index,
        layout_json={},
        status="storyboarded",
    )
    db.add(chapter)

    # Panel
    panel = Panel(
        id="panel-1",
        chapter_id=chapter_id,
        order_index=0,
        spec_json={"shot": {"durationSec": 3.0}},
        render_status="completed",
        qa_score=0.85,
    )
    db.add(panel)

    # LayerPack
    layerpack = LayerPack(
        id="lp-1",
        panel_id="panel-1",
        status="completed",
        file_full="images/panel1/full.png",
        full_url="images/panel1/full.png",
    )
    db.add(layerpack)
    panel.active_layer_pack_id = "lp-1"

    db.commit()
    return chapter, panel, layerpack


def _seed_compose_job(db, project_id="p-1", episode_number=3):
    """Insert a succeeded episode_video_compose Job matching the chapter."""
    job = Job(
        id="comp-1",
        type="episode_video_compose",
        project_id=project_id,
        provider="ffmpeg",
        status="succeeded",
        progress=1.0,
        finished_at=datetime.utcnow(),
        inputs_json={"episode_number": episode_number, "expected_clip_count": 3},
        outputs_json={
            "video_url": "episode_videos/p-1/ep3/compose_comp-1.mp4",
            "duration_sec": 12.0,
            "clip_count": 3,
            "size_bytes": 1024,
        },
    )
    db.add(job)
    db.commit()
    return job


def _make_in_memory_object_store(in_memory: dict):
    """Build a MagicMock object_store that uses in_memory as backing storage."""
    store = MagicMock()

    async def fake_download_to_file(url_or_key, local_path):
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        data = in_memory.get(url_or_key, b"FAKE_BYTES_FOR_" + url_or_key.encode())
        with open(local_path, "wb") as f:
            f.write(data)

    async def fake_upload_file(local_path, target_key, content_type=None):
        with open(local_path, "rb") as f:
            in_memory[target_key] = f.read()
        return f"http://test/{target_key}"

    store.download_to_file = fake_download_to_file
    store.upload_file = fake_upload_file
    return store


def test_e2e_bundle_includes_chapter_video_when_compose_exists(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    chapter, panel, layerpack = _seed_chapter(db, order_index=3)
    _seed_compose_job(db, episode_number=3)

    in_memory = {
        "images/panel1/full.png": b"FAKE_PNG_BYTES",
        "episode_videos/p-1/ep3/compose_comp-1.mp4": b"FAKE_COMPOSE_MP4",
    }
    object_store = _make_in_memory_object_store(in_memory)

    ctx = BundleBuildContext(
        export_id="exp-1",
        job_id="job-1",
        chapter_id=chapter.id,
    )
    builder = BundleBuilder(db=db, context=ctx)
    builder.object_store = object_store

    result = _drive_build(builder)

    assert result.success is True, f"Build failed: {result.error_message}"

    # Find the uploaded zip in in_memory
    zip_keys = [k for k in in_memory if k.endswith(".zip")]
    assert len(zip_keys) == 1
    zip_bytes = in_memory[zip_keys[0]]

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        # Required root files
        assert "manifest.json" in names
        assert "chapter.json" in names
        assert "assets.json" in names
        assert "provenance/jobs.json" in names
        # Phase E addition
        assert "chapter_video/compose.mp4" in names
        assert zf.read("chapter_video/compose.mp4") == b"FAKE_COMPOSE_MP4"
        # Manifest parses with chapter_video set
        manifest_data = json.loads(zf.read("manifest.json"))
        manifest = BundleManifest(**manifest_data)
        assert manifest.chapter_video is not None
        assert manifest.chapter_video.source_compose_job_id == "comp-1"
        assert manifest.chapter_video.path == "chapter_video/compose.mp4"

    db.close()


def test_e2e_bundle_omits_chapter_video_when_no_compose(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    chapter, panel, layerpack = _seed_chapter(db, order_index=3)
    # NO compose job inserted

    in_memory = {"images/panel1/full.png": b"FAKE_PNG_BYTES"}
    object_store = _make_in_memory_object_store(in_memory)

    ctx = BundleBuildContext(
        export_id="exp-2",
        job_id="job-2",
        chapter_id=chapter.id,
    )
    builder = BundleBuilder(db=db, context=ctx)
    builder.object_store = object_store

    result = _drive_build(builder)

    assert result.success is True

    zip_keys = [k for k in in_memory if k.endswith(".zip")]
    assert len(zip_keys) == 1
    zip_bytes = in_memory[zip_keys[0]]

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        # chapter_video MUST be absent
        assert not any(n.startswith("chapter_video/") for n in names)
        # Manifest still parses; chapter_video is None
        manifest_data = json.loads(zf.read("manifest.json"))
        manifest = BundleManifest(**manifest_data)
        assert manifest.chapter_video is None

    db.close()
```

- [ ] **Step 3: Run — expect 2 pass**

```bash
cd /d/ai-webtoon-studio/apps/api
py -3.13 -m pytest tests/integration/export/test_bundle_e2e.py -v
```

Expected: 2 passed.

If a JSON-column mutation issue surfaces (similar to C's bug with `asset.data_json` in place), check that `BundleBuilder` assigns fresh dicts when modifying JSON columns. The current code path doesn't mutate JSON columns directly — `outputs_json` is set whole via assignment in the worker, not mutated in place. No fix needed unless the test surfaces something specific.

- [ ] **Step 4: Commit**

```bash
cd /d/ai-webtoon-studio
git add apps/api/tests/integration/export/__init__.py \
        apps/api/tests/integration/export/test_bundle_e2e.py
git commit -m "test(api): e2e bundle build with chapter video integration (E)"
```

---

## Group 10: Final Verification

### Task 10.1: Run the full B-1 + C + D + E suite

- [ ] **Step 1: Run**

```bash
cd /d/ai-webtoon-studio/apps/api
py -3.13 -m pytest \
    tests/unit/services/agent \
    tests/unit/services/scene \
    tests/unit/services/scene_anchor \
    tests/unit/services/export \
    tests/unit/test_migration_022.py \
    tests/unit/core/test_logging.py \
    tests/unit/workers \
    tests/unit/routes/test_b1_routes_registered.py \
    tests/unit/routes/test_episode_endpoints_delegate.py \
    tests/unit/routes/test_episode_compose_routes.py \
    tests/unit/test_phase_e_deletions.py \
    tests/unit/test_phase_d_real_impl.py \
    tests/unit/test_phase_e_real_impl.py \
    tests/integration/agent \
    tests/integration/scene \
    tests/integration/video \
    tests/integration/export \
    2>&1 | tail -3
```

Expected: ~243+ passed (224 from B-1+C+D + ~19 new from E).

If anything fails, fix in place and re-run before proceeding.

### Task 10.2: App boot smoke

```bash
cd /d/ai-webtoon-studio/apps/api
py -3.13 -c "from app.main import app; print('routes:', len(app.routes))"
py -3.13 -c "from app.services.export.bundle_builder import BundleBuilder; print('hasattr _collect_chapter_video:', hasattr(BundleBuilder, '_collect_chapter_video'))"
py -3.13 -c "from app.schemas.bundle_manifest import BundleChapterVideo, BundleManifest; print('schema OK')"
```

Expected:
- `routes: 248` (no new routes — E is internal pipeline work)
- `hasattr _collect_chapter_video: True`
- `schema OK`

### Task 10.3: PR + merge prep

- [ ] **Step 1: Confirm commits on branch**

```bash
cd /d/ai-webtoon-studio
git log --oneline feat/c-real-scene-anchor..feat/e-export-bundle-completeness
```

Expected: ~12 commits — one per task plus the spec commit.

- [ ] **Step 2: Diff summary**

```bash
git diff --stat feat/c-real-scene-anchor..feat/e-export-bundle-completeness | tail -3
```

Expected: ~3 source files modified (`bundle_builder.py`, `bundle_manifest.py` schema, no schema changes elsewhere) + ~9 new test files.

- [ ] **Step 3: Push branch**

```bash
git push -u origin feat/e-export-bundle-completeness
```

- [ ] **Step 4: Roll-up decision**

The prior pattern was to fold D into the existing C PR (#3) so all the unmerged work ships as one PR. Same options for E:

- **Fold E into PR #3** (B-1 + C + D + E one PR): merge `feat/e-export-bundle-completeness` into `feat/c-real-scene-anchor` and push.
- **Open separate E PR → main**: PR will include all of B-1 + C + D + E (~258 commits total) since none have merged.
- **Stack E on the C/D branch**: PR targeting `feat/c-real-scene-anchor` showing only the E commits.

Ask the user before pushing.

---

## Summary

- **Files created:** 11
  - `apps/api/tests/unit/services/export/__init__.py`
  - `apps/api/tests/unit/services/export/_helpers.py`
  - `apps/api/tests/unit/services/export/test_bundle_manifest_chapter_video_field.py`
  - `apps/api/tests/unit/services/export/test_collect_chapter_video.py`
  - `apps/api/tests/unit/services/export/test_fetch_chapter_video.py`
  - `apps/api/tests/unit/services/export/test_build_wires_collectors.py`
  - `apps/api/tests/unit/services/export/test_export_gate_blocks_export.py`
  - `apps/api/tests/unit/services/export/test_asset_lock_resolver_smoke.py`
  - `apps/api/tests/unit/services/export/test_provenance_collector_smoke.py`
  - `apps/api/tests/unit/test_phase_e_real_impl.py`
  - `apps/api/tests/integration/export/__init__.py`
  - `apps/api/tests/integration/export/test_bundle_e2e.py`

- **Files modified:** 2
  - `apps/api/app/schemas/bundle_manifest.py` — add `BundleChapterVideo` + optional `chapter_video` field
  - `apps/api/app/services/export/bundle_builder.py` — two new methods (`_collect_chapter_video`, `_fetch_chapter_video`), `write_bundle_root_files` gains `chapter_video=` kwarg, `build()` wires three collectors + gate

- **Tasks:** 12 task commits across 10 groups.

## Test plan

- [x] Schema: `BundleManifest.chapter_video` serialises correctly when present + null when absent — 2 tests.
- [x] `_collect_chapter_video`: 4 tests (no compose, null order_index, latest-wins, episode-number filter).
- [x] `_fetch_chapter_video`: 1 test (directory creation + download invocation).
- [x] `build()` wiring: 5 tests (assets_lock kwarg, provenance_jobs kwarg, gate called before root files, chapter_video kwarg passed, silent-skip on download failure).
- [x] Gate enforcement: 2 tests (rejected → `GATE_REJECTED`, passes → write_bundle_root_files runs).
- [x] Collector smoke: 2 tests (AssetLockResolver, ProvenanceCollector empty input).
- [x] Static-source regression: 6 tests preventing rollback.
- [x] Integration: 2 tests (full bundle with chapter_video, full bundle without).
- [ ] Manual: trigger a real bundle export against MinIO + ensure the resulting zip contains `chapter_video/compose.mp4` when a real D compose exists.

## Self-Review

**Spec coverage:**
- ✅ Spec Section "Architecture": 7-step pipeline reflected — Tasks 3.1, 4.1, 5.1.
- ✅ Spec Section "Bundle Layout + Manifest Schema": `BundleChapterVideo` model + optional manifest field — Task 1.1.
- ✅ Spec Section "Bug #1": `assets_lock` + `provenance_jobs` wired — Task 5.1.
- ✅ Spec Section "Bug #2": `ExportGate.validate_or_raise` called — Task 5.1 (verified by Task 6.1).
- ✅ Spec Section "D Integration Helper": `_collect_chapter_video` and `_fetch_chapter_video` — Tasks 3.1 + 4.1.
- ✅ Spec Section "Testing Strategy": all named test files implemented (4 + 1 + 5 + 2 + 1 + 1 + 6 + 2 = 22 actual tests vs ~18 spec estimate; over delivers).

**Placeholder scan:** no TBD / TODO / "similar to" patterns. Every code step has complete code.

**Type/signature consistency:**
- `_collect_chapter_video(chapter_snapshot)` → `Optional[tuple[BundleChapterVideo, str]]` — same signature in helper, tests, and build() wiring.
- `_fetch_chapter_video(staging_dir, video_url) -> None` async — consistent across helper + test + build() wiring.
- `write_bundle_root_files(..., assets_lock=, provenance_jobs=, chapter_video=)` — consistent in signature, build() call site, and assertion in test_build_wires_collectors.
- `BundleChapterVideo(path, source_compose_job_id, duration_sec, clip_count, size_bytes)` — consistent across schema definition, helper construction, manifest test, integration test.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-11-e-export-bundle-completeness.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Fresh subagent per task, two-stage review between tasks. Same flow that drove the C and D implementations.

**2. Inline Execution** — Execute in this session via the executing-plans skill, batch with checkpoints.

Which approach?
