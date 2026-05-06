# B-1 Phase D — Feature Flag Flip + Observation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (this is a verification-heavy phase, not subagent-friendly).

**Goal:** Turn `NEXT_PUBLIC_USE_NEW_AGENT=true` in dev/staging, run real-LLM end-to-end smoke, hold for 1 week observation, then green-light Phase E (legacy code deletion).

**Architecture:** No code changes. Environment + observation only. Pre-existing code paths exercised under real LLM provider. Decision gate at end determines whether E proceeds.

**Reference spec:** `docs/superpowers/specs/2026-05-06-b1-unified-agent-runner-design.md` §10.6 Rollback matrix — Phase D is the last fully-reversible step.

**Estimated effort:** ~1 week wall-clock (~2 hours active work + 5 days passive observation).

**Phase D does NOT:** delete any code (Phase E), modify backend (Phase A done), modify frontend (Phase B done).

---

## Pre-flight

- [ ] **Step 0: Confirm starting state**

```bash
cd D:/ai-webtoon-studio
git checkout feat/b1c-episode-delegation
git log --oneline -5
```

- [ ] **Step 0.1: Create Phase D branch**

```bash
git checkout -b feat/b1d-flag-flip
```

Phase D's commits are config-only (env files, runbook docs); no app code changes.

---

## Group 1: Configure Real LLM Provider for Smoke

### Task 1.1: Verify backend LLM provider config

- [ ] **Step 1: Inspect current settings**

```bash
cd D:/ai-webtoon-studio/apps/api
grep -E "^LLM_PROVIDER|^OPENAI_API_KEY|^DEEPSEEK_API_KEY|^DOUBAO_API_KEY|^ANTHROPIC_API_KEY|^LLM_MODEL_FLAGSHIP|^LLM_MODEL_FAST" .env 2>/dev/null
```

- [ ] **Step 2: Pick a provider and configure**

Choose one of: `openai`, `deepseek`, `doubao`, `tongyi`, `anthropic`. Doubao is recommended for CN dev (faster RTT, has prompt cache).

Edit `apps/api/.env` (gitignored):
```
LLM_PROVIDER=doubao
DOUBAO_API_KEY=<your key>
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
LLM_MODEL_FLAGSHIP=doubao-pro-32k
LLM_MODEL_MID=doubao-pro
LLM_MODEL_FAST=doubao-lite-32k
```

- [ ] **Step 3: Verify provider connection**

```bash
cd apps/api
py -3.13 -c "
import asyncio
from app.services.agent.llm_provider import get_llm_provider
from app.services.agent.llm_types import LLMMessage

async def test():
    p = get_llm_provider()
    print('provider:', p.name)
    chunks = []
    async for c in p.stream(
        system='You are a test bot.',
        messages=[LLMMessage(role='user', content='Reply with just the word OK')],
        tools=None,
        model='doubao-lite-32k',
        max_tokens=20,
    ):
        chunks.append(c)
        if c.type == 'content_delta':
            print(c.delta, end='', flush=True)
        if c.type == 'stop':
            print(); print('stop_reason:', c.stop_reason)
asyncio.run(test())
"
```

Expected: prints something like `OK\nstop_reason: stop`. If it errors, fix the API key / base_url before continuing.

### Task 1.2: Verify Redis is running (cancellation backend)

```bash
cd apps/api
py -3.13 -c "
import asyncio, redis.asyncio as aio
from app.core.config import settings
async def t():
    r = aio.from_url(settings.REDIS_URL, decode_responses=True)
    await r.set('test', '1', ex=10)
    print('redis OK')
asyncio.run(t())
"
```

If Redis isn't running locally, start it:
```bash
cd D:/ai-webtoon-studio/docker
docker compose up -d redis
```

### Task 1.3: Configure frontend env

- [ ] **Step 1: Create / edit `apps/web/.env.local` (gitignored)**

```
NEXT_PUBLIC_USE_NEW_AGENT=true
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8000
```

- [ ] **Step 2: Restart Next.js dev server to pick up env**

```bash
cd apps/web
npm run dev
```

The flag is now ON in dev.

---

## Group 2: Automated Smoke Tests

### Task 2.1: Run full backend test suite

```bash
cd D:/ai-webtoon-studio/apps/api
py -3.13 -m pytest 2>&1 | tail -10
```

Expected: all tests pass. If pre-existing tests fail (unrelated to B-1), document but don't block. If B-1 tests fail (any in `tests/unit/services/agent/`, `tests/integration/agent/`, etc.), STOP and fix.

### Task 2.2: Run frontend type-check + build

```bash
cd D:/ai-webtoon-studio/apps/web
npx tsc --noEmit 2>&1 | tail -5
npm run build 2>&1 | tail -10
```

Expected: clean tsc, successful build with `/settings/skills`, `/settings/mcp-servers` registered, no new build warnings beyond pre-existing.

---

## Group 3: Real-LLM Manual E2E Smoke

This is **manual** — exercise the user-facing flow with real LLM and check observability.

### Task 3.1: Chat end-to-end with tool calls

- [ ] **Step 1: Open browser to dev server**

`http://localhost:3001`

- [ ] **Step 2: Navigate to /chat/<some-existing-project-id>**

If no project exists yet, create one via UI or via existing seed scripts.

- [ ] **Step 3: Send a chat message that triggers a tool**

Example: `"List my characters."` → should call `query_assets(asset_type=character)` tool.

Verify in UI:
- [ ] User message appears immediately on the right
- [ ] Streaming "thinking..." indicator appears
- [ ] Assistant text streams in token-by-token (or near-instant for fast model)
- [ ] If a tool was called, a `ToolCallCard` appears with collapsed args
- [ ] Tool result appears (success / dispatched stub)
- [ ] Final assistant message appears
- [ ] State indicator returns to idle / done

Verify in backend logs:
- [ ] `webtoon.trace` JSON spans emitted (look for `agent_loop`, `agent_step`, `llm_call`, `tool_call`)
- [ ] No exceptions in API server output
- [ ] `ConversationMessage` rows persisted (check via `sqlite3 apps/api/webtoon_studio.db "select id, role, content from conversation_messages order by created_at desc limit 5"`)
- [ ] `ConversationAction` rows persisted with `trace_id` and `skill_id` populated

### Task 3.2: Episode page chat

- [ ] **Step 1: Navigate to /agent/<projectId>/episodes/1**
- [ ] **Step 2: Confirm new "Agent Chat" panel appears at bottom**
- [ ] **Step 3: Send a message specific to the episode (e.g. "Show me the panels for this episode.")**
- [ ] **Step 4: Verify same observability as Task 3.1**

### Task 3.3: Skills page

- [ ] **Step 1: Navigate to /settings/skills**
- [ ] **Step 2: Confirm 5 builtin skills listed** (webtoon-storyboard-design, webtoon-character-design, webtoon-scene-anchor, webtoon-quality-check, webtoon-render-strategy)
- [ ] **Step 3: Click "Install Skill", try installing a fake URL → expect graceful error**

### Task 3.4: MCP servers page

- [ ] **Step 1: Navigate to /settings/mcp-servers**
- [ ] **Step 2: Confirm empty state**
- [ ] **Step 3: Click "Add Server"; verify the security warning dialog renders + checkbox is required**

### Task 3.5: Cancellation

- [ ] **Step 1: Send a message that triggers a long tool call** (e.g. `"Render all panels in this episode"` if you have rendered panels)
- [ ] **Step 2: While streaming, click Cancel button**
- [ ] **Step 3: Verify state moves to "Canceled" within 1-2 seconds**
- [ ] **Step 4: Verify Redis flag was set** (`redis-cli get agent:cancel:<conversation_id>`)

### Task 3.6: Episode endpoint button path (Phase C delegation)

- [ ] **Step 1: Use existing /agent/<projectId>/episodes/N "Generate Script" button (legacy UI)**
- [ ] **Step 2: Verify the SSE stream works as before** (this exercises Phase C delegation)
- [ ] **Step 3: Verify tool spans show up in trace logs** (the button path now flows through the same tool handlers as chat)

---

## Group 4: Observation Hold (Async, ~1 week)

After all Group 3 manual checks pass, leave the system running with the flag on for **at least 5 working days** of incidental use. During this period:

- [ ] **Daily check**: any new error in API logs? (`docker compose logs --since 24h api | grep -iE 'error|exception'`)
- [ ] **Daily check**: any user-reported issues with chat? (no team in v1, so this is single-user dev observation)
- [ ] **Weekly check**: review trace span volumes — anything anomalous like very long llm_call spans, repeat tool failures, etc.

The plan's spec D.6 says "1-week observation". Adjust as fits — 5 working days is the minimum.

### Task 4.1: Daily observation log

Keep a simple text file `docs/superpowers/plans/b1-phase-d-observation-log.md`:

```
# B-1 Phase D Observation Log

## Day 1 (YYYY-MM-DD)
- chat sessions: N
- p0 issues: 0
- p1 issues: 0
- notes: ...

## Day 2 ...
```

Commit periodic updates:
```bash
git add docs/superpowers/plans/b1-phase-d-observation-log.md
git commit -m "docs: B-1 Phase D observation log day N"
```

---

## Group 5: Decision Gate

### Task 5.1: Decide whether to proceed to Phase E

Criteria for green-light:
- ✓ Group 2 automated smokes are green
- ✓ All Group 3 manual checks passed
- ✓ ≥5 working days of incidental use without P0 / P1 issues
- ✓ Trace logs show normal volume + no repeat exceptions
- ✓ No legacy chat path failures observed

If green-light:
- Proceed to Phase E (legacy code deletion)
- Document the green-light decision in observation log

If red:
- Identify root cause of issue(s)
- Create fix tasks (likely cherry-pick onto a `fix/b1-*` branch from Phase A or B)
- Re-run Group 2 + 3 after fixes
- Reset observation period
- Do NOT proceed to Phase E

### Task 5.2: Final commit

If proceeding to E:

```bash
cd D:/ai-webtoon-studio
git add docs/superpowers/plans/b1-phase-d-observation-log.md
git commit -m "docs: B-1 Phase D observation complete — green-light for Phase E"
```

---

## Self-Review

**Spec coverage:**
- §10.4 D phase definition ("Flip flag + 1-week observation") — Groups 2 + 3 + 4
- §10.6 Rollback matrix — D rollback = "flag → false" — automatic via env change
- §6 Streaming protocol — manually verified via Task 3.1

**Placeholder scan:** None — every step has concrete commands or checklists.

**Type consistency:** N/A (no code changes).

---

## Execution Handoff

Plan complete. Use **executing-plans** skill (NOT subagent-driven-development) since this is verification-heavy and requires user judgment + manual UI interaction. Most tasks are checklist items, not code changes.

After D green-lights, proceed to Phase E plan.
