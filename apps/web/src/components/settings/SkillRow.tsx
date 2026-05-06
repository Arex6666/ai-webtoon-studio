'use client';

import type { SkillRow as SkillRowData } from '@/lib/api/skills';

interface Props {
  skill: SkillRowData;
  onToggle: () => void;
  onUninstall: () => void;
  onViewDetails: () => void;
}

export function SkillRow({ skill, onToggle, onUninstall, onViewDetails }: Props) {
  const statusColor = {
    active: 'text-green-700 bg-green-50',
    disabled: 'text-gray-600 bg-gray-100',
    failed: 'text-red-700 bg-red-50',
    installing: 'text-blue-700 bg-blue-50',
    uninstalled: 'text-gray-400 bg-gray-50',
  }[skill.status];

  return (
    <div className="flex items-center justify-between border-b border-gray-100 py-2 px-3 hover:bg-gray-50">
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium">{skill.name}</span>
          <span className="text-xs text-gray-500">@ {skill.version}</span>
          <span className={`text-xs px-2 py-0.5 rounded ${statusColor}`}>{skill.status}</span>
          <span className="text-xs text-gray-400">{skill.scope}</span>
          <span className="text-xs text-gray-400">{skill.source_type}</span>
        </div>
        {(skill.manifest_json as { description?: string } | undefined)?.description && (
          <div className="text-xs text-gray-500 mt-0.5">
            {(skill.manifest_json as { description?: string }).description}
          </div>
        )}
      </div>
      <div className="flex items-center gap-2">
        <button type="button" onClick={onViewDetails} className="text-xs text-blue-600 hover:underline">
          Details
        </button>
        {skill.source_type !== 'builtin' && (
          <>
            <button type="button" onClick={onToggle} className="text-xs px-2 py-1 border rounded">
              {skill.status === 'active' ? 'Disable' : 'Enable'}
            </button>
            <button type="button" onClick={onUninstall} className="text-xs px-2 py-1 border border-red-300 text-red-600 rounded">
              Uninstall
            </button>
          </>
        )}
      </div>
    </div>
  );
}
