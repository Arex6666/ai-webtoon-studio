# D — Motion-Comic Video Compose: Design Spec

**Status:** Design approved · awaiting implementation plan
**Date:** 2026-05-11
**Predecessor:** C (real scene anchor + canny) — independent
**Successor:** E (export bundle completeness) — independent

## Goal

Stitch the per-panel Doubao Seedance video clips already produced by `episode_video_worker` into a single chapter/episode MP4. No audio, no transitions beyond simple cuts.

The current state ends at "N succeeded per-panel `Job` rows, each with `outputs_json.video_url` pointing at an MP4 in MinIO." D fills the gap from there to "one MP4 per episode."

## Scope

**In scope:**
- New Celery worker that downloads sibling clips, runs ffmpeg concat, uploads result to MinIO.
- Auto-trigger hook in `episode_video_worker.generate_episode_video_task` that enqueues compose when all sibling clips have succeeded.
- New `Job.type = "episode_video_compose"` row tracking the compose lifecycle.
- One retry-only API endpoint (`POST /episode/{N}/compose-video/retry`) for the case where compose itself fails but clips are still good.
- WebSocket events for compose progress/completion.

**Out of scope:**
- Audio (TTS dialogue, background music, sound effects).
- Transitions (crossfade, fade-to-black) — cut transitions only.
- Frontend UI to display the final compose video — endpoints exist; UI deferred until E.
- Ken-Burns / parallax on static panels — assumes per-panel video clips already exist.
- Multi-codec re-encoding — uses `-c copy` stream concat (Doubao Seedance output is uniform H.264/AAC).
- A real-ffmpeg integration test in CI — `subprocess.run` is patched in all tests.

## Architecture

```
Per-panel video gen (existing)        D: Compose stitcher (new)
┌─────────────────────────────┐       ┌────────────────────────────┐
│ POST /episode/{N}/generate- │       │ episode_compose_worker      │
│   video                     │       │  • ffmpeg concat demuxer   │
│  → N × Job(type=episode_    │       │  • download clips to /tmp  │
│    video) → Doubao Seedance │  ───▶ │  • upload final MP4 to     │
│  → Job.outputs_json.video_  │       │    MinIO                   │
│    url                      │       │  • Job(type=episode_video_ │
└──────────┬──────────────────┘       │    compose)                │
           │                          └────────────────────────────┘
           │ on success
           ▼
   _maybe_enqueue_episode_compose(db, project_id, episode_num)
   ├─ all sibling clips succeeded? → enqueue compose
   ├─ any still pending?            → no-op
   └─ any failed?                   → no-op (user retries failed clip)
```

**Boundaries:**
- Auto-trigger lives in `episode_video_worker` (one extra block at the success path) but delegates to a separate helper module (`app/services/video/compose_dispatch.py`) so it is unit-testable without spinning up Celery + Doubao mocks.
- The compose itself lives in a new `app/workers/episode_compose_worker.py` Celery task so it can be retried and scaled independently of clip generation.
- Dedup is enforced at the DB level via a partial unique index (Postgres) plus an in-Python pre-check for SQLite test compatibility.

## Data Model

No new tables. Reuse `Job` with a new `type` value.

| Field | Value for compose row |
|---|---|
| `type` | `"episode_video_compose"` |
| `project_id` | episode's project |
| `provider` | `"ffmpeg"` |
| `inputs_json` | `{episode_number: int, expected_clip_count: int}` — only `episode_number` matters for dispatch; `expected_clip_count` is a sanity-check snapshot |
| `outputs_json` | `{video_url, duration_sec, size_bytes, clip_count}` on success |
| `error_json` | `{code, message, ffmpeg_stderr?}` on failure |
| `status` | `queued → running → succeeded / failed` |

**Important:** Source clip job IDs are **not** frozen in `inputs_json`. The compose worker resolves clips at run time so a clip retried after compose enqueue still flows into the final output.

**Dedup index** (Alembic migration):

```sql
CREATE UNIQUE INDEX uq_episode_compose_inflight
ON jobs (project_id, (inputs_json->>'episode_number'))
WHERE type = 'episode_video_compose' AND status IN ('queued', 'running', 'succeeded');
```

Allows multiple `failed` rows (so retries create new ones) but prevents two simultaneous in-flight composes for the same episode. SQLite tests use the in-Python pre-check helper.

**Output storage path:** `episode_videos/{project_id}/ep{episode_number}/compose_{job_id}.mp4` in MinIO. Sits alongside the per-panel clips.

## Compose Worker Pipeline

`apps/api/app/workers/episode_compose_worker.py` (new):

```
execute_episode_compose(job_id)
  │
  ├─ Load Job, mark running
  │
  ├─ Resolve clips at run time:
  │    SELECT * FROM jobs
  │    WHERE type='episode_video' AND project_id=X AND status='succeeded'
  │      AND inputs_json->>'episode_number' = N
  │    Group by (inputs_json->>'image_index')::int
  │    Within each group, pick the row with latest finished_at
  │    Order by image_index ASC
  │
  ├─ Sanity check: clip_count matches inputs_json.expected_clip_count → else fail with MISSING_CLIPS
  │
  ├─ Create temp working dir under TMP/episode-compose-{job_id}/
  │
  ├─ For each clip in image_index order:
  │    • Download bytes (storage.download_bytes for MinIO key,
  │      httpx.get for http(s) URL fallback)
  │    • Save as clip_000.mp4, clip_001.mp4, ...
  │
  ├─ Write concat list file (concat_list.txt):
  │      file 'clip_000.mp4'
  │      file 'clip_001.mp4'
  │      ...
  │
  ├─ Run: ffmpeg -y -f concat -safe 0 -i concat_list.txt -c copy output.mp4
  │    • Capture stderr → error_json on failure
  │    • -c copy is stream copy → fast, lossless, assumes clips share codec/params
  │      (safe for Doubao Seedance output today; re-encode fallback can be added later)
  │
  ├─ Upload output.mp4 → MinIO key episode_videos/{project_id}/ep{N}/compose_{job_id}.mp4
  │
  ├─ Update Job: status=succeeded, outputs_json populated
  │
  ├─ Clean up temp dir (finally block)
  │
  └─ Emit WS event episode_compose_done
```

**Failure error codes** (in `Job.error_json.code`):
- `MISSING_CLIPS` — expected N clips, found M.
- `DOWNLOAD_FAILED` — couldn't fetch clip K.
- `FFMPEG_FAILED` — non-zero exit; stderr captured.
- `UPLOAD_FAILED` — MinIO put failed.

**Timeout:** 5-min hard cap on ffmpeg subprocess (typical 30s of stitched video completes in <10s with `-c copy`).

## Auto-Trigger Hook

Modification to `episode_video_worker.generate_episode_video_task`, appended at the success path after `db.commit()`:

```python
try:
    _maybe_enqueue_episode_compose(db, project_id, episode_num)
except Exception:
    logger.exception("[EpisodeVideoWorker] compose dispatch check failed")
    # Compose dispatch failure must NOT fail the clip job — the clip succeeded
```

The helper lives in `app/services/video/compose_dispatch.py`:

```python
def _maybe_enqueue_episode_compose(db, project_id: str, episode_number: int) -> Optional[str]:
    """Check sibling state; enqueue compose if all clips succeeded.

    Returns new compose job_id on enqueue, None otherwise.
    Strict policy: every sibling clip must be 'succeeded' before compose fires.
    """
```

**Logic:**
1. Find all sibling `episode_video` jobs for `(project_id, episode_number)`.
2. If any sibling is not `succeeded` → return None (covers pending, failed, retrying).
3. If a non-failed compose row already exists for this episode → return None (dedup).
4. Insert new compose `Job` row; on `IntegrityError` (lost the race) → return None.
5. Dispatch `execute_episode_compose.delay(compose_job_id)`.

**Why a separate helper module:** unit-testable without Celery or Doubao mocks. Tests pass in a fake `db` and assert `Job.add` was called with the right shape.

**Retry endpoint:** `POST /episode/{N}/compose-video/retry` wraps the same helper but bypasses the "existing compose" dedup check. Used only when compose itself failed but clips are still good — without it, the only retry path would be re-running a clip job just to retrigger the on-success check, which is wasteful.

## API + WebSocket Surface

**New routes** (added to `apps/api/app/api/routes/episode_video.py`):

```
POST /episode/{episode_num}/compose-video/retry
  Body: { project_id: str }
  Returns: { job_id, status: "queued" }
  Behavior: bypasses the dedup check; creates a new compose Job.
            Requires all sibling clips to be 'succeeded' (returns 409 otherwise).

GET /episode/compose-jobs/{job_id}
  Returns: { job_id, status, progress, video_url?, error? }
  Mirrors the existing /episode/video-jobs/{job_id} contract.
```

**WebSocket events** (added to `apps/web/src/lib/ws/events.ts` and emitted from the compose worker):

| Event | Payload |
|---|---|
| `episode_compose_created` | `{ job_id, project_id, episode_number }` |
| `episode_compose_progress` | `{ job_id, progress, stage }` — stages: `downloading_clips`, `running_ffmpeg`, `uploading` |
| `episode_compose_done` | `{ job_id, video_url, duration_sec, clip_count }` |
| `episode_compose_failed` | `{ job_id, error_code, message }` |

**Progress emission cadence:**
- `downloading_clips`: emit after every clip download (0.0 → 0.5 linearly across N clips).
- `running_ffmpeg`: emit at start (0.5) and end (0.9) — no inter-frame ffmpeg progress parsing.
- `uploading`: emit at start (0.9) and on success (1.0).

Frontend wiring is deferred. The endpoints and events exist so any consumer (chat agent, future UI, manual cURL) can subscribe.

## Testing Strategy

**Unit tests for the dispatch helper** (`tests/unit/workers/test_episode_compose_dispatch.py`):
- `test_no_siblings_returns_none`
- `test_pending_sibling_skips_dispatch`
- `test_failed_sibling_skips_dispatch`
- `test_all_succeeded_enqueues_compose`
- `test_existing_compose_dedups`
- `test_failed_compose_does_not_dedup`

**Unit tests for the compose worker** (`tests/unit/workers/test_episode_compose_worker.py`):
- `test_compose_resolves_latest_succeeded_per_image_index`
- `test_compose_missing_clips_fails_with_error_code`
- `test_compose_ffmpeg_subprocess_invocation` — patches `subprocess.run`; asserts `-f concat -safe 0 -c copy` flags and concat list contents.
- `test_compose_ffmpeg_failure_captures_stderr`
- `test_compose_uploads_to_correct_minio_path`
- `test_compose_cleans_temp_dir_on_success_and_failure`

**Unit tests for the routes** (`tests/unit/routes/test_episode_compose_routes.py`):
- `test_retry_endpoint_requires_all_clips_succeeded` — returns 409 on pending/failed clips.
- `test_retry_endpoint_creates_new_compose_job`.
- `test_get_compose_job_status_returns_shape`.

**Static-source regression** (`tests/unit/test_phase_d_real_impl.py`) — mirrors C pattern:
- `test_episode_compose_worker_uses_ffmpeg` — `"ffmpeg"` and `"subprocess.run"` appear in source.
- `test_compose_dispatch_helper_exists` — `_maybe_enqueue_episode_compose` importable.
- Prevents accidental rollback to a stub.

**Integration test** (`tests/integration/video/test_episode_compose_e2e.py`):
- Creates 3 fake `episode_video` Job rows (`status=succeeded`, tiny test MP4 bytes uploaded to a stub MinIO).
- Patches `subprocess.run` to a fake that writes a known output file.
- Triggers `_maybe_enqueue_episode_compose` → asserts compose Job row created.
- Invokes `execute_episode_compose` synchronously → asserts clips downloaded in correct order, subprocess called with concat list listing 3 entries, output uploaded to expected MinIO path, `Job.outputs_json` populated correctly.

**Real ffmpeg test** explicitly **not in scope**. Manual smoke test deferred to PR checklist (run a real episode through the pipeline, confirm playable MP4 lands in MinIO).

## Open Questions / Deferred

- **Real-ffmpeg CI test:** if codec drift becomes a recurring failure mode, add a single `@pytest.mark.requires_ffmpeg` test that runs only when `ffmpeg` is on PATH. Deferred.
- **Re-encode fallback:** today's spec uses `-c copy` (stream copy). If Doubao Seedance ever returns mixed codecs across clips, add an `-c:v libx264 -c:a aac` fallback path. Deferred.
- **Transitions and audio:** the "Full motion comic" path (TTS dialogue, crossfades, background music) is a successor workstream, not D.
- **Frontend UI:** displaying the compose video in the chat / studio is deferred to E (export bundle completeness) or later.
