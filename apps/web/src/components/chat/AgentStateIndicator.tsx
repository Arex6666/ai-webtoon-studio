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
