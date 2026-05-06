# B-1 Unified Agent Runner — Design Spec

**Date**: 2026-05-06
**Status**: Draft (awaiting user review)
**Scope**: γ (full extensibility — includes MCP server bidirectional + Skills system)
**Estimated effort**: ~5.5 weeks focused engineering
**Depends on**: PR #2 (`feat/studio-pipeline-refactor`) merged to `main`
**Successor**: B-2 (tracing/observability dashboard, no cost tracking — user explicitly deferred)

---

## 1. Background & Motivation

### Current state
The codebase has accumulated **three independent chat-driven backends**:

| Path | Frontend usage | Status |
|---|---|---|
| `/api/v1/agent/episode/*` | `useScriptStream`, `episodeApi.ts`, `VideoGenerateDialog`, `VideoCard` | Active — PR #1 work; uses `agent_commit/` package |
| `/api/v1/orchestrator/*` | `useOrchestrator.ts` | Legacy — different `StudioOrchestrator` implementation |
| `/api/v1/conversations/{id}/messages/stream` | None (frontend only calls CRUD) | Dead — `AgentOrchestrator` → `AssetAgent`/`ScriptAgent` are TODO stubs |

The legacy paths route by **regex keyword matching** (`intent_router.py`) — a pattern that 2024-era function-calling LLMs make obsolete. The TODOs in `asset_agent.py:116,138,191,212` and `script_agent.py:206` are user-facing capabilities (create character, refine script) that simply don't work today.

### Goals

1. **Consolidate** three chat backends into one canonical path
2. **Replace regex routing** with LLM-native function calling + multi-step agent loop
3. **Make the agent platform extensible** via:
   - Bidirectional MCP server (expose Webtoon Studio tools to external clients; consume external MCP servers)
   - Skills system (markdown-only or MCP-wrapped capability packages, installable from local/url/git)
4. **Bake in tracing** from day 1 (OTel-compatible structured spans; no UI yet)
5. **Retire** ~12 legacy files (~2200 lines) cleanly

### Non-goals (explicitly deferred)

- **USD cost tracking** — user chose dimensions (i)+(ii) but explicitly skipped cost
- **Rate limiting / token budgets** — B-3
- **Permission/ACL beyond per-user MCP token scopes** — B-3
- **Eval harness for prompt regression** — B-4
- **Skill code sandboxing** (Docker/seccomp/namespace) — B-1.5+; v1 forbids tool-bundled external skills as compensation
- **OTel collector + trace UI** — B-2
- **Skill marketplace UI / discovery** — B-1.7
- **Cross-provider LLM fallback** — B-1.5+

### Why approach C (universal agent runner with optional context)

Three architectures considered:
- **A** Conversation-centric (`POST /v1/conversations/{id}/messages/stream`)
- **B** Two endpoints (`/v1/agent/chat` + `/v1/agent/episode/{N}/chat`)
- **C** Single endpoint with `context` in request body

**C chosen** because:
1. Single canonical entry point (no URL forking by use case)
2. Tools auto-filter by `context` — episode tools available iff `episode_number` provided
3. Cleanest fit for extensibility plane (skills/MCP register tools that key off context)
4. Frontend reduces to one hook (`useChat`)

---

## 2. API Surface

### Endpoints

```
POST /v1/agent/chat                                # SSE stream — main entry
GET  /v1/agent/conversations/{id}                   # conversation metadata
GET  /v1/agent/conversations/{id}/messages          # paginated history
GET  /v1/agent/conversations                        # list, filter by project/episode
POST /v1/agent/conversations                        # explicit create (chat usually auto-creates)
POST /v1/agent/conversations/{id}/cancel            # interrupt active loop
DELETE /v1/agent/conversations/{id}                  # soft delete

# Skills
GET  /v1/skills
POST /v1/skills/install                              # body: {source_type, source_url, scope, project_id?}
POST /v1/skills/{id}/enable
POST /v1/skills/{id}/disable
DELETE /v1/skills/{id}

# MCP — inbound (external clients consuming us)
POST /v1/mcp/messages                                # MCP Streamable HTTP (preferred)
GET  /v1/mcp/messages                                # SSE upgrade for streamable_http
GET  /v1/mcp/sse                                     # MCP SSE transport (legacy clients)

# MCP — outbound management
GET  /v1/mcp/connections
POST /v1/mcp/connections                              # add external MCP server
POST /v1/mcp/connections/{id}/reconnect
DELETE /v1/mcp/connections/{id}
```

### Request body — `POST /v1/agent/chat`

```typescript
{
  conversation_id?: string,        // existing → continue; absent → auto-create
  message: string,
  context: {
    project_id: string,            // REQUIRED
    episode_number?: number,
    panel_id?: string,
    chapter_id?: string,
  },
  attachments?: Attachment[],      // reserved for multimodal
  options?: {
    max_steps?: number,            // default 10
    tools_allowlist?: string[],
    model?: string,                // override ModelRouter
  }
}
```

### Streaming protocol decisions

- **SSE** chosen over WebSocket: HTTP-friendly, Nginx passthrough trivial, current `useScriptStream` already uses SSE, cancellation via separate REST call
- **`context.project_id` is required** — agent without a project has no meaning; frontend always knows project from route

---

## 3. Agent Loop

### Pseudocode

```python
async def run_agent_loop(conversation_id, user_message, context, options):
    persist_user_message(conversation_id, user_message)
    
    for step in range(options.max_steps):
        if is_canceled(conversation_id):
            emit("agent_done", reason="user_canceled")
            return

        history = load_messages(conversation_id)
        tools = compute_available_tools(context, options.tools_allowlist)
        skill_guidance = match_and_pack_skills(context, cap_tokens=10000)

        async for chunk in llm.stream(
            system=SYSTEM_PROMPT + skill_guidance,
            messages=history,
            tools=tools,
            model=ModelRouter.select(step_context),
        ):
            if chunk.type == "content_delta":
                emit("assistant_message_chunk", delta=chunk.delta)
            elif chunk.type == "tool_call":
                tool_calls.append(chunk.tool_call)
                emit("tool_call", ...)

        persist_assistant_message(...)

        if not tool_calls:
            emit("agent_done", reason="stop")
            return

        results = await execute_tools(tool_calls, conversation_id)
        for r in results:
            emit("tool_result", ...)
            persist_tool_result(...)

    emit("agent_done", reason="max_steps")
```

### Termination conditions

| reason | trigger | follow-up |
|---|---|---|
| `stop` | LLM stops requesting tools | normal close |
| `max_steps` | loop ran `max_steps` still calling tools | warn, close, set `agent_state=paused`, user nudge resumes |
| `user_canceled` | `POST /cancel` flag detected at step boundary | cleanup, close. **Running Celery jobs not killed** (let finish; result stored but not fed back to LLM) |
| `error` | unrecoverable exception (LLM API down after retries, DB error) | `error` event, close, `agent_state=error` |

### Parallel tool calls

- Read-only tools (marked `read_only: true`): execute concurrently with `asyncio.gather`
- Write tools: execute serially in submission order
- Mixed in same step: read-onlys run in parallel first, then writes serial

### Cancellation semantics

- `POST /v1/agent/conversations/{id}/cancel` writes Redis flag `agent:cancel:{conv_id}` (TTL 5min)
- Loop checks at every step entry + before feeding back tool result
- In-flight Celery tasks are **not** force-terminated (avoids half-done state corruption); their result lands in `ConversationAction.result_json` but is not appended to LLM context

### Long-running tools — γ hybrid strategy

Each tool declares `expected_duration: "fast" | "slow"`:

- **fast (<10s)**: synchronous in loop. Examples: `query_assets`, `refine_script`, `analyze_quality`
- **slow**: dispatch to Celery → return `{success: true, dispatched: {job_id, eta_seconds}}` to agent immediately. Agent typically replies "started, will notify when done" and stops. **Loop does NOT auto-resume on completion** (no-wakeup policy). Real progress flows over WS `jobs:{job_id}` channel; frontend correlates by `job_id`.

Rationale for no-wakeup: predictable behavior, bounded token cost, no runaway agent risk. Multi-step "do A then B" intents require user nudge between async steps. Acceptable tradeoff for v1; chaining can be opt-in via `options.auto_chain` later.

### Step persistence

Each step produces:
- 0 or 1 `ConversationMessage(role="assistant", content=..., tool_calls_json=[...])`
- N `ConversationAction(action_type=tool_name, ..., status, result_json | error_json)`

Tool result fed back to LLM in next step uses `role="tool", tool_call_id=..., content=json(result)` per OpenAI/Anthropic convention.

---

## 4. Tools + Context-Conditional Visibility

### Tool definition (MCP-compatible schema)

```python
@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str                 # what LLM reads to decide whether to call
    json_schema: dict                 # JSON Schema for parameters (OpenAI/Anthropic/MCP universal)
    handler: Callable
    requires_context: list[str]       # context keys that must exist for tool to be visible
    expected_duration: Literal["fast", "slow"]
    read_only: bool                   # determines parallel/serial scheduling
    side_effects: list[str]           # "writes:asset", "writes:render_job", ... (B-3 ACL hook)
    source_skill_id: str | None       # which skill provides this tool; None = built-in
```

### Visibility computation

```python
def compute_available_tools(context, allowlist=None) -> list[ToolDefinition]:
    available = []
    for tool in TOOL_REGISTRY.all():
        if not all(k in context and context[k] is not None for k in tool.requires_context):
            continue
        if allowlist is not None and tool.name not in allowlist:
            continue
        available.append(tool)
    return sorted(available, key=lambda t: t.name)   # deterministic for prompt cache
```

### v1 built-in tool catalog (15 tools)

| Tool | requires_context | duration | read_only | Notes |
|---|---|---|---|---|
| `query_assets` | `project_id` | fast | ✓ | List/filter assets |
| `query_episodes` | `project_id` | fast | ✓ | List episodes + status |
| `query_panels` | `project_id` | fast | ✓ | List panels + preview |
| `generate_script` | `project_id, episode_number` | slow | ✗ | Replaces `/script/stream` |
| `refine_script` | `project_id, episode_number` | fast | ✗ | Replaces `/refine` |
| `analyze_script` | `project_id, episode_number` | fast | ✓ | Pure parse |
| `generate_panels` | `project_id, episode_number` | slow | ✗ | Replaces `/generate-panels` |
| `regenerate_asset_image` | `project_id, asset_id` | slow | ✗ | **NEW** — episode page TODO button |
| `create_character` | `project_id` | slow | ✗ | Replaces `asset_agent._create_character` TODO |
| `create_scene` | `project_id` | slow | ✗ | Replaces `asset_agent._create_scene` TODO |
| `render_panels` | `project_id, episode_number` | slow | ✗ | Replaces `tool_handlers.render_panels` |
| `analyze_quality` | `project_id, panel_id` | fast | ✓ | Replaces `tool_handlers.analyze_quality` |
| `suggest_fixes` | `project_id, panel_id` | fast | ✓ | Replaces `tool_handlers.suggest_fixes` |
| `commit_to_studio` | `project_id, episode_number` | slow | ✗ | Reuses `agent_commit/commit_orchestrator` |
| `update_panel_dialogue` | `project_id, panel_id` | fast | ✗ | New — wraps PATCH /panels/{id} |
| `update_panel_camera` | `project_id, panel_id` | fast | ✗ | Same |

### File layout

```
app/services/agent/
├── runner.py                   # main loop
├── llm_provider.py             # multi-provider function-calling adapter (§7)
├── tool_registry.py            # registration + context filtering
├── trace.py                    # tracing skeleton (§12)
├── skills/                     # skills system (§9)
│   ├── loader.py
│   ├── manifest.py
│   ├── installer.py
│   ├── matcher.py
│   ├── lifecycle.py
│   └── cli.py
├── mcp_server.py               # inbound MCP (§8)
├── mcp_client_pool.py          # outbound MCP
├── mcp_auth.py
├── mcp_tool_adapter.py
└── tools/                      # one file per tool
    ├── __init__.py
    ├── query_assets.py
    ├── generate_script.py
    └── ...
```

---

## 5. State Model

### Existing tables — column additions

#### `Conversation`
- ADD `agent_state: VARCHAR(16)` default `idle` — values: `idle | running | paused | error | done | canceled`
- Existing `status` field (`active|archived|deleted`) is the conversation-lifecycle axis; `agent_state` is the per-loop state machine. Two are orthogonal.

#### `ConversationMessage`
- ADD `trace_id: VARCHAR(64)` indexed
- ADD `finish_reason: VARCHAR(32)` — `stop | tool_calls | length | content_filter | error`

#### `ConversationAction`
- ADD `trace_id: VARCHAR(64)` indexed
- ADD `job_id: VARCHAR(64)` indexed — Celery task id for slow/dispatched tools
- ADD `skill_id: VARCHAR(64)` indexed — which skill provides the tool (`builtin` for native)

### New tables

#### `skill_installations`
```python
class SkillInstallation(Base):
    id: str (PK)
    name: str (indexed, ≤128)
    version: str (≤32, SemVer)
    
    source_type: str       # builtin | local | url | git | mcp_only
    source_url: str | None
    install_path: str | None
    
    manifest_json: JSON
    
    status: str            # active | disabled | failed | uninstalled
    failure_reason: str | None
    
    scope: str             # global | project
    project_id: str | None (indexed)
    
    installed_at: datetime
    last_loaded_at: datetime | None
    
    UNIQUE (name, scope, project_id)
```

#### `mcp_server_connections`
```python
class McpServerConnection(Base):
    id: str (PK)
    name: str (≤128)
    
    transport: str         # stdio | sse | streamable_http
    command: str | None
    args_json: JSON | None
    url: str | None
    env_json: JSON | None
    
    skill_id: str | None (indexed)   # populated if owned by a skill
    
    status: str            # connected | disconnected | failed
    last_connected_at: datetime | None
    last_error: str | None
    capabilities_json: JSON | None    # cached tool list from server
    
    scope: str             # global | project
    project_id: str | None (indexed)
    
    created_at: datetime
```

#### `mcp_access_tokens`
```python
class McpAccessToken(Base):
    id: str (PK)
    token_hash: str (UNIQUE, indexed)   # SHA-256 of plaintext token; plaintext shown once at creation
    name: str (≤128)                     # user-given label
    user_id: str (indexed)
    scopes_json: JSON                    # e.g. {"projects": ["p1"], "tools": ["query_*", "render_panels"]}
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    revoked_at: datetime | None
```

### Cancellation — Redis (not DB)

```
Key: agent:cancel:{conversation_id}
Value: "1"
TTL: 5 minutes
```

Loop checks at step boundaries. High-frequency state, no audit value, TTL prevents stale state.

### State machines

```
agent_state:    idle → running → {done | paused | error | canceled} → idle (next user message)
SkillInstallation.status:    installing → {active | failed} → {disabled ↔ active} → uninstalled
McpServerConnection.status:  disconnected → connected → {disconnected | failed}
```

### Migration

Single migration `022_unified_agent_runner.py`:
- ALTER on existing 3 tables (use `op.batch_alter_table` for SQLite compatibility — precedent: migrations 003, b9a98c1685f5)
- CREATE 3 new tables with indexes
- Down only drops new tables + columns (no data restoration)

---

## 6. Streaming Protocol

### Wire format

```
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no

event: <event_type>
id: <monotonic_id_per_conversation>
data: <single-line JSON>

```

Heartbeat every 15s as SSE comment `: heartbeat\n\n` (no event triggered).

### Loop ↔ stream decoupling (critical)

**Agent loop runs in async background task; SSE is observation window only.**
- Disconnect during stream → loop continues, results land in DB
- Reconnect: client pulls `GET /conversations/{id}/messages` to catch up. v1 does NOT support Last-Event-ID resume.
- Multiple SSE clients on same conversation: server fanout via per-conversation `asyncio.Queue` listener registry.

### Event catalog

```
# Lifecycle
conversation_started   { conversation_id, user_message_id, created_new }
agent_step_started     { step_index, model }
agent_step_completed   { step_index, tool_calls_emitted }
agent_done             { reason, total_steps, total_tool_calls }   ← always last

# Assistant streaming
assistant_message_chunk    { message_id, delta }
assistant_message_complete { message_id, content, finish_reason }

# Tools
tool_call         { action_id, tool_name, args, skill_id }
tool_executing    { action_id }
tool_progress     { action_id, progress, message }       ← fast tools only, rare
tool_result       { action_id, success, result | error | dispatched }
                  # dispatched = { job_id, eta_seconds } for slow tools

# Errors
error             { code, message, recoverable }
```

### Error codes

| code | recoverable | meaning |
|---|---|---|
| `LLM_PROVIDER_ERROR` | false | LLM API call failed after retries |
| `LLM_TIMEOUT` | false | LLM single-call timeout |
| `RATE_LIMITED` | false | LLM API rate limit |
| `TOOL_EXECUTION_ERROR` | true | tool internal exception (loop feeds error back to LLM) |
| `TOOL_TIMEOUT` | true | tool execution timeout |
| `TOOL_INVALID_ARGS` | true | LLM provided args failed JSON Schema validation |
| `TOOL_NOT_FOUND` | true | LLM called nonexistent tool |
| `SKILL_LOAD_ERROR` | true | skill load failed (skipped, loop continues) |
| `MCP_DISCONNECTED` | true | external MCP server dropped |
| `INTERNAL_ERROR` | false | server-side exception |

### Slow-tool progress division of labor

- chat SSE: emits **only** `tool_result` with `dispatched=true` + `job_id`
- Real progress flows over existing **WS `/ws` channel** (`job_progress`, `job_status`, `layerpack_ready`, `clip_status`, etc.)
- Frontend correlates WS events back to chat tool result via `job_id`
- Rationale: avoid duplicating progress on two streams (synchronization nightmare)

### Backpressure & concurrency

- Per-listener queue `maxsize=1000` events; full → drop oldest + emit `INTERNAL_ERROR` + close stream
- Per-conversation: only **1 active loop** at a time. Second `POST /v1/agent/chat` on same `conversation_id` → `409 CONVERSATION_BUSY`
- Multi-observer: any number of concurrent SSE listeners

### Event IDs

Monotonic integers per `(conversation_id, message_id)`. v1 does not journal; reserved for v1.5 Last-Event-ID resume.

---

## 7. LLM Provider Adapter

### Interface

```python
class LLMProvider(ABC):
    async def stream(
        self,
        system: str,
        messages: list[LLMMessage],
        tools: list[ToolDefinition] | None,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        cache_hint: bool = True,
    ) -> AsyncIterator[StreamChunk]: ...
    
    @property
    def name(self) -> str: ...
    @property
    def supports_tools(self) -> bool: ...
    @property
    def supports_streaming_tool_calls(self) -> bool: ...
```

### Provider implementations

| Provider | SDK | Notes |
|---|---|---|
| OpenAI | `openai>=1.x` | Tool-call streaming has incremental index — must reassemble |
| Anthropic | `anthropic>=0.40` | system separate; explicit `cache_control` for cache marking |
| DeepSeek | OpenAI-compatible | Automatic prefix caching, no config |
| Doubao | OpenAI-compatible (`https://ark.cn-beijing.volces.com/api/v3/`) | Use ARK_API_KEY |
| Tongyi | OpenAI-compatible | DashScope key |

**Implementation strategy**: 4 of 5 (all except Anthropic) share an `OpenAICompatibleProvider` class differing only by base_url + api_key.

### Prompt structure (cache-friendly)

Every LLM call's message list segments into 5 blocks (in order):

```
[1] System prompt          (fully static — always cache hit)
[2] Tool definitions       (context-filtered, sorted by name → stable bytes per context)
[3] Skill guidance         (eager-with-cap, see §9; stable per matching set)
[4] Conversation history   (grows incrementally; prefix caches)
[5] Current user message   (only new content)
```

Anthropic explicit cache marking:
```python
[{"role": "user", "content": [
    {"type": "text", "text": "<history>", "cache_control": {"type": "ephemeral"}},
    {"type": "text", "text": "<current message>"}
]}]
```

OpenAI/DeepSeek/Doubao: automatic prefix detection — character-stable prefix → automatic cache hit.

### Model routing (3-tier)

```python
class ModelRouter:
    def select(self, step_context: StepContext) -> str:
        if step_context.user_force_model:
            return step_context.user_force_model
        if step_context.is_simple_chat:        # no tool calls in history
            return settings.MODEL_FAST           # doubao-lite / gpt-4o-mini
        if step_context.has_tool_results:       # summarize after tool
            return settings.MODEL_MID            # doubao-pro / gpt-4o-mini
        return settings.MODEL_FLAGSHIP           # doubao-pro-32k / gpt-4o
```

### Function calling normalization

Tool-call streaming differs by provider; adapter normalizes to:
- `StreamChunk(type="tool_call_delta", tool_call_index=i, delta=...)` during streaming
- `StreamChunk(type="tool_call_done", tool_call=ToolCallSpec(...))` at completion

### Retry policy

- Exponential backoff: 1s → 2s → 4s → 8s
- Triggers: 429, 5xx, network error
- Skip: 4xx (except 429), content_filter
- After 3 retries → `LLMProviderError`
- **No cross-provider fallback in v1** (B-1.5+)

### Settings

```python
LLM_PROVIDER: Literal["openai", "anthropic", "deepseek", "doubao", "tongyi"]
LLM_MODEL_FLAGSHIP: str
LLM_MODEL_MID: str
LLM_MODEL_FAST: str
LLM_MAX_RETRIES: int = 3
LLM_TIMEOUT_SECONDS: int = 60
LLM_PROMPT_CACHE_ENABLED: bool = True
```

### Latency notes (no quality compromise)

Practical impact, ranked:
1. **Prompt caching** — -30% to -80% latency, -50% to -90% cost. Free given §7 prompt structure
2. **Smaller-model routing** for simple/follow-up steps — -50% to -70% on those steps
3. **Tool list context-filtering** — -5% to -15% TTFT (already enforced by §4)
4. **Parallel read-only tools** — best-case halves total tool-call latency (already enforced)
5. **Closer geo provider** — -100~-300ms RTT (Doubao Beijing vs OpenAI for CN users)

**RAG is NOT a latency optimization** for this project. Project knowledge is structured (Asset/Panel/Episode tables) and has tool-based access already (`query_*`). RAG would only help long-conversation memory (B-2+) and ALWAYS adds per-call latency, not subtracts.

---

## 8. MCP Server Architecture (Bidirectional)

### Inbound — Webtoon Studio as MCP server

#### Transport
- Primary: **Streamable HTTP** (MCP 2025-06+ standard) at `POST /v1/mcp/messages` and `GET /v1/mcp/messages` (SSE upgrade)
- Compatibility: **SSE** at `/v1/mcp/sse` for legacy clients (older Claude Desktop)
- No stdio (HTTP service has no use for it)

#### SDK
Anthropic official `mcp>=1.0` Python SDK — server + client primitives.

#### Auth
- Bearer token: `Authorization: Bearer <token>`
- Token from `mcp_access_tokens` table; SHA-256 stored, plaintext shown once at creation
- Scopes: per-token JSON `{projects: [...], tools: [...]}` whitelist

#### What's exposed (v1)
- **Tools only**, not Resources or Prompts
- Same 15 built-in tools, **but every `requires_context` field is lifted to a JSON Schema required parameter** since external clients have no implicit context.
  - Internal: `render_panels({panel_ids})` (project_id from context)
  - External MCP: `render_panels({project_id, episode_number, panel_ids})`
- Adapter does this lift automatically (no per-tool boilerplate)

#### Rate limiting
- 100 RPM/token global
- 10 RPM/token for slow tools (render_panels, generate_panels, etc.)
- Redis sliding window

#### Audit
Every inbound MCP call → write `ConversationAction` record under a synthetic conversation `external-mcp-{token_id}`.

### Outbound — Webtoon Studio as MCP client

#### Connection lifecycle (`mcp_client_pool.py`)
- App startup: load all `status=connected` rows from `mcp_server_connections`, attempt connect
- Handshake → `list_tools` → cache to `capabilities_json` → register tools to `TOOL_REGISTRY` with `source_skill_id="mcp:{conn.id}"`
- Health check: 30s ping; failure → mark `disconnected`, deregister tools
- Reconnect retries: 1min, 5min, 15min, then give up; user manual reconnect

#### Tool naming
External tool names prefixed `mcp_{conn_id}_{original_name}` to prevent collision.
LLM sees normal `original_name` in description; runner internally maps back to prefixed handler.

#### Trust boundary (CRITICAL — v1 known limitation)
- stdio transport spawns a child process with our env (filtered)
- That process can read our filesystem, make network calls
- v1 mitigations:
  1. Default scope `user` (only installer can use it in their chats)
  2. UI dialog with security warning + checkbox confirm
  3. All outbound tool calls audit-logged
  4. stdio command path validated (no `bash`/`sh`/`python -c`)
  5. Env var allowlist (no inheriting full API process env)
- v1 does **NOT** sandbox (Docker/namespace/seccomp). Listed as known limitation; B-1.5+ adds sandboxing.

#### Failure handling
External MCP server failure does not block API startup. Status `failed` + `last_error` recorded; UI shows reconnect button.

---

## 9. Skills System

### Skill anatomy

A skill is a directory:

```
my-skill/
├── skill.yaml          # manifest (required)
├── SKILL.md             # procedural guidance for the LLM (optional but typical)
├── tools/              # Python tool handlers (optional; v1 BUILTIN ONLY)
│   ├── handler.py
│   └── ...
└── mcp_server/         # bundled MCP server config (optional)
    └── server.json
```

### `skill.yaml` schema

```yaml
name: webtoon-storyboard-design
version: 1.0.0
description: |
  Guides agent to break user stories into panels with framing, dialogue, and pacing notes.
author: Webtoon Studio Team
license: MIT

requires:
  webtoon_studio_min_version: "0.5.0"
  python: ">=3.11"

activation:
  intent_keywords: ["分镜", "storyboard", "panel breakdown"]
  context_required: [project_id]
  context_optional: [episode_number]

provides:
  guidance:
    file: SKILL.md
  tools:                                 # only valid for builtin skills in v1
    - name: ...
      handler: tools.module:func
      schema: { ... }
      expected_duration: fast
      read_only: false
  mcp_server:
    transport: stdio
    command: node
    args: [bin/server.js]
    env: { LOG_LEVEL: warn }
    auto_start: true

scope_default: project
```

### Skill types and v1 security policy

| Type | `provides` | Risk | v1 status |
|---|---|---|---|
| **markdown-only** | `guidance` only | None | Allowed (any source) |
| **mcp-wrapped** | `mcp_server` ± `guidance` | Subprocess (per §8 outbound) | Allowed (any source) |
| **tool-bundled** | `tools:` direct Python | **Arbitrary code in API process** | **Allowed only for builtin skills**; rejected for external sources |

**Hard rule v1**: external skills must be markdown-only or mcp-wrapped. To add tool capabilities, third-parties write an MCP server. Sandboxing is the prerequisite for relaxing this; see B-1.5+.

### Install sources

| `source_type` | Form | Example |
|---|---|---|
| `builtin` | bundled in repo | `apps/api/skills/<name>/` |
| `local` | local directory | `webtoon-skill install /path/to/skill` |
| `url` | HTTPS tarball/zip | `webtoon-skill install https://example.com/skill.tar.gz` |
| `git` | git repo (with subpath) | `webtoon-skill install git+https://github.com/u/r@v1#path=skills/foo` |

### Install layout

```
apps/api/skills/                                       # builtin (in repo)
{WEBTOON_DATA_DIR}/skills/global/{name}-{version}/      # global install
{WEBTOON_DATA_DIR}/skills/projects/{pid}/{name}-{ver}/  # project-scoped
```

`WEBTOON_DATA_DIR`: defaults `~/.webtoon` (dev), `/srv/webtoon/data` (prod).

### Install algorithm

1. Fetch source → temp dir
2. Validate manifest (schema check + type policy: external must not have `tools:`)
3. Signature verification — **v1 does not check** (known limitation)
4. Move to target path
5. `loader.load(skill)` → register tools / start MCP servers
6. Insert `SkillInstallation` row

### Bootstrap order

```
1. SkillLoader.bootstrap()
2. Scan apps/api/skills/ → register all builtin
3. Query SkillInstallation WHERE status='active' → load each
4. Failed loads → status='failed' + record last_error; do NOT block startup
5. McpClientPool.start() → start servers for mcp-wrapped skills
```

### Hot lifecycle

```
POST /v1/skills/install   → install + load (immediately usable)
POST /v1/skills/{id}/disable → unload (deregister tools, stop server) → status=disabled
POST /v1/skills/{id}/enable  → load again → status=active
DELETE /v1/skills/{id}        → unload + delete files + soft-delete row
```

v1 does not support multiple versions co-existing. Installing new version auto-disables old.

### Activation in agent loop — eager-with-cap (chosen)

Each step:
1. Score every active skill against current `(intent, context)`:
   - +10 per `intent_keywords` match
   - +5 if all `context_required` satisfied
   - +1 per `context_optional` match
2. Sort skills by score desc
3. Concatenate `SKILL.md` content into prompt segment [3], adding skill-by-skill until token budget `SKILL_GUIDANCE_TOKEN_CAP` (default 10000) reached
4. Wrap each in `<skill name="...">...</skill>` for boundary clarity

Rationale over alternatives:
- (a) Eager-all is cache-hostile at scale
- (c) Lazy-via-tool requires extra LLM round-trip; v1 small skill set doesn't justify

Migration from (b) to (c) is small if needed later: add `activate_skill` tool + alter system prompt template.

### Bundled v1 skills (5)

| Skill | Content | Activation |
|---|---|---|
| `webtoon-storyboard-design` | Story-to-panel craft, camera, bubble layout | intent: 分镜/storyboard |
| `webtoon-character-design` | Character sheet construction, FaceID reference selection | intent: 角色/character |
| `webtoon-scene-anchor` | Background anchor + ControlNet usage (also drives Phase C work) | intent: 场景/scene |
| `webtoon-quality-check` | When to run `analyze_quality`, decision tree on QA failure | tool result has quality fail |
| `webtoon-render-strategy` | Batch vs single-panel, seed/denoise tuning | intent: 渲染/render |

Each ≤2K tokens; total 5 ≤10K (= cap). User-installed external skills compete with builtins by score.

### Authoring CLI

```bash
webtoon-skill create my-skill              # scaffold
webtoon-skill validate ./my-skill          # local validation
webtoon-skill pack ./my-skill              # produces .tar.gz
webtoon-skill install ./my-skill           # local install
webtoon-skill install <url>                 # url install
webtoon-skill install git+<url>             # git install
webtoon-skill list
webtoon-skill enable <name>
webtoon-skill disable <name>
webtoon-skill uninstall <name>
```

Thin wrapper over `/v1/skills/*` REST.

### Management UI (B-1 scope; marketplace deferred to B-1.7)

`/settings/skills` page with:
- List of installed skills + status + scope
- "Install from URL" button + dialog (with manifest preview before confirm)
- Enable/disable/uninstall actions
- Detail panel showing full SKILL.md rendered

Same pattern at `/settings/mcp-servers` for outbound MCP.

Marketplace browsing/discovery (Anthropic registry, ratings, recommendations) → B-1.7.

### Known limitations

- No signature verification on external skills
- No code sandbox for tool-bundled (compensated by external prohibition)
- No multi-version co-existence
- No project-scoped install via UI in v1 (CLI/API only)

---

## 10. Migration Strategy

### Three-bucket inventory

#### Delete (final state)

```
app/services/agents/asset_agent.py
app/services/agents/script_agent.py
app/services/agents/rendering_agent.py
app/services/agents/qa_agent.py
app/services/agents/__init__.py
app/services/agents/   (whole dir)
app/services/conversation/agent_orchestrator.py
app/services/conversation/intent_router.py
app/services/conversation/tool_registry.py
app/services/conversation/tool_handlers.py
app/services/orchestrator/studio_orchestrator.py
app/api/routes/orchestrator.py
app/api/routes/conversations.py    # delete streaming endpoint code only; CRUD endpoints in same file stay
```

Total ~12 files, ~2200 lines.

#### Keep (no change)

- `app/services/agent_commit/*` (whole package — used by `commit-to-studio`)
- Conversation CRUD endpoints (frontend services.ts uses them)
- `app/api/routes/agent.py` episode endpoints (URL preserved; internals refactored)
- `app/api/routes/ws.py` (job-progress events, used per §6)

#### Refactor (URL preserved, internals delegated)

```
POST /agent/episode/{N}/script             → delegate to generate_script tool
POST /agent/episode/{N}/script/stream      → delegate to generate_script(stream=true) tool
POST /agent/episode/{N}/refine             → delegate to refine_script tool
POST /agent/episode/{N}/generate-panels    → delegate to generate_panels tool
POST /agent/episode/{N}/render (if exists) → delegate to render_panels tool
```

Rationale: button-triggered atomic operations don't fit chat shape. Keep direct endpoints. Tool handlers are the single source of truth used by both entry types.

### 5-phase rollout

| Phase | Duration | Cumulative |
|---|---|---|
| **A** Land new infra (no behavior change, feature-flagged) | 2.5w | 2.5w |
| **B** Frontend new chat shell (gated) | 1w | 3.5w |
| **C** Episode endpoint delegation refactor | 0.5w | 4w |
| **D** Flip flag + 1-week observation | 1w | 5w |
| **E** Delete legacy code + remove flag | 0.5w | 5.5w |

### Feature flag

Frontend-only single flag `NEXT_PUBLIC_USE_NEW_AGENT` (default `false`). Backend always runs new+old in parallel until phase E. Justification:

- Backend dual-flagging branches everywhere → unmaintainable
- Frontend flag suffices: which path hit decided client-side
- Phase E removes flag at one site

### Conversation data backward compatibility

Old `tool_calls_json` shape (`{tool_name, parameters}`) differs slightly from new (`{id, name, arguments}`). Reader normalizes on read; **no backfill migration**. Old conversations may have legacy entity formats — runner tolerates them silently.

### Tests per phase

| Phase | Test types |
|---|---|
| A | Unit (registry, provider, runner); static-source (15 tools registered, 5 builtin skills loadable); integration (mock LLM, run full loop) |
| B | Frontend component (useChat, ChatPanel snapshot at both flag states) |
| C | Static-source (PR #2 style) verifying episode endpoints delegate to tools; integration end-to-end (refine → generate-panels → render) |
| D | E2E with real LLM (chat → script → render); manual smoke tests |
| E | Static-source: deleted files don't exist; no remaining imports |

### Rollback matrix

| Phase | Rollback |
|---|---|
| A | Migration `down`; new code unused → safe |
| B | Flag → false |
| C | Single PR revert |
| D | Flag → false |
| E | Irreversible — D must be solid first |

---

## 11. Frontend Cutover

### `useChat` hook

```typescript
export interface UseChatOptions {
  conversationId?: string;
  context: { projectId: string; episodeNumber?: number; chapterId?: string; panelId?: string };
  toolsAllowlist?: string[];
  model?: string;
  onToolCall?: (call: ToolCall) => void;
  onToolResult?: (result: ToolResult) => void;
  onAgentDone?: (reason: AgentDoneReason) => void;
}

export interface UseChatResult {
  conversationId: string | null;
  messages: ChatMessage[];
  agentState: 'idle' | 'running' | 'paused' | 'error' | 'done' | 'canceled';
  isStreaming: boolean;
  pendingToolCalls: ToolCall[];
  dispatchedJobs: Map<string, DispatchedJob>;
  error: ChatError | null;
  sendMessage: (text: string, attachments?: Attachment[]) => Promise<void>;
  cancel: () => Promise<void>;
  loadHistory: () => Promise<void>;
  clearError: () => void;
}
```

Implementation notes:
- SSE parsing via `fetch` + ReadableStream reader (browser's `EventSource` lacks POST support)
- Each event type updates corresponding state slice
- `tool_result.dispatched.job_id` auto-registers a global WS listener; `job_progress` events update `dispatchedJobs`
- Stream disconnect → fall back to `loadHistory()` to catch up
- v1 no Last-Event-ID resume

### ChatPanel decomposition

```
ChatPanel
├─ MessageList
│  ├─ Message (user | assistant) → MessageBubble (markdown render)
│  └─ Message (tool) → ToolCallCard
│     ├─ ToolCallHeader (name + skill_id badge)
│     ├─ ToolCallArgs (collapsed JSON)
│     ├─ DispatchedJobCard (subscribes WS jobs:{job_id})
│     │  ├─ JobProgressBar
│     │  ├─ JobETA
│     │  └─ JobOutputThumbnail
│     └─ ToolResultDisplay
│        ├─ SuccessState
│        └─ ErrorState (with retry button)
├─ AgentStateIndicator (running spinner / paused banner / error / canceled)
└─ ChatInput
   ├─ Textarea (auto-resize)
   ├─ AttachmentDropzone (reserved)
   ├─ AdvancedOptions (folded; ToolsAllowlistChips, ModelSelector)
   └─ SendButton / CancelButton (mutually exclusive on isStreaming)
```

### Page-level changes

- `/chat/[projectId]`: ChatPanel with `{projectId}` context
- `/agent/[projectId]/episodes/[episodeNum]`:
  - Existing `useScriptStream` button stays
  - Add ChatPanel area with episode tools allowlist
  - "Regenerate single character/scene image" gets dual entry: chat ("regenerate X's portrait") AND direct REST button on character card
- `/studio/[projectId]`: DirectorChat becomes thin wrapper around ChatPanel with studio-specific allowlist

### Settings UI (B-1)

`/settings/skills`: SkillList + InstallSkillDialog (source_type picker, manifest preview)
`/settings/mcp-servers`: McpServerList + AddMcpServerDialog (transport picker, security warning)

Marketplace browse → B-1.7.

### Files to add

```
apps/web/src/
├─ hooks/useChat.ts
├─ hooks/useSkills.ts
├─ hooks/useMcpServers.ts
├─ lib/api/chat.ts
├─ lib/api/skills.ts
├─ lib/api/mcp.ts
├─ lib/featureFlags.ts
├─ components/chat/{NewAgentChat,MessageList,Message,ToolCallCard,DispatchedJobCard,AgentStateIndicator,ChatInput}.tsx
├─ components/settings/{SkillList,SkillRow,InstallSkillDialog,McpServerList,McpServerRow,AddMcpServerDialog}.tsx
└─ app/settings/{skills,mcp-servers}/page.tsx
```

### Files to modify

- `components/chat/ChatPanel.tsx` → feature-flagged dispatch
- `components/agent/AgentChat.tsx` → thin wrapper
- `components/studio/chat/DirectorChat.tsx` → thin wrapper
- `app/chat/[projectId]/page.tsx` → use new ChatPanel
- `app/agent/[projectId]/episodes/[episodeNum]/page.tsx` → add chat area + regenerate button
- `app/studio/[projectId]/page.tsx` → DirectorChat with new internals

### Files to delete (phase E)

```
hooks/useOrchestrator.ts
lib/api/orchestrator.ts
lib/store/chatStore.ts                  # state moves to useChat hook
```

---

## 12. Tracing Skeleton

### Choices

- **Structured JSON logs** with OTel-compatible attribute names (`gen_ai.*`, `webtoon.*`)
- **No new traces/spans table** — high write volume, low query value at v1; B-2 adds collector
- **No external dependency** beyond stdlib (`logging`, `contextvars`, `uuid`, `time`)
- **Cross-process tracing** via Celery kwargs propagation

### Span hierarchy

```
trace: <trace_id> (per /v1/agent/chat call)
└── agent_loop
    ├── agent_step (step_index=0)
    │   ├── load_history
    │   ├── compute_tools
    │   ├── skill_match
    │   ├── llm_call    [gen_ai.system, gen_ai.request.model, gen_ai.usage.input_tokens, ...]
    │   ├── tool_call   [webtoon.tool.name, webtoon.tool.skill_id, webtoon.tool.dispatched, ...]
    │   │   ├── tool_arg_validate
    │   │   ├── tool_execute
    │   │   └── tool_persist
    │   └── persist_assistant_message
    └── agent_step (step_index=1)
        └── ...

(continuation in worker process)
trace: <trace_id>
└── celery_task_run [parent_span_id = web tool_call span_id]
    ├── comfyui_submit
    ├── comfyui_wait_completion
    ├── comfyui_fetch_outputs
    └── storage_upload
```

### `Tracer` API

```python
from contextvars import ContextVar
from contextlib import asynccontextmanager
import time, json, uuid, logging

_current_tracer: ContextVar["Tracer | None"] = ContextVar("tracer", default=None)
_log = logging.getLogger("webtoon.trace")

class Tracer:
    def __init__(self, trace_id, conversation_id=None):
        self.trace_id = trace_id
        self.conversation_id = conversation_id
        self._stack: list[str] = []

    @asynccontextmanager
    async def span(self, name, **attrs):
        span_id = uuid.uuid4().hex
        parent_id = self._stack[-1] if self._stack else None
        start = time.monotonic()
        record = {
            "trace_id": self.trace_id, "span_id": span_id,
            "parent_span_id": parent_id, "name": name,
            "ts_start": time.time(),
            "conversation_id": self.conversation_id,
            "attributes": attrs,
        }
        self._stack.append(span_id)
        status, error = "ok", None
        try:
            yield record["attributes"]
        except Exception as e:
            status, error = "error", repr(e)
            raise
        finally:
            self._stack.pop()
            record.update({
                "ts_end": time.time(),
                "duration_ms": (time.monotonic() - start) * 1000,
                "status": status, "error": error,
            })
            _log.info("span", extra={"_trace_record": record})

@asynccontextmanager
async def with_tracer(trace_id, conversation_id=None):
    tracer = Tracer(trace_id, conversation_id)
    token = _current_tracer.set(tracer)
    try: yield tracer
    finally: _current_tracer.reset(token)
```

### Cross-process Celery propagation

```python
# Dispatcher
celery_app.send_task(
    "app.workers.image_worker.run_render",
    args=[panel_ids, opts],
    kwargs={"_trace_id": tracer.trace_id, "_parent_span_id": current_span_id},
    queue="image",
)

# Worker side decorator
def trace_task(fn):
    @functools.wraps(fn)
    async def wrapper(*a, _trace_id=None, _parent_span_id=None, **kw):
        if _trace_id:
            async with with_tracer(_trace_id) as tracer:
                tracer._stack.append(_parent_span_id)
                async with tracer.span(f"celery_{fn.__name__}"):
                    return await fn(*a, **kw)
        return await fn(*a, **kw)
    return wrapper
```

### JSON formatter

```python
class TraceJsonFormatter(logging.Formatter):
    def format(self, record):
        if hasattr(record, "_trace_record"):
            return json.dumps({"kind": "span", **record._trace_record})
        return super().format(record)

# Logger config
LOGGING = {
    "loggers": {
        "webtoon.trace": {"handlers": ["trace_json"], "level": "INFO", "propagate": False}
    },
    "handlers": {"trace_json": {"class": "logging.StreamHandler", "formatter": "trace_json"}},
}
```

### Forward path (B-2)

| B-1 | B-2 |
|---|---|
| JSON log to stdout | OTLP exporter → Tempo/Jaeger |
| trace_id in DB (messages, actions) | unchanged |
| grep / log aggregation | Grafana Tempo UI |
| no dashboards | LLM call rate / token / slow-tool leaderboard |

Field names already use OTel `gen_ai.*` semantic conventions → B-2 collector ingests with zero business code change.

### Files to add/modify

```
add:
app/services/agent/trace.py
app/workers/_trace_decorator.py

modify:
app/core/logging.py                       # TraceJsonFormatter
app/services/agent/runner.py              # main loop spans
app/services/agent/llm_provider.py        # llm_call span attrs
app/services/agent/tool_registry.py       # tool_call span
app/workers/image_worker.py               # @trace_task
app/workers/video_worker.py               # @trace_task
app/workers/anchor_worker.py              # @trace_task
app/workers/export_worker.py              # @trace_task
```

No new dependencies.

---

## 13. Acceptance Criteria

B-1 is "done" when ALL of:

**Functional**:
- [ ] `POST /v1/agent/chat` accepts a message, runs agent loop, streams SSE events per §6
- [ ] All 15 built-in tools registered, each callable both via chat and (where applicable) via existing endpoint
- [ ] All 5 bundled skills loadable; SKILL.md renders into prompt segment [3]
- [ ] Inbound MCP server exposes 15 tools at `/v1/mcp/messages` with bearer token auth
- [ ] Outbound MCP can connect to a stdio-transport server (e.g. filesystem MCP server) and surface its tools to agent loop
- [ ] Skill install from local/url/git via `/v1/skills/install`
- [ ] Settings `/skills` and `/mcp-servers` UIs functional (list, install, enable/disable, uninstall)
- [ ] Cancellation via `POST /v1/agent/conversations/{id}/cancel` interrupts loop within 1 step boundary

**Migration**:
- [ ] Episode endpoints (`/script`, `/script/stream`, `/refine`, `/generate-panels`) internally delegate to tools (verified by static-source tests)
- [ ] Frontend `useChat` hook live; ChatPanel uses it under flag
- [ ] Phase E deletions complete: `agents/`, `conversation/{agent_orchestrator,intent_router,tool_handlers,tool_registry}.py`, `orchestrator.py` route, `studio_orchestrator.py`, legacy frontend hooks/lib

**Quality**:
- [ ] Unit tests cover runner, tool_registry, llm_provider, skill loader (≥80% line coverage on new code)
- [ ] Static-source regression tests guard tool-registration, skill-loadability, endpoint delegation
- [ ] Integration test: mock LLM, full loop with parallel read-only + serial write tools
- [ ] E2E: real LLM chat flow generating script + rendering 1 panel works in dev

**Observability**:
- [ ] Every step + LLM call + tool call emits a JSON log span with OTel-conventional attrs
- [ ] Celery worker spans link back to web parent_span_id
- [ ] `trace_id` populated on every new ConversationMessage and ConversationAction

**Migrations**:
- [ ] Migration `022_unified_agent_runner` runs cleanly on SQLite + Postgres (use batch_alter_table for SQLite)
- [ ] Down migration drops new tables/columns without data loss claims

---

## 14. Known Limitations (carried into B-1.5+)

- No skill code sandbox — compensated by external skill = markdown-only/mcp-wrapped only
- No skill signature verification
- No skill multi-version co-existence
- No SSE Last-Event-ID resume (reconnect = REST refresh)
- No cross-LLM-provider fallback
- No outbound MCP server sandboxing (children inherit filtered env, no namespace isolation)
- No prompt-injection defense beyond LLM provider's content filter
- No rate limiting on internal `/v1/agent/chat` (only on inbound MCP)
- No USD cost tracking (explicit non-goal — user deferred)

---

## 15. Open Risks

- **LLM tool-call streaming quirks** vary by provider; `LLMProvider` adapter must be hardened with exhaustive test fixtures (real recorded streams from each provider). Risk: subtle reassembly bugs cause silent tool-call corruption.
- **Skill loading order** matters when multiple skills register conflicting tool names; v1 last-loaded-wins. Risk: confusing UX. Mitigation: builtin skills always load first; reject external installs whose tool name collides.
- **Outbound MCP latency** unknown — network-bound tool calls add to chat latency. Mitigation: per-tool `expected_duration` lets users mark slow MCP tools so they go through dispatched path.
- **Migration phase D (1-week observation)** may surface real-LLM behaviors not caught in mock tests. Mitigation: D ends in a "hold for issues" gate; only proceed to E with zero P0/P1 issues outstanding.

---

## 16. Successor Phases

- **B-1.5**: Cross-provider fallback, sandbox for tool-bundled skills (Docker/seccomp), skill signature verification, SSE Last-Event-ID resume
- **B-1.6**: Skill marketplace UI (browse Anthropic registry, ratings, recommendations, one-click install)
- **B-2**: Tracing → OTel collector + Grafana Tempo; LLM call rate / token / slow-tool dashboards (NO USD costs)
- **B-3**: Reliability — rate limiting, idempotency keys, retry policies, circuit breaker, project ACL
- **B-4**: Eval harness — fixtures of `(input → expected tool sequence + output)` cases for prompt regression scoring
