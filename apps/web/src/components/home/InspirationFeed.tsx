'use client'

import { motion } from 'framer-motion'
import { Play, Copy, Heart, Eye } from 'lucide-react'

interface WorkCard {
    id: string
    title: string
    author: string
    thumbnail: string
    views: number
    likes: number
    tags: string[]
}

const demoWorks: WorkCard[] = [
    { id: '1', title: '雨夜书店的邂逅', author: '创意大师', thumbnail: '', views: 12500, likes: 890, tags: ['都市', '恋爱'] },
    { id: '2', title: '消失的密室', author: '悬疑控', thumbnail: '', views: 8900, likes: 654, tags: ['悬疑', '推理'] },
    { id: '3', title: '废柴逆袭记', author: '爽文大神', thumbnail: '', views: 23400, likes: 1890, tags: ['爽文', '逆袭'] },
    { id: '4', title: '剑圣修仙路', author: '仙侠迷', thumbnail: '', views: 15600, likes: 1234, tags: ['仙侠', '冒险'] },
]

interface InspirationFeedProps {
    onClone: (workId: string) => void
}

export function InspirationFeed({ onClone }: InspirationFeedProps) {
    const formatNumber = (num: number) => {
        if (num >= 10000) return `${(num / 10000).toFixed(1)}万`
        if (num >= 1000) return `${(num / 1000).toFixed(1)}k`
        return num.toString()
    }

    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="w-full max-w-5xl mx-auto"
        >
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <h2 className="font-heading font-semibold text-xl text-[#FAFAFA]">灵感广场</h2>
                <button className="text-sm font-heading text-[#10B981] hover:underline cursor-pointer">
                    查看更多
                </button>
            </div>

            {/* Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
                {demoWorks.map((work, idx) => (
                    <motion.div
                        key={work.id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 + idx * 0.05 }}
                        className="group relative bg-[#18181B] rounded-xl border border-[#27272A] overflow-hidden hover:border-[#3F3F46] transition-all duration-300"
                    >
                        {/* Thumbnail */}
                        <div className="aspect-[3/4] bg-gradient-to-br from-[#27272A] to-[#18181B] relative overflow-hidden">
                            {work.thumbnail ? (
                                <img src={work.thumbnail} alt={work.title} className="w-full h-full object-cover" />
                            ) : (
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <Play className="w-12 h-12 text-[#3F3F46]" />
                                </div>
                            )}

                            {/* Overlay on hover */}
                            <motion.div
                                initial={{ opacity: 0 }}
                                whileHover={{ opacity: 1 }}
                                className="absolute inset-0 bg-black/60 flex items-center justify-center gap-3"
                            >
                                <motion.button
                                    whileHover={{ scale: 1.1 }}
                                    whileTap={{ scale: 0.9 }}
                                    className="p-3 rounded-full bg-white/20 hover:bg-white/30 text-white transition-colors cursor-pointer"
                                    title="预览"
                                >
                                    <Eye className="w-5 h-5" />
                                </motion.button>
                                <motion.button
                                    whileHover={{ scale: 1.1 }}
                                    whileTap={{ scale: 0.9 }}
                                    onClick={() => onClone(work.id)}
                                    className="p-3 rounded-full bg-[#10B981] hover:bg-[#059669] text-white transition-colors cursor-pointer glow-emerald"
                                    title="复刻"
                                >
                                    <Copy className="w-5 h-5" />
                                </motion.button>
                            </motion.div>

                            {/* Tags */}
                            <div className="absolute top-2 left-2 flex gap-1">
                                {work.tags.slice(0, 2).map((tag) => (
                                    <span key={tag} className="px-2 py-0.5 bg-black/50 backdrop-blur-sm rounded text-[10px] font-heading text-white">
                                        {tag}
                                    </span>
                                ))}
                            </div>
                        </div>

                        {/* Info */}
                        <div className="p-3">
                            <h3 className="font-heading font-medium text-sm text-[#FAFAFA] truncate mb-1">{work.title}</h3>
                            <p className="text-xs text-[#71717A] font-body mb-2">{work.author}</p>
                            <div className="flex items-center gap-3 text-xs text-[#52525B]">
                                <span className="flex items-center gap-1">
                                    <Eye className="w-3 h-3" />
                                    {formatNumber(work.views)}
                                </span>
                                <span className="flex items-center gap-1">
                                    <Heart className="w-3 h-3" />
                                    {formatNumber(work.likes)}
                                </span>
                            </div>
                        </div>
                    </motion.div>
                ))}
            </div>
        </motion.div>
    )
}
