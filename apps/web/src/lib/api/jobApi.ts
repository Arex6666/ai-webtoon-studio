import { apiPost, apiGet } from './client'

export type JobType = 'image' | 'video' | 'storyboard' | 'export'
export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'canceled'

export interface JobCreateRequest {
  type: JobType
  target_id: string
  provider: string
  params?: Record<string, unknown>
}

export interface JobStatusResponse {
  job_id: string
  type: JobType
  status: JobStatus
  progress: number
  message?: string
  agent?: string
  result?: Record<string, unknown>
  error?: string
  created_at?: string
  updated_at?: string
}

export const jobApi = {
  create: (req: JobCreateRequest) =>
    apiPost<JobStatusResponse>('/api/v1/jobs', req),

  get: (jobId: string) =>
    apiGet<JobStatusResponse>(`/api/v1/jobs/${jobId}`),

  list: (chapterId: string) =>
    apiGet<{ items: JobStatusResponse[]; total: number }>(`/api/v1/jobs/chapter/${chapterId}`),

  cancel: (jobId: string) =>
    apiPost<{ job_id: string; status: string }>(`/api/v1/jobs/${jobId}/cancel`, {}),
}
