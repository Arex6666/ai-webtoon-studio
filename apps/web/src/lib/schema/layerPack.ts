import { z } from 'zod'
import { RenderProvider } from './job'

// ============ Layer Output Schema ============

export const LayerOutputSchema = z.object({
    url: z.string(),
    w: z.number().optional(),
    h: z.number().optional(),
})

export type LayerOutput = z.infer<typeof LayerOutputSchema>

// ============ Mask Schema ============

export const MaskKind = z.enum(['char', 'roi', 'depth', 'seg'])
export type MaskKind = z.infer<typeof MaskKind>

export const MaskSchema = z.object({
    url: z.string(),
    kind: MaskKind,
    w: z.number().optional(),
    h: z.number().optional(),
})

export type Mask = z.infer<typeof MaskSchema>

// ============ Extended LayerPack Schema ============

export const ExtendedLayerPackSchema = z.object({
    id: z.string(),
    panelId: z.string(),
    jobId: z.string(),
    version: z.number().default(1),
    createdAt: z.string(),

    engine: z.object({
        provider: RenderProvider,
        modelHint: z.string().optional(),
    }),

    outputs: z.object({
        full: LayerOutputSchema,
        bg: LayerOutputSchema.optional(),
        char: LayerOutputSchema.optional(),
        fg: LayerOutputSchema.optional(),
        text: LayerOutputSchema.optional(),
        mask: MaskSchema.optional(),
    }),

    meta: z.object({
        seed: z.number().optional(),
        steps: z.number().optional(),
        cfg: z.number().optional(),
        notes: z.string().optional(),
    }).optional(),

    qa: z.object({
        score: z.number().min(0).max(1),
        issues: z.array(z.string()),
    }).optional(),
})

export type ExtendedLayerPack = z.infer<typeof ExtendedLayerPackSchema>

// ============ Factory Functions ============

let layerPackVersionCounter: Record<string, number> = {}

export function getNextLayerPackVersion(panelId: string): number {
    if (!layerPackVersionCounter[panelId]) {
        layerPackVersionCounter[panelId] = 0
    }
    layerPackVersionCounter[panelId]++
    return layerPackVersionCounter[panelId]
}

export function createExtendedLayerPack(
    panelId: string,
    jobId: string,
    provider: z.infer<typeof RenderProvider> = 'mock'
): ExtendedLayerPack {
    const version = getNextLayerPackVersion(panelId)
    const seed = panelId.replace(/[^a-z0-9]/gi, '')
    const timestamp = Date.now()

    return {
        id: `lp-${timestamp}-${Math.random().toString(36).slice(2, 8)}`,
        panelId,
        jobId,
        version,
        createdAt: new Date().toISOString(),
        engine: {
            provider,
        },
        outputs: {
            full: {
                url: `https://picsum.photos/seed/${seed}-${version}-full/800/600`,
                w: 800,
                h: 600
            },
            bg: {
                url: `https://picsum.photos/seed/${seed}-${version}-bg/800/600`,
                w: 800,
                h: 600
            },
            char: {
                url: `https://picsum.photos/seed/${seed}-${version}-char/800/600`,
                w: 800,
                h: 600
            },
            fg: {
                url: `https://picsum.photos/seed/${seed}-${version}-fg/800/600`,
                w: 800,
                h: 600
            },
        },
        meta: {
            seed: Math.floor(Math.random() * 1000000),
            steps: 20,
            cfg: 7,
        },
    }
}
