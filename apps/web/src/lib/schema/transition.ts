import { z } from 'zod'

// ============ Transition Types ============

export const transitionTypeSchema = z.enum(['cut', 'fade', 'dissolve', 'push'])
export type TransitionType = z.infer<typeof transitionTypeSchema>

// ============ Transition Schema ============

export const transitionSchema = z.object({
    id: z.string(),
    between: z.object({
        fromClipId: z.string(),
        toClipId: z.string(),
    }),
    type: transitionTypeSchema,
    durationSec: z.number().min(0).max(1.5).default(0.3),
    easing: z.string().optional(),
})

export type Transition = z.infer<typeof transitionSchema>

// ============ Factory Functions ============

export function createDefaultTransition(
    fromClipId: string,
    toClipId: string,
    type: TransitionType = 'fade',
    durationSec: number = 0.3
): Transition {
    return {
        id: `trans-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        between: {
            fromClipId,
            toClipId,
        },
        type,
        durationSec,
    }
}

// ============ Transition Labels ============

export const TRANSITION_LABELS: Record<TransitionType, { label: string; description: string }> = {
    cut: { label: '硬切', description: '直接切换，无过渡' },
    fade: { label: '淡入淡出', description: '渐变过渡' },
    dissolve: { label: '溶解', description: '两画面交叉溶解' },
    push: { label: '推入', description: '新画面推入' },
}
