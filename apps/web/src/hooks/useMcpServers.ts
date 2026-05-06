import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  addMcpConnection, listMcpConnections, reconnectMcp, removeMcpConnection,
  type McpConnectionRow, type AddMcpRequest,
} from '@/lib/api/mcp';

export function useMcpServers(params: { scope?: string; projectId?: string } = {}) {
  const qc = useQueryClient();
  const key = ['mcp-connections', params.scope, params.projectId] as const;

  const list = useQuery({
    queryKey: key,
    queryFn: () => listMcpConnections({ scope: params.scope, project_id: params.projectId }),
  });

  const add = useMutation({
    mutationFn: addMcpConnection,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['mcp-connections'] }),
  });

  const reconnect = useMutation({
    mutationFn: reconnectMcp,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['mcp-connections'] }),
  });

  const remove = useMutation({
    mutationFn: removeMcpConnection,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['mcp-connections'] }),
  });

  return { list, add, reconnect, remove };
}
