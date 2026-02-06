import { z } from 'zod'

// ============ Provider Stats ============

export const providerStatsSchema = z.object({
    provider: z.string(),
    costUsed: z.number(),
    avgScore: z.number(),
    successRate: z.number(),
    retryRate: z.number(),
    jobCount: z.number(),
})

export type ProviderStats = z.infer<typeof providerStatsSchema>

// ============ Character Stats ============

export const characterStatsSchema = z.object({
    assetId: z.string(),
    assetName: z.string(),
    costUsed: z.number(),
    avgScore: z.number(),
    successRate: z.number(),
    retryRate: z.number(),
    usageCount: z.number(),
})

export type CharacterStats = z.infer<typeof characterStatsSchema>

// ============ Chapter Summary ============

export const chapterSummarySchema = z.object({
    totalCost: z.number(),
    avgScore: z.number(),
    totalClips: z.number(),
    succeeded: z.number(),
    needsFix: z.number(),
    failed: z.number(),
    totalRetries: z.number(),
})

export type ChapterSummary = z.infer<typeof chapterSummarySchema>

// ============ Analytics Schema ============

export const analyticsSchema = z.object({
    chapterId: z.string(),
    byProvider: z.array(providerStatsSchema),
    byCharacter: z.array(characterStatsSchema),
    chapterSummary: chapterSummarySchema,
    computedAt: z.string(),
})

export type Analytics = z.infer<typeof analyticsSchema>

// ============ Factory Functions ============

export function createEmptyAnalytics(chapterId: string): Analytics {
    return {
        chapterId,
        byProvider: [],
        byCharacter: [],
        chapterSummary: {
            totalCost: 0,
            avgScore: 0,
            totalClips: 0,
            succeeded: 0,
            needsFix: 0,
            failed: 0,
            totalRetries: 0,
        },
        computedAt: new Date().toISOString(),
    }
}

// ============ Mock Analytics ============

export function createMockAnalytics(chapterId: string): Analytics {
    return {
        chapterId,
        byProvider: [
            { provider: 'kling', costUsed: 25, avgScore: 0.82, successRate: 0.85, retryRate: 0.15, jobCount: 10 },
            { provider: 'tongyi', costUsed: 16, avgScore: 0.78, successRate: 0.75, retryRate: 0.25, jobCount: 5 },
            { provider: 'mock', costUsed: 3, avgScore: 0.70, successRate: 0.90, retryRate: 0.10, jobCount: 3 },
        ],
        byCharacter: [
            { assetId: 'identity-zhouyu', assetName: '周屿', costUsed: 20, avgScore: 0.85, successRate: 0.90, retryRate: 0.10, usageCount: 8 },
            { assetId: 'identity-linzhixia', assetName: '林知夏', costUsed: 15, avgScore: 0.80, successRate: 0.80, retryRate: 0.20, usageCount: 6 },
        ],
        chapterSummary: {
            totalCost: 44,
            avgScore: 0.79,
            totalClips: 18,
            succeeded: 14,
            needsFix: 2,
            failed: 2,
            totalRetries: 5,
        },
        computedAt: new Date().toISOString(),
    }
}
