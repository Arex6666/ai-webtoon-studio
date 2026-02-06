'use client'

import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'

interface Template {
    id: string
    label: string
    prompt: string
    icon: string
}

const templates: Template[] = [
    { id: 'romance', label: '都市恋爱', prompt: '一个发生在现代都市的浪漫爱情故事，男女主角因为一次偶然相遇...', icon: '💕' },
    { id: 'mystery', label: '悬疑推理', prompt: '一个扑朔迷离的悬疑故事，主角需要解开层层迷雾...', icon: '🔍' },
    { id: 'power', label: '爽文逆袭', prompt: '主角从底层起步，通过不断努力获得成功的励志故事...', icon: '🔥' },
    { id: 'fantasy', label: '古风仙侠', prompt: '发生在古代仙侠世界的奇幻冒险故事，主角踏上修仙之路...', icon: '⚔️' },
    { id: 'scifi', label: '科幻未来', prompt: '设定在未来世界的科幻故事，人类面临前所未有的挑战...', icon: '🚀' },
    { id: 'comedy', label: '轻松搞笑', prompt: '一个充满欢乐和幽默的轻喜剧故事...', icon: '😄' },
]

interface TemplateChipsProps {
    selectedId: string | null
    onSelect: (template: Template) => void
}

export function TemplateChips({ selectedId, onSelect }: TemplateChipsProps) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="flex flex-wrap justify-center gap-2"
        >
            {templates.map((template, idx) => (
                <motion.button
                    key={template.id}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.1 + idx * 0.03 }}
                    whileHover={{ scale: 1.05, y: -2 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => onSelect(template)}
                    className={cn(
                        "flex items-center gap-2 px-4 py-2 rounded-full font-heading text-sm font-medium transition-all duration-200 cursor-pointer border",
                        selectedId === template.id
                            ? "bg-[#10B981]/20 border-[#10B981] text-[#10B981]"
                            : "bg-[#18181B] border-[#27272A] text-[#A1A1AA] hover:text-[#FAFAFA] hover:border-[#3F3F46]"
                    )}
                >
                    <span>{template.icon}</span>
                    <span>{template.label}</span>
                </motion.button>
            ))}
        </motion.div>
    )
}

export { templates, type Template }
