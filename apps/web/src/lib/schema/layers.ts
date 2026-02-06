/**
 * 图层分离 Schema
 */
import { z } from 'zod';

// 图层类型
export const LayerTypeSchema = z.enum([
    'full',      // 完整图
    'char',      // 角色层
    'bg',        // 背景层
    'mask',      // 遮罩层
    'depth',     // 深度图
    'pose',      // 姿态图
    'lineart',   // 线稿
    'fg',        // 前景层
]);
export type LayerType = z.infer<typeof LayerTypeSchema>;

// 单个图层
export const LayerSchema = z.object({
    type: LayerTypeSchema,
    url: z.string().nullable(),
    visible: z.boolean().default(true),
    opacity: z.number().min(0).max(1).default(1),
    blendMode: z.enum(['normal', 'multiply', 'screen', 'overlay']).default('normal'),
});
export type Layer = z.infer<typeof LayerSchema>;

// 图层包
export const LayerStackSchema = z.object({
    panelId: z.string(),
    layerpackId: z.string().nullable(),
    layers: z.array(LayerSchema),
    width: z.number().default(1080),
    height: z.number().default(1920),
});
export type LayerStack = z.infer<typeof LayerStackSchema>;

// 图层分离请求
export const LayerSeparationRequestSchema = z.object({
    panelId: z.string(),
    sourceImageUrl: z.string(),
    pointCoords: z.array(z.tuple([z.number(), z.number()])).optional(),
});
export type LayerSeparationRequest = z.infer<typeof LayerSeparationRequestSchema>;

// 图层分离结果
export const LayerSeparationResultSchema = z.object({
    jobId: z.string(),
    status: z.enum(['queued', 'running', 'succeeded', 'failed']),
    progress: z.number().default(0),
    outputs: z.object({
        maskUrl: z.string().nullable(),
        charUrl: z.string().nullable(),
        bgUrl: z.string().nullable(),
    }).nullable(),
});
export type LayerSeparationResult = z.infer<typeof LayerSeparationResultSchema>;

// 图层名称映射
export const LAYER_NAMES: Record<LayerType, string> = {
    full: '完整图',
    char: '角色层',
    bg: '背景层',
    mask: '遮罩',
    depth: '深度图',
    pose: '姿态图',
    lineart: '线稿',
    fg: '前景层',
};

// 图层颜色标识
export const LAYER_COLORS: Record<LayerType, string> = {
    full: '#6366f1',
    char: '#f43f5e',
    bg: '#22c55e',
    mask: '#f59e0b',
    depth: '#3b82f6',
    pose: '#8b5cf6',
    lineart: '#64748b',
    fg: '#ec4899',
};
