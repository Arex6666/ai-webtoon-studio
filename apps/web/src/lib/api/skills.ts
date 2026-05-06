/** Skills API — wraps /api/v1/skills/*. */
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export interface SkillRow {
  id: string;
  name: string;
  version: string;
  source_type: 'builtin' | 'local' | 'url' | 'git' | 'mcp_only';
  source_url: string | null;
  status: 'active' | 'disabled' | 'failed' | 'uninstalled' | 'installing';
  scope: 'global' | 'project';
  project_id: string | null;
  manifest_json: Record<string, unknown>;
}

export async function listSkills(params: { scope?: string; project_id?: string } = {}): Promise<SkillRow[]> {
  const qs = new URLSearchParams();
  if (params.scope) qs.set('scope', params.scope);
  if (params.project_id) qs.set('project_id', params.project_id);
  const r = await fetch(`${API_BASE}/api/v1/skills${qs.toString() ? `?${qs}` : ''}`);
  if (!r.ok) throw new Error(`listSkills: ${r.status}`);
  return r.json();
}

export async function installSkill(payload: {
  source_type: 'local' | 'url' | 'git';
  source: string;
  scope: 'global' | 'project';
  project_id?: string | null;
}): Promise<SkillRow> {
  const r = await fetch(`${API_BASE}/api/v1/skills/install`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(`installSkill: ${r.status} ${await r.text()}`);
  return r.json();
}

export async function enableSkill(skillId: string): Promise<SkillRow> {
  const r = await fetch(`${API_BASE}/api/v1/skills/${skillId}/enable`, { method: 'POST' });
  if (!r.ok) throw new Error(`enableSkill: ${r.status}`);
  return r.json();
}

export async function disableSkill(skillId: string): Promise<SkillRow> {
  const r = await fetch(`${API_BASE}/api/v1/skills/${skillId}/disable`, { method: 'POST' });
  if (!r.ok) throw new Error(`disableSkill: ${r.status}`);
  return r.json();
}

export async function uninstallSkill(skillId: string): Promise<void> {
  const r = await fetch(`${API_BASE}/api/v1/skills/${skillId}`, { method: 'DELETE' });
  if (!r.ok) throw new Error(`uninstallSkill: ${r.status}`);
}
