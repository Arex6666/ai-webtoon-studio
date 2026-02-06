import { z } from 'zod'

// ============ Enum Definitions ============

export const PropCategory = {
    HAND_PROP: 'hand_prop',
    SET_DRESSING: 'set_dressing',
} as const

export type PropCategoryType = typeof PropCategory[keyof typeof PropCategory]

// ============ Prop Asset Schema ============

export const propAssetSchema = z.object({
    id: z.string(),
    project_id: z.string(),
    canonical_name: z.string().min(1, "Name is required"),
    category: z.enum([PropCategory.HAND_PROP, PropCategory.SET_DRESSING]),

    // Visual Description
    visual_brief: z.string().optional(),
    material: z.string().optional(),
    colors: z.array(z.string()).default([]),
    shape: z.string().optional(),
    key_features: z.array(z.string()).default([]),

    // Generation
    default_prompt_tokens: z.array(z.string()).default([]),

    // References
    ref_image_paths: z.array(z.string()).default([]),
    ref_image_status: z.enum(['none', 'generating', 'ready', 'failed']).default('none'),

    // Embedding
    embedding_path: z.string().optional(),

    // Aliases
    aliases: z.array(z.string()).default([]),

    status: z.string().default('pending'),
    created_at: z.string(),
    updated_at: z.string().optional(),
})

export type PropAsset = z.infer<typeof propAssetSchema>

export const createPropAssetSchema = propAssetSchema.pick({
    project_id: true,
    canonical_name: true,
    category: true,
    visual_brief: true,
    material: true,
    colors: true,
    shape: true,
    key_features: true,
    aliases: true,
})

export type CreatePropAssetRequest = z.infer<typeof createPropAssetSchema>

export const updatePropAssetSchema = propAssetSchema.partial().omit({
    id: true,
    project_id: true,
    created_at: true,
    updated_at: true
})

export type UpdatePropAssetRequest = z.infer<typeof updatePropAssetSchema>

// ============ Outfit Variant Schema ============

export const outfitVariantSchema = z.object({
    id: z.string(),
    character_asset_id: z.string(),

    outfit_name: z.string().min(1, "Outfit name is required"),
    outfit_description: z.string(),
    garment_items: z.array(z.string()).default([]),
    colors: z.array(z.string()).default([]),
    materials: z.array(z.string()).default([]),

    outfit_prompt: z.string(),

    ref_image_path: z.string().optional(),
    ref_image_status: z.enum(['none', 'generating', 'ready', 'failed']).default('none'),

    is_default: z.boolean().default(false),
    status: z.string().default('pending'),

    created_at: z.string(),
    updated_at: z.string().optional(),
})

export type OutfitVariant = z.infer<typeof outfitVariantSchema>

export const createOutfitVariantSchema = outfitVariantSchema.pick({
    character_asset_id: true,
    outfit_name: true,
    outfit_description: true,
    garment_items: true,
    colors: true,
    materials: true,
    outfit_prompt: true,
    is_default: true,
})

export type CreateOutfitVariantRequest = z.infer<typeof createOutfitVariantSchema>

export const updateOutfitVariantSchema = outfitVariantSchema.partial().omit({
    id: true,
    character_asset_id: true,
    created_at: true,
    updated_at: true,
})

export type UpdateOutfitVariantRequest = z.infer<typeof updateOutfitVariantSchema>
