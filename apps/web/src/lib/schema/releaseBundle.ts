import { z } from 'zod'
import { analyticsSchema, type Analytics } from './analytics'

// ============ QA History Entry ============

export const qaHistoryEntrySchema = z.object({
    attempt: z.number(),
    provider: z.string(),
    score: z.number(),
    issues: z.array(z.string()),
    cost: z.number(),
    timestamp: z.string(),
})

export type QAHistoryEntry = z.infer<typeof qaHistoryEntrySchema>

// ============ QA Report ============

export const qaReportSchema = z.record(z.string(), z.array(qaHistoryEntrySchema)) // clipId -> history

export type QAReport = z.infer<typeof qaReportSchema>

// ============ LayerPacks Index ============

export const layerPacksIndexSchema = z.record(
    z.string(), // panelId
    z.record(z.string(), z.string()) // layerPackId -> manifestUrl
)

export type LayerPacksIndex = z.infer<typeof layerPacksIndexSchema>

// ============ Template Fingerprint ============

export const templateFingerprintSchema = z.object({
    templateId: z.string().nullable(),
    styleProfileId: z.string().nullable(),
    identityAssetIds: z.array(z.string()),
    sceneAssetIds: z.array(z.string()),
})

export type TemplateFingerprint = z.infer<typeof templateFingerprintSchema>

// ============ Release Bundle Schema ============

export const releaseBundleSchema = z.object({
    projectId: z.string(),
    chapterId: z.string(),
    releaseVersion: z.string(),
    exportSpec: z.any(), // Reference to ExportSpec
    layerPacksIndex: layerPacksIndexSchema,
    qaReport: qaReportSchema,
    analytics: analyticsSchema,
    templateFingerprint: templateFingerprintSchema,
    generatedAt: z.string(),
    notes: z.string().optional(),
})

export type ReleaseBundle = z.infer<typeof releaseBundleSchema>

// ============ Factory Functions ============

export function createReleaseBundle(
    projectId: string,
    chapterId: string,
    releaseVersion: string,
    exportSpec: any,
    analytics: Analytics
): ReleaseBundle {
    return {
        projectId,
        chapterId,
        releaseVersion,
        exportSpec,
        layerPacksIndex: {},
        qaReport: {},
        analytics,
        templateFingerprint: {
            templateId: null,
            styleProfileId: null,
            identityAssetIds: [],
            sceneAssetIds: [],
        },
        generatedAt: new Date().toISOString(),
    }
}
