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
