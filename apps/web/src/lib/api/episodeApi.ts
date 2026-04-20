import { env } from '@/lib/utils/env'

// ─── Types ───

export interface ArtStyle {
    base_style: string
    color_tone: string
    atmosphere: string
}

export interface CharacterData {
    name: string
    description: string
    visual_prompt: string
    image_url?: string | null
    regenerate_image?: boolean
}

export interface SceneData {
    name: string
    description: string
    visual_prompt: string
    image_url?: string | null
    possible_variants?: string[]
    regenerate_image?: boolean
}

export interface PanelData {
    id: string
    scene_name: string
    scene_description: string
    composition: string
    camera_movement: string
    characters: string[]
    voice_character: string
    dialogue: string
    duration_sec: number
    time_of_day?: string    // day/night/dawn/dusk
    weather?: string        // clear/rain/snow/cloudy
    image_url?: string | null
}

export interface Highlight {
    title: string
    description: string
}

export interface EpisodeScriptData {
    episode_number: number
    episode_title: string
    story_summary: string
    highlights: Highlight[]
    art_style: ArtStyle
    characters: CharacterData[]
    scenes: SceneData[]
    panels: PanelData[]
}

export interface PanelResult {
    id: string
    image_url: string | null
    status: 'success' | 'failed'
    error?: string
}

export interface GeneratePanelsResponse {
    panels: PanelResult[]
}

export interface RefineResponse {
    action: string
    updates: {
        characters?: CharacterData[]
        scenes?: SceneData[]
        panels?: PanelData[]
        art_style?: ArtStyle
    } | null
    affected_panels: string[]
    reply: string
}

// ─── API Functions ───

export async function generateEpisodeScript(
    projectId: string,
    episodeNumber: number,
    outlineText: string,
    conversationContext?: { role: string; content: string }[],
): Promise<EpisodeScriptData> {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 180_000)

    const resp = await fetch(`${env.API_BASE_URL}/api/v1/agent/episode/${episodeNumber}/script`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            project_id: projectId,
            episode_number: episodeNumber,
            outline_text: outlineText,
            conversation_context: conversationContext,
        }),
        signal: controller.signal,
    })
    clearTimeout(timeoutId)

    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
        throw new Error(err.detail || `HTTP ${resp.status}`)
    }
    return resp.json()
}

export async function generatePanelImages(
    episodeNumber: number,
    data: {
        project_id: string
        art_style: ArtStyle
        characters: CharacterData[]
        scenes: SceneData[]
        panels: { id: string; scene_name: string; scene_description: string; composition: string; camera_movement: string; characters: string[] }[]
    },
): Promise<GeneratePanelsResponse> {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 300_000) // 5 min for many panels

    const resp = await fetch(`${env.API_BASE_URL}/api/v1/agent/episode/${episodeNumber}/generate-panels`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
        signal: controller.signal,
    })
    clearTimeout(timeoutId)

    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
        throw new Error(err.detail || `HTTP ${resp.status}`)
    }
    return resp.json()
}

export async function refineEpisode(
    episodeNumber: number,
    phase: string,
    message: string,
    currentData: { art_style: ArtStyle; characters: CharacterData[]; scenes: SceneData[]; panels: PanelData[] },
): Promise<RefineResponse> {
    const resp = await fetch(`${env.API_BASE_URL}/api/v1/agent/episode/${episodeNumber}/refine`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            phase,
            message,
            current_data: currentData,
        }),
    })

    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
        throw new Error(err.detail || `HTTP ${resp.status}`)
    }
    return resp.json()
}
