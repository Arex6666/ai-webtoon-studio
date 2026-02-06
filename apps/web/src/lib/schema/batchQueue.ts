import { z } from 'zod'

// ============ Batch Item Schema ============

export const batchItemStatusSchema = z.enum(['pending', 'running', 'succeeded', 'failed', 'needs_fix', 'skipped'])
export type BatchItemStatus = z.infer<typeof batchItemStatusSchema>

export const batchItemSchema = z.object({
    clipId: z.string(),
    status: batchItemStatusSchema,
    progress: z.number().min(0).max(1),
    attempt: z.number(),
    provider: z.string().optional(),
    error: z.string().optional(),
})

export type BatchItem = z.infer<typeof batchItemSchema>

// ============ Batch Queue Status ============

export const batchQueueStatusSchema = z.enum(['Idle', 'Running', 'Paused', 'Completed', 'Canceled'])
export type BatchQueueStatus = z.infer<typeof batchQueueStatusSchema>

// ============ Batch Controls ============

export const batchControlsSchema = z.object({
    concurrency: z.number().min(1).max(5).default(2),
    stopOnNeedsFix: z.boolean().default(true),
})

export type BatchControls = z.infer<typeof batchControlsSchema>

// ============ Batch Stats ============

export const batchStatsSchema = z.object({
    total: z.number(),
    done: z.number(),
    failed: z.number(),
    needsFix: z.number(),
    running: z.number(),
    pending: z.number(),
})

export type BatchStats = z.infer<typeof batchStatsSchema>

// ============ Batch Queue Schema ============

export const batchQueueSchema = z.object({
    id: z.string(),
    chapterId: z.string(),
    items: z.array(batchItemSchema),
    status: batchQueueStatusSchema,
    controls: batchControlsSchema,
    stats: batchStatsSchema,
    createdAt: z.string(),
    updatedAt: z.string(),
})

export type BatchQueue = z.infer<typeof batchQueueSchema>

// ============ Factory Functions ============

export function createBatchQueue(chapterId: string, clipIds: string[]): BatchQueue {
    const now = new Date().toISOString()
    return {
        id: `batch-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        chapterId,
        items: clipIds.map(clipId => ({
            clipId,
            status: 'pending',
            progress: 0,
            attempt: 0,
        })),
        status: 'Idle',
        controls: { concurrency: 2, stopOnNeedsFix: true },
        stats: {
            total: clipIds.length,
            done: 0,
            failed: 0,
            needsFix: 0,
            running: 0,
            pending: clipIds.length,
        },
        createdAt: now,
        updatedAt: now,
    }
}

export function computeBatchStats(items: BatchItem[]): BatchStats {
    return {
        total: items.length,
        done: items.filter(i => i.status === 'succeeded').length,
        failed: items.filter(i => i.status === 'failed').length,
        needsFix: items.filter(i => i.status === 'needs_fix').length,
        running: items.filter(i => i.status === 'running').length,
        pending: items.filter(i => i.status === 'pending').length,
    }
}
