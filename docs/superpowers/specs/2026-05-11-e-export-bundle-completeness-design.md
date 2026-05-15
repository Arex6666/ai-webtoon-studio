# E — Export Bundle Completeness: Design Spec

**Status:** Design approved · awaiting implementation plan
**Date:** 2026-05-11
**Predecessor:** D (motion-comic video compose) — supplies the chapter video that E now ships in the bundle
**Successor:** none (last item from the original ABCDE menu)

## Goal

Close the real bugs in the export bundle pipeline, integrate D's motion-comic MP4 into the bundle, and add the unit + integration tests that the bundle subsystem has never had.

The scaffolding for chapter export bundles already exists in `apps/api/app/services/export/`. `BundleBuilder` runs a 6-step pipeline and ships a zipped bundle to MinIO. But two real bugs prevent it from being usable in production, the D output is invisible to it, and there are zero tests covering it.

## Scope

**In scope:**
- Bug #1 fix: `BundleBuilder.build()` calls `write_bundle_root_files(...)` without `assets_lock` and `provenance_jobs` kwargs → produced bundles ship empty `assets.json` and `provenance/jobs.json`. Fix the call site.
- Bug #2 fix: `ExportGate` exists as a class but is never invoked in `build()`. Wire `gate.validate_or_raise(...)` after panel plans are resolved.
- D integration: a new `_collect_chapter_video()` helper finds the latest succeeded `episode_video_compose` job for the chapter and downloads its MP4 into `staging_dir/chapter_video/compose.mp4`. Adds an optional `BundleChapterVideo` reference to the manifest schema.
- Tests: ~18 new tests across unit + static-source regression + integration covering the bug fixes and the D integration.

**Out of scope:**
- Legacy `export_worker.execute_export_job` cleanup (uses mock `https://storage.example.com/...` URLs for `strip_png` exports) — separate workstream.
- `AssetLockResolver` structured-inputs upgrade (TODO marker stays).
- `ProvenanceCollector` RenderAttempt history (TODO marker stays).
- `Chapter.episode_number` column. The chapter↔episode link uses the existing `Chapter.order_index` convention; no schema change.
- Manifest `spec_version` bump. The new `chapter_video` field is purely additive and optional.
- Manifest warnings array (failed chapter-video download is logged but does not surface in the bundle).
- Real MinIO / real ffmpeg / frontend UI to display the chapter video.

## Architecture

Today's `BundleBuilder.build()` runs 6 steps. After E it runs 7 steps with the gate and the collectors finally wired in:

```
build() — current                build() — after E
═══════════════                  ═══════════════════════════
Step 1: collect_chapter_snapshot Step 1: collect_chapter_snapshot
Step 2+3 (loop): resolve+fetch   Step 2+3 (loop): resolve+fetch
Step 4 (loop): write_panel       Step 4 (loop): write_panel
                                 Step 4.6: collect_assets_lock     ← AssetLockResolver
                                 Step 4.6: collect_provenance      ← ProvenanceCollector
                                 Step 4.6: collect_chapter_video   ← NEW: query D compose
                                 Step 4.7: gate.validate_or_raise  ← ExportGate (was skipped)
Step 4.5: upload_previews        Step 4.5: upload_previews
Step 5: write_bundle_root_files  Step 5: write_bundle_root_files (now receives all 3 collectors)
Step 6: zip_and_upload           Step 6: zip_and_upload
```

**Boundaries:**

- The new `_collect_chapter_video(chapter_snapshot)` and `_fetch_chapter_video(staging_dir, video_url)` helpers live as private methods on `BundleBuilder` so they can be unit-tested directly. They never write to the DB; they only read.
- `AssetLockResolver` and `ProvenanceCollector` already exist and already do the right thing. We just call them.
- `ExportGate.validate_or_raise()` raises `GateRejectedError` (subclass of `BundleBuildError`) on failure → caught by the existing `except BundleBuildError as e` block → flows into `BundleBuildResult(success=False, error_code=e.code, ...)` → returned to the worker → propagates to `Job.status=failed` and a WS push. No new error plumbing.
- The legacy `export_worker.execute_export_job` parallel path (used for `strip_png` exports) stays untouched. E only changes `BundleBuilder` (used for `bundle` exports via `bundle_worker.export_bundle_task`).

## Bundle Layout + Manifest Schema

**New bundle structure** (additions marked **NEW**):

```
bundle.zip
├── manifest.json       ← now populates chapter_video field
├── chapter.json
├── assets.json         ← was always empty/skeleton; now real
├── README.txt          ← gains a "chapter_video/" line when video is present
├── chapter_video/      ← NEW (optional, omitted when no compose video exists)
│   └── compose.mp4
├── panels/
│   └── 0001/
│       ├── panel.json
│       ├── layerpack/...
│       └── typeset/...
└── provenance/
    └── jobs.json       ← was always empty/skeleton; now real
```

**Manifest schema change** in `apps/api/app/schemas/bundle_manifest.py`:

```python
class BundleChapterVideo(BaseModel):
    """Phase E: reference to the D motion-comic MP4 for this chapter."""
    path: str = "chapter_video/compose.mp4"   # relative to bundle root
    source_compose_job_id: str                 # provenance: which compose job produced it
    duration_sec: Optional[float] = None
    clip_count: Optional[int] = None           # mirrors compose Job outputs_json
    size_bytes: Optional[int] = None


class BundleManifest(BaseModel):
    # ... existing fields ...
    chapter_video: Optional[BundleChapterVideo] = None   # ← NEW
```

The field is optional. Old consumers that don't know about it still parse the manifest. Chapters without a compose job ship a bundle where `chapter_video` is null (or absent, depending on serializer settings).

**README.txt** gains one line only when video is present:

```
- chapter_video/compose.mp4: motion-comic video for this chapter (Phase E)
```

**No `spec_version` bump.** The new field is purely additive at the Pydantic level. `BundleManifest.spec_version = "1.0.0"` stays.

## Bug Fixes

### Bug #1: `assets_lock` + `provenance_jobs` never wired in

Today's `BundleBuilder.build()` (around line 655) calls:

```python
manifest = self.write_bundle_root_files(staging_dir, chapter_snapshot, panel_plans)
```

The helper signature already accepts `assets_lock=` and `provenance_jobs=` kwargs — they just aren't passed. After every panel is written, build the two collector results and pass them in:

```python
# After the panel write loop, before write_bundle_root_files
assets_lock = AssetLockResolver(self.db).resolve(chapter_snapshot, panel_plans)
provenance = ProvenanceCollector(self.db).collect(chapter_snapshot, panel_plans)

manifest = self.write_bundle_root_files(
    staging_dir,
    chapter_snapshot,
    panel_plans,
    assets_lock=assets_lock,
    provenance_jobs=provenance,
    chapter_video=chapter_video_info,   # see D Integration below
)
```

After the fix, `assets.json` and `provenance/jobs.json` ship populated. The skeleton-when-None fallback in `write_bundle_root_files` stays as defensive code.

### Bug #2: `ExportGate` defined but never called

Insert one call site after panel plans are resolved (after the resolve-fetch-write panel loop):

```python
gate = ExportGate(self.db)
gate.validate_or_raise(chapter_snapshot, panel_plans, allow_qa_failure=True)
```

`allow_qa_failure=True` matches today's implicit behavior — low QA scores are warnings, not blockers. The strict mode (`False`) is reserved for a future config flag and is not exposed in E.

`validate_or_raise` raises `GateRejectedError` on failure → existing `except BundleBuildError as e` block on line 682 → `BundleBuildResult(success=False, error_code=e.code, ...)`. No new plumbing.

## D Integration Helper

Two private methods on `BundleBuilder`. The collector is sync (DB queries only), the fetcher is async (object store).

```python
def _collect_chapter_video(
    self, chapter_snapshot: ChapterSnapshot
) -> Optional[tuple[BundleChapterVideo, str]]:
    """Find the D compose job whose episode_number matches this chapter's
    order_index. Returns (manifest_entry, minio_video_url) or None.
    Picks the most recent succeeded compose if multiple exist.
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


async def _fetch_chapter_video(
    self, staging_dir: str, video_url: str
) -> None:
    target_dir = os.path.join(staging_dir, "chapter_video")
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, "compose.mp4")
    await self.object_store.download_to_file(video_url, target_path)
    logger.info(f"[Bundle] Downloaded chapter video to {target_path}")
```

**Wiring inside `build()`** — after the collectors block, before `write_bundle_root_files`:

```python
chapter_video_info = None
chapter_video_result = self._collect_chapter_video(chapter_snapshot)
if chapter_video_result is not None:
    chapter_video_info, video_url = chapter_video_result
    try:
        await self._fetch_chapter_video(staging_dir, video_url)
    except Exception as e:
        # Silent skip — bundle still ships without the video
        logger.warning(
            f"[Bundle] chapter_video download failed: {e}; bundling without video"
        )
        chapter_video_info = None
```

`write_bundle_root_files` gains a new optional kwarg `chapter_video: Optional[BundleChapterVideo] = None` that gets copied into `BundleManifest.chapter_video`.

**Failure mode:** if MinIO download fails (network glitch, key removed), the bundle still ships — just without the video. Logged but does not fail the export. This matches the "skip silently" decision from Section 2.

## Testing Strategy

**Unit tests** (`apps/api/tests/unit/services/export/` — new directory, with `__init__.py`):

- `test_collect_chapter_video.py` (4 tests)
  - `test_returns_none_when_no_compose_job_exists`
  - `test_returns_none_when_chapter_order_index_is_none`
  - `test_picks_latest_succeeded_compose_by_finished_at` (two composes for same chapter; newer wins)
  - `test_matches_only_jobs_for_correct_project_and_episode_number`

- `test_build_wires_collectors.py` (3 tests)
  - `test_build_calls_write_bundle_root_files_with_assets_lock`
  - `test_build_calls_write_bundle_root_files_with_provenance_jobs`
  - `test_build_calls_gate_validate_or_raise_before_root_files`

- `test_export_gate_blocks_export.py` (2 tests)
  - `test_gate_failure_returns_result_with_error_code_GATE_REJECTED`
  - `test_gate_passes_when_all_panels_have_full_image`

- `test_bundle_manifest_chapter_video_field.py` (2 tests)
  - `test_manifest_serialises_chapter_video_when_present`
  - `test_manifest_omits_or_nulls_chapter_video_when_none`

- `test_asset_lock_resolver_no_panel_plans.py` (1 test) — empty inputs return empty spec without raising.
- `test_provenance_collector_no_jobs.py` (1 test) — same smoke for the other collector.

**Static-source regression** (`apps/api/tests/unit/test_phase_e_real_impl.py`, mirrors the C and D patterns):

- `test_bundle_builder_passes_assets_lock_to_write_root` — `inspect.getsource(BundleBuilder.build)` contains `assets_lock=`.
- `test_bundle_builder_calls_gate_validate_or_raise` — contains `validate_or_raise`.
- `test_bundle_builder_has_collect_chapter_video_helper` — `hasattr(BundleBuilder, "_collect_chapter_video")`.
- `test_manifest_has_chapter_video_field` — `"chapter_video" in BundleManifest.model_fields`.

**Integration test** (`apps/api/tests/integration/export/test_bundle_e2e.py` — new, with `__init__.py`):

Drives `BundleBuilder.build()` end-to-end with in-memory SQLite + patched `object_store`:

1. Insert a Chapter (order_index=3), one Panel with a LayerPack, one succeeded `episode_video_compose` Job with `inputs_json.episode_number=3` and `outputs_json.video_url="images/compose.mp4"`.
2. Pre-seed `in_memory[video_url] = b"FAKE_MP4_BYTES"`.
3. Patch `object_store.download_to_file` to write bytes from `in_memory` to disk; patch `object_store.upload_file` to capture uploads.
4. Drive `BundleBuilder.build()`. Assert:
   - Returns `success=True`.
   - The captured zip contains `manifest.json`, `chapter.json`, `assets.json`, `provenance/jobs.json`, `panels/0001/...`, **`chapter_video/compose.mp4` with bytes `b"FAKE_MP4_BYTES"`**.
   - `manifest.json` parses as `BundleManifest` with `chapter_video.source_compose_job_id` set and `chapter_video.path == "chapter_video/compose.mp4"`.
5. Re-run with the compose Job removed; assert the bundle still builds successfully but without `chapter_video/` and with `manifest.chapter_video is None`.

**Real ffmpeg, real MinIO, real Chapter run** are explicitly **not in scope.** All file/network I/O is patched in CI.

Total: ~13 unit + 4 static-source + 1 e2e = **~18 new tests**.

## Open Questions / Deferred

- **Manifest warning array** for failed chapter-video downloads. Today, a failed download is logged and the bundle ships without the video. If reviewers want a structured warning to surface in the manifest, that's a follow-up.
- **Strict gate mode** (`allow_qa_failure=False`) — wired into a future config flag, not exposed in E.
- **`Chapter.episode_number` column** — defer the schema change; the order_index convention is good enough for now and matches the rest of the codebase.
- **`AssetLockResolver` structured-inputs upgrade** and **`ProvenanceCollector` RenderAttempt history** — TODO markers stay; address when a real use case demands them.
- **Legacy `export_worker.execute_export_job` cleanup** — the `strip_png` path still uses placeholder URLs. Separate workstream.
