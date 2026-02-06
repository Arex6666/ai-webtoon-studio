/**
 * Conversation System Type Definitions
 * TypeScript types for the conversational agent system
 */

// ===== Conversation Models =====

export interface Conversation {
  id: string;
  project_id: string;
  chapter_id?: string;
  title?: string;
  status: 'active' | 'paused' | 'completed';
  current_intent?: string;
  context_json?: Record<string, any>;
  message_count: number;
  total_tokens_used: number;
  created_at: string;
  updated_at: string;
}

export interface ConversationMessage {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  intent?: string;
  entities_json?: Record<string, any>;
  tool_calls_json?: ToolCall[];
  tool_results_json?: ToolResult[];
  model_used?: string;
  tokens_used?: number;
  latency_ms?: number;
  created_at: string;
  updated_at: string;
}

export interface ConversationAction {
  id: string;
  conversation_id: string;
  message_id: string;
  action_type: string;
  action_params_json?: Record<string, any>;
  status: 'pending' | 'running' | 'completed' | 'failed';
  job_id?: string;
  result_json?: Record<string, any>;
  error_json?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

// ===== Tool System =====

export interface ToolCall {
  tool_name: string;
  parameters: Record<string, any>;
}

export interface ToolResult {
  tool_name: string;
  result: any;
  error?: string;
}

// ===== WebSocket Events =====

export type WsEventType =
  | 'connected'
  | 'user_message'
  | 'assistant_message'
  | 'assistant_message_chunk'
  | 'message_chunk'
  | 'message_complete'
  | 'tool_call'
  | 'action_started'
  | 'action_progress'
  | 'action_completed'
  | 'error'
  | 'ping'
  | 'pong';

export interface WsBaseEvent {
  type: WsEventType;
}

export interface WsConnectedEvent extends WsBaseEvent {
  type: 'connected';
  conversation_id: string;
  message: string;
}

export interface WsUserMessageEvent extends WsBaseEvent {
  type: 'user_message';
  content: string;
}

export interface WsAssistantMessageEvent extends WsBaseEvent {
  type: 'assistant_message';
  message_id?: string;
  content: string;
  intent?: string;
  entities?: Record<string, any>;
}

export interface WsMessageChunkEvent extends WsBaseEvent {
  type: 'assistant_message_chunk' | 'message_chunk';
  message_id?: string;
  chunk: string;
  is_final?: boolean;
}

export interface WsMessageCompleteEvent extends WsBaseEvent {
  type: 'message_complete';
  message_id: string;
}

export interface WsToolCallEvent extends WsBaseEvent {
  type: 'tool_call';
  tool_call: ToolCall;
}

export interface WsActionStartedEvent extends WsBaseEvent {
  type: 'action_started';
  action_id: string;
  action_type: string;
  description: string;
}

export interface WsActionProgressEvent extends WsBaseEvent {
  type: 'action_progress';
  action_id: string;
  action_type?: string;
  progress: number;
  description?: string;
  preview_url?: string;
}

export interface WsActionCompletedEvent extends WsBaseEvent {
  type: 'action_completed';
  action_id: string;
  action_type?: string;
  result: Record<string, any>;
}

export interface WsErrorEvent extends WsBaseEvent {
  type: 'error';
  error: string;
}

export interface WsPingEvent extends WsBaseEvent {
  type: 'ping';
}

export interface WsPongEvent extends WsBaseEvent {
  type: 'pong';
}

export type WsEvent =
  | WsConnectedEvent
  | WsUserMessageEvent
  | WsAssistantMessageEvent
  | WsMessageChunkEvent
  | WsMessageCompleteEvent
  | WsToolCallEvent
  | WsActionStartedEvent
  | WsActionProgressEvent
  | WsActionCompletedEvent
  | WsErrorEvent
  | WsPingEvent
  | WsPongEvent;

// ===== API Request/Response Types =====

export interface CreateConversationRequest {
  project_id: string;
  chapter_id?: string;
  title?: string;
}

export interface SendMessageRequest {
  content: string;
  streaming?: boolean;
}

export interface ConversationListResponse {
  conversations: Conversation[];
  total: number;
}

export interface MessageListResponse {
  messages: ConversationMessage[];
  total: number;
}

// ===== UI State Types =====

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
  intent?: string;
  toolCalls?: ToolCall[];
  actions?: ActionState[];
}

export interface ActionState {
  id: string;
  type: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress?: number;
  previewUrl?: string;
  result?: Record<string, any>;
  error?: string;
}

export interface ConversationState {
  id: string | null;
  projectId: string | null;
  chapterId: string | null;
  messages: ChatMessage[];
  isConnected: boolean;
  isStreaming: boolean;
  pendingActions: ActionState[];
  error: string | null;
}
