import { z } from 'zod'
import { panelSpecSchema } from './panelSpec'

export const chapterSpecSchema = z.object({
  projectId: z.string(),
  chapterId: z.string(),
  version: z.string(),
  panels: z.array(panelSpecSchema),
})

export type ChapterSpec = z.infer<typeof chapterSpecSchema>
