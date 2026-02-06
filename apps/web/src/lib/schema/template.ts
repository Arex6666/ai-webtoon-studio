import { z } from 'zod'
import { qaConfigSchema, type QAConfig, createDefaultQAConfig } from './qa'
import { retryPolicySchema, type RetryPolicy, createDefaultRetryPolicy } from './retryPolicy'
import { anchorKindSchema, type AnchorKind } from './anchor'
import { providerSchema, type Provider } from './provider'

// ============ Motion Defaults ============

export const motionDefaultsSchema = z.object({
    fpsDefault: z.number().default(8),
    durationDefault: z.number().default(3),
    providerChainDefault: z.array(providerSchema).default(['mock']),
    promptPreset: z.string().optional(),
})

export type MotionDefaults = z.infer<typeof motionDefaultsSchema>

// ============ Anchor Defaults ============

export const anchorDefaultsSchema = z.object({
    kinds: z.array(anchorKindSchema).default([]),
    weights: z.record(z.string(), z.number()).default({}),
})

export type AnchorDefaults = z.infer<typeof anchorDefaultsSchema>

// ============ Template Schema ============

export const templateSchema = z.object({
    id: z.string(),
    name: z.string(),
    description: z.string().default(''),
    styleProfileId: z.string().nullable(),
    identityAssetIds: z.array(z.string()),
    sceneAssetIds: z.array(z.string()),
    anchorDefaults: anchorDefaultsSchema,
    qaConfig: qaConfigSchema,
    retryPolicy: retryPolicySchema,
    motionDefaults: motionDefaultsSchema,
    createdAt: z.string(),
})

export type Template = z.infer<typeof templateSchema>

// ============ Factory Functions ============

export function createTemplate(name: string, description: string = ''): Template {
    return {
        id: `template-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name,
        description,
        styleProfileId: null,
        identityAssetIds: [],
        sceneAssetIds: [],
        anchorDefaults: { kinds: [], weights: {} },
        qaConfig: createDefaultQAConfig(),
        retryPolicy: createDefaultRetryPolicy(),
        motionDefaults: {
            fpsDefault: 8,
            durationDefault: 3,
            providerChainDefault: ['mock'],
        },
        createdAt: new Date().toISOString(),
    }
}

// ============ Apply Scope ============

export const applyScopeSchema = z.enum(['chapter_defaults', 'all_panels', 'all_clips', 'selected_only'])
export type ApplyScope = z.infer<typeof applyScopeSchema>

// ============ Mock Templates ============

export const MOCK_TEMPLATES: Template[] = [
    {
        id: 'template-rainy-heal',
        name: '雨天治愈风',
        description: '柔和的光照、淡雅配色，适合治愈系日常漫画',
        styleProfileId: 'style-anime-soft',
        identityAssetIds: ['identity-zhouyu', 'identity-linzhixia'],
        sceneAssetIds: ['scene-rain-lighting', 'scene-cafe-interior'],
        anchorDefaults: { kinds: ['depth'], weights: { depth: 0.8 } },
        qaConfig: { threshold: 0.75, maxIssues: 3, rulesEnabled: { identity: true, anatomy: true, text: true, flicker: true } },
        retryPolicy: {
            maxAttempts: 3,
            providerChain: ['kling', 'tongyi', 'mock'],
            budget: { maxCost: 30, costUsed: 0 },
            backoffMs: 500,
            onLowScore: 'retry',
            autoFixStrategy: 'inpaint',
        },
        motionDefaults: { fpsDefault: 8, durationDefault: 4, providerChainDefault: ['kling', 'mock'] },
        createdAt: new Date().toISOString(),
    },
    {
        id: 'template-cyberpunk',
        name: '赛博朋克风',
        description: '霓虹、暗调、高对比度，适合科幻悬疑题材',
        styleProfileId: 'style-webtoon-dark',
        identityAssetIds: [],
        sceneAssetIds: [],
        anchorDefaults: { kinds: ['lineart', 'depth'], weights: { lineart: 1.0, depth: 0.6 } },
        qaConfig: { threshold: 0.7, maxIssues: 4, rulesEnabled: { identity: true, anatomy: true, text: false, flicker: true } },
        retryPolicy: {
            maxAttempts: 4,
            providerChain: ['doubao', 'tongyi', 'comfyui_svd', 'mock'],
            budget: { maxCost: 50, costUsed: 0 },
            backoffMs: 500,
            onLowScore: 'retry',
            autoFixStrategy: 'reroll',
        },
        motionDefaults: { fpsDefault: 12, durationDefault: 3, providerChainDefault: ['doubao', 'mock'] },
        createdAt: new Date().toISOString(),
    },
]
