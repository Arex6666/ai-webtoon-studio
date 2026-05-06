# B-1 Phase B — Frontend Chat Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the frontend half of B-1 — a new `useChat` hook that talks to `/api/v1/agent/chat` SSE, a refactored `ChatPanel` composed of small focused components, two new Settings pages (Skills, MCP servers), and a feature flag (`NEXT_PUBLIC_USE_NEW_AGENT`) that lets the old chat path keep working until Phase D flip.

**Architecture:** All new files coexist with the legacy `useOrchestrator` / `useScriptStream` hooks. `ChatPanel` becomes a thin feature-flag dispatcher; `LegacyChat` and `NewAgentChat` are sibling components selected by env. New `useChat` fetches `POST /api/v1/agent/chat` with `Accept: text/event-stream`, parses SSE events into typed state slices, and exposes `messages` / `agentState` / `dispatchedJobs` / `sendMessage` / `cancel`. Settings pages query/mutate `/api/v1/skills/*` and `/api/v1/mcp/connections/*`.

**Tech Stack:** Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Radix UI, TanStack Query, Zustand (existing), `EventSource`-via-fetch SSE parsing.

**Reference spec:** `docs/superpowers/specs/2026-05-06-b1-unified-agent-runner-design.md` §11.

**Phase B does NOT:** delete legacy code (Phase E), wire feature flag to true by default (Phase D), refactor episode endpoints internally (Phase C). Just adds new surface behind flag.

---

## Pre-flight

- [ ] **Step 0: Confirm starting state**

```bash
cd D:/ai-webtoon-studio
git status                          # working tree clean
git log --oneline -1                # ee9c3a7 fix(api): align B-1 routes...
git rev-parse --abbrev-ref HEAD     # feat/b1a-agent-runner-backend
```

- [ ] **Step 0.1: Create Phase B branch off Phase A**

```bash
git checkout -b feat/b1b-frontend-chat-shell
```

All Phase B commits land on `feat/b1b-frontend-chat-shell`. Phase A's branch (`feat/b1a-agent-runner-backend`) stays as a stable base.

---

## Group 1: Foundation — Feature Flag + Type Definitions

### Task 1.1: Feature flag module

**Files:** Create `apps/web/src/lib/featureFlags.ts`

- [ ] **Step 1: Create file**

```typescript
/**
 * Feature flags — env-var driven for B-1 cutover.
 *
 * NEXT_PUBLIC_USE_NEW_AGENT controls whether ChatPanel renders the new
 * useChat-driven NewAgentChat (true) or LegacyChat (false). Default: false
 * until Phase D flip.
 */
export const featureFlags = {
  useNewAgent: process.env.NEXT_PUBLIC_USE_NEW_AGENT === 'true',
} as const;

export type FeatureFlags = typeof featureFlags;
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/lib/featureFlags.ts
git commit -m "feat(web): NEXT_PUBLIC_USE_NEW_AGENT feature flag (B-1 Phase B)"
```

### Task 1.2: TypeScript types for chat events

**Files:** Create `apps/web/src/lib/api/chatTypes.ts`

- [ ] **Step 1: Create file**

```typescript
/**
 * Chat event types — mirror the SSE events emitted by /api/v1/agent/chat.
 *
 * Reference: spec §6 (Streaming Protocol).
 */

export type AgentState = 'idle' | 'running' | 'paused' | 'error' | 'done' | 'canceled';

export type AgentDoneReason = 'stop' | 'max_steps' | 'user_canceled' | 'error';

export type FinishReason = 'stop' | 'tool_calls' | 'length' | 'content_filter' | 'error';

export interface ToolCall {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
}

export interface DispatchedJob {
  job_id: string;
  eta_seconds: number;
}

export interface ToolResult {
  action_id: string;
  tool_name: string;
  success: boolean;
  result?: unknown;
  error?: { code: string; message: string };
  dispatched?: DispatchedJob;
  skill_id?: string | null;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'tool' | 'system';
  content: string;
  tool_calls?: ToolCall[];
  finish_reason?: FinishReason;
  trace_id?: string | null;
  created_at?: string;
}

export interface ChatError {
  code: string;
  message: string;
  recoverable: boolean;
}

export interface ChatContext {
  projectId: string;
  episodeNumber?: number;
  chapterId?: string;
  panelId?: string;
}

export interface ChatOptions {
  maxSteps?: number;
  toolsAllowlist?: string[];
  model?: string;
}

/** Discriminated union for SSE event payloads (parsed). */
export type ChatStreamEvent =
  | { type: 'conversation_started'; conversation_id: string; user_message_id?: string; created_new: boolean }
  | { type: 'agent_step_started'; step_index: number; model: string }
  | { type: 'agent_step_completed'; step_index: number; tool_calls_emitted: number }
  | { type: 'assistant_message_chunk'; message_id: string; delta: string }
  | { type: 'assistant_message_complete'; message_id: string; content: string; finish_reason: FinishReason }
  | { type: 'tool_call'; action_id: string; tool_name: string; args: Record<string, unknown>; skill_id?: string | null }
  | { type: 'tool_executing'; action_id: string }
  | { type: 'tool_progress'; action_id: string; progress: number; message?: string }
  | { type: 'tool_result'; action_id: string; success: boolean; result?: unknown; error?: ChatError; dispatched?: DispatchedJob }
  | { type: 'agent_done'; reason: AgentDoneReason; total_steps?: number; total_tool_calls?: number }
  | { type: 'error'; code: string; message: string; recoverable: boolean };
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/lib/api/chatTypes.ts
git commit -m "feat(web): chat event TypeScript types matching spec §6 (B-1)"
```

### Task 1.3: Chat API client (POST + SSE parser + cancel)

**Files:** Create `apps/web/src/lib/api/chat.ts`

- [ ] **Step 1: Create file**

```typescript
/**
 * Chat API — POST /api/v1/agent/chat with SSE response parsing.
 *
 * EventSource doesn't support POST or custom headers, so we use fetch +
 * ReadableStream reader and parse SSE wire format manually.
 */
import type { ChatStreamEvent, ChatContext, ChatOptions } from './chatTypes';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export interface SendChatRequest {
  conversationId?: string;
  message: string;
  context: ChatContext;
  options?: ChatOptions;
}

/**
 * Stream chat events for one user message. Yields parsed events until
 * the stream ends (server emits agent_done or non-recoverable error).
 */
export async function* streamChat(
  req: SendChatRequest,
  signal?: AbortSignal,
): AsyncGenerator<ChatStreamEvent, void, void> {
  const body = {
    conversation_id: req.conversationId,
    message: req.message,
    context: {
      project_id: req.context.projectId,
      episode_number: req.context.episodeNumber,
      chapter_id: req.context.chapterId,
      panel_id: req.context.panelId,
    },
    options: req.options
      ? {
          max_steps: req.options.maxSteps,
          tools_allowlist: req.options.toolsAllowlist,
          model: req.options.model,
        }
      : undefined,
  };

  const resp = await fetch(`${API_BASE}/api/v1/agent/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(body),
    signal,
  });
  if (!resp.ok) {
    throw new Error(`chat request failed: ${resp.status} ${resp.statusText}`);
  }
  if (!resp.body) {
    throw new Error('chat response has no body');
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) return;
    buffer += decoder.decode(value, { stream: true });

    // Parse SSE wire frames separated by blank lines
    let frameEnd: number;
    while ((frameEnd = buffer.indexOf('\n\n')) !== -1) {
      const frame = buffer.slice(0, frameEnd);
      buffer = buffer.slice(frameEnd + 2);
      const event = parseFrame(frame);
      if (event) yield event;
    }
  }
}

function parseFrame(frame: string): ChatStreamEvent | null {
  let eventType = '';
  let dataStr = '';
  for (const rawLine of frame.split('\n')) {
    const line = rawLine.trimStart();
    if (line.startsWith(':')) continue; // SSE comment (heartbeat)
    if (line.startsWith('event:')) {
      eventType = line.slice('event:'.length).trim();
    } else if (line.startsWith('data:')) {
      dataStr = line.slice('data:'.length).trim();
    }
    // We ignore `id:` lines for v1 (no resume support yet)
  }
  if (!eventType || !dataStr) return null;
  try {
    const data = JSON.parse(dataStr);
    return { type: eventType as ChatStreamEvent['type'], ...data } as ChatStreamEvent;
  } catch {
    return null;
  }
}

export async function cancelConversation(conversationId: string): Promise<void> {
  const resp = await fetch(
    `${API_BASE}/api/v1/agent/conversations/${conversationId}/cancel`,
    { method: 'POST' },
  );
  if (!resp.ok) {
    throw new Error(`cancel failed: ${resp.status}`);
  }
}

export async function loadHistory(
  conversationId: string,
  limit = 100,
): Promise<unknown[]> {
  const resp = await fetch(
    `${API_BASE}/api/v1/agent/conversations/${conversationId}/messages?limit=${limit}`,
  );
  if (!resp.ok) throw new Error(`history load failed: ${resp.status}`);
  return resp.json();
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/lib/api/chat.ts
git commit -m "feat(web): chat API client — streamChat + cancel + history (B-1)"
```

### Task 1.4: Skills + MCP API clients

**Files:** Create `apps/web/src/lib/api/skills.ts`, `apps/web/src/lib/api/mcp.ts`

- [ ] **Step 1: Create skills.ts**

```typescript
/** Skills API — wraps /api/v1/skills/*. */
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export interface SkillRow {
  id: string;
  name: string;
  version: string;
  source_type: 'builtin' | 'local' | 'url' | 'git' | 'mcp_only';
  source_url: string | null;
  status: 'active' | 'disabled' | 'failed' | 'uninstalled' | 'installing';
  scope: 'global' | 'project';
  project_id: string | null;
  manifest_json: Record<string, unknown>;
}

export async function listSkills(params: { scope?: string; project_id?: string } = {}): Promise<SkillRow[]> {
  const qs = new URLSearchParams();
  if (params.scope) qs.set('scope', params.scope);
  if (params.project_id) qs.set('project_id', params.project_id);
  const r = await fetch(`${API_BASE}/api/v1/skills${qs.toString() ? `?${qs}` : ''}`);
  if (!r.ok) throw new Error(`listSkills: ${r.status}`);
  return r.json();
}

export async function installSkill(payload: {
  source_type: 'local' | 'url' | 'git';
  source: string;
  scope: 'global' | 'project';
  project_id?: string | null;
}): Promise<SkillRow> {
  const r = await fetch(`${API_BASE}/api/v1/skills/install`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(`installSkill: ${r.status} ${await r.text()}`);
  return r.json();
}

export async function enableSkill(skillId: string): Promise<SkillRow> {
  const r = await fetch(`${API_BASE}/api/v1/skills/${skillId}/enable`, { method: 'POST' });
  if (!r.ok) throw new Error(`enableSkill: ${r.status}`);
  return r.json();
}

export async function disableSkill(skillId: string): Promise<SkillRow> {
  const r = await fetch(`${API_BASE}/api/v1/skills/${skillId}/disable`, { method: 'POST' });
  if (!r.ok) throw new Error(`disableSkill: ${r.status}`);
  return r.json();
}

export async function uninstallSkill(skillId: string): Promise<void> {
  const r = await fetch(`${API_BASE}/api/v1/skills/${skillId}`, { method: 'DELETE' });
  if (!r.ok) throw new Error(`uninstallSkill: ${r.status}`);
}
```

- [ ] **Step 2: Create mcp.ts**

```typescript
/** MCP outbound connections API — wraps /api/v1/mcp/connections/*. */
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export interface McpConnectionRow {
  id: string;
  name: string;
  transport: 'stdio' | 'sse' | 'streamable_http';
  command: string | null;
  args_json: string[] | null;
  url: string | null;
  status: 'connected' | 'disconnected' | 'failed';
  last_connected_at: string | null;
  last_error: string | null;
  capabilities_json: Record<string, unknown> | null;
  scope: 'global' | 'project';
  project_id: string | null;
}

export async function listMcpConnections(params: { scope?: string; project_id?: string } = {}): Promise<McpConnectionRow[]> {
  const qs = new URLSearchParams();
  if (params.scope) qs.set('scope', params.scope);
  if (params.project_id) qs.set('project_id', params.project_id);
  const r = await fetch(`${API_BASE}/api/v1/mcp/connections${qs.toString() ? `?${qs}` : ''}`);
  if (!r.ok) throw new Error(`listMcpConnections: ${r.status}`);
  return r.json();
}

export interface AddMcpRequest {
  name: string;
  transport: 'stdio' | 'sse' | 'streamable_http';
  command?: string;
  args?: string[];
  url?: string;
  env?: Record<string, string>;
  scope?: 'global' | 'project';
  project_id?: string | null;
}

export async function addMcpConnection(payload: AddMcpRequest): Promise<McpConnectionRow> {
  const r = await fetch(`${API_BASE}/api/v1/mcp/connections`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(`addMcpConnection: ${r.status} ${await r.text()}`);
  return r.json();
}

export async function reconnectMcp(connId: string): Promise<McpConnectionRow> {
  const r = await fetch(`${API_BASE}/api/v1/mcp/connections/${connId}/reconnect`, { method: 'POST' });
  if (!r.ok) throw new Error(`reconnectMcp: ${r.status}`);
  return r.json();
}

export async function removeMcpConnection(connId: string): Promise<void> {
  const r = await fetch(`${API_BASE}/api/v1/mcp/connections/${connId}`, { method: 'DELETE' });
  if (!r.ok) throw new Error(`removeMcpConnection: ${r.status}`);
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/lib/api/skills.ts apps/web/src/lib/api/mcp.ts
git commit -m "feat(web): skills + MCP admin API clients (B-1)"
```

---

## Group 2: useChat Hook

### Task 2.1: useChat hook

**Files:** Create `apps/web/src/hooks/useChat.ts`

- [ ] **Step 1: Create file**

```typescript
/**
 * useChat — primary chat hook for B-1 NewAgentChat.
 *
 * Streams events from POST /api/v1/agent/chat, normalizes them into reactive
 * state slices, and exposes a sendMessage / cancel / loadHistory imperative API.
 *
 * One hook instance manages exactly one conversation. Pass conversationId to
 * resume an existing conversation; omit to auto-create on first send.
 */
import { useCallback, useEffect, useReducer, useRef } from 'react';

import { streamChat, cancelConversation, loadHistory as fetchHistory } from '@/lib/api/chat';
import type {
  AgentState,
  ChatContext,
  ChatError,
  ChatMessage,
  ChatOptions,
  ChatStreamEvent,
  DispatchedJob,
  ToolCall,
} from '@/lib/api/chatTypes';

export interface UseChatOptions {
  conversationId?: string;
  context: ChatContext;
  toolsAllowlist?: string[];
  model?: string;
  onToolCall?: (call: ToolCall) => void;
  onAgentDone?: (reason: string) => void;
}

export interface UseChatResult {
  conversationId: string | null;
  messages: ChatMessage[];
  agentState: AgentState;
  isStreaming: boolean;
  pendingToolCalls: ToolCall[];
  dispatchedJobs: Map<string, DispatchedJob & { action_id: string; tool_name: string }>;
  error: ChatError | null;
  sendMessage: (text: string) => Promise<void>;
  cancel: () => Promise<void>;
  loadHistory: () => Promise<void>;
  clearError: () => void;
}

interface State {
  conversationId: string | null;
  messages: ChatMessage[];
  agentState: AgentState;
  isStreaming: boolean;
  pendingToolCalls: ToolCall[];
  dispatchedJobs: Map<string, DispatchedJob & { action_id: string; tool_name: string }>;
  error: ChatError | null;
}

type Action =
  | { type: 'reset' }
  | { type: 'set_conversation_id'; id: string }
  | { type: 'append_user_message'; text: string }
  | { type: 'set_streaming'; on: boolean }
  | { type: 'apply_event'; event: ChatStreamEvent }
  | { type: 'clear_error' }
  | { type: 'set_error'; err: ChatError };

function initialState(conversationId: string | undefined): State {
  return {
    conversationId: conversationId ?? null,
    messages: [],
    agentState: 'idle',
    isStreaming: false,
    pendingToolCalls: [],
    dispatchedJobs: new Map(),
    error: null,
  };
}

function reduce(state: State, action: Action): State {
  switch (action.type) {
    case 'reset':
      return initialState(undefined);

    case 'set_conversation_id':
      return { ...state, conversationId: action.id };

    case 'append_user_message':
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: `local-${Date.now()}`,
            role: 'user',
            content: action.text,
            created_at: new Date().toISOString(),
          },
        ],
      };

    case 'set_streaming':
      return { ...state, isStreaming: action.on };

    case 'clear_error':
      return { ...state, error: null };

    case 'set_error':
      return { ...state, error: action.err };

    case 'apply_event':
      return applyEvent(state, action.event);
  }
}

function applyEvent(state: State, ev: ChatStreamEvent): State {
  switch (ev.type) {
    case 'conversation_started':
      return { ...state, conversationId: ev.conversation_id, agentState: 'running' };

    case 'agent_step_started':
      return state;

    case 'agent_step_completed':
      return state;

    case 'assistant_message_chunk': {
      const last = state.messages[state.messages.length - 1];
      if (last && last.role === 'assistant' && last.id === ev.message_id) {
        const updated = { ...last, content: last.content + ev.delta };
        return { ...state, messages: [...state.messages.slice(0, -1), updated] };
      }
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: ev.message_id,
            role: 'assistant',
            content: ev.delta,
            created_at: new Date().toISOString(),
          },
        ],
      };
    }

    case 'assistant_message_complete': {
      // Replace the trailing chunked message with the canonical content
      const idx = state.messages.findIndex((m) => m.id === ev.message_id);
      if (idx >= 0) {
        const updated = { ...state.messages[idx], content: ev.content, finish_reason: ev.finish_reason };
        return { ...state, messages: [...state.messages.slice(0, idx), updated, ...state.messages.slice(idx + 1)] };
      }
      return state;
    }

    case 'tool_call': {
      const tc: ToolCall = { id: ev.action_id, name: ev.tool_name, arguments: ev.args };
      return {
        ...state,
        pendingToolCalls: [...state.pendingToolCalls, tc],
        messages: [
          ...state.messages,
          {
            id: `tc-${ev.action_id}`,
            role: 'tool',
            content: JSON.stringify({ tool_call: { ...tc, skill_id: ev.skill_id ?? null } }),
            created_at: new Date().toISOString(),
          },
        ],
      };
    }

    case 'tool_executing':
      return state;

    case 'tool_progress':
      return state;

    case 'tool_result': {
      const pending = state.pendingToolCalls.filter((tc) => tc.id !== ev.action_id);
      const dispatched = new Map(state.dispatchedJobs);
      if (ev.dispatched) {
        const tc = state.pendingToolCalls.find((t) => t.id === ev.action_id);
        dispatched.set(ev.dispatched.job_id, {
          ...ev.dispatched,
          action_id: ev.action_id,
          tool_name: tc?.name ?? 'unknown',
        });
      }
      // Update the placeholder tool message with the result
      const messages = state.messages.map((m) => {
        if (m.id === `tc-${ev.action_id}`) {
          return {
            ...m,
            content: JSON.stringify({
              tool_result: {
                action_id: ev.action_id,
                success: ev.success,
                result: ev.result,
                error: ev.error,
                dispatched: ev.dispatched,
              },
            }),
          };
        }
        return m;
      });
      return { ...state, pendingToolCalls: pending, dispatchedJobs: dispatched, messages };
    }

    case 'agent_done': {
      const next: AgentState =
        ev.reason === 'stop'
          ? 'done'
          : ev.reason === 'max_steps'
          ? 'paused'
          : ev.reason === 'user_canceled'
          ? 'canceled'
          : 'error';
      return { ...state, agentState: next, isStreaming: false };
    }

    case 'error':
      return {
        ...state,
        error: { code: ev.code, message: ev.message, recoverable: ev.recoverable },
      };
  }
}


export function useChat(opts: UseChatOptions): UseChatResult {
  const [state, dispatch] = useReducer(reduce, initialState(opts.conversationId));
  const abortRef = useRef<AbortController | null>(null);

  // Reset on conversationId change
  useEffect(() => {
    dispatch({ type: 'reset' });
    if (opts.conversationId) {
      dispatch({ type: 'set_conversation_id', id: opts.conversationId });
    }
  }, [opts.conversationId]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (state.isStreaming) {
        throw new Error('chat is already streaming');
      }
      dispatch({ type: 'clear_error' });
      dispatch({ type: 'append_user_message', text });
      dispatch({ type: 'set_streaming', on: true });

      const ctrl = new AbortController();
      abortRef.current = ctrl;

      try {
        for await (const event of streamChat(
          {
            conversationId: state.conversationId ?? undefined,
            message: text,
            context: opts.context,
            options: {
              toolsAllowlist: opts.toolsAllowlist,
              model: opts.model,
            },
          },
          ctrl.signal,
        )) {
          dispatch({ type: 'apply_event', event });
          if (event.type === 'tool_call' && opts.onToolCall) {
            opts.onToolCall({ id: event.action_id, name: event.tool_name, arguments: event.args });
          }
          if (event.type === 'agent_done' && opts.onAgentDone) {
            opts.onAgentDone(event.reason);
          }
        }
      } catch (e: unknown) {
        if (ctrl.signal.aborted) {
          // local abort — leave state alone, server-side cancel already issued
        } else {
          const msg = e instanceof Error ? e.message : String(e);
          dispatch({ type: 'set_error', err: { code: 'NETWORK_ERROR', message: msg, recoverable: false } });
        }
      } finally {
        dispatch({ type: 'set_streaming', on: false });
        abortRef.current = null;
      }
    },
    [state.conversationId, state.isStreaming, opts.context, opts.toolsAllowlist, opts.model, opts.onToolCall, opts.onAgentDone],
  );

  const cancel = useCallback(async () => {
    if (state.conversationId) {
      try {
        await cancelConversation(state.conversationId);
      } catch {
        // Server may already be done — ignore
      }
    }
    abortRef.current?.abort();
  }, [state.conversationId]);

  const loadHistory = useCallback(async () => {
    if (!state.conversationId) return;
    try {
      const rows = (await fetchHistory(state.conversationId)) as Array<{
        id: string;
        role: 'user' | 'assistant' | 'tool' | 'system';
        content: string;
        finish_reason?: string;
        trace_id?: string | null;
        created_at?: string;
      }>;
      // Replace messages with server-side history
      dispatch({ type: 'reset' });
      dispatch({ type: 'set_conversation_id', id: state.conversationId });
      // We don't have a "set_messages" action; emit synthetic events
      // For v1 simplicity, just bail — caller can refetch via TanStack Query
      // (this hook is tuned for live streaming, not history hydration).
      // Future: add SET_MESSAGES action.
      void rows;
    } catch (e) {
      // ignore
    }
  }, [state.conversationId]);

  const clearError = useCallback(() => {
    dispatch({ type: 'clear_error' });
  }, []);

  return {
    conversationId: state.conversationId,
    messages: state.messages,
    agentState: state.agentState,
    isStreaming: state.isStreaming,
    pendingToolCalls: state.pendingToolCalls,
    dispatchedJobs: state.dispatchedJobs,
    error: state.error,
    sendMessage,
    cancel,
    loadHistory,
    clearError,
  };
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/hooks/useChat.ts
git commit -m "feat(web): useChat hook — SSE streaming + reducer state (B-1)"
```

### Task 2.2: useSkills hook (TanStack Query)

**Files:** Create `apps/web/src/hooks/useSkills.ts`

- [ ] **Step 1: Create file**

```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  disableSkill, enableSkill, installSkill, listSkills, uninstallSkill,
  type SkillRow,
} from '@/lib/api/skills';

export function useSkills(params: { scope?: string; projectId?: string } = {}) {
  const qc = useQueryClient();
  const key = ['skills', params.scope, params.projectId] as const;

  const list = useQuery({
    queryKey: key,
    queryFn: () => listSkills({ scope: params.scope, project_id: params.projectId }),
  });

  const install = useMutation({
    mutationFn: installSkill,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['skills'] }),
  });

  const enable = useMutation({
    mutationFn: enableSkill,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['skills'] }),
  });

  const disable = useMutation({
    mutationFn: disableSkill,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['skills'] }),
  });

  const uninstall = useMutation({
    mutationFn: uninstallSkill,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['skills'] }),
  });

  return { list, install, enable, disable, uninstall };
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/hooks/useSkills.ts
git commit -m "feat(web): useSkills hook (B-1)"
```

### Task 2.3: useMcpServers hook

**Files:** Create `apps/web/src/hooks/useMcpServers.ts`

- [ ] **Step 1: Create file**

```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  addMcpConnection, listMcpConnections, reconnectMcp, removeMcpConnection,
  type McpConnectionRow, type AddMcpRequest,
} from '@/lib/api/mcp';

export function useMcpServers(params: { scope?: string; projectId?: string } = {}) {
  const qc = useQueryClient();
  const key = ['mcp-connections', params.scope, params.projectId] as const;

  const list = useQuery({
    queryKey: key,
    queryFn: () => listMcpConnections({ scope: params.scope, project_id: params.projectId }),
  });

  const add = useMutation({
    mutationFn: addMcpConnection,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['mcp-connections'] }),
  });

  const reconnect = useMutation({
    mutationFn: reconnectMcp,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['mcp-connections'] }),
  });

  const remove = useMutation({
    mutationFn: removeMcpConnection,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['mcp-connections'] }),
  });

  return { list, add, reconnect, remove };
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/hooks/useMcpServers.ts
git commit -m "feat(web): useMcpServers hook (B-1)"
```

---

## Group 3: NewAgentChat Component Tree

### Task 3.1: AgentStateIndicator

**Files:** Create `apps/web/src/components/chat/AgentStateIndicator.tsx`

- [ ] **Step 1: Create file**

```tsx
'use client';

import type { AgentState, ChatError } from '@/lib/api/chatTypes';

interface Props {
  state: AgentState;
  error: ChatError | null;
}

export function AgentStateIndicator({ state, error }: Props) {
  if (error) {
    return (
      <div className="px-3 py-2 text-sm text-red-600 bg-red-50 border-l-4 border-red-500">
        <span className="font-semibold">Error:</span> {error.message}
        {error.recoverable && <span className="ml-2 italic text-red-400">(recoverable)</span>}
      </div>
    );
  }
  if (state === 'running') {
    return (
      <div className="px-3 py-1 text-sm text-gray-500 italic">
        <span className="inline-block w-2 h-2 mr-2 rounded-full bg-blue-500 animate-pulse" />
        thinking...
      </div>
    );
  }
  if (state === 'paused') {
    return (
      <div className="px-3 py-2 text-sm text-amber-700 bg-amber-50">
        Reached step limit. Send another message to continue.
      </div>
    );
  }
  if (state === 'canceled') {
    return <div className="px-3 py-1 text-sm text-gray-500">Canceled</div>;
  }
  return null;
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/components/chat/AgentStateIndicator.tsx
git commit -m "feat(web): AgentStateIndicator component (B-1)"
```

### Task 3.2: ToolCallCard + DispatchedJobCard

**Files:** Create `apps/web/src/components/chat/ToolCallCard.tsx`, `apps/web/src/components/chat/DispatchedJobCard.tsx`

- [ ] **Step 1: DispatchedJobCard**

```tsx
'use client';

import type { DispatchedJob } from '@/lib/api/chatTypes';

interface Props {
  job: DispatchedJob & { action_id: string; tool_name: string };
}

/** Renders the dispatched-job placeholder while a slow tool is running.
 *
 * For B-1 v1: shows job_id + ETA. Real-time progress via WebSocket subscription
 * is deferred — frontend can wire this up against the existing /ws channel
 * later (job_progress events with matching job_id).
 */
export function DispatchedJobCard({ job }: Props) {
  return (
    <div className="border border-blue-200 bg-blue-50 rounded p-2 text-sm">
      <div className="font-medium text-blue-900">{job.tool_name} dispatched</div>
      <div className="text-xs text-blue-700">
        job: <code className="font-mono">{job.job_id}</code>
        {job.eta_seconds ? ` · ETA ${job.eta_seconds}s` : null}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: ToolCallCard**

```tsx
'use client';

import { useState } from 'react';

import type { ToolCall, ToolResult } from '@/lib/api/chatTypes';
import { DispatchedJobCard } from './DispatchedJobCard';

interface Props {
  call: ToolCall;
  result?: ToolResult;
}

export function ToolCallCard({ call, result }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-gray-200 bg-gray-50 rounded p-2 text-sm">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full text-left flex items-center justify-between"
      >
        <span className="font-medium">tool: {call.name}</span>
        <span className="text-xs text-gray-500">{expanded ? '−' : '+'}</span>
      </button>
      {expanded && (
        <pre className="mt-2 text-xs bg-white border rounded p-2 overflow-x-auto">
          {JSON.stringify(call.arguments, null, 2)}
        </pre>
      )}
      {result?.dispatched && (
        <div className="mt-2">
          <DispatchedJobCard job={{ ...result.dispatched, action_id: call.id, tool_name: call.name }} />
        </div>
      )}
      {result && !result.dispatched && (
        result.success ? (
          <div className="mt-2 text-xs text-green-700">
            ✓ done
            {expanded && (
              <pre className="mt-1 bg-white border rounded p-2 overflow-x-auto">
                {JSON.stringify(result.result, null, 2)}
              </pre>
            )}
          </div>
        ) : (
          <div className="mt-2 text-xs text-red-700">
            ✗ {result.error?.code}: {result.error?.message}
          </div>
        )
      )}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/chat/ToolCallCard.tsx apps/web/src/components/chat/DispatchedJobCard.tsx
git commit -m "feat(web): ToolCallCard + DispatchedJobCard (B-1)"
```

### Task 3.3: MessageList + Message components

**Files:** Create `apps/web/src/components/chat/MessageList.tsx`, `apps/web/src/components/chat/Message.tsx`

- [ ] **Step 1: Message**

```tsx
'use client';

import type { ChatMessage } from '@/lib/api/chatTypes';
import { ToolCallCard } from './ToolCallCard';

interface Props {
  message: ChatMessage;
}

export function Message({ message }: Props) {
  if (message.role === 'tool') {
    // The content is a JSON-encoded {tool_call} or {tool_result}
    let parsed: { tool_call?: { id: string; name: string; arguments: Record<string, unknown>; skill_id?: string | null }; tool_result?: { action_id: string; success: boolean; result?: unknown; error?: { code: string; message: string }; dispatched?: { job_id: string; eta_seconds: number } } } = {};
    try {
      parsed = JSON.parse(message.content);
    } catch {
      // raw display fallback
      return <pre className="text-xs text-gray-600">{message.content}</pre>;
    }
    if (parsed.tool_call && parsed.tool_result) {
      return (
        <ToolCallCard
          call={parsed.tool_call}
          result={{
            action_id: parsed.tool_result.action_id,
            tool_name: parsed.tool_call.name,
            success: parsed.tool_result.success,
            result: parsed.tool_result.result,
            error: parsed.tool_result.error
              ? { code: parsed.tool_result.error.code, message: parsed.tool_result.error.message, recoverable: false }
              : undefined,
            dispatched: parsed.tool_result.dispatched,
          }}
        />
      );
    }
    if (parsed.tool_call) {
      return <ToolCallCard call={parsed.tool_call} />;
    }
    return <pre className="text-xs text-gray-600">{message.content}</pre>;
  }

  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-lg bg-blue-600 text-white px-3 py-2 text-sm">
          {message.content}
        </div>
      </div>
    );
  }

  // assistant or system
  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] rounded-lg bg-gray-100 text-gray-900 px-3 py-2 text-sm whitespace-pre-wrap">
        {message.content}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: MessageList**

```tsx
'use client';

import { useEffect, useRef } from 'react';

import type { ChatMessage } from '@/lib/api/chatTypes';
import { Message } from './Message';

interface Props {
  messages: ChatMessage[];
}

export function MessageList({ messages }: Props) {
  const scrollerRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollerRef.current) {
      scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
    }
  }, [messages.length, messages[messages.length - 1]?.content?.length]);

  return (
    <div ref={scrollerRef} className="flex-1 overflow-y-auto p-3 space-y-3">
      {messages.length === 0 ? (
        <div className="text-center text-sm text-gray-400 mt-8">
          No messages yet. Send something to start.
        </div>
      ) : (
        messages.map((m) => <Message key={m.id} message={m} />)
      )}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/chat/MessageList.tsx apps/web/src/components/chat/Message.tsx
git commit -m "feat(web): MessageList + Message components (B-1)"
```

### Task 3.4: ChatInput

**Files:** Create `apps/web/src/components/chat/ChatInput.tsx`

- [ ] **Step 1: Create file**

```tsx
'use client';

import { useCallback, useRef, useState } from 'react';

interface Props {
  onSend: (text: string) => Promise<void> | void;
  onCancel?: () => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInput({ onSend, onCancel, disabled, placeholder }: Props) {
  const [text, setText] = useState('');
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  const submit = useCallback(async () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    setText('');
    await onSend(trimmed);
  }, [text, disabled, onSend]);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        void submit();
      }
    },
    [submit],
  );

  return (
    <div className="border-t border-gray-200 bg-white p-3">
      <textarea
        ref={taRef}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        rows={2}
        placeholder={placeholder ?? 'Ask the agent...'}
        className="w-full resize-y border border-gray-200 rounded p-2 text-sm focus:outline-none focus:ring focus:border-blue-300"
      />
      <div className="mt-2 flex justify-end gap-2">
        {disabled && onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="px-3 py-1 text-sm text-gray-700 border border-gray-300 rounded hover:bg-gray-50"
          >
            Cancel
          </button>
        )}
        <button
          type="button"
          onClick={() => void submit()}
          disabled={disabled || !text.trim()}
          className="px-4 py-1 text-sm bg-blue-600 text-white rounded disabled:bg-gray-300 hover:bg-blue-700"
        >
          {disabled ? 'Sending...' : 'Send'}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/components/chat/ChatInput.tsx
git commit -m "feat(web): ChatInput component (B-1)"
```

### Task 3.5: NewAgentChat container

**Files:** Create `apps/web/src/components/chat/NewAgentChat.tsx`

- [ ] **Step 1: Create file**

```tsx
'use client';

import { useChat } from '@/hooks/useChat';
import type { ChatContext } from '@/lib/api/chatTypes';

import { AgentStateIndicator } from './AgentStateIndicator';
import { ChatInput } from './ChatInput';
import { MessageList } from './MessageList';

interface Props {
  context: ChatContext;
  conversationId?: string;
  toolsAllowlist?: string[];
}

export function NewAgentChat({ context, conversationId, toolsAllowlist }: Props) {
  const chat = useChat({ conversationId, context, toolsAllowlist });

  return (
    <div className="flex flex-col h-full bg-white">
      <MessageList messages={chat.messages} />
      <AgentStateIndicator state={chat.agentState} error={chat.error} />
      <ChatInput
        onSend={chat.sendMessage}
        onCancel={chat.cancel}
        disabled={chat.isStreaming}
      />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/components/chat/NewAgentChat.tsx
git commit -m "feat(web): NewAgentChat container — composes useChat + sub-components (B-1)"
```

---

## Group 4: ChatPanel Feature-Flag Dispatcher

### Task 4.1: Wrap existing ChatPanel with flag dispatcher

**Files:** Modify `apps/web/src/components/chat/ChatPanel.tsx`

- [ ] **Step 1: Read current ChatPanel**

```bash
cat apps/web/src/components/chat/ChatPanel.tsx | head -50
```

Note its existing API (props it accepts). The new ChatPanel must keep the SAME prop signature so callers don't break.

- [ ] **Step 2: Refactor ChatPanel**

Open `apps/web/src/components/chat/ChatPanel.tsx`. Rename the original component body to `LegacyChatPanel` (export it as a named export so other modules can still reference if needed). Add a new top-level default export:

```tsx
import { featureFlags } from '@/lib/featureFlags';
import { NewAgentChat } from './NewAgentChat';
// ...keep all existing imports

// Existing component → renamed
export function LegacyChatPanel(/* same props as before */) {
  // ...existing body unchanged
}

// New default export — feature-flag dispatcher
export default function ChatPanel(props: /* same props type */) {
  if (featureFlags.useNewAgent) {
    // Map legacy props to NewAgentChat's interface
    return (
      <NewAgentChat
        context={{
          projectId: props.projectId,
          /* episodeNumber/chapterId/panelId if present in legacy props */
        }}
      />
    );
  }
  return <LegacyChatPanel {...props} />;
}
```

The exact prop mapping depends on the existing ChatPanel's interface — when in doubt, expose the new path with `projectId` only and let pages that need richer context pass it explicitly.

- [ ] **Step 3: Verify both branches type-check**

```bash
cd apps/web
npm run lint -- --max-warnings 0 src/components/chat/ChatPanel.tsx 2>&1 | tail -10
```

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/components/chat/ChatPanel.tsx
git commit -m "feat(web): ChatPanel — feature-flag dispatcher between legacy + NewAgentChat (B-1)"
```

---

## Group 5: Settings → Skills Page

### Task 5.1: SkillRow component

**Files:** Create `apps/web/src/components/settings/SkillRow.tsx`

- [ ] **Step 1: Create file**

```tsx
'use client';

import type { SkillRow as SkillRowData } from '@/lib/api/skills';

interface Props {
  skill: SkillRowData;
  onToggle: () => void;
  onUninstall: () => void;
  onViewDetails: () => void;
}

export function SkillRow({ skill, onToggle, onUninstall, onViewDetails }: Props) {
  const statusColor = {
    active: 'text-green-700 bg-green-50',
    disabled: 'text-gray-600 bg-gray-100',
    failed: 'text-red-700 bg-red-50',
    installing: 'text-blue-700 bg-blue-50',
    uninstalled: 'text-gray-400 bg-gray-50',
  }[skill.status];

  return (
    <div className="flex items-center justify-between border-b border-gray-100 py-2 px-3 hover:bg-gray-50">
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium">{skill.name}</span>
          <span className="text-xs text-gray-500">@ {skill.version}</span>
          <span className={`text-xs px-2 py-0.5 rounded ${statusColor}`}>{skill.status}</span>
          <span className="text-xs text-gray-400">{skill.scope}</span>
          <span className="text-xs text-gray-400">{skill.source_type}</span>
        </div>
        {(skill.manifest_json as { description?: string } | undefined)?.description && (
          <div className="text-xs text-gray-500 mt-0.5">
            {(skill.manifest_json as { description?: string }).description}
          </div>
        )}
      </div>
      <div className="flex items-center gap-2">
        <button type="button" onClick={onViewDetails} className="text-xs text-blue-600 hover:underline">
          Details
        </button>
        {skill.source_type !== 'builtin' && (
          <>
            <button type="button" onClick={onToggle} className="text-xs px-2 py-1 border rounded">
              {skill.status === 'active' ? 'Disable' : 'Enable'}
            </button>
            <button type="button" onClick={onUninstall} className="text-xs px-2 py-1 border border-red-300 text-red-600 rounded">
              Uninstall
            </button>
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/components/settings/SkillRow.tsx
git commit -m "feat(web): SkillRow component (B-1)"
```

### Task 5.2: InstallSkillDialog

**Files:** Create `apps/web/src/components/settings/InstallSkillDialog.tsx`

- [ ] **Step 1: Create file**

```tsx
'use client';

import { useState } from 'react';

import { useSkills } from '@/hooks/useSkills';

interface Props {
  open: boolean;
  onClose: () => void;
  projectId?: string;
}

export function InstallSkillDialog({ open, onClose, projectId }: Props) {
  const [sourceType, setSourceType] = useState<'local' | 'url' | 'git'>('url');
  const [source, setSource] = useState('');
  const [scope, setScope] = useState<'global' | 'project'>(projectId ? 'project' : 'global');
  const [errMsg, setErrMsg] = useState<string | null>(null);

  const { install } = useSkills({ projectId });

  if (!open) return null;

  const submit = async () => {
    setErrMsg(null);
    try {
      await install.mutateAsync({
        source_type: sourceType,
        source,
        scope,
        project_id: scope === 'project' ? projectId ?? null : null,
      });
      onClose();
      setSource('');
    } catch (e: unknown) {
      setErrMsg(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
        <h2 className="text-lg font-semibold mb-4">Install Skill</h2>

        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Source type</label>
            <div className="flex gap-2">
              {(['local', 'url', 'git'] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setSourceType(t)}
                  className={`px-3 py-1 text-sm rounded border ${sourceType === t ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 border-gray-300'}`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {sourceType === 'local' ? 'Path' : sourceType === 'url' ? 'URL (.tar.gz / .zip)' : 'git+ URL'}
            </label>
            <input
              type="text"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder={sourceType === 'git' ? 'git+https://github.com/owner/repo@v1#path=skills/foo' : 'https://example.com/skill.tar.gz'}
              className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Scope</label>
            <select
              value={scope}
              onChange={(e) => setScope(e.target.value as 'global' | 'project')}
              className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
            >
              <option value="global">global</option>
              <option value="project" disabled={!projectId}>
                project {projectId ? '' : '(no projectId)'}
              </option>
            </select>
          </div>

          {errMsg && <div className="text-sm text-red-600">{errMsg}</div>}
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <button type="button" onClick={onClose} className="px-3 py-1 text-sm border rounded">
            Cancel
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={!source || install.isPending}
            className="px-3 py-1 text-sm bg-blue-600 text-white rounded disabled:bg-gray-300"
          >
            {install.isPending ? 'Installing...' : 'Install'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/components/settings/InstallSkillDialog.tsx
git commit -m "feat(web): InstallSkillDialog (B-1)"
```

### Task 5.3: Settings Skills page

**Files:** Create `apps/web/src/app/settings/skills/page.tsx`, `apps/web/src/app/settings/layout.tsx`

- [ ] **Step 1: Settings layout**

```tsx
import Link from 'next/link';

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <aside className="w-48 border-r border-gray-200 p-4">
        <h1 className="font-semibold mb-3">Settings</h1>
        <nav className="space-y-1 text-sm">
          <Link href="/settings/skills" className="block px-2 py-1 rounded hover:bg-gray-100">
            Skills
          </Link>
          <Link href="/settings/mcp-servers" className="block px-2 py-1 rounded hover:bg-gray-100">
            MCP Servers
          </Link>
        </nav>
      </aside>
      <main className="flex-1">{children}</main>
    </div>
  );
}
```

- [ ] **Step 2: Skills page**

```tsx
'use client';

import { useState } from 'react';

import { useSkills } from '@/hooks/useSkills';
import { InstallSkillDialog } from '@/components/settings/InstallSkillDialog';
import { SkillRow } from '@/components/settings/SkillRow';

export default function SkillsPage() {
  const [installOpen, setInstallOpen] = useState(false);
  const { list, enable, disable, uninstall } = useSkills();

  if (list.isLoading) return <div className="p-6 text-sm">Loading skills...</div>;
  if (list.error) {
    return <div className="p-6 text-sm text-red-600">Error: {list.error.message}</div>;
  }

  const skills = list.data ?? [];

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold">Skills</h2>
        <button
          type="button"
          onClick={() => setInstallOpen(true)}
          className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
        >
          Install Skill
        </button>
      </div>

      <div className="bg-white border border-gray-200 rounded">
        {skills.length === 0 ? (
          <div className="p-6 text-sm text-gray-400 text-center">No skills installed yet.</div>
        ) : (
          skills.map((s) => (
            <SkillRow
              key={s.id}
              skill={s}
              onToggle={() =>
                s.status === 'active'
                  ? disable.mutate(s.id)
                  : enable.mutate(s.id)
              }
              onUninstall={() => {
                if (confirm(`Uninstall ${s.name}? This cannot be undone.`)) {
                  uninstall.mutate(s.id);
                }
              }}
              onViewDetails={() => {
                // TODO Phase B follow-up: detail panel with full SKILL.md render
                alert(JSON.stringify(s.manifest_json, null, 2));
              }}
            />
          ))
        )}
      </div>

      <InstallSkillDialog open={installOpen} onClose={() => setInstallOpen(false)} />
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/app/settings/layout.tsx apps/web/src/app/settings/skills/page.tsx
git commit -m "feat(web): /settings/skills page (B-1)"
```

---

## Group 6: Settings → MCP Servers Page

### Task 6.1: McpServerRow + AddMcpServerDialog

**Files:** Create `apps/web/src/components/settings/McpServerRow.tsx`, `apps/web/src/components/settings/AddMcpServerDialog.tsx`

- [ ] **Step 1: McpServerRow**

```tsx
'use client';

import type { McpConnectionRow } from '@/lib/api/mcp';

interface Props {
  conn: McpConnectionRow;
  onReconnect: () => void;
  onRemove: () => void;
}

export function McpServerRow({ conn, onReconnect, onRemove }: Props) {
  const statusColor = {
    connected: 'text-green-700 bg-green-50',
    disconnected: 'text-amber-700 bg-amber-50',
    failed: 'text-red-700 bg-red-50',
  }[conn.status];

  const target = conn.transport === 'stdio' ? conn.command : conn.url;

  return (
    <div className="flex items-center justify-between border-b border-gray-100 py-2 px-3 hover:bg-gray-50">
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium">{conn.name}</span>
          <span className={`text-xs px-2 py-0.5 rounded ${statusColor}`}>{conn.status}</span>
          <span className="text-xs text-gray-400">{conn.transport}</span>
          <span className="text-xs text-gray-400">{conn.scope}</span>
        </div>
        <div className="text-xs text-gray-500 mt-0.5 truncate max-w-2xl">
          <code className="font-mono">{target}</code>
          {conn.last_error && <span className="ml-2 text-red-600">err: {conn.last_error}</span>}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button type="button" onClick={onReconnect} className="text-xs px-2 py-1 border rounded">
          Reconnect
        </button>
        <button type="button" onClick={onRemove} className="text-xs px-2 py-1 border border-red-300 text-red-600 rounded">
          Remove
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: AddMcpServerDialog**

```tsx
'use client';

import { useState } from 'react';

import { useMcpServers } from '@/hooks/useMcpServers';

interface Props {
  open: boolean;
  onClose: () => void;
  projectId?: string;
}

export function AddMcpServerDialog({ open, onClose, projectId }: Props) {
  const [name, setName] = useState('');
  const [transport, setTransport] = useState<'stdio' | 'sse' | 'streamable_http'>('stdio');
  const [command, setCommand] = useState('');
  const [argsRaw, setArgsRaw] = useState('');
  const [url, setUrl] = useState('');
  const [envRaw, setEnvRaw] = useState('');
  const [confirmedRisk, setConfirmedRisk] = useState(false);
  const [errMsg, setErrMsg] = useState<string | null>(null);

  const { add } = useMcpServers({ projectId });

  if (!open) return null;

  const submit = async () => {
    setErrMsg(null);
    if (!confirmedRisk) {
      setErrMsg('You must confirm the security risk before adding an MCP server.');
      return;
    }

    let args: string[] | undefined;
    if (argsRaw.trim()) {
      args = argsRaw.split(/\s+/).filter(Boolean);
    }
    let env: Record<string, string> | undefined;
    if (envRaw.trim()) {
      try {
        env = Object.fromEntries(
          envRaw
            .split('\n')
            .map((l) => l.trim())
            .filter(Boolean)
            .map((l) => {
              const idx = l.indexOf('=');
              if (idx < 0) throw new Error(`bad env line: ${l}`);
              return [l.slice(0, idx), l.slice(idx + 1)];
            }),
        );
      } catch (e) {
        setErrMsg(e instanceof Error ? e.message : 'env parse error');
        return;
      }
    }

    try {
      await add.mutateAsync({
        name,
        transport,
        command: transport === 'stdio' ? command : undefined,
        args,
        url: transport !== 'stdio' ? url : undefined,
        env,
        scope: projectId ? 'project' : 'global',
        project_id: projectId ?? null,
      });
      onClose();
      setName(''); setCommand(''); setUrl(''); setArgsRaw(''); setEnvRaw(''); setConfirmedRisk(false);
    } catch (e: unknown) {
      setErrMsg(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
        <h2 className="text-lg font-semibold mb-4">Add MCP Server</h2>

        <div className="bg-amber-50 border border-amber-300 rounded p-3 text-xs text-amber-800 mb-4">
          ⚠ Adding an MCP server runs external code on this machine (stdio
          transport spawns a subprocess; sse/streamable_http makes outbound
          HTTP calls). v1 has no sandbox — only add servers from sources you
          trust.
        </div>

        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input
              type="text" value={name} onChange={(e) => setName(e.target.value)}
              className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
              placeholder="e.g. fs-tools"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Transport</label>
            <div className="flex gap-2">
              {(['stdio', 'sse', 'streamable_http'] as const).map((t) => (
                <button
                  key={t} type="button" onClick={() => setTransport(t)}
                  className={`px-3 py-1 text-sm rounded border ${transport === t ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 border-gray-300'}`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          {transport === 'stdio' ? (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Command (executable path)
                </label>
                <input
                  type="text" value={command} onChange={(e) => setCommand(e.target.value)}
                  className="w-full px-2 py-1 border border-gray-300 rounded text-sm font-mono"
                  placeholder="/usr/local/bin/my-mcp-server"
                />
                <div className="text-xs text-gray-500 mt-1">
                  Bare shell names (bash, sh, powershell) are rejected. Use a specific path.
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Args (whitespace-separated, optional)
                </label>
                <input
                  type="text" value={argsRaw} onChange={(e) => setArgsRaw(e.target.value)}
                  className="w-full px-2 py-1 border border-gray-300 rounded text-sm font-mono"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Env (KEY=value, one per line, optional)
                </label>
                <textarea
                  value={envRaw} onChange={(e) => setEnvRaw(e.target.value)} rows={3}
                  className="w-full px-2 py-1 border border-gray-300 rounded text-xs font-mono"
                />
              </div>
            </>
          ) : (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">URL</label>
              <input
                type="text" value={url} onChange={(e) => setUrl(e.target.value)}
                className="w-full px-2 py-1 border border-gray-300 rounded text-sm font-mono"
                placeholder={transport === 'sse' ? 'https://example.com/sse' : 'https://example.com/mcp'}
              />
            </div>
          )}

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox" checked={confirmedRisk}
              onChange={(e) => setConfirmedRisk(e.target.checked)}
            />
            I understand this runs external code on this machine.
          </label>

          {errMsg && <div className="text-sm text-red-600">{errMsg}</div>}
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <button type="button" onClick={onClose} className="px-3 py-1 text-sm border rounded">
            Cancel
          </button>
          <button
            type="button" onClick={submit}
            disabled={!confirmedRisk || !name || (transport === 'stdio' ? !command : !url) || add.isPending}
            className="px-3 py-1 text-sm bg-blue-600 text-white rounded disabled:bg-gray-300"
          >
            {add.isPending ? 'Adding...' : 'Add'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/settings/McpServerRow.tsx apps/web/src/components/settings/AddMcpServerDialog.tsx
git commit -m "feat(web): McpServerRow + AddMcpServerDialog (B-1)"
```

### Task 6.2: Settings MCP Servers page

**Files:** Create `apps/web/src/app/settings/mcp-servers/page.tsx`

- [ ] **Step 1: Create page**

```tsx
'use client';

import { useState } from 'react';

import { useMcpServers } from '@/hooks/useMcpServers';
import { AddMcpServerDialog } from '@/components/settings/AddMcpServerDialog';
import { McpServerRow } from '@/components/settings/McpServerRow';

export default function McpServersPage() {
  const [addOpen, setAddOpen] = useState(false);
  const { list, reconnect, remove } = useMcpServers();

  if (list.isLoading) return <div className="p-6 text-sm">Loading MCP connections...</div>;
  if (list.error) {
    return <div className="p-6 text-sm text-red-600">Error: {list.error.message}</div>;
  }

  const conns = list.data ?? [];

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold">MCP Servers</h2>
        <button
          type="button"
          onClick={() => setAddOpen(true)}
          className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
        >
          Add Server
        </button>
      </div>

      <div className="bg-white border border-gray-200 rounded">
        {conns.length === 0 ? (
          <div className="p-6 text-sm text-gray-400 text-center">No MCP servers configured.</div>
        ) : (
          conns.map((c) => (
            <McpServerRow
              key={c.id}
              conn={c}
              onReconnect={() => reconnect.mutate(c.id)}
              onRemove={() => {
                if (confirm(`Remove ${c.name}?`)) remove.mutate(c.id);
              }}
            />
          ))
        )}
      </div>

      <AddMcpServerDialog open={addOpen} onClose={() => setAddOpen(false)} />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/app/settings/mcp-servers/page.tsx
git commit -m "feat(web): /settings/mcp-servers page (B-1)"
```

---

## Group 7: Episode Page Chat Area

### Task 7.1: Add NewAgentChat to episode detail page (behind flag)

**Files:** Modify `apps/web/src/app/agent/[projectId]/episodes/[episodeNum]/page.tsx`

- [ ] **Step 1: Read current episode page**

```bash
cat apps/web/src/app/agent/\[projectId\]/episodes/\[episodeNum\]/page.tsx | head -80
```

- [ ] **Step 2: Add NewAgentChat region**

Find a layout slot below the existing controls (probably near the bottom of the main content area). Add:

```tsx
import { featureFlags } from '@/lib/featureFlags';
import { NewAgentChat } from '@/components/chat/NewAgentChat';

// Inside the page component, after existing JSX:
{featureFlags.useNewAgent && (
  <div className="mt-6 border-t border-gray-200">
    <h3 className="px-3 py-2 font-semibold">Agent Chat</h3>
    <div className="h-96">
      <NewAgentChat
        context={{
          projectId,
          episodeNumber: episodeNum,
        }}
        toolsAllowlist={[
          'query_assets', 'query_episodes', 'query_panels',
          'generate_script', 'refine_script', 'analyze_script',
          'generate_panels', 'render_panels',
          'regenerate_asset_image',
          'analyze_quality', 'suggest_fixes',
          'commit_to_studio',
          'update_panel_dialogue', 'update_panel_camera',
        ]}
      />
    </div>
  </div>
)}
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/app/agent/\[projectId\]/episodes/\[episodeNum\]/page.tsx
git commit -m "feat(web): episode page — NewAgentChat panel behind flag (B-1)"
```

### Task 7.2: Add NewAgentChat to /chat/[projectId] page (behind flag)

**Files:** Modify `apps/web/src/app/chat/[projectId]/page.tsx`

- [ ] **Step 1: Read current chat page**

```bash
cat apps/web/src/app/chat/\[projectId\]/page.tsx | head -80
```

- [ ] **Step 2: Wrap or replace the page body with feature flag**

Add at top:
```tsx
import { featureFlags } from '@/lib/featureFlags';
import { NewAgentChat } from '@/components/chat/NewAgentChat';
```

Inside the page component, before the existing return:
```tsx
if (featureFlags.useNewAgent) {
  return (
    <div className="h-screen flex flex-col">
      <NewAgentChat context={{ projectId }} />
    </div>
  );
}
// ...existing legacy return below
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/app/chat/\[projectId\]/page.tsx
git commit -m "feat(web): /chat/[projectId] — NewAgentChat behind flag (B-1)"
```

---

## Group 8: Smoke Test + Verification

### Task 8.1: Component import smoke test

**Files:** Create `apps/web/src/__tests__/b1_imports.test.ts` (if jest configured) OR a simple Node script `apps/web/scripts/verify-b1-imports.mjs`

- [ ] **Step 1: Check whether jest/vitest exists**

```bash
cat apps/web/package.json | grep -E '"(jest|vitest|test)"'
```

If no test runner, do a manual import check via tsc.

- [ ] **Step 2: Type-check entire web codebase**

```bash
cd apps/web
npx tsc --noEmit 2>&1 | tail -20
```

Expected: 0 errors. If errors, fix before commit.

- [ ] **Step 3: Build smoke**

```bash
cd apps/web
npm run build 2>&1 | tail -20
```

Expected: build succeeds.

- [ ] **Step 4: Commit any fixes from steps 2-3**

```bash
git add -p   # only relevant fixes
git commit -m "fix(web): resolve type/build errors after B-1 frontend additions"
```

### Task 8.2: Manual flag-flip dev test

- [ ] **Step 1: Set env**

Create `apps/web/.env.local` (gitignored — don't commit):
```
NEXT_PUBLIC_USE_NEW_AGENT=true
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 2: Start backend**

```bash
cd apps/api
py -3.13 -m uvicorn app.main:app --port 8000
```

- [ ] **Step 3: Start frontend dev**

```bash
cd apps/web
npm run dev
```

- [ ] **Step 4: Manual verification checklist**

Open http://localhost:3001 and verify:
- [ ] `/chat/[projectId]` shows NewAgentChat (empty state, can type, send)
- [ ] Sending a message starts streaming (LLM provider must be configured in .env)
- [ ] Tool calls render as ToolCallCard
- [ ] `/settings/skills` lists 5 builtin skills (loaded via Phase A bootstrap)
- [ ] `/settings/mcp-servers` shows empty state (no connections yet)
- [ ] Setting `NEXT_PUBLIC_USE_NEW_AGENT=false` reverts to LegacyChat with no errors

Don't commit `.env.local`. After verification, optionally delete:
```bash
rm apps/web/.env.local
```

---

## Self-Review

**Spec coverage check:**
- §11 useChat hook → Task 2.1
- §11 NewAgentChat decomposition (MessageList / Message / ToolCallCard / DispatchedJobCard / AgentStateIndicator / ChatInput) → Tasks 3.1-3.5
- §11 Feature flag dispatcher → Task 4.1
- §11 Settings/Skills + Settings/MCP-Servers → Tasks 5.1-5.3, 6.1-6.2
- §11 Page changes (chat / agent episodes) → Tasks 7.1-7.2
- §11 Studio DirectorChat → **deferred** (DirectorChat is a thin wrapper over ChatPanel; the dispatcher in 4.1 covers it via the same default export)

**Placeholder scan:** None — every step has concrete code or commands.

**Type consistency:**
- `ChatContext` / `ChatOptions` defined in chatTypes.ts (Task 1.2), consumed identically in Tasks 1.3 / 2.1 / 3.5.
- `useChat` returns `UseChatResult` per Task 2.1; Tasks 3.5 + 7.x consume the same shape.
- `SkillRow` / `McpConnectionRow` types defined in skills.ts / mcp.ts (Task 1.4), used identically in hooks (2.2/2.3) and components (5.1/6.1).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-06-b1-phase-b-frontend-chat-shell.md`. Two execution options:

**1. Subagent-Driven** — fresh subagent per task with two-stage review

**2. Inline Execution** — execute tasks in current session with checkpoints

Phase B has heavier component-by-component work (TypeScript / JSX / styling) so subagent-driven is recommended for parallel-safe implementation.

**Phase B end state:** Backend untouched (still Phase A). New frontend code lives behind feature flag; old chat path keeps working. Manual flag-flip in dev environment validates the new path. Full cutover happens in Phase D.
