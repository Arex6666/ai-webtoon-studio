import { z } from 'zod'
import { providerSchema } from './provider'

// VideoJob 状态
export const videoJobStatusSchema = z.enum([
  'Queued',
  'Running',
  'Succeeded',
  'Failed',
])

export type VideoJobStatus = z.infer<typeof videoJobStatusSchema>

// VideoJob schema
export const videoJobSchema = z.object({
  id: z.string(),
  clipId: z.string(),
  provider: providerSchema,
  status: videoJobStatusSchema,
  progress: z.number().min(0).max(1),
  createdAt: z.string(),
  updatedAt: z.string(),
  error: z.string().optional(),
})

export type VideoJob = z.infer<typeof videoJobSchema>

// 创建 VideoJob
export function createVideoJob(
  clipId: string,
  provider: z.infer<typeof providerSchema>
): VideoJob {
  const now = new Date().toISOString()
  return {
    id: `vjob-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    clipId,
    provider,
    status: 'Queued',
    progress: 0,
    createdAt: now,
    updatedAt: now,
  }
}
