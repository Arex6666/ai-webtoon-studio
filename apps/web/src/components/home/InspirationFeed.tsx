'use client'

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Play, Copy, Heart, Eye, Sparkles, FolderOpen, Trash2 } from 'lucide-react'
import { projectsApi, type Project } from '@/lib/api'
import { useRouter } from 'next/navigation'

interface InspirationFeedProps {
    onClone: (workId: string) => void
}

export function InspirationFeed({ onClone }: InspirationFeedProps) {
    const router = useRouter()
    const [projects, setProjects] = useState<Project[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        projectsApi.list()
            .then((res) => setProjects(res.items.slice(0, 8)))
            .catch(() => {})
            .finally(() => setLoading(false))
    }, [])

    const formatDate = (dateStr: string) => {
        const d = new Date(dateStr)
        const now = new Date()
        const diffMs = now.getTime() - d.getTime()
        const diffMin = Math.floor(diffMs / 60000)
        if (diffMin < 1) return '刚刚'
        if (diffMin < 60) return `${diffMin} 分钟前`
        const diffHour = Math.floor(diffMin / 60)
        if (diffHour < 24) return `${diffHour} 小时前`
        const diffDay = Math.floor(diffHour / 24)
        if (diffDay < 30) return `${diffDay} 天前`
        return d.toLocaleDateString('zh-CN')
    }

    const methodLabel = (m: string) => {
        if (m === 'agent') return 'AI 创作'
        if (m === 'workbench') return '工作台'
        return m
    }

    if (loading) {
        return (
            <div className="w-full max-w-5xl mx-auto">
                <div className="flex items-center justify-between mb-6">
                    <h2 className="font-heading font-semibold text-xl text-[#FAFAFA]">我的作品</h2>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
                    {[0, 1, 2, 3].map((i) => (
                        <div key={i} className="bg-[#18181B] rounded-xl border border-[#27272A] overflow-hidden animate-pulse">
                            <div className="aspect-[3/4] bg-[#27272A]" />
                            <div className="p-3 space-y-2">
                                <div className="h-4 bg-[#27272A] rounded w-3/4" />
                                <div className="h-3 bg-[#27272A] rounded w-1/2" />
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        )
    }

    if (projects.length === 0) {
        return (
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.2 }}
                className="w-full max-w-5xl mx-auto"
            >
                <div className="flex items-center justify-between mb-6">
                    <h2 className="font-heading font-semibold text-xl text-[#FAFAFA]">我的作品</h2>
                </div>
                <div className="flex flex-col items-center justify-center py-16 bg-[#18181B]/50 rounded-2xl border border-[#27272A] border-dashed">
                    <FolderOpen className="w-12 h-12 text-[#3F3F46] mb-4" />
                    <p className="text-[#71717A] font-heading text-sm mb-1">还没有作品</p>
                    <p className="text-[#52525B] text-xs">在上方输入创意，开始你的第一个漫剧项目</p>
                </div>
            </motion.div>
        )
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
                <h2 className="font-heading font-semibold text-xl text-[#FAFAFA]">我的作品</h2>
                <button
                    onClick={() => router.push('/projects')}
                    className="text-sm font-heading text-[#10B981] hover:underline cursor-pointer"
                >
                    查看全部
                </button>
            </div>

            {/* Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
                {projects.map((project, idx) => (
                    <motion.div
                        key={project.id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 + idx * 0.05 }}
                        onClick={() => router.push(`/projects/${project.id}`)}
                        className="group relative bg-[#18181B] rounded-xl border border-[#27272A] overflow-hidden hover:border-[#3F3F46] transition-all duration-300 cursor-pointer"
                    >
                        {/* Thumbnail */}
                        <div className="aspect-[3/4] bg-gradient-to-br from-[#27272A] to-[#18181B] relative overflow-hidden">
                            {project.cover_image ? (
                                <img
                                    src={project.cover_image}
                                    alt={project.name}
                                    className="w-full h-full object-cover"
                                />
                            ) : (
                                <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
                                    <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#10B981]/20 to-[#8B5CF6]/20 border border-[#27272A] flex items-center justify-center">
                                        <Sparkles className="w-7 h-7 text-[#10B981]/60" />
                                    </div>
                                    <span className="text-[#3F3F46] text-xs font-heading">暂无封面</span>
                                </div>
                            )}

                            {/* Hover overlay */}
                            <div className="absolute inset-0 bg-black/60 flex items-center justify-center gap-3 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                                <motion.button
                                    whileHover={{ scale: 1.1 }}
                                    whileTap={{ scale: 0.9 }}
                                    className="p-3 rounded-full bg-white/20 hover:bg-white/30 text-white transition-colors cursor-pointer"
                                    title="打开"
                                    onClick={(e) => {
                                        e.stopPropagation()
                                        router.push(`/projects/${project.id}`)
                                    }}
                                >
                                    <Eye className="w-5 h-5" />
                                </motion.button>
                                <motion.button
                                    whileHover={{ scale: 1.1 }}
                                    whileTap={{ scale: 0.9 }}
                                    className="p-3 rounded-full bg-red-500/20 hover:bg-red-500/40 text-red-100 transition-colors cursor-pointer"
                                    title="删除项目"
                                    onClick={async (e) => {
                                        e.stopPropagation()
                                        if (window.confirm(`确定要永久删除项目「${project.name}」及其所有数据吗？`)) {
                                            try {
                                                await projectsApi.delete(project.id)
                                                setProjects(prev => prev.filter(p => p.id !== project.id))
                                            } catch (err) {
                                                console.error('Failed to delete project:', err)
                                                alert('删除失败，请重试')
                                            }
                                        }
                                    }}
                                >
                                    <Trash2 className="w-5 h-5" />
                                </motion.button>
                            </div>

                            {/* Tags */}
                            <div className="absolute top-2 left-2 flex gap-1">
                                <span className="px-2 py-0.5 bg-black/50 backdrop-blur-sm rounded text-[10px] font-heading text-white">
                                    {methodLabel(project.creation_method)}
                                </span>
                                {project.chapter_count > 0 && (
                                    <span className="px-2 py-0.5 bg-black/50 backdrop-blur-sm rounded text-[10px] font-heading text-white">
                                        {project.chapter_count} 章
                                    </span>
                                )}
                            </div>
                        </div>

                        {/* Info */}
                        <div className="p-3">
                            <h3 className="font-heading font-medium text-sm text-[#FAFAFA] truncate mb-1">
                                {project.name}
                            </h3>
                            {project.description && (
                                <p className="text-xs text-[#71717A] font-body mb-2 line-clamp-1">
                                    {project.description}
                                </p>
                            )}
                            <div className="flex items-center gap-2 text-xs text-[#52525B]">
                                <span>{formatDate(project.updated_at)}</span>
                            </div>
                        </div>
                    </motion.div>
                ))}
            </div>
        </motion.div>
    )
}
