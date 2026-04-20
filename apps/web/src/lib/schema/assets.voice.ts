import { z } from 'zod'

// ============ Voice Agent Types ============

export const voiceAgentSchema = z.object({
    id: z.string(),
    projectId: z.string(),
    characterAssetId: z.string(),
    name: z.string(),
    voiceId: z.string(),
    provider: z.string(),
    voiceConfig: z.object({
        speed: z.number().optional(),
        pitch: z.number().optional(),
        volume: z.number().optional(),
    }),
    sampleAudioUrl: z.string().optional(),
    isDefault: z.boolean(),
    status: z.string(),
    createdAt: z.string(),
    updatedAt: z.string(),
})

export type VoiceAgent = z.infer<typeof voiceAgentSchema>

// ============ Music Asset Types ============

export const musicAssetSchema = z.object({
    id: z.string(),
    projectId: z.string(),
    name: z.string(),
    genre: z.string().optional(),
    mood: z.string().optional(),
    durationSec: z.number().optional(),
    audioUrl: z.string().optional(),
    provider: z.string(),
    generationPrompt: z.string().optional(),
    status: z.string(),
    thumbnailUrl: z.string().optional(),
    createdAt: z.string(),
    updatedAt: z.string(),
})

export type MusicAsset = z.infer<typeof musicAssetSchema>

// ============ Available Voice ============

export const availableVoiceSchema = z.object({
    voiceId: z.string(),
    name: z.string(),
    gender: z.string(),
    ageGroup: z.string(),
    description: z.string(),
})

export type AvailableVoice = z.infer<typeof availableVoiceSchema>

// ============ Music Generation Request ============

export const musicGenerateRequestSchema = z.object({
    projectId: z.string(),
    name: z.string(),
    prompt: z.string(),
    style: z.string().optional(),
    duration: z.number().optional(),
    genre: z.string().optional(),
    mood: z.string().optional(),
})

export type MusicGenerateRequest = z.infer<typeof musicGenerateRequestSchema>

// ============ Music Genres ============

export const MUSIC_GENRES = [
    { value: 'cinematic', label: '电影配乐' },
    { value: 'pop', label: '流行' },
    { value: 'rock', label: '摇滚' },
    { value: 'jazz', label: '爵士' },
    { value: 'electronic', label: '电子' },
    { value: 'classical', label: '古典' },
    { value: 'ambient', label: '氛围' },
    { value: 'folk', label: '民谣' },
] as const

export const MUSIC_MOODS = [
    { value: 'happy', label: '欢快' },
    { value: 'sad', label: '悲伤' },
    { value: 'tense', label: '紧张' },
    { value: 'relaxed', label: '放松' },
    { value: 'epic', label: '史诗' },
    { value: 'romantic', label: '浪漫' },
    { value: 'mysterious', label: '神秘' },
    { value: 'action', label: '动作' },
] as const
