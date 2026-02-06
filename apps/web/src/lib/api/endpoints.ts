export const ENDPOINTS = {
  PROJECTS: '/api/v1/projects',
  CHAPTERS: '/api/v1/chapters',
  PANELS: '/api/v1/panels',
  RENDER_JOBS: '/api/v1/render',
  EXPORTS: '/api/v1/exports',
} as const

export type Endpoint = typeof ENDPOINTS[keyof typeof ENDPOINTS]
