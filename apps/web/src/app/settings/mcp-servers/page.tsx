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
