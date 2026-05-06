'use client';

import { useState } from 'react';

import { useSkills } from '@/hooks/useSkills';

interface Props {
  open: boolean;
  onClose: () => void;
  projectId?: string;
}

export function InstallSkillDialog({ open, onClose, projectId }: Props) {
  const [sourceType, setSourceType] = useState<'local' | 'url' | 'git'>('url');
  const [source, setSource] = useState('');
  const [scope, setScope] = useState<'global' | 'project'>(projectId ? 'project' : 'global');
  const [errMsg, setErrMsg] = useState<string | null>(null);

  const { install } = useSkills({ projectId });

  if (!open) return null;

  const submit = async () => {
    setErrMsg(null);
    try {
      await install.mutateAsync({
        source_type: sourceType,
        source,
        scope,
        project_id: scope === 'project' ? projectId ?? null : null,
      });
      onClose();
      setSource('');
    } catch (e: unknown) {
      setErrMsg(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
        <h2 className="text-lg font-semibold mb-4">Install Skill</h2>

        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Source type</label>
            <div className="flex gap-2">
              {(['local', 'url', 'git'] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setSourceType(t)}
                  className={`px-3 py-1 text-sm rounded border ${sourceType === t ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 border-gray-300'}`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {sourceType === 'local' ? 'Path' : sourceType === 'url' ? 'URL (.tar.gz / .zip)' : 'git+ URL'}
            </label>
            <input
              type="text"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder={sourceType === 'git' ? 'git+https://github.com/owner/repo@v1#path=skills/foo' : 'https://example.com/skill.tar.gz'}
              className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Scope</label>
            <select
              value={scope}
              onChange={(e) => setScope(e.target.value as 'global' | 'project')}
              className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
            >
              <option value="global">global</option>
              <option value="project" disabled={!projectId}>
                project {projectId ? '' : '(no projectId)'}
              </option>
            </select>
          </div>

          {errMsg && <div className="text-sm text-red-600">{errMsg}</div>}
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <button type="button" onClick={onClose} className="px-3 py-1 text-sm border rounded">
            Cancel
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={!source || install.isPending}
            className="px-3 py-1 text-sm bg-blue-600 text-white rounded disabled:bg-gray-300"
          >
            {install.isPending ? 'Installing...' : 'Install'}
          </button>
        </div>
      </div>
    </div>
  );
}
