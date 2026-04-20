# Performance Optimization: Zustand Selectors + N+1 Query Fixes

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate unnecessary frontend re-renders via Zustand selectors + React.memo, and fix backend N+1 queries with eager loading and batch queries.

**Architecture:** Frontend: convert all destructured `useStudioStore()` calls to per-field selectors; wrap heavy list-item components with `React.memo`. Backend: add `selectinload`/`joinedload` to list endpoints; replace in-loop DB queries with batch pre-fetches; add missing indexes.

**Tech Stack:** Zustand (React), SQLAlchemy (Python), Alembic (migrations)

---

## Part A: Zustand Selectors + React.memo (Frontend)

### Task 1: Add selector helpers to studioStore

**Files:**
- Modify: `apps/web/src/lib/store/studioStore.ts:1-12`

The store already uses `create<StudioStore>()`. We need to add a shallow-equality helper so multi-field selectors don't cause spurious re-renders.

- [ ] **Step 1: Install zustand shallow import and add useShallow helper**

Zustand v4+ ships `useShallow` from `zustand/react/shallow`. No install needed. Add a re-export at the bottom of studioStore.ts:

```typescript
// At the top of studioStore.ts, add:
import { useShallow } from 'zustand/react/shallow'

// At the bottom of the file, add convenience selectors:

// Re-export for consumers that need multiple fields
export { useShallow }

// Common selectors (avoid re-creating inline arrow functions)
export const selectPanelList = (s: StudioStore) => s.panelList
export const selectSelectedPanelId = (s: StudioStore) => s.selectedPanelId
export const selectSelectPanel = (s: StudioStore) => s.selectPanel
export const selectJobs = (s: StudioStore) => s.jobs
export const selectChapterId = (s: StudioStore) => s.chapterId
export const selectProjectId = (s: StudioStore) => s.projectId
export const selectScript = (s: StudioStore) => s.script
export const selectSetScript = (s: StudioStore) => s.setScript
export const selectSetStudioData = (s: StudioStore) => s.setStudioData
export const selectCharacters = (s: StudioStore) => s.characters
export const selectScenes = (s: StudioStore) => s.scenes
export const selectStyles = (s: StudioStore) => s.styles
export const selectProps = (s: StudioStore) => s.props
```

- [ ] **Step 2: Verify the app still compiles**

Run: `cd apps/web && npx next build 2>&1 | tail -5`
Expected: Build succeeds (or at least no new errors from this change)

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/lib/store/studioStore.ts
git commit -m "feat(web): add Zustand shallow selectors to studioStore"
```

---

### Task 2: Convert StoryboardView to use selectors

**Files:**
- Modify: `apps/web/src/components/studio/center/StoryboardView.tsx:4,13`

- [ ] **Step 1: Replace destructured store call with individual selectors**

Change line 4 and line 13 from:

```typescript
import { useStudioStore } from "@/lib/store/studioStore"
// ...
const { panelList, selectedPanelId, selectPanel } = useStudioStore()
```

To:

```typescript
import { useStudioStore, selectPanelList, selectSelectedPanelId, selectSelectPanel } from "@/lib/store/studioStore"
// ...
const panelList = useStudioStore(selectPanelList)
const selectedPanelId = useStudioStore(selectSelectedPanelId)
const selectPanel = useStudioStore(selectSelectPanel)
```

- [ ] **Step 2: Verify it compiles**

Run: `cd apps/web && npx tsc --noEmit 2>&1 | head -20`
Expected: No new type errors

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/studio/center/StoryboardView.tsx
git commit -m "perf(web): StoryboardView uses Zustand selectors"
```

---

### Task 3: Wrap PanelCard with React.memo

**Files:**
- Modify: `apps/web/src/components/studio/center/PanelCard.tsx:6,69-70,268`

PanelCard is rendered in a list. Each store update (jobs, clips, etc.) currently re-renders every PanelCard. We memo the component and convert its internal store usage to selectors.

- [ ] **Step 1: Add React.memo and convert store usage**

```typescript
// Line 1: add memo import
import { memo, useCallback } from 'react'

// Line 6: change store import
import { useStudioStore, useShallow } from "@/lib/store/studioStore"

// Line 69-70: replace full destructure with useShallow for the 4 fields it needs
const { jobs, addPanelAsClip, setStudioData, chapterId } = useStudioStore(
  useShallow((s) => ({
    jobs: s.jobs,
    addPanelAsClip: s.addPanelAsClip,
    setStudioData: s.setStudioData,
    chapterId: s.chapterId,
  }))
)

// Line 69: rename function and wrap export
function PanelCardInner({ panel, selected, onClick, onDoubleClick }: PanelCardProps) {
  // ... existing body unchanged ...
}

export const PanelCard = memo(PanelCardInner)
```

- [ ] **Step 2: Verify it compiles**

Run: `cd apps/web && npx tsc --noEmit 2>&1 | head -20`
Expected: No new type errors

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/studio/center/PanelCard.tsx
git commit -m "perf(web): wrap PanelCard with React.memo + useShallow selectors"
```

---

### Task 4: Convert remaining high-impact studio components

**Files (batch — each follows the same pattern as Task 2/3):**
- Modify: `apps/web/src/components/studio/left/ScriptEditor.tsx`
- Modify: `apps/web/src/components/studio/left/AssetBrowser.tsx`
- Modify: `apps/web/src/components/studio/right/InspectorTabs.tsx`
- Modify: `apps/web/src/components/studio/right/InspectorLayers.tsx`
- Modify: `apps/web/src/components/studio/right/InspectorCast.tsx`
- Modify: `apps/web/src/components/studio/right/InspectorFormProvider.tsx`
- Modify: `apps/web/src/components/studio/right/InspectorConsistency.tsx`
- Modify: `apps/web/src/components/studio/right/InspectorAnchors.tsx`
- Modify: `apps/web/src/components/studio/right/InspectorTimeline.tsx`
- Modify: `apps/web/src/components/studio/right/InspectorQA.tsx`
- Modify: `apps/web/src/components/studio/bottom/ClipRow.tsx`
- Modify: `apps/web/src/components/studio/bottom/JobsConsole.tsx`
- Modify: `apps/web/src/components/studio/bottom/TimelinePanel.tsx`
- Modify: `apps/web/src/components/studio/StudioTopbar.tsx`
- Modify: `apps/web/src/components/studio/StudioShell.tsx`
- Modify: `apps/web/src/components/studio/modals/DraftPreviewModal.tsx`
- Modify: `apps/web/src/components/studio/modals/PanelEditorModal.tsx`
- Modify: `apps/web/src/components/studio/modals/CreateAssetModal.tsx`
- Modify: `apps/web/src/components/studio/modals/FixModal.tsx`
- Modify: `apps/web/src/components/studio/modals/ImportModal.tsx`
- Modify: `apps/web/src/components/studio/modals/AssetDetailModal.tsx`
- Modify: `apps/web/src/components/studio/controls/BatchRenderButton.tsx`
- Modify: `apps/web/src/components/studio/left/StoryboardSettings.tsx`
- Modify: `apps/web/src/components/studio/TierSelector.tsx` (already uses selectors — skip)
- Modify: `apps/web/src/components/studio/panels/AssetsLockPanel.tsx` (already uses selectors — skip)

**Conversion pattern for each file:**

For every file that currently does:
```typescript
const { fieldA, fieldB, actionC } = useStudioStore()
```

Replace with one of:

**Option A — Single field (preferred when ≤2 fields):**
```typescript
const fieldA = useStudioStore((s) => s.fieldA)
const actionC = useStudioStore((s) => s.actionC)
```

**Option B — Multiple fields with useShallow (when 3+ fields):**
```typescript
const { fieldA, fieldB, actionC } = useStudioStore(
  useShallow((s) => ({ fieldA: s.fieldA, fieldB: s.fieldB, actionC: s.actionC }))
)
```

**Additionally, for list-item components rendered in `.map()` loops** (ClipRow, etc.), wrap with `React.memo`.

- [ ] **Step 1: Convert all ScriptEditor, AssetBrowser, StoryboardSettings (left panel)**

Apply the selector pattern. These are simpler components with few fields.

- [ ] **Step 2: Convert all Inspector* components (right panel)**

Apply the selector pattern. InspectorLayers has the most fields (~10); use useShallow for it.

- [ ] **Step 3: Convert bottom panel components (ClipRow, JobsConsole, TimelinePanel)**

ClipRow is rendered in a loop — also wrap with `React.memo`.

- [ ] **Step 4: Convert StudioTopbar, StudioShell**

These access many fields + use `getState()` in callbacks. Only convert the render-time subscriptions; leave `getState()` calls in callbacks as-is (they don't cause re-renders).

- [ ] **Step 5: Convert all modal components**

Modals use `getState()`/`setState()` patterns — only convert the direct `useStudioStore()` destructures at component top level.

- [ ] **Step 6: Verify full build**

Run: `cd apps/web && npm run build 2>&1 | tail -10`
Expected: Build succeeds

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/components/studio/
git commit -m "perf(web): convert all studio components to Zustand selectors + memo"
```

---

### Task 5: Convert hooks to use selectors

**Files:**
- Modify: `apps/web/src/hooks/useStoryboardGeneration.ts:2,8-12`
- Modify: `apps/web/src/hooks/useOrchestrator.ts`

- [ ] **Step 1: Convert useStoryboardGeneration**

```typescript
// Line 2: change import
import { useStudioStore, useShallow } from '@/lib/store/studioStore'

// Lines 8-12: replace destructure
const { chapterId, script, selectPanel } = useStudioStore(
  useShallow((s) => ({ chapterId: s.chapterId, script: s.script, selectPanel: s.selectPanel }))
)
```

Leave the `useStudioStore.getState()` and `useStudioStore.setState()` calls in async callbacks unchanged — those are already optimal.

- [ ] **Step 2: Convert useOrchestrator (if it uses useStudioStore)**

Check if it imports useStudioStore. If so, apply the same pattern.

- [ ] **Step 3: Verify build**

Run: `cd apps/web && npm run build 2>&1 | tail -10`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/hooks/
git commit -m "perf(web): hooks use Zustand selectors"
```

---

### Task 6: Convert chatStore consumer

**Files:**
- Modify: `apps/web/src/components/chat/ChatPanel.tsx:9`

- [ ] **Step 1: Convert ChatPanel to use selectors**

ChatPanel destructures 8 fields from useChatStore. Apply useShallow:

```typescript
import { useChatStore } from '@/lib/store/chatStore'
import { useShallow } from 'zustand/react/shallow'

const { messages, pendingActions, isConnected, isStreaming, error, connect, disconnect, sendMessage } = useChatStore(
  useShallow((s) => ({
    messages: s.messages,
    pendingActions: s.pendingActions,
    isConnected: s.isConnected,
    isStreaming: s.isStreaming,
    error: s.error,
    connect: s.connect,
    disconnect: s.disconnect,
    sendMessage: s.sendMessage,
  }))
)
```

- [ ] **Step 2: Verify build**

Run: `cd apps/web && npm run build 2>&1 | tail -10`

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/chat/ChatPanel.tsx
git commit -m "perf(web): ChatPanel uses Zustand shallow selectors"
```

---

## Part B: N+1 Query Fixes (Backend)

### Task 7: Fix projects list N+1 query

**Files:**
- Modify: `apps/api/app/api/routes/projects.py:5,86-107`

The current code uses `joinedload(Project.chapters)` but then calls `query.count()` which resets the eager-load. It also loads ALL chapter data just to count them.

- [ ] **Step 1: Replace joinedload+count with subquery count**

Replace lines 86-107:

```python
from sqlalchemy import func

@router.get("", response_model=ProjectListResponse)
async def list_projects(
    skip: int = 0,
    limit: int = 20,
    archived: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取项目列表"""
    from app.models.chapter import Chapter

    base_query = db.query(Project).filter(Project.is_archived == archived)
    total = base_query.count()
    projects = base_query.order_by(Project.updated_at.desc()).offset(skip).limit(limit).all()

    # Batch-fetch chapter counts for all projects in ONE query
    project_ids = [p.id for p in projects]
    chapter_counts = {}
    if project_ids:
        rows = db.query(
            Chapter.project_id, func.count(Chapter.id)
        ).filter(
            Chapter.project_id.in_(project_ids)
        ).group_by(Chapter.project_id).all()
        chapter_counts = {pid: cnt for pid, cnt in rows}

    items = [
        ProjectResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            cover_image=p.cover_image,
            is_archived=p.is_archived,
            creation_method=p.creation_method,
            created_at=p.created_at,
            updated_at=p.updated_at,
            chapter_count=chapter_counts.get(p.id, 0)
        )
        for p in projects
    ]

    return ProjectListResponse(items=items, total=total)
```

This reduces from N+1 queries to exactly 3 queries (count, projects, chapter counts).

- [ ] **Step 2: Also fix get_project and create_project responses**

For single-project responses (lines ~146, ~194), use a direct count:

```python
chapter_count = db.query(func.count(Chapter.id)).filter(
    Chapter.project_id == project.id
).scalar() or 0
```

- [ ] **Step 3: Verify the API still works**

Run: `cd apps/api && python -c "from app.api.routes.projects import router; print('OK')"`
Expected: OK (import succeeds)

- [ ] **Step 4: Commit**

```bash
git add apps/api/app/api/routes/projects.py
git commit -m "perf(api): fix N+1 query in project list — batch chapter counts"
```

---

### Task 8: Fix chapters list N+1 query

**Files:**
- Modify: `apps/api/app/api/routes/chapters.py:1-4,65-85`

- [ ] **Step 1: Replace loop panel access with batch count**

```python
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.panel import Panel

@router.get("/project/{project_id}", response_model=ChapterListResponse)
async def list_chapters(
    project_id: str,
    db: Session = Depends(get_db)
):
    """获取项目的所有章节"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    chapters = db.query(Chapter).filter(
        Chapter.project_id == project_id
    ).order_by(Chapter.order_index).all()

    # Batch-fetch panel counts in ONE query
    chapter_ids = [c.id for c in chapters]
    panel_counts = {}
    if chapter_ids:
        rows = db.query(
            Panel.chapter_id, func.count(Panel.id)
        ).filter(
            Panel.chapter_id.in_(chapter_ids)
        ).group_by(Panel.chapter_id).all()
        panel_counts = {cid: cnt for cid, cnt in rows}

    items = [
        ChapterResponse(
            id=c.id,
            project_id=c.project_id,
            title=c.title,
            description=c.description,
            order_index=c.order_index,
            layout_json=c.layout_json or {},
            export_status=c.export_status,
            exported_url=c.exported_url,
            created_at=c.created_at,
            updated_at=c.updated_at,
            panel_count=panel_counts.get(c.id, 0)
        )
        for c in chapters
    ]

    return ChapterListResponse(items=items, total=len(items))
```

- [ ] **Step 2: Fix single chapter responses too**

For `get_chapter` and `create_chapter`, add:

```python
panel_count = db.query(func.count(Panel.id)).filter(Panel.chapter_id == chapter.id).scalar() or 0
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/api/routes/chapters.py
git commit -m "perf(api): fix N+1 query in chapter list — batch panel counts"
```

---

### Task 9: Fix panels list N+1 query (get_panel_image_url in loop)

**Files:**
- Modify: `apps/api/app/api/routes/panels.py:24-50,84-118`

This is the most critical N+1: `get_panel_image_url()` makes a DB query per panel inside a list comprehension.

- [ ] **Step 1: Replace per-panel query with batch pre-fetch**

```python
from sqlalchemy import func, and_

@router.get("/chapter/{chapter_id}", response_model=PanelListResponse)
async def list_panels(
    chapter_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取章节的所有分镜"""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    panels = db.query(Panel).filter(
        Panel.chapter_id == chapter_id
    ).order_by(Panel.order_index).all()

    # Batch pre-fetch: latest completed render job per panel (ONE query)
    rendered_panel_ids = [p.id for p in panels if p.render_status == "rendered"]
    render_job_map: dict[str, RenderJob] = {}
    if rendered_panel_ids:
        # Subquery: max completed_at per panel
        from sqlalchemy.orm import aliased
        subq = db.query(
            RenderJob.panel_id,
            func.max(RenderJob.completed_at).label("max_completed")
        ).filter(
            RenderJob.panel_id.in_(rendered_panel_ids),
            RenderJob.job_type == JobType.LAYER_GENERATION.value,
            RenderJob.status == JobStatus.COMPLETED.value
        ).group_by(RenderJob.panel_id).subquery()

        jobs = db.query(RenderJob).join(
            subq,
            and_(
                RenderJob.panel_id == subq.c.panel_id,
                RenderJob.completed_at == subq.c.max_completed
            )
        ).all()
        render_job_map = {j.panel_id: j for j in jobs}

    def get_preview_url(panel: Panel) -> str | None:
        """Get preview URL without DB query — uses pre-fetched data."""
        if panel.typeset_image_url:
            try:
                return storage_client.get_url(panel.typeset_image_url, expires=3600)
            except Exception:
                pass
        job = render_job_map.get(panel.id)
        if job and job.output_data:
            layers = job.output_data.get("layers", [])
            for layer in layers:
                if layer.get("type") == "full" and layer.get("storage_path"):
                    try:
                        return storage_client.get_url(layer["storage_path"], expires=3600)
                    except Exception:
                        pass
        return None

    items = [
        PanelResponse(
            id=p.id,
            chapter_id=p.chapter_id,
            order_index=p.order_index,
            spec_json=p.spec_json or {},
            render_status=p.render_status,
            active_layer_pack_id=p.active_layer_pack_id,
            typeset_status=p.typeset_status,
            typeset_image_url=p.typeset_image_url,
            preview_url=get_preview_url(p),
            qa_score=p.qa_score,
            needs_manual_fix=p.needs_manual_fix,
            created_at=p.created_at,
            updated_at=p.updated_at
        )
        for p in panels
    ]

    return PanelListResponse(items=items, total=len(items))
```

Also fix the bare `except:` on lines 30 and 47 to use `except Exception:`.

- [ ] **Step 2: Keep the original get_panel_image_url for single-panel use**

Don't delete it — other routes may call it for individual panels. But fix its bare excepts:

```python
def get_panel_image_url(panel: Panel, db: Session) -> Optional[str]:
    if panel.typeset_image_url:
        try:
            return storage_client.get_url(panel.typeset_image_url, expires=3600)
        except Exception:
            pass
    # ... rest unchanged but with except Exception instead of bare except
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/api/routes/panels.py
git commit -m "perf(api): fix N+1 in panel list — batch pre-fetch render jobs"
```

---

### Task 10: Add database indexes via Alembic migration

**Files:**
- Create: `apps/api/migrations/versions/018_add_performance_indexes.py`

- [ ] **Step 1: Create migration file**

```python
"""Add performance indexes for frequently queried columns

Revision ID: 018_add_performance_indexes
"""
from alembic import op

# revision identifiers
revision = '018_add_performance_indexes'
down_revision = '017_voice_assets'
branch_labels = None
depends_on = None


def upgrade():
    # Chapter lookups by project (used in list_chapters, chapter counts)
    op.create_index('ix_chapter_project_id', 'chapters', ['project_id'])

    # Panel lookups by chapter (used in list_panels, panel counts)
    op.create_index('ix_panel_chapter_id', 'panels', ['chapter_id'])

    # RenderJob lookups by panel (used in get_panel_image_url batch)
    op.create_index('ix_render_job_panel_id', 'render_jobs', ['panel_id'])

    # RenderJob compound index for the batch pre-fetch query
    op.create_index(
        'ix_render_job_panel_type_status',
        'render_jobs',
        ['panel_id', 'job_type', 'status']
    )

    # Asset lookups by project + type (used in studio.py)
    op.create_index('ix_asset_project_type', 'assets', ['project_id', 'type'])


def downgrade():
    op.drop_index('ix_asset_project_type', 'assets')
    op.drop_index('ix_render_job_panel_type_status', 'render_jobs')
    op.drop_index('ix_render_job_panel_id', 'render_jobs')
    op.drop_index('ix_panel_chapter_id', 'panels')
    op.drop_index('ix_chapter_project_id', 'chapters')
```

- [ ] **Step 2: Verify migration can be applied**

Run: `cd apps/api && python -c "from migrations.versions import; print('OK')"` or check syntax.

Note: If your database already has these indexes (some ORMs create them from ForeignKey definitions), the migration will fail. In that case, wrap each `create_index` in a try/except or use `if_not_exists=True` (PostgreSQL only).

- [ ] **Step 3: Commit**

```bash
git add apps/api/migrations/versions/018_add_performance_indexes.py
git commit -m "perf(api): add database indexes for chapter/panel/render_job lookups"
```

---

### Task 11: Fix chapters/crud.py N+1 (if exists)

**Files:**
- Modify: `apps/api/app/api/routes/chapters/crud.py` (if this file exists and has the same patterns)

- [ ] **Step 1: Check if file exists and apply same batch-count pattern as Task 8**

If `chapters/crud.py` has `len(c.panels)` in a loop, apply the identical fix: batch query panel counts with `func.count()` + `group_by`.

- [ ] **Step 2: Commit**

```bash
git add apps/api/app/api/routes/chapters/
git commit -m "perf(api): fix N+1 in chapters/crud.py"
```

---

## Verification

### Task 12: Full build verification

- [ ] **Step 1: Verify frontend build**

Run: `cd apps/web && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 2: Verify backend imports**

Run: `cd apps/api && python -c "from app.main import app; print('FastAPI app OK')"`
Expected: No import errors

- [ ] **Step 3: Run existing tests**

Run: `cd apps/api && pytest --tb=short 2>&1 | tail -20`
Expected: All existing tests still pass

- [ ] **Step 4: Final commit (if any remaining changes)**

```bash
git add -A
git status
# Only commit if there are meaningful changes
```
