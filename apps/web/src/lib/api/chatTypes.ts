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
