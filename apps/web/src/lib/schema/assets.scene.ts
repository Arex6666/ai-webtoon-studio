import { z } from 'zod'

// ============ Scene Asset Type ============

export const sceneAssetTypeSchema = z.enum(['bg_pack', 'scene_lora', 'style_lora', 'palette', 'lighting_preset'])
export type SceneAssetType = z.infer<typeof sceneAssetTypeSchema>

// ============ Scene Asset File ============

export const sceneAssetFileSchema = z.object({
    kind: z.enum(['image', 'safetensors', 'json', 'preset']),
    url: z.string(),
})

export type SceneAssetFile = z.infer<typeof sceneAssetFileSchema>

// ============ Scene Asset Schema ============

export const sceneAssetSchema = z.object({
    id: z.string(),
    type: sceneAssetTypeSchema,
    name: z.string(),
    files: z.array(sceneAssetFileSchema),
    params: z.object({
        strength: z.number().min(0).max(2).optional(),
        promptAddon: z.string().optional(),
    }).optional(),
    createdAt: z.string(),
})

export type SceneAsset = z.infer<typeof sceneAssetSchema>

// ============ Factory Functions ============

export function createSceneAsset(
    name: string,
    type: SceneAssetType
): SceneAsset {
    return {
        id: `scene-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        type,
        name,
        files: [],
        params: { strength: 1 },
        createdAt: new Date().toISOString(),
    }
}

// ============ Mock Scene Assets ============

export const MOCK_SCENE_ASSETS: SceneAsset[] = [
    {
        id: 'scene-bookstore',
        type: 'bg_pack',
        name: '旧书店门口',
        files: [
            { kind: 'image', url: 'https://picsum.photos/seed/bookstore/1024/1820' },
        ],
        params: { promptAddon: 'old bookstore entrance, vintage style, warm lighting' },
        createdAt: new Date().toISOString(),
    },
    {
        id: 'scene-rain-lighting',
        type: 'lighting_preset',
        name: '雨天光照',
        files: [
            { kind: 'preset', url: '/assets/lighting/rainy.json' },
        ],
        params: { promptAddon: 'rainy day, overcast sky, soft diffused lighting' },
        createdAt: new Date().toISOString(),
    },
    {
        id: 'scene-cafe-interior',
        type: 'bg_pack',
        name: '咖啡馆内部',
        files: [
            { kind: 'image', url: 'https://picsum.photos/seed/cafe/1024/1820' },
        ],
        params: { promptAddon: 'cozy cafe interior, modern minimalist' },
        createdAt: new Date().toISOString(),
    },
]
