/**
 * ScriptAnalysisV1 - 剧情结构化注册表 (Zod Schema)
 * 
 * 与后端 ScriptAnalysisV1 对应
 */
import { z } from 'zod'

// ============ 枚举 ============

export const TimeOfDaySchema = z.enum(['day', 'night', 'dawn', 'dusk'])
export type TimeOfDay = z.infer<typeof TimeOfDaySchema>

export const WeatherSchema = z.enum(['clear', 'rainy', 'cloudy', 'foggy', 'snowy'])
export type Weather = z.infer<typeof WeatherSchema>

export const CharacterRoleSchema = z.enum(['protagonist', 'supporting', 'minor', 'unknown'])
export type CharacterRole = z.infer<typeof CharacterRoleSchema>

export const LocationTypeSchema = z.enum(['interior', 'exterior', 'semi'])
export type LocationType = z.infer<typeof LocationTypeSchema>

// ============ SourceSpan 溯源 ============

export const SourceSpanSchema = z.object({
    quote: z.string().min(10).max(200),
    start_char: z.number().int().optional().nullable(),
    end_char: z.number().int().optional().nullable(),
})
export type SourceSpan = z.infer<typeof SourceSpanSchema>

// ============ CharacterEntity 角色注册 ============

export const CharacterEntitySchema = z.object({
    canonical_name: z.string().min(1),
    aliases: z.array(z.string()).default([]),
    role: CharacterRoleSchema.default('supporting'),

    // 外观特征（至少 2 个）
    appearance_traits: z.array(z.string()).min(2),

    // 性格特征（至少 2 个）
    personality_traits: z.array(z.string()).min(2),

    wardrobe_notes: z.string().optional().nullable(),
    signature_props: z.array(z.string()).default([]),

    first_appearance_span: SourceSpanSchema,
})
export type CharacterEntity = z.infer<typeof CharacterEntitySchema>

// ============ LocationEntity 地点注册 ============

export const LocationEntitySchema = z.object({
    canonical_location: z.string().min(1),
    type: LocationTypeSchema.default('interior'),
    time_of_day_default: TimeOfDaySchema.default('day'),
    weather_default: WeatherSchema.default('clear'),

    anchor_hint: z.string().min(5),

    first_appearance_span: SourceSpanSchema,
})
export type LocationEntity = z.infer<typeof LocationEntitySchema>

// ============ Beat 节拍 ============

export const BeatSchema = z.object({
    beat_id: z.string().regex(/^b\d{3}$/),
    summary: z.string().min(5),
    characters_involved: z.array(z.string()),
    location_ref: z.string().optional().nullable(),
    emotional_tone: z.string().optional().nullable(),
    source_span: SourceSpanSchema,
})
export type Beat = z.infer<typeof BeatSchema>

// ============ ScriptAnalysisV1 主结构 ============

export const ScriptAnalysisV1Schema = z.object({
    schema_version: z.literal('script_analysis_v1'),
    language: z.enum(['zh', 'en']).default('zh'),
    script_digest: z.string().min(8),

    characters: z.array(CharacterEntitySchema).min(1),
    locations: z.array(LocationEntitySchema).min(1),
    beats: z.array(BeatSchema).min(1),

    created_at: z.string().optional(),
})
export type ScriptAnalysisV1 = z.infer<typeof ScriptAnalysisV1Schema>

// ============ 辅助函数 ============

export function parseScriptAnalysis(data: unknown): ScriptAnalysisV1 {
    return ScriptAnalysisV1Schema.parse(data)
}

export function safeParseScriptAnalysis(data: unknown) {
    return ScriptAnalysisV1Schema.safeParse(data)
}
