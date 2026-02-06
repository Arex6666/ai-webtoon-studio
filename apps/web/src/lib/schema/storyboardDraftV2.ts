/**
 * StoryboardDraftV2 - 面板级结构化输出 (Zod Schema)
 * 
 * 与后端 StoryboardDraftV2 对应
 */
import { z } from 'zod'
import { SourceSpanSchema, TimeOfDaySchema, WeatherSchema } from './scriptAnalysisV1'

// ============ 枚举 ============

export const ShotTypeSchema = z.enum(['ECU', 'CU', 'MS', 'LS', 'WS', 'OTS'])
export type ShotType = z.infer<typeof ShotTypeSchema>

export const CameraMoveSchema = z.enum([
    'static', 'pan', 'tilt', 'dolly_in', 'dolly_out',
    'zoom_in', 'zoom_out', 'handheld'
])
export type CameraMove = z.infer<typeof CameraMoveSchema>

export const CameraHeightSchema = z.enum(['eye', 'high', 'low'])
export type CameraHeight = z.infer<typeof CameraHeightSchema>

// ============ PanelDraft 分镜格 ============

export const PanelDraftSchema = z.object({
    index: z.number().int().min(1),
    beat_ref: z.string().optional().nullable(),

    // 镜头参数
    shot_type: ShotTypeSchema,
    camera_move: CameraMoveSchema,
    duration_s: z.number().min(1.5).max(8.0),
    lens_hint: z.string().default('50mm'),
    mood: z.string().min(1),

    // 场景参数
    location: z.string().min(1),
    time_of_day: TimeOfDaySchema,
    weather: WeatherSchema,

    // 角色
    cast: z.array(z.string()),

    // 动作描述
    actions: z.string().min(10),

    // 构图注释（至少 2 条）
    composition_notes: z.array(z.string()).min(2),

    // 对话
    dialogue_lines: z.array(z.string()).default([]),

    // 视觉提示
    visual_prompt: z.string().min(20),

    // 连续性注释（至少 1 条）
    continuity_notes: z.array(z.string()).min(1),

    // 原文溯源
    source_span: SourceSpanSchema,

    // 可选字段
    negative_prompt: z.string().optional().nullable(),
    style_tags: z.array(z.string()).default([]),
    sfx: z.array(z.string()).default([]),
    camera_height: CameraHeightSchema.optional().nullable(),
    is_establishing: z.boolean().default(false),
})
export type PanelDraft = z.infer<typeof PanelDraftSchema>

// ============ StoryboardDraftV2 主结构 ============

export const StoryboardDraftV2Schema = z.object({
    schema_version: z.literal('storyboard_draft_v2'),
    prompt_version: z.string().default('pc_v1'),
    analysis_ref: z.string().optional().nullable(),

    panels: z.array(PanelDraftSchema).min(1),

    total_duration_s: z.number().default(0),
    director_notes: z.string().default(''),
    created_at: z.string().optional(),
})
export type StoryboardDraftV2 = z.infer<typeof StoryboardDraftV2Schema>

// ============ 辅助函数 ============

export function parseStoryboardDraft(data: unknown): StoryboardDraftV2 {
    return StoryboardDraftV2Schema.parse(data)
}

export function safeParseStoryboardDraft(data: unknown) {
    return StoryboardDraftV2Schema.safeParse(data)
}

/**
 * 验证单个分镜
 */
export function validatePanelDraft(panel: unknown): { valid: boolean; errors: string[] } {
    const result = PanelDraftSchema.safeParse(panel)
    if (result.success) {
        return { valid: true, errors: [] }
    }

    const errors = result.error.issues.map((e) =>
        `${String(e.path.join('.'))}: ${e.message}`
    )
    return { valid: false, errors }
}

/**
 * 获取镜头类型中文描述
 */
export function getShotTypeLabel(shotType: ShotType): string {
    const labels: Record<ShotType, string> = {
        ECU: '极特写',
        CU: '特写',
        MS: '中景',
        LS: '远景',
        WS: '大远景',
        OTS: '过肩',
    }
    return labels[shotType] || shotType
}

/**
 * 获取运镜类型中文描述
 */
export function getCameraMoveLabel(cameraMove: CameraMove): string {
    const labels: Record<CameraMove, string> = {
        static: '静止',
        pan: '摇摄',
        tilt: '俯仰',
        dolly_in: '推',
        dolly_out: '拉',
        zoom_in: '变焦推',
        zoom_out: '变焦拉',
        handheld: '手持',
    }
    return labels[cameraMove] || cameraMove
}
