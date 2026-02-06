/**
 * 生产规格常量定义
 * LayerPack Manifest v1 规范的前端实现
 */

// ============ 画幅规格 ============

export type AspectPreset = 'webtoon_standard' | 'webtoon_hd' | 'square' | 'landscape'

export const ASPECT_DIMENSIONS: Record<AspectPreset, { width: number; height: number; aspect: string }> = {
    webtoon_standard: { width: 1080, height: 1920, aspect: '9:16' },
    webtoon_hd: { width: 1440, height: 2560, aspect: '9:16' },
    square: { width: 1024, height: 1024, aspect: '1:1' },
    landscape: { width: 1920, height: 1080, aspect: '16:9' },
}

export const DEFAULT_ASPECT: AspectPreset = 'webtoon_standard'
export const DEFAULT_WIDTH = 1080
export const DEFAULT_HEIGHT = 1920

// ============ MinIO 配置 ============

export const MINIO_BUCKET = 'webtoon-studio'

export function buildMinioKey(
    projectId: string,
    chapterId: string,
    panelId: string,
    attemptId: string,
    filename: string
): string {
    return `${projectId}/${chapterId}/${panelId}/${attemptId}/${filename}`
}

export function buildMinioPrefix(
    projectId: string,
    chapterId?: string,
    panelId?: string,
    attemptId?: string
): string {
    const parts = [projectId]
    if (chapterId) parts.push(chapterId)
    if (panelId) parts.push(panelId)
    if (attemptId) parts.push(attemptId)
    return parts.join('/') + '/'
}

// ============ ID 生成 ============

export function generateProjectId(): string {
    return `proj-${crypto.randomUUID().slice(0, 8)}`
}

export function generateChapterId(order: number): string {
    return `ch-${order.toString().padStart(3, '0')}`
}

export function generatePanelId(order: number): string {
    return `panel-${order.toString().padStart(3, '0')}`
}

export function generateAttemptId(attempt: number): string {
    return `attempt-${attempt.toString().padStart(3, '0')}`
}

export function generateLayerPackId(): string {
    const timestamp = Math.floor(Date.now() / 1000)
    const unique = crypto.randomUUID().slice(0, 6)
    return `lp-${timestamp}-${unique}`
}

// ============ Manifest 类型 ============

export interface Dimensions {
    width: number
    height: number
    aspect: string
}

export interface GenerationParams {
    seed: number
    model: string
    modelVersion?: string
    provider: string
    steps?: number
    cfg?: number
    sampler?: string
    scheduler?: string
}

export interface Prompts {
    positive: string
    negative?: string
}

export interface Outputs {
    full: string
    background?: string
    character?: string
    lineart?: string
    alpha?: string
}

export interface Metadata {
    createdAt: string
    durationMs?: number
    cost?: number
}

export interface ManifestQAResult {
    score: number
    issues: string[]
}

export interface AnchorRef {
    kind: string
    weight: number
}

export interface LayerPackManifest {
    version: string
    id: string
    panelId: string
    projectId: string
    chapterId: string
    attempt: number
    dimensions: Dimensions
    generation: GenerationParams
    prompts: Prompts
    outputs: Outputs
    metadata: Metadata
    identityAssets?: string[]
    sceneAssets?: string[]
    styleProfileId?: string
    anchors?: AnchorRef[]
    qa?: ManifestQAResult
    parentLayerpackId?: string
}

// ============ 文件名常量 ============

export const MANIFEST_FILENAME = 'manifest.json'
export const FULL_LAYER_FILENAME = 'full.png'
export const BACKGROUND_LAYER_FILENAME = 'background.png'
export const CHARACTER_LAYER_FILENAME = 'character.png'
export const LINEART_LAYER_FILENAME = 'lineart.png'
export const ALPHA_LAYER_FILENAME = 'alpha.png'

export const LAYER_FILENAMES: Record<string, string> = {
    full: FULL_LAYER_FILENAME,
    background: BACKGROUND_LAYER_FILENAME,
    character: CHARACTER_LAYER_FILENAME,
    lineart: LINEART_LAYER_FILENAME,
    alpha: ALPHA_LAYER_FILENAME,
}

// ============ 创建 Manifest ============

export function createManifest(params: {
    panelId: string
    projectId: string
    chapterId: string
    seed: number
    model: string
    positivePrompt: string
    negativePrompt?: string
    provider?: string
    attempt?: number
    dimensions?: Dimensions
}): LayerPackManifest {
    const now = new Date().toISOString()
    const lpId = generateLayerPackId()
    const attemptId = generateAttemptId(params.attempt || 1)
    const dims = params.dimensions || ASPECT_DIMENSIONS[DEFAULT_ASPECT]

    return {
        version: '1.0.0',
        id: lpId,
        panelId: params.panelId,
        projectId: params.projectId,
        chapterId: params.chapterId,
        attempt: params.attempt || 1,
        dimensions: dims,
        generation: {
            seed: params.seed,
            model: params.model,
            provider: params.provider || 'comfyui',
        },
        prompts: {
            positive: params.positivePrompt,
            negative: params.negativePrompt || '',
        },
        outputs: {
            full: `${attemptId}/full.png`,
        },
        metadata: {
            createdAt: now,
        },
    }
}
