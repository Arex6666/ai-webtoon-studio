import { z } from 'zod'
import { providerSchema } from './provider'
import { keyframeRefSchema, motionModeSchema, type KeyframeRef, type MotionMode } from './keyframe'

// Clip 状态
export const clipStatusSchema = z.enum([
  'Idle',
  'Queued',
  'Running',
  'Succeeded',
  'Failed',
])

export type ClipStatus = z.infer<typeof clipStatusSchema>

// Clip 类型
export const clipTypeSchema = z.enum(['motion_clip', 'transition'])
export type ClipType = z.infer<typeof clipTypeSchema>

// Clip 输出
export const clipOutputSchema = z.object({
  videoUrl: z.string().optional(),
  previewUrl: z.string().optional(),
  frames: z.array(z.string()).optional(),
})

export type ClipOutput = z.infer<typeof clipOutputSchema>

// Camera Plan (可选)
export const cameraPlanSchema = z.object({
  move: z.string(),
  intensity: z.number().min(0).max(1),
  beat: z.enum(['slow', 'medium', 'fast']),
}).optional()

export type CameraPlan = z.infer<typeof cameraPlanSchema>

// Clip schema
export const clipSchema = z.object({
  id: z.string(),
  projectId: z.string(),
  chapterId: z.string(),
  panelId: z.string(),
  layerPackId: z.string().nullable(),
  type: clipTypeSchema.default('motion_clip'),

  // 关键帧 (Task 07)
  startFrame: keyframeRefSchema.nullable().optional(),
  endFrame: keyframeRefSchema.nullable().optional(),
  motionMode: motionModeSchema.default('dual_keyframe'),
  cameraPlan: cameraPlanSchema,

  durationSec: z.number().min(0.5).max(10),
  fps: z.number(),
  provider: providerSchema,
  motionPrompt: z.string(),
  negative: z.string(),
  seedMode: z.enum(['keep', 'new']),
  status: clipStatusSchema,
  progress: z.number().min(0).max(1),
  output: clipOutputSchema.optional(),
  error: z.string().optional(),
  createdAt: z.string(),
  updatedAt: z.string(),
})

export type Clip = z.infer<typeof clipSchema>

// 创建默认 Clip
export function createDefaultClip(
  panelId: string,
  chapterId: string,
  projectId: string,
  layerPackId: string | null = null,
  startFrame: KeyframeRef | null = null
): Clip {
  const now = new Date().toISOString()
  return {
    id: `clip-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    projectId,
    chapterId,
    panelId,
    layerPackId,
    type: 'motion_clip',
    startFrame: startFrame || null,
    endFrame: null,
    motionMode: 'dual_keyframe',
    cameraPlan: undefined,
    durationSec: 3,
    fps: 8,
    provider: 'mock',
    motionPrompt: '',
    negative: '',
    seedMode: 'new',
    status: 'Idle',
    progress: 0,
    createdAt: now,
    updatedAt: now,
  }
}

// 检查 Clip 是否可以生成
export function canGenerateClip(clip: Clip): { canGenerate: boolean; reason?: string } {
  if (clip.status === 'Running' || clip.status === 'Queued') {
    return { canGenerate: false, reason: '正在生成中' }
  }

  if (clip.motionMode === 'dual_keyframe') {
    if (!clip.startFrame) {
      return { canGenerate: false, reason: '请设置起始关键帧' }
    }
    if (!clip.endFrame) {
      return { canGenerate: false, reason: '请设置结束关键帧' }
    }
  } else {
    if (!clip.startFrame) {
      return { canGenerate: false, reason: '请设置起始关键帧' }
    }
  }

  return { canGenerate: true }
}
