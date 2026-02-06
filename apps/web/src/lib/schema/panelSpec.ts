import { z } from 'zod'

// Shot configuration
export const shotSchema = z.object({
  shotType: z.enum(['WS', 'MS', 'CU', 'ECU', 'OTS', 'POV', 'Establishing']),
  cameraMove: z.enum(['static', 'pan', 'tilt', 'dolly_in', 'dolly_out', 'truck', 'handheld', 'zoom']),
  durationSec: z.number().min(0.5).max(15),
  description: z.string().optional(),
  lensHint: z.string().optional(),
})

// Scene configuration
export const sceneSchema = z.object({
  location: z.string(),
  timeOfDay: z.enum(['day', 'night', 'dusk', 'dawn', 'indoor']),
  weather: z.enum(['clear', 'rain', 'snow', 'fog', 'overcast']),
  mood: z.string(),
})

// Dialogue line
export const dialogueLineSchema = z.object({
  speaker: z.string(),
  text: z.string(),
  type: z.enum(['speech', 'narration', 'thought']),
})

// Dialogue configuration
export const dialogueSchema = z.object({
  lines: z.array(dialogueLineSchema),
})

// Style configuration
export const styleSchema = z.object({
  styleProfileId: z.string().nullable(),
  negativePrompt: z.string().optional(),
})

// Render status
export const renderSchema = z.object({
  status: z.enum(['Draft', 'Queued', 'Running', 'Rendered', 'NeedsFix']),
  lastRenderAt: z.string().nullable(),
  warnings: z.array(z.string()),
})

// Metadata
export const metaSchema = z.object({
  createdAt: z.string(),
  updatedAt: z.string(),
})

// Complete PanelSpec schema
export const panelSpecSchema = z.object({
  id: z.string(),
  index: z.number(),
  shot: shotSchema,
  scene: sceneSchema,
  characters: z.array(z.string()),
  dialogue: dialogueSchema,
  style: styleSchema,
  render: renderSchema,
  meta: metaSchema,
})

export type PanelSpec = z.infer<typeof panelSpecSchema>

// Factory function to create default PanelSpec
export function createDefaultPanelSpec(panelId: string, index: number): PanelSpec {
  const now = new Date().toISOString()

  return {
    id: panelId,
    index,
    shot: {
      shotType: 'MS',
      cameraMove: 'static',
      durationSec: 3.0,
      description: '',
      lensHint: '',
    },
    scene: {
      location: 'Unknown Location',
      timeOfDay: 'day',
      weather: 'clear',
      mood: 'neutral',
    },
    characters: [],
    dialogue: {
      lines: [],
    },
    style: {
      styleProfileId: 'default',
      negativePrompt: '',
    },
    render: {
      status: 'Draft',
      lastRenderAt: null,
      warnings: [],
    },
    meta: {
      createdAt: now,
      updatedAt: now,
    },
  }
}
