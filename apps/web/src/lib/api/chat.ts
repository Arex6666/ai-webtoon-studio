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
