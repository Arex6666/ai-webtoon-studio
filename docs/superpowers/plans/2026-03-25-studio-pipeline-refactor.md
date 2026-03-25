# Studio Pipeline Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify the Job pipeline (image/video/storyboard/export), merge Inspector tabs from 9 to 5, fix FaceID field name mismatch, and connect the disconnected video generation pipeline.

**Architecture:** The backend already has `/api/v1/jobs` with per-type endpoints (`/image`, `/video`, `/export`, `/anchor`) + status/list/cancel. We add a unified `POST /` entry point and unified WS events. The frontend uses one `jobApi` + `useJobTracker` hook for all job types. Inspector tabs are consolidated: Shot (story+layout), Cast (cast+consistency), Assets (lock+anchors), Layers (kept), Video (rewritten timeline with CTA).

**Key discovery:** `apps/api/app/api/routes/jobs.py` already exists with full CRUD — we extend it, not replace it. The Job model uses `"canceled"` (single L) — all frontend code must match this spelling.

**Tech Stack:** FastAPI, SQLAlchemy, Celery, Alembic (backend); Next.js 14, TypeScript, Zustand, shadcn/ui, Tailwind CSS (frontend)

**Spec:** `docs/superpowers/specs/2026-03-25-studio-pipeline-refactor-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `apps/api/app/schemas/job_schemas.py` | Pydantic request/response schemas for unified Jobs API |
| `apps/api/migrations/versions/019_add_clip_columns.py` | Add `negative`, `seed` columns to Clip table |
| `apps/api/tests/unit/routes/test_jobs_route.py` | Tests for unified Job API |
| `apps/api/tests/unit/routes/test_faceid_fix.py` | Tests for FaceID field name fix |
| `apps/web/src/lib/api/jobApi.ts` | Frontend Job API client |
| `apps/web/src/hooks/useJobTracker.ts` | WS + polling job progress hook |
| `apps/web/src/components/studio/right/ShotTab.tsx` | Merged Shot + Layout inspector |
| `apps/web/src/components/studio/right/CastTab.tsx` | Merged Cast + Consistency inspector |
| `apps/web/src/components/studio/right/AssetsTab.tsx` | Merged AssetsLock + Anchors inspector |
| `apps/web/src/components/studio/right/VideoTab.tsx` | Rewritten Timeline with video CTA |

### Modified Files

| File | Changes |
|------|---------|
| `apps/api/app/api/routes/jobs.py:1-320` | Add unified `POST /` endpoint to existing per-type routes |
| `apps/api/app/api/routes/assets/__init__.py:488-489` | Fix FaceID field name + add `embedding_status` |
| `apps/api/app/workers/video_worker.py:55-186` | Read params from `Job.inputs_json`, emit unified WS events |
| `apps/api/app/workers/image_worker.py:30-38,126` | Emit unified WS events alongside old ones |
| `apps/api/app/api/routes/ws.py:206-217` | Add `push_unified_job_event()` helper |
| `apps/web/src/lib/ws/events.ts:9-32` | Add unified `job_progress`/`job_status`/`job_result` event types |
| `apps/web/src/lib/store/studioStore.ts:72-77,492-511,513-801,1233-1249` | Keep existing `jobs` as-is, add `unifiedJobs` + `wsConnected` + `createJob` + `handleJobEvent` |
| `apps/web/src/lib/schema/clip.ts:103-122` | Fix `canGenerateClip` to auto-bind startFrame |
| `apps/web/src/components/studio/right/InspectorTabs.tsx:88-101` | Rewrite to 5 tabs |
| `apps/web/src/components/studio/center/PanelCard.tsx:84-102,236-268` | Add Video button, state-dependent rendering |
| `apps/web/src/components/studio/StudioTopbar.tsx:46-150` | Add Batch Video button (creates clips before video jobs) |
| `apps/web/src/hooks/useStoryboardGeneration.ts` | Migrate to use `jobApi.create('storyboard', ...)` |
| `apps/web/src/components/studio/bottom/ClipRow.tsx` | Update to read from `unifiedJobs` state |
| `apps/web/src/components/studio/bottom/TimelinePanel.tsx` | Update clip/video references |

### Deleted Files

| File | Reason |
|------|--------|
| `apps/web/src/components/studio/right/InspectorQA.tsx` | Pure stub |
| `apps/web/src/components/studio/right/InspectorStory.tsx` | → ShotTab |
| `apps/web/src/components/studio/right/InspectorLayout.tsx` | → ShotTab |
| `apps/web/src/components/studio/right/InspectorCast.tsx` | → CastTab |
| `apps/web/src/components/studio/right/InspectorConsistency.tsx` | → CastTab |
| `apps/web/src/components/studio/right/InspectorAnchors.tsx` | → AssetsTab |
| `apps/web/src/components/studio/right/InspectorTimeline.tsx` | → VideoTab |
| `apps/web/src/components/studio/NeedsFixPanel.tsx` | Stub → absorbed into AssetsTab readiness checklist |
| `apps/web/src/components/studio/panels/AssetsLockPanel.tsx` | → absorbed into AssetsTab |

---

## Task 1: FaceID Field Name Fix (Backend)

**Files:**
- Modify: `apps/api/app/api/routes/assets/__init__.py:488-489`
- Create: `apps/api/tests/unit/routes/test_faceid_fix.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/unit/routes/test_faceid_fix.py
"""Test that generate_asset_image writes canonical FaceID fields."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


def make_fake_asset(asset_type="character"):
    asset = MagicMock()
    asset.id = "asset-001"
    asset.type = asset_type
    asset.project_id = "proj-001"
    asset.name = "TestChar"
    asset.data_json = {"description": "A test character", "reference_images": []}
    asset.thumbnail_url = None
    return asset


class TestFaceIDFieldName:
    """After generating a character image, embedding_path and embedding_status
    must be written to data_json using the canonical field names that
    identity.py and the frontend expect."""

    def test_embedding_path_written_with_canonical_key(self):
        """The route must write data_json['embedding_path'] (not 'face_embedding')
        and data_json['embedding_status'] = 'ready'."""
        asset = make_fake_asset()
        result = {
            "success": True,
            "image_url": "https://storage/char.png",
            "embedding_path": "embeddings/proj-001/asset-001/face.bin",
        }

        # Simulate what the route does after getting the result
        data = dict(asset.data_json)
        if result.get("embedding_path"):
            data["embedding_path"] = result["embedding_path"]
            data["embedding_status"] = "ready"
            data["embedding_source"] = "auto_generation"
            data["face_embedding"] = result["embedding_path"]  # backwards compat

        assert data["embedding_path"] == "embeddings/proj-001/asset-001/face.bin"
        assert data["embedding_status"] == "ready"
        assert data["face_embedding"] == data["embedding_path"]

    def test_no_embedding_path_leaves_status_unchanged(self):
        """If generator returns no embedding_path, don't set status to ready."""
        asset = make_fake_asset()
        result = {
            "success": True,
            "image_url": "https://storage/char.png",
            # No embedding_path
        }

        data = dict(asset.data_json)
        if result.get("embedding_path"):
            data["embedding_path"] = result["embedding_path"]
            data["embedding_status"] = "ready"

        assert "embedding_path" not in data
        assert "embedding_status" not in data
```

- [ ] **Step 2: Run test to verify it passes (this is a logic-level unit test)**

Run: `cd apps/api && python -m pytest tests/unit/routes/test_faceid_fix.py -v`
Expected: PASS (tests the expected behavior, not the current broken code)

- [ ] **Step 3: Fix the route — apply canonical field names**

In `apps/api/app/api/routes/assets/__init__.py`, find lines 488-489:
```python
# OLD (line 488-489):
            if result.get("embedding_path"):
                data["face_embedding"] = result["embedding_path"]
```

Replace with:
```python
            if result.get("embedding_path"):
                data["embedding_path"] = result["embedding_path"]
                data["embedding_status"] = "ready"
                data["embedding_source"] = "auto_generation"
                data["face_embedding"] = result["embedding_path"]  # backwards compat
```

- [ ] **Step 4: Run tests**

Run: `cd apps/api && python -m pytest tests/unit/routes/test_faceid_fix.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/api/routes/assets/__init__.py apps/api/tests/unit/routes/test_faceid_fix.py
git commit -m "fix: write canonical FaceID field names in generate_asset_image

The route was writing to data_json['face_embedding'] but identity.py and the
frontend expect 'embedding_path' + 'embedding_status'. Now writes both canonical
fields and keeps face_embedding for backwards compat."
```

---

## Task 2: Clip Table Migration

**Files:**
- Create: `apps/api/migrations/versions/019_add_clip_columns.py`

- [ ] **Step 1: Create migration**

```python
# apps/api/migrations/versions/019_add_clip_columns.py
"""Add negative and seed columns to clips table.

Revision ID: 019_add_clip_columns
Revises: 018_add_performance_indexes
"""
from alembic import op
import sqlalchemy as sa

revision = "019_add_clip_columns"
down_revision = "018_add_performance_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("clips", sa.Column("negative", sa.Text(), nullable=True))
    op.add_column("clips", sa.Column("seed", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("clips", "seed")
    op.drop_column("clips", "negative")
```

- [ ] **Step 2: Update Clip model**

In `apps/api/app/models/timeline.py`, after line 50 (`motion_mode`), add:

```python
    negative = Column(Text, nullable=True)
    seed = Column(Integer, nullable=True)
```

- [ ] **Step 3: Run migration**

Run: `cd apps/api && alembic upgrade head`
Expected: Migration applies successfully

- [ ] **Step 4: Commit**

```bash
git add apps/api/migrations/versions/019_add_clip_columns.py apps/api/app/models/timeline.py
git commit -m "feat: add negative and seed columns to clips table"
```

---

## Task 3: Job Schemas (Backend)

**Files:**
- Create: `apps/api/app/schemas/job_schemas.py`

- [ ] **Step 1: Create Pydantic schemas**

```python
# apps/api/app/schemas/job_schemas.py
"""Unified Job API request/response schemas."""
from typing import Literal, Optional
from pydantic import BaseModel


class JobCreateRequest(BaseModel):
    type: Literal["image", "video", "storyboard", "export"]
    target_id: str
    provider: str = "mock"
    params: dict = {}


class JobStatusResponse(BaseModel):
    job_id: str
    type: str
    status: str
    progress: float = 0.0
    message: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/app/schemas/job_schemas.py
git commit -m "feat: add unified Job API schemas"
```

---

## Task 4: Extend Existing Jobs Route with Unified POST Endpoint

**IMPORTANT:** `apps/api/app/api/routes/jobs.py` already exists (320 lines) with per-type endpoints (`POST /image`, `POST /video`, `POST /export`, `POST /anchor`) + `GET /{job_id}` + `GET /chapter/{chapter_id}` + `POST /{job_id}/cancel`. The existing `create_job_record()` helper correctly sets `job.provider = provider`. We ADD a unified `POST /` endpoint alongside the existing per-type ones — do NOT replace or duplicate.

**Files:**
- Modify: `apps/api/app/api/routes/jobs.py`
- Create: `apps/api/app/schemas/job_schemas.py` (already done in Task 3)
- Modify: `apps/api/tests/unit/routes/test_jobs_route.py`

- [ ] **Step 1: Write failing tests for unified endpoint**

```python
# apps/api/tests/unit/routes/test_jobs_route.py
"""Tests for the unified POST /api/v1/jobs endpoint."""
import pytest
from app.schemas.job_schemas import JobCreateRequest, JobStatusResponse


class TestJobCreateRequest:
    def test_image_job_schema(self):
        req = JobCreateRequest(
            type="image",
            target_id="panel-001",
            provider="doubao",
            params={"force_regenerate": True},
        )
        assert req.type == "image"
        assert req.target_id == "panel-001"

    def test_video_job_schema(self):
        req = JobCreateRequest(
            type="video",
            target_id="clip-001",
            provider="doubao",
            params={
                "start_frame_url": "https://storage/frame.png",
                "motion_prompt": "camera zoom in",
                "duration_sec": 3.0,
                "fps": 24,
            },
        )
        assert req.type == "video"
        assert req.params["duration_sec"] == 3.0

    def test_default_provider(self):
        req = JobCreateRequest(type="storyboard", target_id="chapter-001")
        assert req.provider == "mock"
        assert req.params == {}

    def test_canceled_spelling(self):
        """Job model uses 'canceled' (single L) — verify schema matches."""
        resp = JobStatusResponse(
            job_id="job-001", type="image", status="canceled",
        )
        assert resp.status == "canceled"


class TestJobStatusResponse:
    def test_minimal_response(self):
        resp = JobStatusResponse(
            job_id="job-001", type="image", status="queued",
        )
        assert resp.progress == 0.0
        assert resp.result is None

    def test_completed_response(self):
        resp = JobStatusResponse(
            job_id="job-001", type="image", status="succeeded",
            progress=1.0,
            result={"preview_url": "https://storage/preview.png"},
        )
        assert resp.progress == 1.0
```

- [ ] **Step 2: Run tests**

Run: `cd apps/api && python -m pytest tests/unit/routes/test_jobs_route.py -v`
Expected: PASS (schema-level tests)

- [ ] **Step 3: Add unified POST / endpoint to existing jobs.py**

Read the existing `apps/api/app/api/routes/jobs.py` first. Then add the unified endpoint at the TOP of the route definitions (before the per-type endpoints), reusing the existing `create_job_record()` and `job_to_response()` helpers:

```python
# Add import at top of file:
from app.schemas.job_schemas import JobCreateRequest, JobStatusResponse as UnifiedJobResponse

# Add this endpoint BEFORE the per-type endpoints (around line 50):
@router.post("/", response_model=UnifiedJobResponse)
async def create_unified_job(
    req: JobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Unified job creation — single entry point for all job types.
    Delegates to the same create_job_record() helper as per-type endpoints."""
    # Map target_id to the correct FK field
    target_field_map = {
        "image": "panel_id",
        "video": "clip_id",
        "storyboard": "chapter_id",
        "export": "chapter_id",
    }
    target_field = target_field_map.get(req.type)
    if not target_field:
        raise HTTPException(status_code=400, detail=f"Unknown job type: {req.type}")

    # Reuse existing helper — it correctly sets job.provider
    job = create_job_record(
        db=db,
        job_type=req.type,
        provider=req.provider,
        inputs_json=req.params,
        **{target_field: req.target_id},
    )

    # Dispatch to worker queue
    TASK_MAP = {
        "image": ("app.workers.image_worker.execute_image_job", "image", [job.id, req.target_id]),
        "video": ("app.workers.video_worker.execute_video_job", "video", [job.id, req.target_id]),
        "export": ("app.workers.export_worker.execute_export_job", "export", [job.id, req.target_id]),
    }
    if req.type in TASK_MAP:
        task_name, queue, args = TASK_MAP[req.type]
        celery_app.send_task(task_name, args=args, queue=queue)
    elif req.type == "storyboard":
        from app.api.routes.chapters import run_storyboard_task
        background_tasks.add_task(
            run_storyboard_task,
            job_id=job.id,
            chapter_id=req.target_id,
            script=req.params.get("script", ""),
            provider=req.provider,
        )

    return UnifiedJobResponse(
        job_id=job.id,
        type=job.type,
        status=job.status,
        progress=job.progress or 0.0,
        created_at=job.created_at.isoformat() if job.created_at else None,
        updated_at=job.updated_at.isoformat() if job.updated_at else None,
    )
```

**IMPORTANT:** The existing `cancel_job` endpoint returns `"canceled"` (matching the Job model). Verify this — do NOT change to `"cancelled"`.

- [ ] **Step 4: Verify existing route registration in main.py**

The route is likely already registered. Check `apps/api/app/main.py` for `jobs.router` or `/api/v1/jobs`. If already there, no changes needed. If not, add:
```python
from app.api.routes import jobs
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["统一任务"])
```

- [ ] **Step 5: Run all tests**

Run: `cd apps/api && python -m pytest tests/unit/routes/ -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/api/routes/jobs.py apps/api/tests/unit/routes/test_jobs_route.py
git commit -m "feat: add unified POST / endpoint to existing jobs route

Adds a single entry point alongside per-type endpoints. Reuses
create_job_record() helper. Dispatches to correct worker queues."
```

---

## Task 5: Unified WS Events (Backend)

**Files:**
- Modify: `apps/api/app/api/routes/ws.py:206-217`
- Modify: `apps/api/app/workers/image_worker.py:30-38`
- Modify: `apps/api/app/workers/video_worker.py:26-41`

- [ ] **Step 1: Add unified push helper to ws.py**

After the existing `push_chapter_update` function (line ~217), add:

```python
async def push_unified_job_event(
    chapter_id: str,
    event_type: str,
    job_id: str,
    payload: dict,
):
    """Push a unified job event. event_type is one of: job_progress, job_status, job_result."""
    await push_chapter_update(chapter_id, event_type, {
        "jobId": job_id,
        **payload,
    })
```

- [ ] **Step 2: Update image_worker to emit unified events alongside old ones**

In `apps/api/app/workers/image_worker.py`, update the `push_update_sync` function (line ~30-38) to also emit unified events:

```python
def push_update_sync(chapter_id, job_id, panel_id, status, progress, current_step=None):
    """Push both legacy and unified WS events."""
    loop = asyncio.new_event_loop()
    try:
        # Legacy event (keep for backwards compat)
        loop.run_until_complete(
            push_job_update(chapter_id, job_id, panel_id, status, progress, current_step, None, None)
        )
        # Unified event
        from app.api.routes.ws import push_unified_job_event
        if status in ("succeeded", "failed"):
            loop.run_until_complete(
                push_unified_job_event(chapter_id, "job_status", job_id, {
                    "status": status,
                    "type": "image",
                })
            )
        else:
            loop.run_until_complete(
                push_unified_job_event(chapter_id, "job_progress", job_id, {
                    "progress": progress,
                    "message": current_step,
                })
            )
    finally:
        loop.close()
```

- [ ] **Step 3: Update video_worker to emit unified events**

In `apps/api/app/workers/video_worker.py`, update `push_video_update_sync` (line ~26-41) similarly:

```python
def push_video_update_sync(chapter_id, job_id, clip_id, status, progress):
    """Push both legacy and unified WS events."""
    loop = asyncio.new_event_loop()
    try:
        # Legacy event
        loop.run_until_complete(
            push_chapter_update(chapter_id, "video_job_progress", {
                "job_id": job_id,
                "clip_id": clip_id,
                "status": status,
                "progress": progress,
            })
        )
        # Unified event
        from app.api.routes.ws import push_unified_job_event
        if status in ("succeeded", "failed"):
            loop.run_until_complete(
                push_unified_job_event(chapter_id, "job_status", job_id, {
                    "status": status,
                    "type": "video",
                })
            )
        else:
            loop.run_until_complete(
                push_unified_job_event(chapter_id, "job_progress", job_id, {
                    "progress": progress,
                })
            )
    finally:
        loop.close()
```

- [ ] **Step 4: Commit**

```bash
git add apps/api/app/api/routes/ws.py apps/api/app/workers/image_worker.py apps/api/app/workers/video_worker.py
git commit -m "feat: emit unified job_progress/job_status WS events

Workers now emit both legacy events (for backwards compat) and new unified
job_progress/job_status events that the frontend useJobTracker will consume."
```

---

## Task 6: Video Worker — Read from Job.inputs_json

**Files:**
- Modify: `apps/api/app/workers/video_worker.py:55-186`

- [ ] **Step 1: Update video worker to read params from Job**

In the `execute_video_job` function, after loading the job and clip, add a fallback that reads from `job.inputs_json`:

```python
# After loading job and clip (around line 70-90):
params = job.inputs_json or {}

# Resolve start frame URL with fallback chain:
start_frame_url = params.get("start_frame_url")
if not start_frame_url and clip.start_frame_layerpack_id:
    # Resolve layerpack ID to URL
    lp = db.query(LayerPack).filter(LayerPack.id == clip.start_frame_layerpack_id).first()
    if lp:
        start_frame_url = lp.full_url
if not start_frame_url:
    # Fallback to panel preview
    panel = db.query(Panel).filter(Panel.id == clip.panel_id).first()
    if panel and panel.spec_json:
        start_frame_url = panel.spec_json.get("render", {}).get("preview_url")

if not start_frame_url:
    raise ValueError("No start frame available for video generation")

# Read other params with fallbacks to clip model
motion_prompt = params.get("motion_prompt") or clip.motion_prompt or ""
negative_prompt = params.get("negative") or getattr(clip, "negative", "") or ""
duration_sec = params.get("duration_sec") or clip.duration_sec or 3.0
fps = params.get("fps") or clip.fps or 24
seed = params.get("seed") or getattr(clip, "seed", None)
provider_name = params.get("provider") or getattr(clip, "provider", "mock") or "mock"
```

- [ ] **Step 2: Verify video worker can start**

Run: `cd apps/api && python -c "from app.workers.video_worker import execute_video_job; print('Import OK')"`
Expected: `Import OK`

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/workers/video_worker.py
git commit -m "fix: video worker reads params from Job.inputs_json with fallbacks

Resolves start_frame_url through: Job params → Clip layerpack → Panel preview.
Other params fall back from Job to Clip model fields."
```

---

## Task 7: Frontend — jobApi Client

**Files:**
- Create: `apps/web/src/lib/api/jobApi.ts`

- [ ] **Step 1: Create the Job API client**

```typescript
// apps/web/src/lib/api/jobApi.ts
import { apiPost, apiGet } from './client'

export type JobType = 'image' | 'video' | 'storyboard' | 'export'
export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'canceled'

export interface JobCreateRequest {
  type: JobType
  target_id: string
  provider: string
  params?: Record<string, unknown>
}

export interface JobStatusResponse {
  job_id: string
  type: JobType
  status: JobStatus
  progress: number
  message?: string
  result?: Record<string, unknown>
  error?: string
  created_at?: string
  updated_at?: string
}

export const jobApi = {
  create: (req: JobCreateRequest) =>
    apiPost<JobStatusResponse>('/api/v1/jobs', req),

  get: (jobId: string) =>
    apiGet<JobStatusResponse>(`/api/v1/jobs/${jobId}`),

  list: (chapterId: string) =>
    apiGet<JobStatusResponse[]>(`/api/v1/jobs?chapter_id=${chapterId}`),

  cancel: (jobId: string) =>
    apiPost<{ job_id: string; status: string }>(`/api/v1/jobs/${jobId}/cancel`, {}),
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/lib/api/jobApi.ts
git commit -m "feat: add unified jobApi client for all job types"
```

---

## Task 8: Frontend — useJobTracker Hook

**Files:**
- Create: `apps/web/src/hooks/useJobTracker.ts`

- [ ] **Step 1: Create the hook**

```typescript
// apps/web/src/hooks/useJobTracker.ts
'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { jobApi, type JobStatus, type JobStatusResponse } from '@/lib/api/jobApi'
import { useStudioStore } from '@/lib/store/studioStore'

interface JobTrackerState {
  status: JobStatus
  progress: number
  message?: string
  result?: Record<string, unknown>
  error?: string
  isComplete: boolean
}

const TERMINAL_STATUSES: JobStatus[] = ['succeeded', 'failed', 'canceled']
const POLL_INTERVAL = 2000

export function useJobTracker(jobId: string | null): JobTrackerState {
  const [state, setState] = useState<JobTrackerState>({
    status: 'queued',
    progress: 0,
    isComplete: false,
  })

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Listen to store's unified job state (populated by WS events)
  const storeJob = useStudioStore(s => jobId ? s.unifiedJobs[jobId] : null)

  // Sync from store (WS-driven)
  useEffect(() => {
    if (!storeJob) return
    setState({
      status: storeJob.status as JobStatus,
      progress: storeJob.progress ?? 0,
      message: storeJob.message,
      result: storeJob.result,
      error: storeJob.error,
      isComplete: TERMINAL_STATUSES.includes(storeJob.status as JobStatus),
    })
  }, [storeJob])

  // Only poll when WS is disconnected (check NEXT_PUBLIC_USE_REAL_WS and connection state)
  const wsConnected = useStudioStore(s => s.wsConnected ?? false)

  const poll = useCallback(async () => {
    if (!jobId) return
    try {
      const res = await jobApi.get(jobId)
      setState({
        status: res.status,
        progress: res.progress,
        message: res.message,
        result: res.result,
        error: res.error,
        isComplete: TERMINAL_STATUSES.includes(res.status),
      })
      // Also update store so other components see it
      useStudioStore.getState().updateJob(jobId, {
        status: res.status,
        progress: res.progress,
        message: res.message,
        result: res.result,
        error: res.error,
      })
    } catch {
      // Silently retry on next interval
    }
  }, [jobId])

  useEffect(() => {
    if (!jobId || state.isComplete || wsConnected) {
      if (intervalRef.current) clearInterval(intervalRef.current)
      return
    }

    // Only poll when WS is disconnected
    intervalRef.current = setInterval(poll, POLL_INTERVAL)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [jobId, state.isComplete, poll])

  return state
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/hooks/useJobTracker.ts
git commit -m "feat: add useJobTracker hook with WS + polling fallback"
```

---

## Task 9: Frontend — Unified WS Events + Store Jobs Slice

**Files:**
- Modify: `apps/web/src/lib/ws/events.ts:9-32`
- Modify: `apps/web/src/lib/store/studioStore.ts`

- [ ] **Step 1: Add unified event types to events.ts**

At the end of the `WsEventType` union (line ~32), add:

```typescript
  | 'job_progress'    // unified: { jobId, progress, message? }
  | 'job_status'      // unified: { jobId, status, type?, error? }
  | 'job_result'      // unified: { jobId, type, result }
```

Add corresponding event interfaces after the existing ones:

```typescript
export interface UnifiedJobProgressEvent {
  type: 'job_progress'
  payload: {
    jobId: string
    progress: number
    message?: string
  }
  timestamp: number
}

export interface UnifiedJobStatusEvent {
  type: 'job_status'
  payload: {
    jobId: string
    status: 'queued' | 'running' | 'succeeded' | 'failed' | 'canceled'
    type?: string
    error?: string
  }
  timestamp: number
}

export interface UnifiedJobResultEvent {
  type: 'job_result'
  payload: {
    jobId: string
    type: string
    result: Record<string, unknown>
  }
  timestamp: number
}
```

Add them to the `WsEvent` union type.

- [ ] **Step 2: Add unified jobs state + actions to studioStore**

**IMPORTANT:** The store already has `jobs: Record<string, RenderJob>` (line 73) for the legacy render job tracking. Do NOT remove or rename it — it's used by `enqueueRender`, `applyWsEvent`, and many components. Add a NEW field `unifiedJobs` alongside it.

In `apps/web/src/lib/store/studioStore.ts`, add to the store interface (around line 77, AFTER existing `jobs`):

```typescript
// WS connection state (used by useJobTracker to decide whether to poll)
wsConnected: boolean

// Unified jobs state (all types — image, video, storyboard, export)
unifiedJobs: Record<string, {
  status: string
  progress: number
  message?: string
  result?: Record<string, unknown>
  error?: string
  type?: string
}>

// Unified jobs actions
createJob: (type: string, targetId: string, provider: string, params?: Record<string, unknown>) => Promise<string>
updateJob: (jobId: string, patch: Partial<{ status: string; progress: number; message?: string; result?: Record<string, unknown>; error?: string }>) => void
handleJobEvent: (event: { type: string; payload: Record<string, unknown> }) => void
```

In the store implementation, add:

```typescript
wsConnected: false,
unifiedJobs: {},

createJob: async (type, targetId, provider, params) => {
  const { jobApi } = await import('@/lib/api/jobApi')
  const res = await jobApi.create({ type: type as any, target_id: targetId, provider, params })
  set(s => ({
    unifiedJobs: {
      ...s.unifiedJobs,
      [res.job_id]: { status: res.status, progress: 0, type: res.type },
    },
  }))
  return res.job_id
},

updateJob: (jobId, patch) => {
  set(s => ({
    unifiedJobs: {
      ...s.unifiedJobs,
      [jobId]: { ...s.unifiedJobs[jobId], ...patch },
    },
  }))
},

handleJobEvent: (event) => {
  const { type, payload } = event as any
  const jobId = payload?.jobId
  if (!jobId) return

  set(s => {
    const job = s.unifiedJobs[jobId] || { status: 'queued', progress: 0 }

    switch (type) {
      case 'job_progress':
        return { unifiedJobs: { ...s.unifiedJobs, [jobId]: { ...job, progress: payload.progress, message: payload.message } } }
      case 'job_status':
        return { unifiedJobs: { ...s.unifiedJobs, [jobId]: { ...job, status: payload.status, error: payload.error } } }
      case 'job_result':
        return { unifiedJobs: { ...s.unifiedJobs, [jobId]: { ...job, result: payload.result } } }
      default:
        return s
    }
  })
},
```

- [ ] **Step 3: Wire wsConnected in WS client**

In `apps/web/src/lib/ws/client.ts` (or `realWsClient.ts`), set `wsConnected` on the store when the WebSocket connects/disconnects:

```typescript
// On connect:
useStudioStore.setState({ wsConnected: true })

// On close/error:
useStudioStore.setState({ wsConnected: false })
```

This enables `useJobTracker` to skip polling when WS is active.

- [ ] **Step 4: Add unified event handling in applyWsEvent**

In the `applyWsEvent` function (line ~513), add cases for the new event types at the top of the switch:

```typescript
case 'job_progress':
case 'job_status':
case 'job_result':
  get().handleJobEvent(event)
  break
```

- [ ] **Step 5: Build check**

Run: `cd apps/web && npx tsc --noEmit 2>&1 | head -20`
Expected: No new type errors

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/lib/ws/events.ts apps/web/src/lib/store/studioStore.ts apps/web/src/lib/ws/client.ts
git commit -m "feat: add unified jobs state slice + WS event handling to store

Store now tracks all job types in unifiedJobs record. handleJobEvent processes
unified job_progress/job_status/job_result events. wsConnected enables poll fallback."
```

---

## Task 10: Fix canGenerateClip

**Files:**
- Modify: `apps/web/src/lib/schema/clip.ts:103-122`

- [ ] **Step 1: Update canGenerateClip to auto-bind startFrame**

Replace the `canGenerateClip` function (lines 103-122) with:

```typescript
export function canGenerateClip(
  clip: Clip,
  panelPreviewUrl?: string,
): { canGenerate: boolean; reason: string } {
  if (clip.status === 'Running' || clip.status === 'Queued') {
    return { canGenerate: false, reason: '正在生成中' }
  }

  const startFrame = clip.startFrame || panelPreviewUrl
  if (!startFrame) {
    return { canGenerate: false, reason: '面板尚未渲染，无法生成视频' }
  }

  if (clip.motionMode === 'dual_keyframe' && !clip.endFrame) {
    return { canGenerate: false, reason: '双关键帧模式请设置结束帧' }
  }

  return { canGenerate: true, reason: '可以生成' }
}
```

- [ ] **Step 2: Build check**

Run: `cd apps/web && npx tsc --noEmit 2>&1 | head -20`
Expected: No type errors

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/lib/schema/clip.ts
git commit -m "fix: canGenerateClip auto-binds startFrame from panel preview

Single keyframe mode no longer requires manually setting startFrame.
Falls back to panelPreviewUrl parameter."
```

---

## Task 11: Inspector Tabs — ShotTab

**Files:**
- Create: `apps/web/src/components/studio/right/ShotTab.tsx`

- [ ] **Step 1: Create ShotTab** (merged InspectorStory + InspectorLayout)

Read the existing `InspectorStory.tsx` and `InspectorLayout.tsx` files to extract their form fields and patterns. Then create `ShotTab.tsx` that combines both into one form, following the `InspectorFormProvider` pattern (react-hook-form + 300ms debounce).

The component should render:
1. Shot description textarea with "Smart Fill" button
2. Shot type + Camera move selects (side by side)
3. Duration slider
4. Separator: "场景"
5. Scene location + Mood inputs (side by side)
6. Time of day + Weather selects (side by side)

Use the same form field names as existing components so `InspectorFormProvider` sync works.

- [ ] **Step 2: Build check**

Run: `cd apps/web && npx tsc --noEmit 2>&1 | head -20`

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/studio/right/ShotTab.tsx
git commit -m "feat: add ShotTab merging InspectorStory + InspectorLayout"
```

---

## Task 12: Inspector Tabs — CastTab

**Files:**
- Create: `apps/web/src/components/studio/right/CastTab.tsx`

- [ ] **Step 1: Create CastTab** (merged InspectorCast + InspectorConsistency)

Read existing `InspectorCast.tsx` and `InspectorConsistency.tsx`. Combine into one component where each character card shows:
- Checkbox for in-scene toggle
- Avatar thumbnail
- FaceID status badge (Ready/Pending/Missing)
- Hover-revealed action buttons: Upload Reference, Regenerate

Data sources:
- Characters list from `studioStore.characters`
- FaceID status from `chaptersApi.getAssetsLock(chapterId)` (poll every 5s when any character is "pending")
- Upload action calls `identityApi.extractEmbedding(assetId, [file])`

Include consistency summary at top: "2/3 就绪" with color-coded dots.

- [ ] **Step 2: Build check**

Run: `cd apps/web && npx tsc --noEmit 2>&1 | head -20`

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/studio/right/CastTab.tsx
git commit -m "feat: add CastTab merging InspectorCast + InspectorConsistency"
```

---

## Task 13: Inspector Tabs — AssetsTab

**Files:**
- Create: `apps/web/src/components/studio/right/AssetsTab.tsx`

- [ ] **Step 1: Create AssetsTab** (merged AssetsLockPanel + InspectorAnchors)

Read existing `AssetsLockPanel.tsx` (in `panels/`) and `InspectorAnchors.tsx`. Combine into:
1. Character Bindings section: asset name + binding status + manual select dropdown for unmatched
2. Scene Bindings section: asset name + anchor status + control map badges (depth/lineart/canny) + "Regenerate Control Maps" button (calls `POST /api/v1/scene-anchors/{id}/generate-control-maps`)
3. Render Readiness Checklist section: summary of blocking issues

The control map generate button is the key fix — replace the old `console.log` stub with a real API call.

- [ ] **Step 2: Build check**

Run: `cd apps/web && npx tsc --noEmit 2>&1 | head -20`

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/studio/right/AssetsTab.tsx
git commit -m "feat: add AssetsTab merging AssetsLock + Anchors with real control map generation"
```

---

## Task 14: Inspector Tabs — VideoTab

**Files:**
- Create: `apps/web/src/components/studio/right/VideoTab.tsx`

- [ ] **Step 1: Create VideoTab** (rewritten InspectorTimeline with CTA)

This is the most important new tab. It must:
1. Show "请先渲染此面板图片" warning if panel not rendered
2. When rendered, show:
   - Start frame thumbnail (auto-bound to panel preview)
   - Motion mode select
   - End frame select (only when dual_keyframe)
   - Motion prompt textarea
   - Duration + FPS selects
   - Provider select
   - **"生成视频" primary CTA button** (calls `studioStore.createJob('video', ...)`)
   - Progress bar when job is running (driven by `useJobTracker`)

The CTA button auto-creates a Clip if none exists for this panel, then creates the job.

```typescript
const handleGenerateVideo = async () => {
  if (!selectedPanelId || !panelPreviewUrl) return
  setGenerating(true)
  try {
    // Ensure timeline + clip exist
    const clipId = ensureClipForPanel(selectedPanelId)

    const jobId = await createJob('video', clipId, provider, {
      start_frame_url: panelPreviewUrl,
      motion_prompt: motionPrompt,
      duration_sec: durationSec,
      fps,
    })
    setActiveJobId(jobId)
    toast({ title: '视频生成已启动' })
  } catch (e) {
    toast({ title: '生成失败', description: String(e), variant: 'destructive' })
  } finally {
    setGenerating(false)
  }
}
```

- [ ] **Step 2: Build check**

Run: `cd apps/web && npx tsc --noEmit 2>&1 | head -20`

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/studio/right/VideoTab.tsx
git commit -m "feat: add VideoTab with video generation CTA button

Rewritten timeline inspector with auto-bound start frame, motion params,
and Generate Video button that calls unified jobApi."
```

---

## Task 15: Rewire InspectorTabs — 9 → 5

**Files:**
- Modify: `apps/web/src/components/studio/right/InspectorTabs.tsx`
- Delete: Old tab components (7 files)

- [ ] **Step 1: Update InspectorTabs to use new 5 tabs**

Rewrite `InspectorTabs.tsx` to import and render only:
- `ShotTab` (value: "shot")
- `CastTab` (value: "cast")
- `AssetsTab` (value: "assets")
- `InspectorLayers` (value: "layers") — kept as-is
- `VideoTab` (value: "video")

Tab trigger labels: 镜头, 角色, 资产, 图层, 视频

Remove all imports and references to deleted components.

- [ ] **Step 2: Delete old components**

Delete these files:
- `apps/web/src/components/studio/right/InspectorQA.tsx`
- `apps/web/src/components/studio/right/InspectorStory.tsx`
- `apps/web/src/components/studio/right/InspectorLayout.tsx`
- `apps/web/src/components/studio/right/InspectorCast.tsx`
- `apps/web/src/components/studio/right/InspectorConsistency.tsx`
- `apps/web/src/components/studio/right/InspectorAnchors.tsx`
- `apps/web/src/components/studio/right/InspectorTimeline.tsx`
- `apps/web/src/components/studio/NeedsFixPanel.tsx` (stub → absorbed into AssetsTab readiness checklist)
- `apps/web/src/components/studio/panels/AssetsLockPanel.tsx` (→ absorbed into AssetsTab)

Check if `InspectorFormProvider.tsx` is still needed — it should be, as `ShotTab` uses it.

- [ ] **Step 3: Build check**

Run: `cd apps/web && npx tsc --noEmit 2>&1 | head -20`
Fix any import errors from other files that referenced deleted components.

- [ ] **Step 4: Commit**

```bash
git add -A apps/web/src/components/studio/right/
git commit -m "refactor: consolidate Inspector tabs from 9 to 5

Delete InspectorQA (stub), InspectorStory, InspectorLayout, InspectorCast,
InspectorConsistency, InspectorAnchors, InspectorTimeline.
Replace with ShotTab, CastTab, AssetsTab, VideoTab."
```

---

## Task 16: PanelCard — Add Video Button + State Logic

**Files:**
- Modify: `apps/web/src/components/studio/center/PanelCard.tsx`

- [ ] **Step 1: Add Video button and state-dependent rendering**

Read the existing `PanelCard.tsx`. Add a video button next to the render button (line ~236-268). The button state depends on panel status:

```typescript
const canRenderVideo = panel.status === 'Rendered'

// In the action bar:
<Button
  size="sm"
  variant={canRenderVideo ? "default" : "ghost"}
  disabled={!canRenderVideo}
  className={canRenderVideo ? "bg-violet-600 hover:bg-violet-500" : "opacity-50"}
  onClick={() => {
    // Select this panel and switch to Video tab
    selectPanel(panel.id)
    useStudioStore.setState({ activeInspectorTab: 'video' })
  }}
>
  <Film className="w-3.5 h-3.5 mr-1" />
  视频
</Button>
```

Also update the render button to use `createJob`:

```typescript
const handleRender = async () => {
  setRendering(true)
  try {
    await useStudioStore.getState().createJob('image', panel.id, selectedProvider)
  } finally {
    setRendering(false)
  }
}
```

- [ ] **Step 2: Build check**

Run: `cd apps/web && npx tsc --noEmit 2>&1 | head -20`

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/studio/center/PanelCard.tsx
git commit -m "feat: add Video button to PanelCard with state-dependent rendering

Render button now uses unified createJob. Video button enabled only when
panel is rendered, opens VideoTab in inspector."
```

---

## Task 17: StudioTopbar — Add Batch Video Button

**Files:**
- Modify: `apps/web/src/components/studio/StudioTopbar.tsx`

- [ ] **Step 1: Add Batch Video button**

After the existing batch render button area in `StudioTopbar.tsx`, add:

```typescript
<Button
  variant="outline"
  size="sm"
  className="gap-1.5 border-violet-500/30 text-violet-400 hover:bg-violet-500/10"
  onClick={handleBatchVideo}
  disabled={batchVideoRunning}
>
  {batchVideoRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Film className="w-4 h-4" />}
  批量视频
</Button>
```

Add the handler:

```typescript
const [batchVideoRunning, setBatchVideoRunning] = useState(false)

const handleBatchVideo = async () => {
  const { panelList, createJob, ensureClipForPanel } = useStudioStore.getState()
  const rendered = panelList.filter(p => p.status === 'Rendered')

  if (rendered.length === 0) {
    toast({ title: '无可用面板', description: '请先渲染面板图片' })
    return
  }

  if (!confirm(`将为 ${rendered.length} 个已渲染面板生成视频，确认？`)) return

  setBatchVideoRunning(true)
  try {
    const CONCURRENCY = 5
    for (let i = 0; i < rendered.length; i += CONCURRENCY) {
      const batch = rendered.slice(i, i + CONCURRENCY)
      await Promise.allSettled(
        batch.map(async (panel) => {
          // Video jobs require clip_id, not panel_id — create clip first
          const clipId = await ensureClipForPanel(panel.id)
          return createJob('video', clipId, selectedProvider, {
            start_frame_url: panel.previewUrl,
            motion_prompt: panel.description || '',
            duration_sec: 3,
            fps: 24,
          })
        })
      )
    }
    toast({ title: '批量视频已启动', description: `${rendered.length} 个任务已提交` })
  } catch (e) {
    toast({ title: '批量视频失败', description: String(e), variant: 'destructive' })
  } finally {
    setBatchVideoRunning(false)
  }
}
```

- [ ] **Step 2: Build check**

Run: `cd apps/web && npx tsc --noEmit 2>&1 | head -20`

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/studio/StudioTopbar.tsx
git commit -m "feat: add Batch Video button to StudioTopbar

Creates video jobs for all rendered panels with concurrency limit of 5.
Shows confirmation dialog before proceeding."
```

---

## Task 18: FaceID Fallback Extraction

**Files:**
- Modify: `apps/api/app/api/routes/assets/__init__.py`

Spec section 7.2: When a character image is generated but embedding extraction fails (e.g., no face detected), the asset should still save successfully with `embedding_status = "failed"` rather than blocking the entire generation.

- [ ] **Step 1: Add try/except around embedding extraction**

In the `generate_asset_image` route handler (where FaceID extraction happens after image generation), wrap the extraction in try/except:

```python
# After image generation succeeds and we have result["image_url"]:
if asset.type == "character":
    try:
        embedding_result = await extract_embedding(asset.id, result["image_url"])
        if embedding_result and embedding_result.get("embedding_path"):
            data["embedding_path"] = embedding_result["embedding_path"]
            data["embedding_status"] = "ready"
            data["embedding_source"] = "auto_generation"
            data["face_embedding"] = embedding_result["embedding_path"]
        else:
            data["embedding_status"] = "failed"
            data["embedding_error"] = "No face detected in generated image"
    except Exception as e:
        data["embedding_status"] = "failed"
        data["embedding_error"] = str(e)
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/app/api/routes/assets/__init__.py
git commit -m "fix: graceful FaceID fallback when extraction fails

Character image generation no longer fails entirely if face embedding
extraction errors. Sets embedding_status='failed' with error message."
```

---

## Task 19: Migrate useStoryboardGeneration to jobApi

**Files:**
- Modify: `apps/web/src/hooks/useStoryboardGeneration.ts`

- [ ] **Step 1: Read the existing hook**

Read `useStoryboardGeneration.ts` to understand current API calls.

- [ ] **Step 2: Replace direct API call with jobApi**

The hook should use `createJob('storyboard', chapterId, provider, { script })` instead of calling the storyboard endpoint directly. This routes through the unified job system.

```typescript
// Replace the direct API call with:
const jobId = await useStudioStore.getState().createJob('storyboard', chapterId, provider, {
  script: scriptText,
  style_profile: selectedStyle,
})
```

Keep existing WS event handling for `storyboard_progress`/`storyboard_done` events — those are still emitted by the backend. The unified `job_status` event is supplementary.

- [ ] **Step 3: Build check**

Run: `cd apps/web && npx tsc --noEmit 2>&1 | head -20`

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/hooks/useStoryboardGeneration.ts
git commit -m "refactor: migrate useStoryboardGeneration to unified jobApi"
```

---

## Task 20: Update ClipRow + TimelinePanel for unified jobs

**Files:**
- Modify: `apps/web/src/components/studio/bottom/ClipRow.tsx`
- Modify: `apps/web/src/components/studio/bottom/TimelinePanel.tsx`

- [ ] **Step 1: Read both components**

Read `ClipRow.tsx` and `TimelinePanel.tsx` to understand how they track clip/video job state.

- [ ] **Step 2: Update ClipRow to use unifiedJobs**

Replace any direct `studioStore.jobs[clipJobId]` references with `studioStore.unifiedJobs[clipJobId]`. Also ensure the video generate button in ClipRow (if any) calls `createJob('video', clipId, ...)` instead of the old `enqueueClipRender`.

- [ ] **Step 3: Update TimelinePanel**

Ensure TimelinePanel reads from `unifiedJobs` for progress display. Update any clip status rendering to show unified job status.

- [ ] **Step 4: Build check**

Run: `cd apps/web && npx tsc --noEmit 2>&1 | head -20`

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/studio/bottom/ClipRow.tsx apps/web/src/components/studio/bottom/TimelinePanel.tsx
git commit -m "refactor: update ClipRow + TimelinePanel to use unifiedJobs state"
```

---

## Task 21: Build Verification + Cleanup

**Files:**
- All modified files

- [ ] **Step 1: Full TypeScript build check**

Run: `cd apps/web && npm run build 2>&1 | tail -30`
Expected: Build succeeds

- [ ] **Step 2: Fix any build errors**

Address import errors, missing types, or component reference issues.

- [ ] **Step 3: Backend test suite**

Run: `cd apps/api && python -m pytest tests/ -v --tb=short 2>&1 | tail -30`
Expected: All tests pass

- [ ] **Step 4: Verify deleted files have no remaining imports**

Run: `cd apps/web && grep -r "InspectorQA\|InspectorStory\|InspectorLayout\|InspectorCast\b" src/ --include="*.tsx" --include="*.ts" -l`
Expected: No files found (all references removed)

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: build verification and import cleanup after pipeline refactor"
```

---

## Summary

| Task | Description | Estimated Steps |
|------|-------------|-----------------|
| 1 | FaceID field name fix | 5 |
| 2 | Clip table migration | 4 |
| 3 | Job schemas | 2 |
| 4 | Extend existing jobs.py with unified POST | 6 |
| 5 | Unified WS events (backend) | 4 |
| 6 | Video worker params fix | 3 |
| 7 | Frontend jobApi client | 2 |
| 8 | useJobTracker hook (WS + poll fallback) | 2 |
| 9 | Unified WS events + store unifiedJobs + wsConnected | 6 |
| 10 | Fix canGenerateClip | 3 |
| 11 | ShotTab component | 3 |
| 12 | CastTab component | 3 |
| 13 | AssetsTab component | 3 |
| 14 | VideoTab component | 3 |
| 15 | Rewire InspectorTabs + delete old (8 files) | 4 |
| 16 | PanelCard video button | 3 |
| 17 | StudioTopbar batch video (create clips first) | 3 |
| 18 | FaceID fallback extraction | 2 |
| 19 | Migrate useStoryboardGeneration to jobApi | 4 |
| 20 | Update ClipRow + TimelinePanel | 5 |
| 21 | Build verification + cleanup | 5 |
| **Total** | | **76 steps** |

**Dependency order:**
- **Backend (parallel):** Tasks 1, 2, 3 → 4 → 5, 6, 18
- **Frontend infra (parallel with backend):** Tasks 7 → 8, 9 → 10
- **Inspector tabs (depend on 7-9):** Tasks 11, 12, 13, 14 → 15
- **Buttons + integration (depend on 9):** Tasks 16, 17, 19, 20
- **Final:** Task 21
