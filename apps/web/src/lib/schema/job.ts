import { z } from 'zod'

// ============ Enums ============

export const RenderProvider = z.enum([
    'mock',
    'comfyui',
    'keling',
    'tongyi',
    'doubao',
])
export type RenderProvider = z.infer<typeof RenderProvider>

export const RenderJobStatus = z.enum([
    'Queued',
    'Running',
    'Succeeded',
    'Failed',
])
export type RenderJobStatus = z.infer<typeof RenderJobStatus>

// ============ RenderJob Schema ============

export const RenderJobSchema = z.object({
    id: z.string(),
    type: z.enum(['render', 'export', 'bundle']).default('render'),
    panelId: z.string().optional(), // Export jobs may not have panelId
    chapterId: z.string(),
    projectId: z.string(),
    provider: RenderProvider,
    status: RenderJobStatus,
    progress: z.number().min(0).max(1).default(0),
    createdAt: z.string(),
    updatedAt: z.string(),
    error: z.string().optional(),
    message: z.string().optional(), // For progress messages
    output: z.object({
        bundle_url: z.string().optional(),
        manifest_url: z.string().optional(),
    }).optional(),
    qa: z
        .object({
            score: z.number().min(0).max(1),
            issues: z.array(z.string()),
        })
        .optional(),
})

export type RenderJob = z.infer<typeof RenderJobSchema>

// ============ LayerPack Schema ============

export const LayerPackSchema = z.object({
    id: z.string(),
    panelId: z.string(),
    jobId: z.string(),
    createdAt: z.string(),
    layers: z.object({
        full: z.string(), // URL
        background: z.string().optional(),
        character: z.string().optional(),
        foreground: z.string().optional(),
        effects: z.string().optional(),
    }),
})

export type LayerPack = z.infer<typeof LayerPackSchema>

// ============ Factory Functions ============

export function createRenderJob(
    panelId: string,
    chapterId: string,
    projectId: string,
    provider: RenderProvider = 'mock'
): RenderJob {
    const now = new Date().toISOString()
    return {
        id: `job-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        type: 'render',
        panelId,
        chapterId,
        projectId,
        provider,
        status: 'Queued',
        progress: 0,
        createdAt: now,
        updatedAt: now,
    }
}

export function createMockLayerPack(panelId: string, jobId: string): LayerPack {
    // 使用 picsum.photos 生成占位图
    const seed = panelId.replace(/[^a-z0-9]/gi, '')
    return {
        id: `lp-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        panelId,
        jobId,
        createdAt: new Date().toISOString(),
        layers: {
            full: `https://picsum.photos/seed/${seed}-full/800/600`,
            background: `https://picsum.photos/seed/${seed}-bg/800/600`,
            character: `https://picsum.photos/seed/${seed}-char/800/600`,
            foreground: `https://picsum.photos/seed/${seed}-fg/800/600`,
        },
    }
}
