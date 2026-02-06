/**
 * 气泡排版 Schema
 */
import { z } from 'zod';

// 气泡样式类型
export const BubbleStyleSchema = z.enum([
    'speech',      // 普通对话
    'thought',     // 思考泡泡
    'shout',       // 喊叫
    'whisper',     // 低语
    'narration',   // 旁白
    'sfx',         // 音效
    'caption',     // 说明文字
]);
export type BubbleStyle = z.infer<typeof BubbleStyleSchema>;

// 气泡尾巴方向
export const TailDirectionSchema = z.enum([
    'none',
    'top-left', 'top', 'top-right',
    'left', 'right',
    'bottom-left', 'bottom', 'bottom-right',
]);
export type TailDirection = z.infer<typeof TailDirectionSchema>;

// 文字对齐
export const TextAlignSchema = z.enum(['left', 'center', 'right']);
export type TextAlign = z.infer<typeof TextAlignSchema>;

// 单个气泡
export const BubbleSchema = z.object({
    id: z.string(),
    text: z.string(),
    style: BubbleStyleSchema.default('speech'),

    // 位置 (相对于面板，百分比)
    x: z.number().min(0).max(100).default(50),
    y: z.number().min(0).max(100).default(50),

    // 尺寸
    width: z.number().min(50).max(500).default(200),
    height: z.number().min(30).max(300).default(80),

    // 样式
    fontSize: z.number().min(12).max(72).default(24),
    fontFamily: z.string().default('Noto Sans SC'),
    fontWeight: z.enum(['normal', 'bold']).default('normal'),
    textAlign: TextAlignSchema.default('center'),
    textColor: z.string().default('#000000'),

    // 气泡外观
    backgroundColor: z.string().default('#ffffff'),
    borderColor: z.string().default('#000000'),
    borderWidth: z.number().min(0).max(10).default(2),
    borderRadius: z.number().min(0).max(50).default(20),

    // 尾巴
    tailDirection: TailDirectionSchema.default('bottom'),
    tailSize: z.number().min(0).max(50).default(15),

    // 特效
    shadow: z.boolean().default(false),
    glow: z.boolean().default(false),
    rotation: z.number().min(-45).max(45).default(0),

    // 层级
    zIndex: z.number().default(1),
});
export type Bubble = z.infer<typeof BubbleSchema>;

// 面板排版数据
export const PanelTypesetSchema = z.object({
    panelId: z.string(),
    bubbles: z.array(BubbleSchema),
    lastModified: z.string().optional(),
});
export type PanelTypeset = z.infer<typeof PanelTypesetSchema>;

// 预设样式
export const BUBBLE_PRESETS: Record<BubbleStyle, Partial<Bubble>> = {
    speech: {
        backgroundColor: '#ffffff',
        borderColor: '#000000',
        borderWidth: 2,
        borderRadius: 20,
        tailDirection: 'bottom',
    },
    thought: {
        backgroundColor: '#ffffff',
        borderColor: '#888888',
        borderWidth: 1,
        borderRadius: 50,
        tailDirection: 'bottom',
    },
    shout: {
        backgroundColor: '#ffff00',
        borderColor: '#ff0000',
        borderWidth: 3,
        borderRadius: 5,
        fontSize: 32,
        fontWeight: 'bold',
    },
    whisper: {
        backgroundColor: '#f0f0f0',
        borderColor: '#cccccc',
        borderWidth: 1,
        borderRadius: 15,
        fontSize: 18,
    },
    narration: {
        backgroundColor: '#fffde7',
        borderColor: '#8d6e63',
        borderWidth: 1,
        borderRadius: 4,
        tailDirection: 'none',
    },
    sfx: {
        backgroundColor: 'transparent',
        borderColor: 'transparent',
        borderWidth: 0,
        fontSize: 48,
        fontWeight: 'bold',
        textColor: '#ff0000',
    },
    caption: {
        backgroundColor: 'rgba(0,0,0,0.7)',
        borderColor: 'transparent',
        borderWidth: 0,
        borderRadius: 4,
        textColor: '#ffffff',
        tailDirection: 'none',
    },
};

// 气泡样式名称
export const BUBBLE_STYLE_NAMES: Record<BubbleStyle, string> = {
    speech: '对话',
    thought: '思考',
    shout: '喊叫',
    whisper: '低语',
    narration: '旁白',
    sfx: '音效',
    caption: '说明',
};
