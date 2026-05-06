import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  disableSkill, enableSkill, installSkill, listSkills, uninstallSkill,
  type SkillRow,
} from '@/lib/api/skills';

export function useSkills(params: { scope?: string; projectId?: string } = {}) {
  const qc = useQueryClient();
  const key = ['skills', params.scope, params.projectId] as const;

  const list = useQuery({
    queryKey: key,
    queryFn: () => listSkills({ scope: params.scope, project_id: params.projectId }),
  });

  const install = useMutation({
    mutationFn: installSkill,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['skills'] }),
  });

  const enable = useMutation({
    mutationFn: enableSkill,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['skills'] }),
  });

  const disable = useMutation({
    mutationFn: disableSkill,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['skills'] }),
  });

  const uninstall = useMutation({
    mutationFn: uninstallSkill,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['skills'] }),
  });

  return { list, install, enable, disable, uninstall };
}
