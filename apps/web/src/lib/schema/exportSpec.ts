import { z } from 'zod'
import { providerSchema } from './provider'

// ExportSpec 中的 Clip 信息
export const exportClipSchema = z.object({
  order: z.number(),
  clipId: z.string(),
  panelId: z.string(),
  layerPackId: z.string().nullable(),
  provider: providerSchema,
  durationSec: z.number(),
  fps: z.number(),
  motionPrompt: z.string(),
  input: z.object({
    imageUrl: z.string(),
    endImageUrl: z.string().optional(),
  }),
  output: z.object({
    videoUrl: z.string().optional(),
    frames: z.array(z.string()).optional(),
  }).optional(),
})

export type ExportClip = z.infer<typeof exportClipSchema>

// ExportSpec schema
export const exportSpecSchema = z.object({
  projectId: z.string(),
  chapterId: z.string(),
  version: z.string(),
  timeline: z.object({
    fps: z.number(),
    aspect: z.string(),
    totalDurationSec: z.number(),
  }),
  clips: z.array(exportClipSchema),
  generatedAt: z.string(),
  notes: z.string().optional(),
})

export type ExportSpec = z.infer<typeof exportSpecSchema>

// ExportJob schema
export const exportJobSchema = z.object({
  id: z.string(),
  chapterId: z.string(),
  status: z.enum(['Queued', 'Running', 'Succeeded', 'Failed']),
  progress: z.number().min(0).max(1),
  outputSpecUrl: z.string().optional(),
  error: z.string().optional(),
  createdAt: z.string(),
  updatedAt: z.string(),
})

export type ExportJob = z.infer<typeof exportJobSchema>

// 创建 ExportJob
export function createExportJob(chapterId: string): ExportJob {
  const now = new Date().toISOString()
  return {
    id: `export-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    chapterId,
    status: 'Queued',
    progress: 0,
    createdAt: now,
    updatedAt: now,
  }
}
