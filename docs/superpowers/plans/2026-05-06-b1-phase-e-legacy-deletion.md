# B-1 Phase E — Legacy Code Deletion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Delete the ~12 legacy backend files (~2200 lines) and ~3 legacy frontend files that B-1's new path replaces. Remove the `NEXT_PUBLIC_USE_NEW_AGENT` feature flag wiring. Confirm the new path works without any legacy code present. End state: single canonical chat code path, no dual-maintenance burden.

**Architecture:** No new code. Pure deletion + minor edits to remove flag dispatchers. The new path (Phase A backend + Phase B frontend) becomes unconditional. Static-source regression tests guard against accidental resurrection.

**Reference spec:** `docs/superpowers/specs/2026-05-06-b1-unified-agent-runner-design.md` §10.1 三分清单 ("Three-bucket inventory"), specifically the "Delete (final state)" bucket.

**Estimated effort:** ~0.5 week (~12 tasks).

**Prerequisite:** Phase D green-lighted. Do NOT start E without Phase D's decision-gate approval — E is irreversible (the deletions go through git history but reverting once active users are on the new path is messy).

---

## Pre-flight

- [ ] **Step 0: Confirm Phase D green-light**

```bash
cd D:/ai-webtoon-studio
cat docs/superpowers/plans/b1-phase-d-observation-log.md | tail -20
```

Confirm the log contains an explicit "green-light" decision. If not, STOP and finish D first.

- [ ] **Step 0.1: Create Phase E branch**

```bash
git checkout feat/b1d-flag-flip
git checkout -b feat/b1e-legacy-deletion
```

---

## Group 1: Delete Backend Legacy Files

Per spec §10.1 待删 list, 12 files / ~2200 lines.

### Task 1.1: Delete the four legacy agent classes

**Files to delete:**
- `apps/api/app/services/agents/asset_agent.py`
- `apps/api/app/services/agents/script_agent.py`
- `apps/api/app/services/agents/rendering_agent.py`
- `apps/api/app/services/agents/qa_agent.py`

These were stubs replaced by the 16 tools in Phase A Group 5.

- [ ] **Step 1: Verify nothing in the new code path imports them**

```bash
cd D:/ai-webtoon-studio
grep -rn "from app.services.agents.asset_agent\|from app.services.agents.script_agent\|from app.services.agents.rendering_agent\|from app.services.agents.qa_agent\|AssetAgent\|ScriptAgent\|RenderingAgent\|QAAgent" apps/api/app/services/agent/ apps/api/app/api/routes/agent_chat.py apps/api/app/api/routes/agent_conversations.py 2>&1 | head
```

Expected: empty (or only comments). If anything matches in the new code, STOP and resolve before deleting.

- [ ] **Step 2: Delete the four files**

```bash
rm apps/api/app/services/agents/asset_agent.py
rm apps/api/app/services/agents/script_agent.py
rm apps/api/app/services/agents/rendering_agent.py
rm apps/api/app/services/agents/qa_agent.py
```

- [ ] **Step 3: Update `apps/api/app/services/agents/__init__.py`**

Remove the imports / exports of the four deleted classes. Read the file first; the legacy `__init__.py` likely re-exports them. Edit to remove only those four references; leave any unrelated exports untouched. (If after removal the file is empty, delete it too; check Task 1.2.)

- [ ] **Step 4: Find + remove any registration call sites**

```bash
grep -rn "asset_agent\|script_agent\|rendering_agent\|qa_agent\|AssetAgent\|ScriptAgent\|RenderingAgent\|QAAgent" apps/api/app/ 2>&1
```

Expected matches: pre-Phase-E was these files import from each other. After deletions, the only remaining references should be in:
- `app/services/conversation/agent_orchestrator.py` (also being deleted in Task 1.3)
- Maybe `app/api/routes/conversations.py` legacy stream endpoint (deleted in Task 1.5)

If matches show in code we're keeping, fix.

- [ ] **Step 5: Run tests to confirm no broken imports**

```bash
cd apps/api
py -3.13 -c "from app.main import app; print('main imports OK')"
py -3.13 -m pytest tests/unit/services/agent tests/integration/agent 2>&1 | tail -5
```

Expected: app imports cleanly, B-1 tests pass.

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/services/agents/
git commit -m "chore(api): delete legacy agent classes (asset/script/rendering/qa) — replaced by 16 tools (B-1 Phase E)"
```

### Task 1.2: Delete `app/services/agents/__init__.py` (if empty)

- [ ] **Step 1: Inspect remaining content**

```bash
cat apps/api/app/services/agents/__init__.py
```

If only `# noqa` lines or whitespace remain, delete the entire `agents/` directory (it has nothing left).

```bash
ls apps/api/app/services/agents/
# If dir is empty:
rmdir apps/api/app/services/agents
```

If there are still files (e.g. `base_agent.py`, `schema_guard.py` are referenced elsewhere), keep them. The `__init__.py` should be edited rather than deleted.

- [ ] **Step 2: Verify imports**

```bash
cd apps/api
py -3.13 -c "from app.main import app; print('main imports OK')"
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/services/agents/
git commit -m "chore(api): clean up empty agents/__init__.py after legacy deletion (B-1 Phase E)"
```

### Task 1.3: Delete `app/services/conversation/agent_orchestrator.py` + `intent_router.py`

These are the legacy orchestrator + regex router replaced by `app/services/agent/runner.py` + LLM native function calling.

- [ ] **Step 1: Verify no imports outside the legacy /conversations stream endpoint**

```bash
grep -rn "from app.services.conversation.agent_orchestrator\|from app.services.conversation.intent_router\|AgentOrchestrator\|IntentRouter" apps/api/ 2>&1
```

Expected: only references in `app/api/routes/conversations.py` (legacy stream path, also being deleted in Task 1.5).

- [ ] **Step 2: Delete files**

```bash
rm apps/api/app/services/conversation/agent_orchestrator.py
rm apps/api/app/services/conversation/intent_router.py
```

- [ ] **Step 3: Edit `app/services/conversation/__init__.py` to remove their exports**

- [ ] **Step 4: Verify, commit**

```bash
py -3.13 -c "from app.main import app; print('main imports OK')"
git add apps/api/app/services/conversation/
git commit -m "chore(api): delete agent_orchestrator + intent_router — replaced by AgentRunner + native function calling (B-1 Phase E)"
```

### Task 1.4: Delete `app/services/conversation/tool_registry.py` + `tool_handlers.py`

These are the legacy tool registry + handlers replaced by `app/services/agent/tool_registry.py` + `app/services/agent/tools/*`.

- [ ] **Step 1: Verify no callers**

```bash
grep -rn "from app.services.conversation.tool_registry\|from app.services.conversation.tool_handlers" apps/api/ 2>&1
```

- [ ] **Step 2: Delete + commit**

```bash
rm apps/api/app/services/conversation/tool_registry.py
rm apps/api/app/services/conversation/tool_handlers.py
git add apps/api/app/services/conversation/
git commit -m "chore(api): delete legacy tool_registry + tool_handlers — replaced by app/services/agent/tools/ (B-1 Phase E)"
```

### Task 1.5: Delete `/conversations/{id}/messages/stream` endpoint code

`apps/api/app/api/routes/conversations.py` may have a streaming endpoint that uses `AgentOrchestrator.process_message`. Delete that endpoint specifically (keep CRUD endpoints).

- [ ] **Step 1: Inspect file, identify streaming endpoint**

```bash
grep -n "process_message\|agent_orchestrator\|AgentOrchestrator\|messages/stream" apps/api/app/api/routes/conversations.py
```

- [ ] **Step 2: Edit file to remove only the streaming endpoint + its imports**

Keep all CRUD endpoints (list / get / messages / delete / save / reset).

- [ ] **Step 3: Verify, commit**

```bash
py -3.13 -c "from app.main import app; print('main imports OK')"
py -3.13 -m pytest tests/unit/api/routes 2>&1 | tail -5
git add apps/api/app/api/routes/conversations.py
git commit -m "chore(api): delete /conversations streaming endpoint — replaced by /v1/agent/chat (B-1 Phase E)"
```

### Task 1.6: Delete `app/services/orchestrator/studio_orchestrator.py` + `app/api/routes/orchestrator.py`

The `/orchestrator/*` route family + StudioOrchestrator class.

- [ ] **Step 1: Verify no callers (frontend orchestrator API client gets deleted in Task 2.x)**

```bash
grep -rn "studio_orchestrator\|StudioOrchestrator\|orchestrator import\|orchestrator.router\|/orchestrator/" apps/api/ 2>&1
```

- [ ] **Step 2: Delete files**

```bash
rm apps/api/app/services/orchestrator/studio_orchestrator.py
rm apps/api/app/api/routes/orchestrator.py
```

If `app/services/orchestrator/__init__.py` only exports `StudioOrchestrator`, also delete the directory:

```bash
ls apps/api/app/services/orchestrator/
# If empty after: rmdir apps/api/app/services/orchestrator
```

- [ ] **Step 3: Remove `app.include_router(orchestrator.router, ...)` line from `apps/api/app/main.py`**

Also remove the `from app.api.routes import orchestrator` import.

- [ ] **Step 4: Verify, commit**

```bash
py -3.13 -c "from app.main import app; print('routes:', len(app.routes))"
git add apps/api/app/services/orchestrator/ apps/api/app/api/routes/orchestrator.py apps/api/app/main.py
git commit -m "chore(api): delete StudioOrchestrator + /orchestrator routes — replaced by /v1/agent/chat (B-1 Phase E)"
```

---

## Group 2: Delete Frontend Legacy Files

### Task 2.1: Delete `useOrchestrator.ts` + `lib/api/orchestrator.ts`

- [ ] **Step 1: Verify no callers**

```bash
grep -rn "useOrchestrator\|api/orchestrator\|orchestratorApi" apps/web/src/
```

Should show only the files we're deleting + maybe pre-existing test files (also delete those).

- [ ] **Step 2: Delete files**

```bash
rm apps/web/src/hooks/useOrchestrator.ts
rm apps/web/src/lib/api/orchestrator.ts
```

- [ ] **Step 3: Verify build**

```bash
cd apps/web
npx tsc --noEmit 2>&1 | tail -5
```

If tsc surfaces errors about missing `useOrchestrator` import, find + fix the importer (probably in /chat/[projectId]/page.tsx legacy fallback or similar).

- [ ] **Step 4: Commit**

```bash
git add -u apps/web/src/hooks/ apps/web/src/lib/api/
git commit -m "chore(web): delete useOrchestrator hook + orchestrator API client (B-1 Phase E)"
```

### Task 2.2: Delete `lib/store/chatStore.ts` (per spec §10.7 option A)

- [ ] **Step 1: Verify no callers**

```bash
grep -rn "chatStore\|useChatStore" apps/web/src/
```

- [ ] **Step 2: Delete + verify + commit**

```bash
rm apps/web/src/lib/store/chatStore.ts
cd apps/web && npx tsc --noEmit 2>&1 | tail -5
git add -u apps/web/src/lib/store/
git commit -m "chore(web): delete chatStore — useChat hook owns chat state (B-1 Phase E)"
```

---

## Group 3: Remove Feature Flag Wiring

### Task 3.1: Remove `featureFlags.useNewAgent` branches

The flag was: `process.env.NEXT_PUBLIC_USE_NEW_AGENT === 'true'`. After Phase E, the new path is unconditional.

- [ ] **Step 1: Find all flag references**

```bash
grep -rn "featureFlags.useNewAgent\|useNewAgent" apps/web/src/
```

Expected files:
- `apps/web/src/components/chat/ChatPanel.tsx` (the dispatcher)
- `apps/web/src/app/agent/[projectId]/episodes/[episodeNum]/page.tsx`
- `apps/web/src/app/chat/[projectId]/page.tsx` (a comment, no behavior — remove it)

- [ ] **Step 2: Refactor ChatPanel.tsx**

Replace:
```tsx
export default function ChatPanel(props) {
  if (featureFlags.useNewAgent) {
    return <NewAgentChat ... />;
  }
  return <LegacyChatPanel {...props} />;
}
```

With:
```tsx
export default function ChatPanel(props: ChatPanelProps) {
  return (
    <NewAgentChat
      conversationId={props.conversationId}
      context={{ projectId: props.projectId, chapterId: props.chapterId }}
    />
  );
}
```

Also delete the `LegacyChatPanel` named export (if no other module imports it; check via grep).

- [ ] **Step 3: Refactor episode page**

In `apps/web/src/app/agent/[projectId]/episodes/[episodeNum]/page.tsx`:

```tsx
{featureFlags.useNewAgent && (
  <div className="mt-6 ...">
    <NewAgentChat ... />
  </div>
)}
```

→

```tsx
<div className="mt-6 ...">
  <NewAgentChat ... />
</div>
```

- [ ] **Step 4: Refactor /chat/[projectId]/page.tsx**

Remove the comment about "flag dispatch handled via ChatPanel" added in Phase B Task 7.2 — no longer needed.

- [ ] **Step 5: Delete `apps/web/src/lib/featureFlags.ts`**

```bash
grep -rn "featureFlags\|@/lib/featureFlags" apps/web/src/
```

If empty (after the page edits above), delete:
```bash
rm apps/web/src/lib/featureFlags.ts
```

If anything still imports `featureFlags` for other reasons, leave the file alone (just remove the `useNewAgent` field).

- [ ] **Step 6: Verify build**

```bash
cd apps/web
npx tsc --noEmit 2>&1 | tail -5
npm run build 2>&1 | tail -10
```

- [ ] **Step 7: Commit**

```bash
git add -u apps/web/src/
git commit -m "chore(web): remove NEXT_PUBLIC_USE_NEW_AGENT flag — new path is unconditional (B-1 Phase E)"
```

---

## Group 4: Static-Source Regression Tests

Guard against accidental resurrection of legacy code.

### Task 4.1: Backend regression test

`apps/api/tests/unit/test_phase_e_deletions.py`:

```python
"""Static-source regression: verify legacy B-1 files don't exist (Phase E)."""
import os.path
import pytest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.mark.parametrize("relpath", [
    "app/services/agents/asset_agent.py",
    "app/services/agents/script_agent.py",
    "app/services/agents/rendering_agent.py",
    "app/services/agents/qa_agent.py",
    "app/services/conversation/agent_orchestrator.py",
    "app/services/conversation/intent_router.py",
    "app/services/conversation/tool_registry.py",
    "app/services/conversation/tool_handlers.py",
    "app/services/orchestrator/studio_orchestrator.py",
    "app/api/routes/orchestrator.py",
])
def test_legacy_file_deleted(relpath: str):
    p = os.path.join(REPO_ROOT, relpath)
    assert not os.path.exists(p), f"legacy file still exists: {relpath}"


def test_no_legacy_imports_remain():
    """Grep-based regression: no live module imports the deleted classes."""
    import subprocess
    forbidden = [
        "AssetAgent", "ScriptAgent", "RenderingAgent", "QAAgent",
        "AgentOrchestrator", "IntentRouter", "StudioOrchestrator",
    ]
    for needle in forbidden:
        result = subprocess.run(
            ["python", "-c", f"""
import os, re
for root, dirs, files in os.walk('{REPO_ROOT}/app'):
    for f in files:
        if f.endswith('.py'):
            p = os.path.join(root, f)
            with open(p, encoding='utf-8') as fh:
                if re.search(r'\\b{needle}\\b', fh.read()):
                    print(p)
"""],
            capture_output=True, text=True,
        )
        if result.stdout.strip():
            assert False, f"forbidden symbol {needle} still referenced in:\n{result.stdout}"
```

- [ ] **Step 1: Create + run test**

```bash
cd apps/api
py -3.13 -m pytest tests/unit/test_phase_e_deletions.py -v
```

Expected: all parametrized cases pass.

- [ ] **Step 2: Commit**

```bash
git add apps/api/tests/unit/test_phase_e_deletions.py
git commit -m "test(api): static-source regression for Phase E deletions (B-1)"
```

### Task 4.2: Frontend regression (optional smoke)

A simple bash check is fine since web doesn't have a dedicated unit-test framework wired up:

```bash
test ! -f apps/web/src/hooks/useOrchestrator.ts && echo "useOrchestrator deleted ✓"
test ! -f apps/web/src/lib/api/orchestrator.ts && echo "orchestrator API client deleted ✓"
test ! -f apps/web/src/lib/store/chatStore.ts && echo "chatStore deleted ✓"
```

Run as a manual check; no commit needed.

---

## Group 5: Final Verification

### Task 5.1: Full backend test suite

```bash
cd apps/api
py -3.13 -m pytest 2>&1 | tail -10
```

Expected: 0 failures from B-1 changes. Pre-existing failures unrelated to B-1 are out of scope (document them).

### Task 5.2: Frontend type-check + build

```bash
cd apps/web
npx tsc --noEmit 2>&1 | tail -5
npm run build 2>&1 | tail -10
```

Expected: clean.

### Task 5.3: Smoke test in dev environment

- [ ] **Step 1: Start backend + frontend with no env override**

```bash
# Note: NO NEXT_PUBLIC_USE_NEW_AGENT set anywhere
cd apps/api && py -3.13 -m uvicorn app.main:app --port 8000
# Other terminal:
cd apps/web && npm run dev
```

- [ ] **Step 2: Open /chat/<some-project> and verify new chat works**

If anything breaks, the issue is in the unconditional path that Phase B's flag gate was hiding. Fix and re-test.

- [ ] **Step 3: Confirm /settings/skills + /settings/mcp-servers still render**

### Task 5.4: PR + merge

After all verifications pass:

```bash
cd D:/ai-webtoon-studio
git push -u origin feat/b1e-legacy-deletion
gh pr create --base main --title "B-1: Phase E — legacy code deletion" --body "$(cat <<'EOF'
## Summary
- Deletes ~12 backend files (~2200 lines) replaced by Phase A unified agent runner
- Deletes 3 frontend files (useOrchestrator, orchestrator API client, chatStore)
- Removes NEXT_PUBLIC_USE_NEW_AGENT flag — new path is unconditional
- Adds static-source regression tests guarding against accidental resurrection

## Test plan
- [x] Backend: full pytest suite green
- [x] Frontend: tsc + build clean
- [x] Smoke: chat / skills / MCP servers all functional with no flag set

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review

**Spec coverage:**
- §10.1 待删 list: all 12 backend files covered by Tasks 1.1-1.6
- §10.7 chatStore option A (delete): Task 2.2
- §10.3 feature flag removal: Task 3.1
- §10.5 phase E test types: Task 4.1

**Placeholder scan:** None — every step has concrete file paths or commands.

**Type consistency:** Tasks 3.1 step 2 + 3 require ChatPanel and episode page to keep the same prop shape after flag removal — verify before commit.

---

## Execution Handoff

Plan complete. Use **subagent-driven-development** to execute with care — each deletion task has independent verification (grep for callers before delete). After Phase E lands, B-1 is fully shipped.

End-to-end milestone: B-1 unified agent runner is the only chat code path; legacy is history.
