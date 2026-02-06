import { z } from 'zod'

// ============ KeyframeRef Types ============

/**
 * 关键帧引用 - 可来自 LayerPack 或 Asset
 */
export const keyframeRefSchema = z.discriminatedUnion('type', [
    z.object({
        type: z.literal('layerpack'),
        panelId: z.string(),
        layerPackId: z.string(),
        url: z.string(),
        w: z.number(),
        h: z.number(),
    }),
    z.object({
        type: z.literal('asset'),
        assetId: z.string(),
        url: z.string(),
        w: z.number(),
        h: z.number(),
    }),
])

export type KeyframeRef = z.infer<typeof keyframeRefSchema>

// ============ Motion Mode ============

export const motionModeSchema = z.enum(['single_keyframe', 'dual_keyframe'])
export type MotionMode = z.infer<typeof motionModeSchema>

// ============ Factory Functions ============

/**
 * 从 LayerPack 创建关键帧引用
 */
export function createKeyframeFromLayerPack(
    panelId: string,
    layerPackId: string,
    url: string,
    w: number = 800,
    h: number = 600
): KeyframeRef {
    return {
        type: 'layerpack',
        panelId,
        layerPackId,
        url,
        w,
        h,
    }
}

/**
 * 从 Asset 创建关键帧引用
 */
export function createKeyframeFromAsset(
    assetId: string,
    url: string,
    w: number = 800,
    h: number = 600
): KeyframeRef {
    return {
        type: 'asset',
        assetId,
        url,
        w,
        h,
    }
}
