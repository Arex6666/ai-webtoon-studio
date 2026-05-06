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
