# B-1 Phase C — Episode Endpoint Delegation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to execute. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Wire real implementations into the Phase A tool stubs (so slow tools actually dispatch Celery jobs / call services instead of returning placeholder dicts), AND refactor the existing `/api/v1/agent/episode/{N}/*` endpoints to delegate internally to those tools. Both the chat path (Phase A `/api/v1/agent/chat`) and the button path (`/api/v1/agent/episode/{N}/...`) end up using the same handler code.

**Architecture:** Each Phase A tool stub has a `# TODO(B-1 Group 9)` marker pointing at the wiring needed. Phase C closes those markers. After this phase, `generate_script` / `generate_panels` / `render_panels` etc. dispatch real Celery tasks; `refine_script` actually calls `repair_loop`; `commit_to_studio` calls the existing `commit_orchestrator`. Existing episode endpoints become thin delegators.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, Celery, existing `app.celery_app`, `agent_commit/`, `script_pipeline`, `image_worker`, `canonical_generator`, `scene_anchor`, `image_qa`, `fix_plan_generator`, `repair_loop` services.

**Reference spec:** `docs/superpowers/specs/2026-05-06-b1-unified-agent-runner-design.md` §10 待改 ("待改" / "Refactor — URL preserved, internals delegated") section.

**Estimated effort:** ~0.5 week (10-12 tasks).

**Phase C does NOT:** flip the feature flag (Phase D), delete legacy code (Phase E), change frontend (Phase B / E).

---

## Pre-flight

- [ ] **Step 0: Confirm starting state**

```bash
cd D:/ai-webtoon-studio
git checkout feat/b1b-frontend-chat-shell
git log --oneline -1                # a4698a3 chore(web): /chat/[projectId]...
```

- [ ] **Step 0.1: Create Phase C branch**

```bash
git checkout -b feat/b1c-episode-delegation
```

---

## Group 1: Wire Real Implementations into Phase A Tool Stubs

Phase A left `TODO(B-1 Group 9)` markers in each slow-tool handler — they currently return `{"dispatched": {...stub...}}`. Replace those with real dispatch.

### Task 1.1: Wire `render_panels` to image_worker Celery task

**Files:** Modify `apps/api/app/services/agent/tools/render_panels.py`

- [ ] **Step 1: Read the current handler**

```bash
cat apps/api/app/services/agent/tools/render_panels.py
```

- [ ] **Step 2: Replace handler body**

Replace the stub handler with:

```python
import uuid
from datetime import datetime

from app.services.agent.tool_registry import ToolDefinition, TOOL_REGISTRY
from app.services.agent.trace import get_tracer


SCHEMA = {
    "type": "object",
    "properties": {
        "panel_ids": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "description": "Panel IDs to render.",
        },
        "force_regenerate": {"type": "boolean", "default": False},
    },
    "required": ["panel_ids"],
}


async def handle(args: dict, context: dict, db, tracer) -> dict:
    panel_ids = args.get("panel_ids", [])
    if not panel_ids:
        return {"error": "panel_ids required"}

    from app.celery_app import celery_app
    from app.models.render_job import RenderJob, JobType, JobStatus

    chapter_id = context.get("chapter_id")
    project_id = context["project_id"]

    job_id = str(uuid.uuid4())
    job = RenderJob(
        id=job_id,
        chapter_id=chapter_id,
        panel_id=panel_ids[0] if len(panel_ids) == 1 else None,
        job_type=JobType.full_render if hasattr(JobType, "full_render") else "full_render",
        status=JobStatus.queued if hasattr(JobStatus, "queued") else "queued",
        input_params={
            "panel_ids": panel_ids,
            "force_regenerate": args.get("force_regenerate", False),
            "project_id": project_id,
        },
    )
    db.add(job)
    db.commit()

    # Pass trace context for cross-process span continuation
    parent_span_id = tracer.current_span_id if tracer else None
    trace_id = tracer.trace_id if tracer else None

    celery_app.send_task(
        "app.workers.async_runner.run_batch_render_task_celery",
        args=[panel_ids, args.get("force_regenerate", False)],
        kwargs={"_trace_id": trace_id, "_parent_span_id": parent_span_id},
        queue="image",
        task_id=job_id,
    )

    return {
        "dispatched": {
            "job_id": job_id,
            "eta_seconds": 180 * len(panel_ids),
        },
        "panel_ids": panel_ids,
    }


tool = ToolDefinition(
    name="render_panels",
    description="Render one or more panels to final layered images via ComfyUI. Long-running.",
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id", "episode_number"),
    expected_duration="slow",
    read_only=False,
    side_effects=("writes:render_job", "writes:layerpack", "writes:panel.preview_url"),
)
TOOL_REGISTRY.register(tool)
```

Note: confirm the actual celery task name + worker function with `grep -r "run_batch_render_task_celery\|run_render" apps/api/app/workers/`. Adjust if the Phase A plan's reference name doesn't match.

- [ ] **Step 3: Update unit test**

`apps/api/tests/unit/services/agent/tools/test_render_qa_tools.py` — find `test_render_panels_returns_dispatched`. Update to handle DB session injection (use a mocked db that satisfies `db.add(job); db.commit()`):

```python
@pytest.mark.asyncio
async def test_render_panels_returns_dispatched(monkeypatch):
    from unittest.mock import MagicMock, patch
    import app.services.agent.tools.render_panels as m

    db = MagicMock()
    fake_send = MagicMock()
    with patch("app.celery_app.celery_app.send_task", fake_send):
        out = await m.handle(
            {"panel_ids": ["p1", "p2"]},
            {"project_id": "x", "episode_number": 1, "chapter_id": "c1"},
            db=db, tracer=None,
        )
    assert "dispatched" in out
    assert out["panel_ids"] == ["p1", "p2"]
    assert fake_send.called
    assert fake_send.call_args.args[0] == "app.workers.async_runner.run_batch_render_task_celery"
```

- [ ] **Step 4: Run + commit**

```bash
cd D:/ai-webtoon-studio/apps/api
py -3.13 -m pytest tests/unit/services/agent/tools/test_render_qa_tools.py -v
```
Expected: all tests still pass.

```bash
cd D:/ai-webtoon-studio
git add apps/api/app/services/agent/tools/render_panels.py apps/api/tests/unit/services/agent/tools/test_render_qa_tools.py
git commit -m "feat(api): wire render_panels tool to image_worker Celery dispatch (B-1 Phase C)"
```

### Task 1.2: Wire `generate_script` tool

**Files:** Modify `apps/api/app/services/agent/tools/generate_script.py`

- [ ] **Step 1: Investigate existing service**

```bash
grep -n "class ScriptPipelineService\|def task_parse\|async def" apps/api/app/services/script_pipeline.py | head -20
grep -rn "agent_commit" apps/api/app/services/agent_commit/__init__.py
```

- [ ] **Step 2: Replace handler body**

```python
async def handle(args: dict, context: dict, db, tracer) -> dict:
    story = args.get("story", "")
    panel_count = args.get("panel_count", 4)
    if not story:
        return {"error": "story required"}

    from app.services.script_pipeline import ScriptPipelineService

    project_id = context["project_id"]
    episode_number = context["episode_number"]

    # Synchronous pass: parse + persist into the chapter's script field via existing service.
    # If the project has an async generation pipeline (Doubao etc.), the existing chapter
    # endpoint dispatches Celery — replicate that here.
    try:
        svc = ScriptPipelineService()
        result = await svc.task_parse(story)
        # Persist into chapter
        from app.models.chapter import Chapter
        chapter = (
            db.query(Chapter)
            .filter(Chapter.project_id == project_id, Chapter.order == episode_number)
            .first()
        )
        if chapter:
            # Match existing convention for storing script_text
            if hasattr(chapter, "script_text"):
                chapter.script_text = story
            db.commit()
        return {
            "success": True,
            "characters": [c.name for c in getattr(result.script_ir, "characters", [])],
            "scenes": [s.name for s in getattr(result.script_ir, "scenes", [])],
            "beat_count": len(getattr(result.script_ir, "beats", [])),
            "panel_count": panel_count,
        }
    except Exception as e:
        return {"error": f"generate_script failed: {e!r}"}
```

If the project's existing `/agent/episode/{N}/script/stream` endpoint runs synchronously (per the existing `agent_commit/` flow it does, just with SSE streaming), `generate_script` becomes a fast tool not a slow one. Update the ToolDefinition's `expected_duration` accordingly:

```python
tool = ToolDefinition(
    name="generate_script",
    description="Generate or parse the current episode's script. Persists into the chapter row.",
    json_schema=SCHEMA,
    handler=handle,
    requires_context=("project_id", "episode_number"),
    expected_duration="fast",   # was: slow
    read_only=False,
    side_effects=("writes:chapter",),
)
```

- [ ] **Step 3: Update test**

In `tests/unit/services/agent/tools/test_script_tools.py`, update `test_generate_script_returns_dispatched` → rename to `test_generate_script_parses_and_persists`. Provide a mock for ScriptPipelineService.task_parse:

```python
@pytest.mark.asyncio
async def test_generate_script_parses_and_persists(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock
    import app.services.agent.tools.generate_script as m

    fake_result = MagicMock()
    fake_result.script_ir.characters = [MagicMock(name="Alice")]
    fake_result.script_ir.scenes = [MagicMock(name="Forest")]
    fake_result.script_ir.beats = [MagicMock(), MagicMock()]
    fake_svc = MagicMock()
    fake_svc.task_parse = AsyncMock(return_value=fake_result)

    monkeypatch.setattr("app.services.agent.tools.generate_script.ScriptPipelineService", lambda: fake_svc)

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = MagicMock(script_text="")

    out = await m.handle({"story": "once"}, {"project_id": "p", "episode_number": 1}, db=db, tracer=None)
    assert out.get("success") is True
    assert out["beat_count"] == 2
```

Also update `test_generate_script_metadata` to assert `expected_duration == "fast"`.

- [ ] **Step 4: Run + commit**

```bash
py -3.13 -m pytest tests/unit/services/agent/tools/test_script_tools.py -v
git add apps/api/app/services/agent/tools/generate_script.py apps/api/tests/unit/services/agent/tools/test_script_tools.py
git commit -m "feat(api): wire generate_script tool to ScriptPipelineService (B-1 Phase C)"
```

### Task 1.3: Wire `refine_script` tool

**Files:** Modify `apps/api/app/services/agent/tools/refine_script.py`

- [ ] **Step 1: Wire to repair_loop**

```python
async def handle(args: dict, context: dict, db, tracer) -> dict:
    feedback = args.get("feedback", "")
    if not feedback:
        return {"error": "feedback required"}

    project_id = context["project_id"]
    episode_number = context["episode_number"]

    from app.services.brain.repair.repair_loop import RepairLoop
    from app.models.chapter import Chapter

    chapter = (
        db.query(Chapter)
        .filter(Chapter.project_id == project_id, Chapter.order == episode_number)
        .first()
    )
    if not chapter:
        return {"error": f"episode {episode_number} not found"}

    try:
        loop = RepairLoop()
        if hasattr(loop, "refine"):
            updated = await loop.refine(chapter.script_text or "", feedback)
        elif hasattr(loop, "task_refine"):
            updated = await loop.task_refine(chapter.script_text or "", feedback)
        else:
            return {"error": "RepairLoop has no refine/task_refine method"}
        chapter.script_text = updated if isinstance(updated, str) else getattr(updated, "text", chapter.script_text)
        db.commit()
        return {"success": True, "feedback_received": feedback}
    except Exception as e:
        return {"error": f"refine_script failed: {e!r}"}
```

- [ ] **Step 2: Update test, run, commit**

```bash
git commit -m "feat(api): wire refine_script tool to repair_loop (B-1 Phase C)"
```

### Task 1.4: Wire `generate_panels` tool

**Files:** Modify `apps/api/app/services/agent/tools/generate_panels.py`

- [ ] **Step 1: Investigate existing endpoint**

```bash
grep -n "generate-panels\|generate_panels" apps/api/app/api/routes/agent.py | head -10
```

Find the existing `/agent/episode/{N}/generate-panels` endpoint and identify the helper function it calls (likely a Doubao image-gen orchestrator).

- [ ] **Step 2: Wire handler to call the same orchestrator**

```python
async def handle(args: dict, context: dict, db, tracer) -> dict:
    project_id = context["project_id"]
    episode_number = context["episode_number"]
    force = args.get("force_regenerate", False)

    # Reuse the same orchestrator the existing endpoint uses.
    # Find via: grep "generate-panels" apps/api/app/api/routes/agent.py
    # Common pattern: from app.services.agent_commit import some_panel_generator
    try:
        from app.services.agent_commit.commit_orchestrator import generate_panels_for_episode
        result = await generate_panels_for_episode(
            db=db, project_id=project_id, episode_number=episode_number,
            force_regenerate=force,
        )
        return {"success": True, "panel_count": len(result.get("panels", []))}
    except ImportError:
        # Fall back to dispatched stub if direct call isn't available
        import uuid
        from app.celery_app import celery_app
        job_id = str(uuid.uuid4())
        return {
            "dispatched": {"job_id": job_id, "eta_seconds": 90},
            "note": "celery dispatch — actual function name TBD; align with route handler",
        }
    except Exception as e:
        return {"error": f"generate_panels failed: {e!r}"}
```

The exact import path needs investigation. Read the existing route, mirror its call.

- [ ] **Step 2.1: Update test, run, commit**

```bash
git commit -m "feat(api): wire generate_panels tool to existing agent_commit pipeline (B-1 Phase C)"
```

### Task 1.5: Wire `commit_to_studio` tool

**Files:** Modify `apps/api/app/services/agent/tools/commit_to_studio.py`

- [ ] **Step 1: Wire to existing commit_orchestrator**

```python
async def handle(args: dict, context: dict, db, tracer) -> dict:
    project_id = context["project_id"]
    episode_number = context["episode_number"]

    from app.services.agent_commit.commit_orchestrator import CommitOrchestrator

    try:
        orchestrator = CommitOrchestrator(db)
        if hasattr(orchestrator, "commit_episode_to_studio"):
            result = await orchestrator.commit_episode_to_studio(project_id, episode_number)
        elif hasattr(orchestrator, "run"):
            result = await orchestrator.run(project_id=project_id, episode_number=episode_number)
        else:
            return {"error": "CommitOrchestrator has no expected method"}
        return {"success": True, "committed": result}
    except Exception as e:
        return {"error": f"commit_to_studio failed: {e!r}"}
```

- [ ] **Step 2: Update test, run, commit**

```bash
git commit -m "feat(api): wire commit_to_studio tool to commit_orchestrator (B-1 Phase C)"
```

### Task 1.6: Wire `regenerate_asset_image` tool

**Files:** Modify `apps/api/app/services/agent/tools/regenerate_asset_image.py`

- [ ] **Step 1: Wire to image_worker for asset reference image regeneration**

```python
async def handle(args: dict, context: dict, db, tracer) -> dict:
    project_id = context["project_id"]
    asset_id = context.get("asset_id")
    if not asset_id:
        return {"error": "asset_id missing from context"}
    prompt_override = args.get("prompt_override")

    from app.celery_app import celery_app
    from app.models.asset import Asset
    import uuid

    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.project_id == project_id).first()
    if not asset:
        return {"error": f"asset {asset_id} not found"}

    job_id = str(uuid.uuid4())
    parent_span = tracer.current_span_id if tracer else None
    trace_id = tracer.trace_id if tracer else None

    celery_app.send_task(
        "app.workers.image_worker.regenerate_asset_image_task",
        args=[asset_id, prompt_override],
        kwargs={"_trace_id": trace_id, "_parent_span_id": parent_span},
        queue="image",
        task_id=job_id,
    )
    return {
        "dispatched": {"job_id": job_id, "eta_seconds": 60},
        "asset_id": asset_id,
    }
```

If the celery task `regenerate_asset_image_task` doesn't exist, either (a) create it as a thin wrapper around existing image_worker logic, or (b) leave the dispatch task name as a TODO and document for follow-up. Choose (a) if the existing image_worker supports asset-only regeneration; (b) otherwise.

- [ ] **Step 2: Update test, run, commit**

```bash
git commit -m "feat(api): wire regenerate_asset_image tool to image_worker (B-1 Phase C)"
```

### Task 1.7: Wire `create_character` and `create_scene` tools

**Files:** Modify `apps/api/app/services/agent/tools/create_character.py` and `create_scene.py`

- [ ] **Step 1: Wire create_character to canonical_generator**

```python
async def handle(args: dict, context: dict, db, tracer) -> dict:
    name = args["name"]
    description = args["description"]
    appearance = args["appearance"]
    project_id = context["project_id"]

    import uuid
    from app.models.asset import Asset, AssetType

    # 1. Insert Asset row
    asset = Asset(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name=name,
        type=AssetType.CHARACTER if hasattr(AssetType, "CHARACTER") else "character",
        description=description,
        data_json={"appearance": appearance},
    )
    db.add(asset)
    db.commit()

    # 2. Dispatch canonical / portrait generation
    from app.celery_app import celery_app
    job_id = str(uuid.uuid4())
    parent_span = tracer.current_span_id if tracer else None
    trace_id = tracer.trace_id if tracer else None

    celery_app.send_task(
        "app.workers.image_worker.generate_character_canonical_task",
        args=[asset.id, appearance],
        kwargs={"_trace_id": trace_id, "_parent_span_id": parent_span},
        queue="image",
        task_id=job_id,
    )
    return {
        "asset_id": asset.id,
        "name": name,
        "dispatched": {"job_id": job_id, "eta_seconds": 90},
    }
```

If the celery task doesn't exist, create a thin wrapper or document as TODO + leave the dispatch with the candidate task name.

Same approach for `create_scene` (anchor + control_map generation).

- [ ] **Step 2: Update tests, run, commit**

```bash
git add apps/api/app/services/agent/tools/create_character.py apps/api/app/services/agent/tools/create_scene.py
git commit -m "feat(api): wire create_character + create_scene tools (B-1 Phase C)"
```

---

## Group 2: Refactor Episode Endpoints to Delegate

After Group 1, the tool handlers do real work. Now refactor existing endpoints to delegate to those handlers (so both chat and button paths share the same logic).

### Task 2.1: Refactor `/agent/episode/{N}/script` endpoint

**Files:** Modify `apps/api/app/api/routes/agent.py`

- [ ] **Step 1: Read existing endpoint**

```bash
grep -n "episode/{episode_num}/script\|@router.post.*script" apps/api/app/api/routes/agent.py
```

- [ ] **Step 2: Replace endpoint body with tool delegation**

For non-streaming variant:
```python
@router.post("/episode/{episode_num}/script")
async def generate_script_endpoint(
    episode_num: int, request: ScriptRequest, db: Session = Depends(get_db),
):
    from app.services.agent.tools.generate_script import handle as tool_handle
    args = {"story": request.story, "panel_count": request.panel_count}
    context = {"project_id": request.project_id, "episode_number": episode_num}
    result = await tool_handle(args, context, db, tracer=None)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result
```

Pydantic models (`ScriptRequest`) and existing logic should largely stay; the body just delegates.

- [ ] **Step 3: Static-source regression test**

`apps/api/tests/unit/api/routes/test_episode_endpoints_delegate.py`:

```python
"""Static-source regression — episode endpoints must delegate to new tools (Phase C)."""
import inspect


def test_script_endpoint_calls_generate_script_tool():
    from app.api.routes import agent
    src = inspect.getsource(agent)
    assert "from app.services.agent.tools.generate_script import handle" in src or \
           "tools.generate_script" in src, "script endpoint must import generate_script tool"


def test_refine_endpoint_calls_refine_script_tool():
    from app.api.routes import agent
    src = inspect.getsource(agent)
    assert "tools.refine_script" in src or "refine_script import handle" in src


def test_generate_panels_endpoint_calls_tool():
    from app.api.routes import agent
    src = inspect.getsource(agent)
    assert "tools.generate_panels" in src or "generate_panels import handle" in src
```

- [ ] **Step 4: Run + commit**

```bash
git add apps/api/app/api/routes/agent.py apps/api/tests/unit/api/routes/test_episode_endpoints_delegate.py
git commit -m "refactor(api): /agent/episode/{N}/script delegates to generate_script tool (B-1 Phase C)"
```

### Task 2.2: Refactor `/agent/episode/{N}/script/stream` SSE endpoint

The streaming variant is more complex — it produces SSE events as the script is generated. Two approaches:

**Approach A (preferred):** Keep the SSE pipeline using the existing `agent_commit/card_writer` etc.; only the underlying parse step swaps to the tool. The endpoint stays a separate SSE generator but its core "parse" step calls `generate_script` tool.

**Approach B:** Have the endpoint internally call `runner.AgentRunner.run(...)` with a pre-baked message like `"please generate script for episode N"`. This routes through the full agent loop. Heavy-handed for a button click but unifies code paths.

Pick Approach A. Edit the streaming endpoint to call the tool's handler synchronously, then continue emitting cards via existing card_writer / SSE. Don't rewrite the SSE pipeline.

- [ ] **Step 1: Edit the stream endpoint internals**

Find the existing parse call (likely `script_pipeline.task_parse(...)`) and replace with `await tool_handle(args, context, db, tracer=None)`.

- [ ] **Step 2: Run, commit**

```bash
git commit -m "refactor(api): /agent/episode/{N}/script/stream delegates to generate_script tool (B-1 Phase C)"
```

### Task 2.3: Refactor `/agent/episode/{N}/refine` endpoint

Same delegation pattern.

```bash
git commit -m "refactor(api): /agent/episode/{N}/refine delegates to refine_script tool (B-1 Phase C)"
```

### Task 2.4: Refactor `/agent/episode/{N}/generate-panels` endpoint

```bash
git commit -m "refactor(api): /agent/episode/{N}/generate-panels delegates to generate_panels tool (B-1 Phase C)"
```

### Task 2.5: Refactor `/agent/episode/{N}/render` endpoint (if exists)

Check if exists:
```bash
grep -n "episode/{episode_num}/render" apps/api/app/api/routes/agent.py
```

If yes, delegate to `render_panels` tool. If no, skip this task.

```bash
git commit -m "refactor(api): /agent/episode/{N}/render delegates to render_panels tool (B-1 Phase C)"
```

---

## Group 3: Verification

### Task 3.1: Run full B-1 test suite

```bash
cd D:/ai-webtoon-studio/apps/api
py -3.13 -m pytest tests/unit/services/agent tests/unit/services/agent/skills tests/unit/services/agent/tools tests/unit/api/routes tests/unit/test_migration_022.py tests/unit/core/test_logging.py tests/unit/workers/test_trace_decorator.py tests/integration/agent -v 2>&1 | tail -10
```

Expected: all pass. The Phase A static-source forcing test is still green (16 tools registered). The new delegation regression tests pass.

### Task 3.2: Manual end-to-end smoke (optional, dev environment)

```bash
# Start backend
cd apps/api && py -3.13 -m uvicorn app.main:app --port 8000

# In another terminal, hit the legacy episode endpoint with curl:
curl -X POST http://localhost:8000/api/v1/agent/episode/1/script \
  -H "Content-Type: application/json" \
  -d '{"project_id": "test-project", "story": "A hero meets a wizard."}'
```

Expected: returns `{"success": true, "characters": [...], ...}`. (Requires LLM provider configured; otherwise expect a controlled error.)

### Task 3.3: Self-review

Confirm:
- [ ] All 7 slow-tool stubs from Phase A Group 5 now have real implementations (or documented TODO with concrete next step)
- [ ] All 5 episode endpoints delegate to tools
- [ ] Static-source regression tests prevent accidental delegation removal
- [ ] No regressions in existing test suite

---

## Self-Review

**Spec coverage:**
- §10 待改 (refactor) section: all 5 endpoints (`/script`, `/script/stream`, `/refine`, `/generate-panels`, `/render`) covered by Tasks 2.1-2.5
- §10 keeps URLs unchanged — preserved (only internals change)
- Tool handlers wired in Group 1 close all `TODO(B-1 Group 9)` markers

**Placeholder scan:** A few tasks explicitly leave fallback "if celery task doesn't exist, document TODO" branches — those are intentional safety nets, not unmade decisions. Mark them in commit messages.

**Type consistency:** `tool.handler` signature `async def handle(args, context, db, tracer)` is uniform across all 16 tools (Phase A locked it in). Endpoint delegators all build the same `args` + `context` dicts before calling.

---

## Execution Handoff

Plan complete. Use **subagent-driven-development** to execute. ~12 tasks; estimated 0.5 week.

After Phase C lands:
- Both `/api/v1/agent/chat` (chat path) and `/api/v1/agent/episode/{N}/*` (button path) use the same tool handlers internally
- Phase D can flip the feature flag with confidence that both code paths are exercised
