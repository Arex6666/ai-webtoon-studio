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
