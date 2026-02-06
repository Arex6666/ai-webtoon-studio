import { z } from 'zod'
import { providerSchema, type Provider } from './provider'

// ============ On Low Score Action ============

export const onLowScoreActionSchema = z.enum(['retry', 'needs_fix'])
export type OnLowScoreAction = z.infer<typeof onLowScoreActionSchema>

// ============ Auto Fix Strategy ============

export const autoFixStrategySchema = z.enum(['inpaint', 'redraw_char', 'redraw_bg', 'reroll'])
export type AutoFixStrategy = z.infer<typeof autoFixStrategySchema>

// ============ Budget ============

export const budgetSchema = z.object({
    maxCost: z.number().min(0).default(50),
    costUsed: z.number().min(0).default(0),
})

export type Budget = z.infer<typeof budgetSchema>

// ============ Retry Policy ============

export const retryPolicySchema = z.object({
    maxAttempts: z.number().min(1).max(10).default(3),
    providerChain: z.array(providerSchema).default(['kling', 'tongyi', 'doubao', 'comfyui_svd', 'mock']),
    budget: budgetSchema,
    backoffMs: z.number().min(0).default(500),
    onLowScore: onLowScoreActionSchema.default('retry'),
    autoFixStrategy: autoFixStrategySchema.default('inpaint'),
})

export type RetryPolicy = z.infer<typeof retryPolicySchema>

// ============ Factory Functions ============

export function createDefaultRetryPolicy(): RetryPolicy {
    return {
        maxAttempts: 3,
        providerChain: ['kling', 'tongyi', 'doubao', 'comfyui_svd', 'mock'],
        budget: { maxCost: 50, costUsed: 0 },
        backoffMs: 500,
        onLowScore: 'retry',
        autoFixStrategy: 'inpaint',
    }
}

// ============ Provider Cost ============

export const PROVIDER_COST: Record<Provider, number> = {
    kling: 5,
    tongyi: 4,
    doubao: 3,
    comfyui_svd: 2,
    mock: 1,
}

export function getNextProvider(
    currentProvider: Provider,
    providerChain: Provider[]
): Provider | null {
    const currentIndex = providerChain.indexOf(currentProvider)
    if (currentIndex === -1 || currentIndex >= providerChain.length - 1) {
        return null
    }
    return providerChain[currentIndex + 1]
}

export function canRetry(
    attempts: number,
    maxAttempts: number,
    costUsed: number,
    maxCost: number
): boolean {
    return attempts < maxAttempts && costUsed < maxCost
}
