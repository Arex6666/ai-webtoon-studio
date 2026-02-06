import { z } from 'zod'

// Provider 统一枚举
export const providerSchema = z.enum([
  'mock',
  'comfyui_svd',
  'kling',
  'tongyi',
  'doubao',
])

export type Provider = z.infer<typeof providerSchema>

// Provider 显示名称
export const providerLabels: Record<Provider, string> = {
  mock: 'Mock',
  comfyui_svd: 'ComfyUI SVD',
  kling: 'Kling',
  tongyi: '通义',
  doubao: '豆包',
}

// Provider 默认配置
export const providerDefaults: Record<Provider, { fps: number; maxDuration: number }> = {
  mock: { fps: 8, maxDuration: 10 },
  comfyui_svd: { fps: 6, maxDuration: 4 },
  kling: { fps: 24, maxDuration: 10 },
  tongyi: { fps: 24, maxDuration: 6 },
  doubao: { fps: 24, maxDuration: 5 },
}
