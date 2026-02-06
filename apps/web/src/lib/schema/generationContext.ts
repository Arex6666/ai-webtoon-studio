import { z } from 'zod'
import { qaConfigSchema, type QAConfig, createDefaultQAConfig } from './qa'
import { retryPolicySchema, type RetryPolicy, createDefaultRetryPolicy } from './retryPolicy'

// ============ Generation Context Schema ============

/**
 * GenerationContext 将所有生成参数绑定到一次生成任务
 * 是对接后端和确保生产线可复现的关键数据结构
 */
export const generationContextSchema = z.object({
    // 目标
    clipId: z.string().optional(),
    panelId: z.string().optional(),

    // 风格
    styleProfileId: z.string().nullable(),

    // 一致性资产
    identityAssetIds: z.array(z.string()),
    sceneAssetIds: z.array(z.string()),

    // 控制图
    anchorIds: z.array(z.string()),

    // 质量控制
    qaConfig: qaConfigSchema,
    retryPolicy: retryPolicySchema,

    // 运行时状态
    currentAttempt: z.number().default(0),
    currentProvider: z.string().optional(),
})

export type GenerationContext = z.infer<typeof generationContextSchema>

// ============ Factory Functions ============

export function createDefaultGenerationContext(
    clipId?: string,
    panelId?: string
): GenerationContext {
    return {
        clipId,
        panelId,
        styleProfileId: null,
        identityAssetIds: [],
        sceneAssetIds: [],
        anchorIds: [],
        qaConfig: createDefaultQAConfig(),
        retryPolicy: createDefaultRetryPolicy(),
        currentAttempt: 0,
    }
}

// ============ Panel/Clip Bindings ============

export const bindingsSchema = z.object({
    identityAssetIds: z.array(z.string()).default([]),
    sceneAssetIds: z.array(z.string()).default([]),
    anchorIds: z.array(z.string()).default([]),
    styleProfileId: z.string().nullable().default(null),
    // Clip 专有
    qaConfig: qaConfigSchema.optional(),
    retryPolicy: retryPolicySchema.optional(),
})

export type Bindings = z.infer<typeof bindingsSchema>

export function createDefaultBindings(): Bindings {
    return {
        identityAssetIds: [],
        sceneAssetIds: [],
        anchorIds: [],
        styleProfileId: null,
    }
}

// ============ Defaults Config ============

export const defaultsConfigSchema = z.object({
    styleProfileId: z.string().nullable().default(null),
    qaConfig: qaConfigSchema,
    retryPolicy: retryPolicySchema,
})

export type DefaultsConfig = z.infer<typeof defaultsConfigSchema>

export function createDefaultsConfig(): DefaultsConfig {
    return {
        styleProfileId: null,
        qaConfig: createDefaultQAConfig(),
        retryPolicy: createDefaultRetryPolicy(),
    }
}
