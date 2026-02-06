import { z } from 'zod'

// ============ Fix Strategy ============

export const FixStrategy = z.enum([
    'inpaint',     // 局部修复
    'redraw_char', // 重绘角色
    'redraw_bg',   // 重绘背景
    'reroll',      // 重新抽卡（整体重绘）
])
export type FixStrategy = z.infer<typeof FixStrategy>

// ============ ROI Schema ============

export const RoiSchema = z.object({
    x: z.number(),
    y: z.number(),
    w: z.number(),
    h: z.number(),
})

export type Roi = z.infer<typeof RoiSchema>

// ============ Seed Mode ============

export const SeedMode = z.enum(['keep', 'new'])
export type SeedMode = z.infer<typeof SeedMode>

// ============ FixPlan Schema ============

export const FixPlanSchema = z.object({
    panelId: z.string(),
    layerPackId: z.string(),
    strategy: FixStrategy,
    roi: RoiSchema.nullable(),
    prompt: z.string(),
    negative: z.string().default(''),
    strength: z.number().min(0).max(1).default(0.75),
    seedMode: SeedMode.default('new'),
    createdAt: z.string(),
})

export type FixPlan = z.infer<typeof FixPlanSchema>

// ============ Factory Functions ============

export function createDefaultFixPlan(
    panelId: string,
    layerPackId: string,
    strategy: FixStrategy = 'inpaint'
): FixPlan {
    return {
        panelId,
        layerPackId,
        strategy,
        roi: null,
        prompt: '',
        negative: '',
        strength: 0.75,
        seedMode: 'new',
        createdAt: new Date().toISOString(),
    }
}

// ============ Strategy Labels ============

export const STRATEGY_LABELS: Record<FixStrategy, { label: string; description: string }> = {
    inpaint: {
        label: '局部修复',
        description: '使用选区修复特定区域'
    },
    redraw_char: {
        label: '重绘角色',
        description: '保持背景，重新生成角色'
    },
    redraw_bg: {
        label: '重绘背景',
        description: '保持角色，重新生成背景'
    },
    reroll: {
        label: '重新抽卡',
        description: '完全重新生成整张图片'
    },
}
