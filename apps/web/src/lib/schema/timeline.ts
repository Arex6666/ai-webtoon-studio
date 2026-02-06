import { z } from 'zod'
import { clipSchema, type Clip } from './clip'
import { transitionSchema, type Transition } from './transition'

// Timeline 设置
export const timelineSettingsSchema = z.object({
  fpsDefault: z.number().default(8),
  aspect: z.enum(['9:16', '16:9', '1:1']).default('9:16'),
  exportPreset: z.enum(['draft', 'final']).default('draft'),
})

export type TimelineSettings = z.infer<typeof timelineSettingsSchema>

// Subtitle Item (占位)
export const subtitleItemSchema = z.object({
  id: z.string(),
  text: z.string(),
  startTime: z.number(),
  endTime: z.number(),
  style: z.object({
    fontSize: z.number().optional(),
    color: z.string().optional(),
    position: z.enum(['top', 'center', 'bottom']).optional(),
  }).optional(),
})

export type SubtitleItem = z.infer<typeof subtitleItemSchema>

// Tracks 结构 (多轨道)
export const tracksSchema = z.object({
  video: z.array(clipSchema),
  text: z.array(subtitleItemSchema),
})

export type Tracks = z.infer<typeof tracksSchema>

// Timeline schema (升级版)
export const timelineSchema = z.object({
  projectId: z.string(),
  chapterId: z.string(),
  // 向后兼容：保留 clips 字段
  clips: z.array(clipSchema),
  // 新增：多轨道结构
  tracks: tracksSchema.optional(),
  // 新增：转场列表
  transitions: z.array(transitionSchema).optional(),
  settings: timelineSettingsSchema,
  meta: z.object({
    updatedAt: z.string(),
  }),
})

export type Timeline = z.infer<typeof timelineSchema>

// 创建默认 Timeline
export function createDefaultTimeline(
  projectId: string,
  chapterId: string
): Timeline {
  return {
    projectId,
    chapterId,
    clips: [],
    tracks: {
      video: [],
      text: [],
    },
    transitions: [],
    settings: {
      fpsDefault: 8,
      aspect: '9:16',
      exportPreset: 'draft',
    },
    meta: {
      updatedAt: new Date().toISOString(),
    },
  }
}

// 计算总时长
export function calculateTotalDuration(clips: Clip[]): number {
  return clips.reduce((sum, clip) => sum + clip.durationSec, 0)
}

// 获取两个 clip 之间的转场
export function getTransitionBetween(
  transitions: Transition[] | undefined,
  fromClipId: string,
  toClipId: string
): Transition | undefined {
  return transitions?.find(
    t => t.between.fromClipId === fromClipId && t.between.toClipId === toClipId
  )
}
