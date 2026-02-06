import { z } from 'zod'
import { providerSchema, type Provider } from './provider'

// ============ Identity Asset Type ============

export const identityAssetTypeSchema = z.enum(['lora', 'embedding', 'faceid', 'refnet'])
export type IdentityAssetType = z.infer<typeof identityAssetTypeSchema>

// ============ Asset File ============

export const assetFileSchema = z.object({
    kind: z.enum(['safetensors', 'embedding', 'image_ref', 'json']),
    url: z.string(),
})

export type AssetFile = z.infer<typeof assetFileSchema>

// ============ Identity Asset Schema ============

export const identityAssetSchema = z.object({
    id: z.string(),
    type: identityAssetTypeSchema,
    name: z.string(),
    tags: z.array(z.string()),
    providerHint: providerSchema.optional(),
    files: z.array(assetFileSchema),
    params: z.object({
        strength: z.number().min(0).max(2).optional(),
        triggerWords: z.array(z.string()).optional(),
    }),
    createdAt: z.string(),
})

export type IdentityAsset = z.infer<typeof identityAssetSchema>

// ============ Factory Functions ============

export function createIdentityAsset(
    name: string,
    type: IdentityAssetType,
    tags: string[] = []
): IdentityAsset {
    return {
        id: `identity-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        type,
        name,
        tags,
        files: [],
        params: { strength: 1 },
        createdAt: new Date().toISOString(),
    }
}

// ============ Mock Identity Assets ============

export const MOCK_IDENTITY_ASSETS: IdentityAsset[] = [
    {
        id: 'identity-zhouyu',
        type: 'lora',
        name: '周屿',
        tags: ['主角', '男性', '青年', '短发'],
        files: [{ kind: 'safetensors', url: '/assets/lora/zhouyu.safetensors' }],
        params: { strength: 0.8, triggerWords: ['zhouyu_character'] },
        createdAt: new Date().toISOString(),
    },
    {
        id: 'identity-linzhixia',
        type: 'embedding',
        name: '林知夏',
        tags: ['女主', '女性', '青年', '长发'],
        files: [{ kind: 'embedding', url: '/assets/embedding/linzhixia.pt' }],
        params: { strength: 0.75, triggerWords: ['linzhixia_character'] },
        createdAt: new Date().toISOString(),
    },
    {
        id: 'identity-shopowner',
        type: 'faceid',
        name: '书店老板',
        tags: ['配角', '中年', '男性'],
        files: [{ kind: 'image_ref', url: 'https://picsum.photos/seed/shopowner/256/256' }],
        params: { strength: 0.6 },
        createdAt: new Date().toISOString(),
    },
]
