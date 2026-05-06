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
