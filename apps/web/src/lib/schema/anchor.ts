import { z } from 'zod'

// ============ Anchor Kind ============

export const anchorKindSchema = z.enum(['depth', 'pose', 'seg', 'lineart', 'canny', 'scribble'])
export type AnchorKind = z.infer<typeof anchorKindSchema>

// ============ Anchor Source ============

export const anchorSourceSchema = z.object({
    type: z.literal('image'),
    url: z.string(),
})

export type AnchorSource = z.infer<typeof anchorSourceSchema>

// ============ Control Image ============

export const controlImageSchema = z.object({
    url: z.string(),
    w: z.number(),
    h: z.number(),
}).nullable()

export type ControlImage = z.infer<typeof controlImageSchema>

// ============ AnchorSpec Schema ============

export const anchorSpecSchema = z.object({
    id: z.string(),
    panelId: z.string(),
    kind: anchorKindSchema,
    source: anchorSourceSchema,
    controlImage: controlImageSchema,
    weight: z.number().min(0).max(2).default(1),
    notes: z.string().optional(),
})

export type AnchorSpec = z.infer<typeof anchorSpecSchema>

// ============ Factory Functions ============

export function createAnchorSpec(
    panelId: string,
    kind: AnchorKind,
    sourceUrl: string
): AnchorSpec {
    return {
        id: `anchor-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        panelId,
        kind,
        source: { type: 'image', url: sourceUrl },
        controlImage: null,
        weight: 1,
    }
}

export function createMockControlImage(panelId: string, kind: AnchorKind): ControlImage {
    return {
        url: `https://picsum.photos/seed/${panelId}-${kind}/512/896`,
        w: 512,
        h: 896,
    }
}

// ============ Anchor Kind Labels ============

export const ANCHOR_KIND_LABELS: Record<AnchorKind, { label: string; description: string }> = {
    depth: { label: '深度图', description: '深度估计控制' },
    pose: { label: '姿态图', description: '人物骨骼姿态控制' },
    seg: { label: '分割图', description: '语义分割控制' },
    lineart: { label: '线稿', description: '线条轮廓控制' },
    canny: { label: 'Canny边缘', description: '边缘检测控制' },
    scribble: { label: '涂鸦', description: '手绘草图控制' },
}
