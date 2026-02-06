import { z } from 'zod'

// ============ Style Profile Schema ============

export const styleProfileSchema = z.object({
    id: z.string(),
    name: z.string(),
    baseModelHint: z.string().optional(),
    promptPrefix: z.string().default(''),
    negativePrefix: z.string().default(''),
    colorTone: z.string().optional(),
    lineStyle: z.string().optional(),
    renderStyle: z.enum(['anime', 'realistic', 'comic', 'watercolor', 'ink']).optional(),
    refImages: z.array(z.string()).optional(),
    params: z.object({
        cfg: z.number().optional(),
        steps: z.number().optional(),
        denoise: z.number().optional(),
    }).optional(),
    createdAt: z.string(),
})

export type StyleProfile = z.infer<typeof styleProfileSchema>

// ============ Factory Functions ============

export function createStyleProfile(name: string): StyleProfile {
    return {
        id: `style-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name,
        promptPrefix: '',
        negativePrefix: '',
        createdAt: new Date().toISOString(),
    }
}

// ============ Mock Style Profiles ============

export const MOCK_STYLE_PROFILES: StyleProfile[] = [
    {
        id: 'style-webtoon-dark',
        name: '暗黑条漫风',
        baseModelHint: 'flux',
        promptPrefix: 'webtoon style, vertical layout, dramatic lighting, cinematic',
        negativePrefix: 'low quality, blurry, deformed',
        colorTone: 'desaturated, dark',
        lineStyle: 'bold',
        renderStyle: 'comic',
        createdAt: new Date().toISOString(),
    },
    {
        id: 'style-anime-soft',
        name: '柔和动漫风',
        baseModelHint: 'sd',
        promptPrefix: 'anime style, soft colors, clean lines, high quality',
        negativePrefix: 'realistic, photo, blurry',
        colorTone: 'pastel, warm',
        lineStyle: 'clean',
        renderStyle: 'anime',
        createdAt: new Date().toISOString(),
    },
    {
        id: 'style-ink-wash',
        name: '水墨风格',
        baseModelHint: 'flux',
        promptPrefix: 'chinese ink wash painting style, elegant, artistic',
        negativePrefix: 'colorful, digital art style',
        colorTone: 'monochrome, subtle',
        lineStyle: 'fluid',
        renderStyle: 'ink',
        createdAt: new Date().toISOString(),
    },
]
