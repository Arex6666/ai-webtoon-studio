'use client';

import type { DispatchedJob } from '@/lib/api/chatTypes';

interface Props {
  job: DispatchedJob & { action_id: string; tool_name: string };
}

/** Renders the dispatched-job placeholder while a slow tool is running.
 *
 * For B-1 v1: shows job_id + ETA. Real-time progress via WebSocket subscription
 * is deferred — frontend can wire this up against the existing /ws channel
 * later (job_progress events with matching job_id).
 */
export function DispatchedJobCard({ job }: Props) {
  return (
    <div className="border border-blue-200 bg-blue-50 rounded p-2 text-sm">
      <div className="font-medium text-blue-900">{job.tool_name} dispatched</div>
      <div className="text-xs text-blue-700">
        job: <code className="font-mono">{job.job_id}</code>
        {job.eta_seconds ? ` · ETA ${job.eta_seconds}s` : null}
      </div>
    </div>
  );
}
