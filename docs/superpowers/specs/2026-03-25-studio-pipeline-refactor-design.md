# Studio Pipeline Refactor — Design Spec

**Date**: 2026-03-25
**Status**: Approved
**Scope**: Deep refactoring — unified Job Pipeline, Inspector Tab merge, FaceID/video fix

---

## 1. Problem Statement

### 1.1 FaceID Extraction — Field Name Mismatch

When generating a character image via `POST /api/v1/assets/{id}/generate-image`, the backend `doubao_asset_generator` extracts FaceID and returns `embedding_path`. The route in `assets/__init__.py:488-489` does write it — but to the wrong field name and without setting the status:

```python
# What the route writes (assets/__init__.py:488-489):
data["face_embedding"] = result["embedding_path"]   # wrong key name, no status

# What identity.py writes (the working path):
data["embedding_path"] = embedding_path              # correct key name
data["embedding_status"] = "ready"                   # status set
```

The frontend (`InspectorConsistency.tsx:148`) checks `character.embedding_path` to determine status. Since the generate route writes to `face_embedding` (not `embedding_path`) and never sets `embedding_status`, the character appears as "missing" despite having an embedding.

- **Working path**: Manual upload via `InspectorConsistency` → `identity.py` → writes `embedding_path` + `embedding_status: "ready"`
- **Broken path**: Generate image → writes `face_embedding` (wrong key) → no `embedding_status` → frontend sees "missing"

### 1.2 Video Generation Completely Disconnected

7 blockers prevent video generation from working:

1. `studioStore.enqueueClipRender()` never calls the backend API — only creates local objects + mock simulation
2. `videoApi.createJob()` exists in `services.ts` but is never invoked
3. `canGenerateClip()` requires `startFrame`/`endFrame` but UI never sets them — button stays disabled
4. `client.ts` `startVideoJob()` in real WS mode returns empty function (no-op)
5. `Clip` DB table partially incomplete: `motion_mode` exists, `start_frame_layerpack_id`/`end_frame_layerpack_id` exist (as FK, not URL), but `negative` and `seed` columns are missing
6. `video_worker.py` reads fields (`negative`, `seed`) that don't exist on Clip model; also expects URL-based `start_frame` but model stores layerpack IDs
7. WS route may not broadcast `video_job_*` events

### 1.3 Fragmented Frontend UX

- 9 Inspector tabs, 2 are stubs (QA hardcoded dummy data, Anchors console.log only)
- Render triggers scattered across 3+ components with different call patterns
- API polling (`useStoryboardGeneration`) and WS push (`applyWsEvent`) coexist without unified tracking
- 8-step pipeline (script → storyboard → draft → assets → FaceID → render → clip → video) spread across 4 panels with no discoverability

---

## 2. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Job Pipeline | Unified `/api/v1/jobs` backend entry + `jobApi` + `useJobTracker` | Single pattern for image/video/storyboard/export, no per-type frontend logic |
| Provider selection | Frontend chooses, sends to backend | User controls which model/GPU to use |
| Inspector Tabs | 10 → 5 (Shot, Cast, Assets, Layers, Video) | Reduce cognitive load, colocate related info |
| Video trigger | PanelCard button + topbar batch | Single-click from card, batch from topbar |
| Deleted tabs | QA (pure stub), old Consistency/Layout/Anchors/Timeline (merged) | Remove dead code, merge related functionality |

---

## 3. Architecture: Unified Job API

### 3.1 Backend Route

**New file**: `apps/api/app/api/routes/jobs.py`

```
POST   /api/v1/jobs              → Create job (dispatches to Celery by type)
GET    /api/v1/jobs/{job_id}     → Get job status + result
GET    /api/v1/jobs?chapter_id=X → List jobs for chapter
DELETE /api/v1/jobs/{job_id}     → Cancel job
```

**Request schema**:
```python
class JobCreateRequest(BaseModel):
    type: Literal["image", "video", "storyboard", "export"]
    target_id: str          # panel_id, clip_id, or chapter_id
    provider: str           # "doubao", "tongyi", "comfyui", "mock"
    params: dict = {}       # type-specific params
```

**Dispatch logic**:
```python
@router.post("/")
async def create_job(req: JobCreateRequest, db: Session, bg: BackgroundTasks):
    job = Job(type=req.type, target_id=req.target_id,
              provider=req.provider, params_json=req.params,
              status="queued")
    db.add(job); db.commit()

    match req.type:
        case "image":
            celery_app.send_task("image_worker.execute",
                                 args=[job.id], queue="image")
        case "video":
            celery_app.send_task("video_worker.execute",
                                 args=[job.id], queue="video")
        case "storyboard":
            bg.add_task(run_storyboard_task, job.id, req.target_id,
                        req.params, req.provider)
        case "export":
            celery_app.send_task("export_worker.execute",
                                 args=[job.id], queue="export")

    return {"job_id": job.id, "type": req.type, "status": "queued"}
```

**Response schema**:
```python
class JobStatusResponse(BaseModel):
    job_id: str
    type: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    progress: float = 0.0       # 0-1
    message: str | None = None  # current step description
    result: dict | None = None  # type-specific output (maps to Job.outputs_json)
    error: str | None = None
    created_at: str
    updated_at: str
```

**Mapping to existing `Job` model** (in `app/models/job.py`):

The existing `Job` model already has `type`, `status`, `progress`, `inputs_json`, `outputs_json`, `project_id`, `chapter_id`, `panel_id`, `clip_id`. The new route reuses this model directly — no new table.

| API Field | Job Model Column |
|-----------|-----------------|
| `type` | `Job.type` |
| `target_id` | Mapped to `panel_id`, `clip_id`, or `chapter_id` based on type |
| `provider` | Stored in `Job.inputs_json["provider"]` |
| `params` | Stored in `Job.inputs_json` |
| `result` | Read from `Job.outputs_json` |
| `status` | `Job.status` (already supports "canceled") |

**DELETE behavior**: Sets `Job.status = "cancelled"`, attempts to revoke Celery task. `useJobTracker` treats "cancelled" as terminal.

### 3.2 Unified WS Events

All job types emit the same 3 events:

```typescript
{ type: "job_progress", payload: { jobId: string, progress: number, message?: string } }
{ type: "job_status",   payload: { jobId: string, status: JobStatus, error?: string } }
{ type: "job_result",   payload: { jobId: string, type: JobType, result: Record<string, unknown> } }
```

Old event types (`job_created`, `panel_status`, `layerpack_ready`, `video_job_progress`, `video_job_status`, `clip_status`, `clip_output_ready`) are **deprecated** — replaced by the 3 above. Workers updated to emit new format. Frontend `applyWsEvent` updated to handle new events and ignore old ones (backwards compat during transition).

### 3.3 Frontend: jobApi + useJobTracker

**New file**: `apps/web/src/lib/api/jobApi.ts`

```typescript
export const jobApi = {
  create: (req: JobCreateRequest) =>
    apiPost<{ job_id: string; type: string; status: string }>('/api/v1/jobs', req),
  get: (jobId: string) =>
    apiGet<JobStatusResponse>(`/api/v1/jobs/${jobId}`),
  list: (chapterId: string) =>
    apiGet<JobStatusResponse[]>(`/api/v1/jobs?chapter_id=${chapterId}`),
  cancel: (jobId: string) =>
    apiDelete(`/api/v1/jobs/${jobId}`),
}
```

**New file**: `apps/web/src/hooks/useJobTracker.ts`

```typescript
export function useJobTracker(jobId: string | null) {
  // 1. Subscribe to WS events for this jobId
  // 2. If WS disconnected, fallback to polling GET /api/v1/jobs/{jobId} every 2s
  // 3. Auto-stop when status is terminal (succeeded | failed)
  return { status, progress, message, result, error, isComplete }
}
```

**Store slice** (in `studioStore.ts`):

```typescript
// Unified jobs state — replaces separate renderJobs/videoJobs/exportJobs
jobs: Record<string, JobState>

// Single dispatch function for all job types
createJob: async (type: JobType, targetId: string, provider: string, params?: Record<string, unknown>) => {
  const res = await jobApi.create({ type, target_id: targetId, provider, params })
  set(s => ({ jobs: { ...s.jobs, [res.job_id]: { ...res, progress: 0 } } }))
  return res.job_id
}

// WS event handler — single handler for all job events
handleJobEvent: (event: JobEvent) => {
  set(s => {
    const job = s.jobs[event.payload.jobId]
    if (!job) return s
    // Update job state based on event type
    // On job_result: also update panel/clip status
  })
}
```

### 3.4 Migration from Old Patterns

| Old Pattern | New Pattern | Migration |
|-------------|-------------|-----------|
| `renderApi.renderPanel()` | `jobApi.create({ type: 'image', ... })` | Wrapper kept for 1 release, logs deprecation |
| `chaptersApi.createStoryboard()` | `jobApi.create({ type: 'storyboard', ... })` | Same |
| `videoApi.createJob()` | `jobApi.create({ type: 'video', ... })` | Direct replace (never worked) |
| `useStoryboardGeneration` polling | `useJobTracker(jobId)` | Replace hook internals |
| `studioStore.enqueueRender()` | `studioStore.createJob('image', ...)` | Rewrite |
| `studioStore.enqueueClipRender()` | `studioStore.createJob('video', ...)` | Rewrite |
| Multiple WS event handlers | Single `handleJobEvent` | Consolidate |

---

## 4. Inspector Tab Merge: 9 → 5

### 4.1 Tab Structure

| New Tab | Merged From | Content |
|---------|-------------|---------|
| **Shot** (镜头) | InspectorStory + InspectorLayout | Shot description, shot type, camera move, duration, scene location, mood, time of day, weather, smart-fill button |
| **Cast** (角色) | InspectorCast + InspectorConsistency | Character checkboxes (in-scene toggle) + FaceID status + upload/regenerate buttons per character, consistency summary |
| **Assets** (资产) | AssetsLockPanel + InspectorAnchors | Asset binding status, manual binding select, scene anchor status, control map status + regenerate, render-readiness checklist |
| **Layers** (图层) | InspectorLayers (kept) | Layer visibility/opacity toggles, version selector, QA score badge, 4 fix buttons |
| **Video** (视频) | InspectorTimeline (rewritten) | Start frame (auto-bound), motion mode, motion prompt, duration, FPS, provider, "Generate Video" CTA button, progress display |

### 4.2 Deleted Components

| Component | Reason |
|-----------|--------|
| `InspectorQA.tsx` | Pure stub — all data hardcoded, no onChange, all buttons disabled. QA score display already in Layers tab |
| `InspectorStory.tsx` | Merged into ShotTab |
| `InspectorLayout.tsx` | Merged into ShotTab |
| `InspectorCast.tsx` | Merged into CastTab |
| `InspectorConsistency.tsx` | Merged into CastTab |
| `InspectorAnchors.tsx` | Merged into AssetsTab, stub generate button fixed |
| `InspectorTimeline.tsx` | Rewritten as VideoTab with CTA button |
| `AssetsLockPanel.tsx` (from `panels/`) | Merged into AssetsTab; `onOpenAssetsLock` callbacks in StudioTopbar updated to switch to Assets tab |

### 4.3 New Component Files

```
components/studio/right/
├── InspectorTabs.tsx          # Updated: 5 tabs instead of 10
├── ShotTab.tsx                # NEW: merged Story + Layout
├── CastTab.tsx                # NEW: merged Cast + Consistency
├── AssetsTab.tsx              # NEW: merged AssetsLock + Anchors
├── InspectorLayers.tsx        # KEPT: minor QA integration
└── VideoTab.tsx               # NEW: rewritten Timeline with CTA
```

### 4.4 ShotTab Component

Merges `InspectorStory` fields + `InspectorLayout` fields into one form.

**Fields**:
- Shot description (textarea)
- Shot type (Select: ECU/CU/MS/WS/Establishing/OTS/POV)
- Camera move (Select: static/pan/tilt/dolly_in/dolly_out/truck/handheld/zoom)
- Duration (Slider: 0.5-15s)
- Scene location (Input)
- Mood (Input)
- Time of day (Select: day/night/dusk/dawn/indoor)
- Weather (Select: clear/rain/snow/fog/overcast)
- Smart Fill button (calls LLM to auto-populate)

**Form management**: Uses existing `InspectorFormProvider` pattern (react-hook-form + 300ms debounce → store sync).

### 4.5 CastTab Component

Each character rendered as a card with:
- Checkbox (toggle in-scene)
- Avatar thumbnail
- Name
- FaceID status badge: `Ready` (green) / `Pending` (blue spinner) / `Missing` (amber) / `No Asset` (gray)
- Action buttons (visible on hover): Upload Reference, Regenerate

**Data source**: Combines `studioStore.characters` (for list) + `chaptersApi.getAssetsLock()` (for FaceID status). Polls every 5s when any character is in "pending" state.

**Upload action**: Calls `identityApi.extractEmbedding(assetId, [file])` → toast feedback → refresh.

**Regenerate action**: Calls `assetsApi.regenerateReference(assetId)` → polls until complete → auto-refreshes FaceID status.

### 4.6 AssetsTab Component

Sections:
1. **Character Bindings**: Each character shows matched asset + binding status (exact/fuzzy/unmatched). Unmatched characters get a Select dropdown to manually bind.
2. **Scene Bindings**: Each scene shows matched asset + anchor status + control map status (depth/lineart/canny). "Regenerate Control Maps" button calls real API endpoint.
3. **Render Readiness Checklist**: Summary of all blocking issues with status icons.

**Control map generation fix**: Replace `console.log` stub with `POST /api/v1/scene-anchors/{scene_id}/generate-control-maps` API call.

### 4.7 VideoTab Component

**Prerequisites gate**: If selected panel `render_status !== 'Rendered'`, show warning message "请先渲染此面板图片" with disabled controls.

**When panel is rendered**:
- Start frame: Auto-bound to `panel.previewUrl` (read-only display with thumbnail)
- Motion mode: Select (single_keyframe / dual_keyframe)
- End frame: Only shown when `dual_keyframe`, Select from other rendered panels
- Motion prompt: Textarea
- Duration: Select (1s / 2s / 3s / 5s)
- FPS: Select (8 / 12 / 24)
- Provider: Select (mock / doubao / tongyi / comfyui)
- **Generate Video** button: Primary CTA, calls `studioStore.createJob('video', ...)`
- Progress bar: Shown when job is running, driven by `useJobTracker`

**Key behavior**: Clicking "Generate Video" auto-creates a Clip record (if none exists for this panel) → creates Job → tracks progress. User does NOT need to manually add clip to timeline first.

---

## 5. PanelCard Actions

### 5.1 Action Bar

Each PanelCard gets a consistent action bar at the bottom:

```
[🖼 Render] [🎬 Video] [⋮ More]
```

### 5.2 State-Dependent Button Behavior

| Panel Status | Render Button | Video Button |
|-------------|---------------|--------------|
| `Draft` | **[🖼 渲染]** primary, enabled | `[🎬 视频]` disabled, gray |
| `Queued` | `[🖼 排队中]` disabled, blue | `[🎬 视频]` disabled |
| `Running` | `[🖼 ━━ 45%]` progress bar | `[🎬 视频]` disabled |
| `Rendered` | `[🖼 重渲]` outline, enabled | **[🎬 视频]** primary, enabled |
| `NeedsFix` | `[🖼 修复]` warning orange | `[🎬 视频]` disabled |
| Video Running | `[🖼 ✅]` check icon | `[🎬 ━━ 60%]` progress bar |
| Video Done | `[🖼 ✅]` check icon | `[🎬 ✅]` check icon |

### 5.3 Click Handlers

**Render button**: `studioStore.createJob('image', panelId, selectedProvider)`

**Video button**: Opens VideoTab in inspector (selects panel + switches to Video tab). If user has already configured motion params, can also directly trigger `studioStore.createJob('video', ...)` via a "quick generate" mode with default params.

**More menu (⋮)**: Edit panel (opens PanelEditorModal), Delete panel, Add to timeline, View LayerPack

---

## 6. Topbar Actions

### 6.1 Updated Layout

```
[← Back] Project / Chapter     Provider: [doubao ▾]
                [AI 分镜] [批量渲染 🖼] [批量视频 🎬] [保存] [导入] [导出 ▾]
```

### 6.2 New: Batch Video Button

**Behavior**: Creates video jobs for ALL rendered panels that don't already have a completed video. Shows confirmation dialog before proceeding.

```typescript
batchVideoGenerate: async (provider: string) => {
  const renderedPanels = panelList.filter(p => p.status === 'Rendered')
  const needsVideo = renderedPanels.filter(p => !hasCompletedVideo(p.id))

  if (needsVideo.length === 0) {
    toast({ title: '无需生成', description: '所有面板已有视频' })
    return
  }

  // Confirmation dialog
  if (!confirm(`将为 ${needsVideo.length} 个面板生成视频，确认？`)) return

  // Concurrency-limited execution (max 5 parallel)
  const CONCURRENCY = 5
  for (let i = 0; i < needsVideo.length; i += CONCURRENCY) {
    const batch = needsVideo.slice(i, i + CONCURRENCY)
    await Promise.allSettled(batch.map(async (panel) => {
      const clip = getOrCreateClip(panel.id, { durationSec: 3, fps: 24 })
      await createJob('video', clip.id, provider, {
        start_frame_url: panel.previewUrl,
        motion_prompt: panel.description || '',
        duration_sec: clip.durationSec,
        fps: clip.fps,
      })
    }))
  }
}
```

**Clip creation prerequisite**: `getOrCreateClip` must first ensure a `Timeline` exists for the chapter (create if not). Then create the Clip with `timeline_id` FK.

---

## 7. FaceID Fix

### 7.1 Backend Route Fix

**File**: `apps/api/app/api/routes/assets/__init__.py`, `generate_asset_image()` endpoint

**Problem**: Line 488-489 writes to `data["face_embedding"]` but identity.py and frontend use `data["embedding_path"]` + `data["embedding_status"]`.

**Change**: Replace the existing write with the canonical field names used by `identity.py`:

```python
# Replace lines 488-489:
# OLD: data["face_embedding"] = result["embedding_path"]
# NEW:
if result.get("embedding_path"):
    data["embedding_path"] = result["embedding_path"]   # canonical key (matches identity.py)
    data["embedding_status"] = "ready"                   # required for frontend to detect
    data["embedding_source"] = "auto_generation"
    # Also keep face_embedding for backwards compat until fully migrated:
    data["face_embedding"] = result["embedding_path"]
```

### 7.2 Fallback Extraction

If `embedding_path` is not returned (provider doesn't support auto-extraction), trigger explicit extraction:

```python
if not result.get("embedding_path") and result.get("image_url"):
    try:
        from app.services.faceid.embedder import embed_character_faceid
        faceid_result = await embed_character_faceid(
            character_id=asset_id,
            reference_image_path=result["image_url"],
            project_id=asset.project_id,
            provider_name="mock"
        )
        if faceid_result["success"]:
            data["embedding_status"] = "ready"
            data["embedding_path"] = faceid_result["embedding_path"]
    except Exception as e:
        logger.warning(f"FaceID fallback extraction failed: {e}")
        data["embedding_status"] = "failed"
```

---

## 8. Video Pipeline Fix

### 8.1 Database Migration

**New migration**: `019_fix_clip_columns.py`

**Existing columns** (no change needed):
- `motion_mode: String(50)` — already exists, default "single_keyframe"
- `start_frame_layerpack_id: String(36)` — exists as FK to LayerPack
- `end_frame_layerpack_id: String(36)` — exists as FK to LayerPack

**Add missing columns**:
- `negative: String` (negative prompt, nullable)
- `seed: Integer` (nullable)

**Keyframe URL resolution**: The video worker will resolve `start_frame_layerpack_id` → LayerPack → `full_url` to get the actual image URL. This avoids adding redundant URL columns alongside existing FK columns. If no layerpack ID is set, fallback to `panel.preview_url`.

### 8.2 Frontend Store Rewrite

Replace `enqueueClipRender` with unified job flow:

```typescript
// Old (broken):
enqueueClipRender: (clipId) => {
  const videoJob = createVideoJob(clipId, clip.provider)
  set({ videoJobs: { ...state.videoJobs, [videoJob.id]: videoJob } })
  connection.startVideoJob(videoJob, clip)  // mock only
}

// New (connected):
generateVideo: async (panelId: string, params: VideoParams) => {
  const clip = getOrCreateClipForPanel(panelId, params)
  const jobId = await createJob('video', clip.id, params.provider, {
    start_frame_url: getPanelPreviewUrl(panelId),
    end_frame_url: params.endFrameUrl,
    motion_prompt: params.motionPrompt,
    duration_sec: params.durationSec,
    fps: params.fps,
  })
  return jobId  // caller uses useJobTracker(jobId) for progress
}
```

### 8.3 canGenerateClip Fix

Remove hard requirement for `startFrame` to be manually set. Auto-bind from panel render result:

```typescript
export function canGenerateClip(clip: Clip, panelPreviewUrl?: string): ValidationResult {
  const startFrame = clip.startFrame || panelPreviewUrl
  if (!startFrame) {
    return { canGenerate: false, reason: '面板尚未渲染，无法生成视频' }
  }
  if (clip.motionMode === 'dual_keyframe' && !clip.endFrame) {
    return { canGenerate: false, reason: '双关键帧模式请设置结束帧' }
  }
  return { canGenerate: true, reason: '' }
}
```

### 8.4 Backend Jobs Route: Video Type

When `type === "video"`, the Jobs route:

1. Find or validate Clip record
2. Set `clip.start_frame` from `params.start_frame_url`
3. Set remaining fields from params
4. Dispatch `video_worker.execute` Celery task
5. Worker reads all fields from Job.params_json (not Clip model directly)

### 8.5 Video Worker Update

Update `video_worker.py` to read params from `Job.params_json` instead of relying on Clip columns:

```python
params = job.params_json
start_frame_url = params["start_frame_url"]
motion_prompt = params.get("motion_prompt", "")
duration_sec = params.get("duration_sec", 3.0)
fps = params.get("fps", 24)
```

This decouples the worker from the Clip model schema, making it work immediately.

---

## 9. Control Map Generation Fix

### 9.1 AssetsTab Integration

Replace `InspectorAnchors` stub button with real API call in the new `AssetsTab`:

```typescript
const handleGenerateControlMaps = async (sceneAssetId: string) => {
  setGenerating(sceneAssetId)
  try {
    await apiPost(`/api/v1/scene-anchors/${sceneAssetId}/generate-control-maps`)
    toast({ title: "控制图生成中", description: "完成后将自动更新" })
    await refreshAssetsLock()
  } catch (e) {
    toast({ title: "生成失败", description: String(e), variant: "destructive" })
  } finally {
    setGenerating(null)
  }
}
```

---

## 10. UI Design System (from ui-ux-pro-max)

### 10.1 Color Tokens

| Token | Value | Usage |
|-------|-------|-------|
| `--bg-primary` | `zinc-900` (#18181b) | Main background |
| `--bg-surface` | `zinc-800` (#27272a) | Cards, inputs, panels |
| `--bg-hover` | `zinc-700` (#3f3f46) | Hover states |
| `--border` | `white/10` | Panel borders |
| `--text-primary` | `zinc-50` (#fafafa) | Primary text |
| `--text-muted` | `zinc-400` (#a1a1aa) | Secondary text |
| `--accent-render` | `emerald-500` (#10b981) | Image render actions |
| `--accent-video` | `violet-500` (#8b5cf6) | Video generate actions |
| `--accent-primary` | `blue-500` (#3b82f6) | Primary/default actions |
| `--accent-warning` | `amber-500` (#f59e0b) | Pending/warning states |
| `--accent-danger` | `red-500` (#ef4444) | Error/destructive actions |

### 10.2 Interaction Standards (per ui-ux-pro-max CRITICAL rules)

- **Touch targets**: All interactive elements min 44px height
- **Loading buttons**: `disabled + Loader2 spinner` during async operations
- **Hover feedback**: 150-300ms transition, `bg-zinc-700` hover on interactive elements
- **Focus states**: Visible focus ring (2px) for keyboard navigation
- **Error feedback**: Toast with description, error icon, near the trigger point
- **Progressive disclosure**: VideoTab shows minimal controls until panel is rendered
- **Disabled clarity**: `opacity-50 + cursor-not-allowed` on disabled elements

### 10.3 Icons

All icons from **Lucide** (already in project). Key mappings:
- Render/Image: `ImageIcon` or `Sparkles`
- Video: `Film` or `Video`
- Refresh: `RefreshCw`
- FaceID Ready: `CheckCircle2` (green)
- FaceID Missing: `AlertCircle` (amber)
- Progress: `Loader2` (spinning)

---

## 11. Files Changed Summary

### New Files
| File | Purpose |
|------|---------|
| `apps/api/app/api/routes/jobs.py` | Unified Job API route |
| `apps/web/src/lib/api/jobApi.ts` | Frontend Job API client |
| `apps/web/src/hooks/useJobTracker.ts` | Job progress tracking hook (WS + polling fallback) |
| `apps/web/src/components/studio/right/ShotTab.tsx` | Merged Shot + Layout inspector |
| `apps/web/src/components/studio/right/CastTab.tsx` | Merged Cast + Consistency inspector |
| `apps/web/src/components/studio/right/AssetsTab.tsx` | Merged Assets Lock + Anchors inspector |
| `apps/web/src/components/studio/right/VideoTab.tsx` | New Video inspector with CTA |
| `apps/api/migrations/versions/019_fix_clip_columns.py` | Add missing Clip columns |

### Modified Files
| File | Changes |
|------|---------|
| `apps/api/app/main.py` | Register `/api/v1/jobs` router |
| `apps/api/app/api/routes/assets/__init__.py` | FaceID field name fix + `embedding_status` in `generate_asset_image` |
| `apps/api/app/workers/image_worker.py` | Emit unified WS events |
| `apps/api/app/workers/video_worker.py` | Read from `Job.params_json`, emit unified WS events |
| `apps/api/app/api/routes/ws.py` | Broadcast `job_progress`/`job_status`/`job_result` events |
| `apps/web/src/lib/store/studioStore.ts` | Replace render/video job logic with unified `createJob` + `handleJobEvent` |
| `apps/web/src/components/studio/right/InspectorTabs.tsx` | 10 tabs → 5 tabs |
| `apps/web/src/components/studio/right/InspectorLayers.tsx` | Minor: ensure QA score displayed |
| `apps/web/src/components/studio/center/PanelCard.tsx` | Add Video button + state-dependent rendering |
| `apps/web/src/components/studio/StudioTopbar.tsx` | Add Batch Video button |
| `apps/web/src/components/studio/bottom/ClipRow.tsx` | Use `useJobTracker` instead of mock |
| `apps/web/src/components/studio/bottom/TimelinePanel.tsx` | Display video job status from unified store |
| `apps/web/src/lib/ws/client.ts` | Handle unified `job_*` events |
| `apps/web/src/lib/ws/events.ts` | Add unified event types |
| `apps/web/src/lib/schema/clip.ts` | Fix `canGenerateClip` to auto-bind startFrame |
| `apps/web/src/hooks/useStoryboardGeneration.ts` | Use `useJobTracker` internally |

### Deleted Files
| File | Reason |
|------|--------|
| `apps/web/src/components/studio/right/InspectorQA.tsx` | Pure stub, all hardcoded |
| `apps/web/src/components/studio/right/InspectorStory.tsx` | Merged into ShotTab |
| `apps/web/src/components/studio/right/InspectorLayout.tsx` | Merged into ShotTab |
| `apps/web/src/components/studio/right/InspectorCast.tsx` | Merged into CastTab |
| `apps/web/src/components/studio/right/InspectorConsistency.tsx` | Merged into CastTab |
| `apps/web/src/components/studio/right/InspectorAnchors.tsx` | Merged into AssetsTab |
| `apps/web/src/components/studio/right/InspectorTimeline.tsx` | Rewritten as VideoTab |
| `apps/web/src/components/studio/panels/AssetsLockPanel.tsx` | Merged into AssetsTab |

---

## 12. Testing Strategy

### Unit Tests
- `test_jobs_route.py`: Create/get/list/cancel jobs for each type
- `test_faceid_auto_extract.py`: Verify `generate_asset_image` writes embedding_path
- `test_can_generate_clip.py`: Validate auto-bind startFrame logic

### Integration Tests
- Full image render flow: `jobApi.create(image)` → worker → WS events → panel status update
- Full video flow: `jobApi.create(video)` → worker → WS events → clip status update
- FaceID flow: Generate character image → verify `embedding_status === "ready"` without manual upload

### Frontend Tests
- `useJobTracker.test.ts`: WS event handling, polling fallback on disconnect, terminal state detection
- `canGenerateClip.test.ts`: Auto-bind startFrame from panel preview, dual_keyframe validation
- Tab rendering: ShotTab, CastTab, AssetsTab, VideoTab render without errors with mock store data

### Manual QA
- Studio walkthrough: Script → AI Storyboard → Review draft → Render panels → Generate videos → Export
- Verify all 5 Inspector tabs load correctly with real data
- Verify PanelCard buttons reflect correct state at each pipeline stage
- Verify batch render + batch video from topbar
