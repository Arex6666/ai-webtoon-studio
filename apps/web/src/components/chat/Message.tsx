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
              ? { code: parsed.tool_result.error.code, message: parsed.tool_result.error.message }
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
