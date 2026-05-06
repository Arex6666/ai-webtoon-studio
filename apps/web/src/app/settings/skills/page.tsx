'use client';

import { useState } from 'react';

import { useSkills } from '@/hooks/useSkills';
import { InstallSkillDialog } from '@/components/settings/InstallSkillDialog';
import { SkillRow } from '@/components/settings/SkillRow';

export default function SkillsPage() {
  const [installOpen, setInstallOpen] = useState(false);
  const { list, enable, disable, uninstall } = useSkills();

  if (list.isLoading) return <div className="p-6 text-sm">Loading skills...</div>;
  if (list.error) {
    return <div className="p-6 text-sm text-red-600">Error: {list.error.message}</div>;
  }

  const skills = list.data ?? [];

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold">Skills</h2>
        <button
          type="button"
          onClick={() => setInstallOpen(true)}
          className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
        >
          Install Skill
        </button>
      </div>

      <div className="bg-white border border-gray-200 rounded">
        {skills.length === 0 ? (
          <div className="p-6 text-sm text-gray-400 text-center">No skills installed yet.</div>
        ) : (
          skills.map((s) => (
            <SkillRow
              key={s.id}
              skill={s}
              onToggle={() =>
                s.status === 'active'
                  ? disable.mutate(s.id)
                  : enable.mutate(s.id)
              }
              onUninstall={() => {
                if (confirm(`Uninstall ${s.name}? This cannot be undone.`)) {
                  uninstall.mutate(s.id);
                }
              }}
              onViewDetails={() => {
                // TODO Phase B follow-up: detail panel with full SKILL.md render
                alert(JSON.stringify(s.manifest_json, null, 2));
              }}
            />
          ))
        )}
      </div>

      <InstallSkillDialog open={installOpen} onClose={() => setInstallOpen(false)} />
    </div>
  );
}
