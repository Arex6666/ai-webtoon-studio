'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import {
    MessageSquare, Layers, Sparkles, ArrowRight, X,
    Bot, MousePointer2
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { projectsApi } from '@/lib/api'

interface ModeOption {
    id: 'agent' | 'studio'
    title: string
    subtitle: string
    description: string
    icon: React.ElementType
    gradient: string
    features: string[]
}

const modeOptions: ModeOption[] = [
    {
        id: 'agent',
        title: 'Agent 智能创作',
        subtitle: '对话驱动',
        description: '通过对话与 AI 导演协作，快速生成剧本、分镜和资产',
        icon: Bot,
        gradient: 'from-emerald-500 to-cyan-500',
        features: ['智能剧本生成', '自动分镜', '资产自动绑定', '一键生成']
    },
    {
        id: 'studio',
        title: 'Studio 精细编辑',
        subtitle: '手动控制',
        description: '完全掌控每个细节，手动调整分镜、图层和渲染参数',
        icon: MousePointer2,
        gradient: 'from-emerald-500 to-purple-500',
        features: ['图层编辑', '精确控制', '高级渲染', '自定义工作流']
    }
]

interface CreateProjectFlowProps {
    isOpen: boolean
    onClose: () => void
}

export function CreateProjectFlow({ isOpen, onClose }: CreateProjectFlowProps) {
    const router = useRouter()
    const [step, setStep] = useState<'name' | 'mode'>('name')
    const [projectName, setProjectName] = useState('')
    const [selectedMode, setSelectedMode] = useState<'agent' | 'studio' | null>(null)
    const [loading, setLoading] = useState(false)

    const handleNext = () => {
        if (step === 'name' && projectName.trim()) {
            setStep('mode')
        }
    }

    const handleCreate = async () => {
        if (!selectedMode || !projectName.trim()) return

        setLoading(true)
        try {
            const project = await projectsApi.create({
                name: projectName,
                description: `Mode: ${selectedMode}`
            })

            onClose()

            // Route based on mode
            if (selectedMode === 'agent') {
                router.push(`/agent/${project.id}`)
            } else {
                router.push(`/studio/${project.id}`)
            }
        } catch (error) {
            console.error('Failed to create project:', error)
        } finally {
            setLoading(false)
        }
    }

    const handleBack = () => {
        if (step === 'mode') {
            setStep('name')
        }
    }

    if (!isOpen) return null

    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            onClick={onClose}
        >
            <div className="absolute inset-0 bg-[#020617]/95 backdrop-blur-md" />

            <motion.div
                initial={{ scale: 0.95, y: 20 }}
                animate={{ scale: 1, y: 0 }}
                exit={{ scale: 0.95, y: 20 }}
                onClick={(e) => e.stopPropagation()}
                className="relative w-full max-w-2xl bg-slate-900/90 rounded-2xl border border-slate-700/50 shadow-2xl overflow-hidden backdrop-blur-sm"
            >
                {/* Gradient Top Bar */}
                <div className="h-1 bg-gradient-to-r from-emerald-500 via-cyan-500 to-emerald-500" />

                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-slate-800/50">
                    <div>
                        <h2 className="font-mono text-xl font-bold text-slate-100">
                            {step === 'name' ? '新建项目' : '选择创作模式'}
                        </h2>
                        <p className="text-sm text-slate-400 mt-1">
                            {step === 'name' ? '为您的漫剧项目命名' : '选择适合您的工作方式'}
                        </p>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 text-slate-500 hover:text-slate-300 hover:bg-slate-800 rounded-lg transition-colors cursor-pointer"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Content */}
                <div className="p-6">
                    <AnimatePresence mode="wait">
                        {step === 'name' ? (
                            <motion.div
                                key="name"
                                initial={{ opacity: 0, x: -20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: 20 }}
                            >
                                <label className="block text-sm font-medium text-slate-300 mb-3">
                                    项目名称
                                </label>
                                <input
                                    type="text"
                                    value={projectName}
                                    onChange={(e) => setProjectName(e.target.value)}
                                    onKeyDown={(e) => e.key === 'Enter' && handleNext()}
                                    placeholder="例如：都市爱情故事"
                                    autoFocus
                                    className="w-full px-4 py-4 bg-slate-800/50 border border-slate-700/50 rounded-xl
                    focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/20 focus:outline-none
                    transition-all text-lg text-slate-100 placeholder:text-slate-500"
                                />
                            </motion.div>
                        ) : (
                            <motion.div
                                key="mode"
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -20 }}
                                className="grid grid-cols-2 gap-4"
                            >
                                {modeOptions.map((mode) => (
                                    <motion.button
                                        key={mode.id}
                                        whileHover={{ scale: 1.02 }}
                                        whileTap={{ scale: 0.98 }}
                                        onClick={() => setSelectedMode(mode.id)}
                                        className={cn(
                                            "relative p-6 rounded-2xl border text-left transition-all cursor-pointer group",
                                            selectedMode === mode.id
                                                ? "border-emerald-500/50 bg-emerald-500/10"
                                                : "border-slate-700/50 bg-slate-800/30 hover:border-slate-600/50 hover:bg-slate-800/50"
                                        )}
                                    >
                                        {/* Gradient Icon */}
                                        <div className={cn(
                                            "w-14 h-14 rounded-xl bg-gradient-to-br flex items-center justify-center mb-4 shadow-lg transition-transform group-hover:scale-105",
                                            mode.gradient,
                                            mode.id === 'agent' ? 'shadow-emerald-500/20' : 'shadow-emerald-500/20'
                                        )}>
                                            <mode.icon className="w-7 h-7 text-white" />
                                        </div>

                                        {/* Title */}
                                        <h3 className="font-mono font-semibold text-lg text-slate-100 mb-1">
                                            {mode.title}
                                        </h3>
                                        <span className={cn(
                                            "inline-block px-2 py-0.5 rounded text-xs font-medium mb-3",
                                            mode.id === 'agent'
                                                ? "bg-emerald-500/20 text-emerald-400"
                                                : "bg-emerald-500/20 text-emerald-400"
                                        )}>
                                            {mode.subtitle}
                                        </span>

                                        {/* Description */}
                                        <p className="text-sm text-slate-400 mb-4 leading-relaxed">
                                            {mode.description}
                                        </p>

                                        {/* Features */}
                                        <div className="flex flex-wrap gap-1.5">
                                            {mode.features.map((feature) => (
                                                <span
                                                    key={feature}
                                                    className="px-2 py-1 bg-slate-800/50 rounded text-xs text-slate-500"
                                                >
                                                    {feature}
                                                </span>
                                            ))}
                                        </div>

                                        {/* Selected Indicator */}
                                        {selectedMode === mode.id && (
                                            <motion.div
                                                layoutId="selected"
                                                className="absolute top-3 right-3 w-6 h-6 rounded-full bg-emerald-500 flex items-center justify-center"
                                            >
                                                <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                                </svg>
                                            </motion.div>
                                        )}
                                    </motion.button>
                                ))}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between p-6 border-t border-slate-800/50 bg-slate-900/50">
                    <button
                        onClick={step === 'name' ? onClose : handleBack}
                        className="px-4 py-2.5 text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
                    >
                        {step === 'name' ? '取消' : '返回'}
                    </button>

                    {step === 'name' ? (
                        <button
                            onClick={handleNext}
                            disabled={!projectName.trim()}
                            className="flex items-center gap-2 px-6 py-2.5 bg-emerald-500 hover:bg-emerald-400 text-white rounded-xl font-medium transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-emerald-500/20"
                        >
                            下一步
                            <ArrowRight className="w-4 h-4" />
                        </button>
                    ) : (
                        <button
                            onClick={handleCreate}
                            disabled={!selectedMode || loading}
                            className="flex items-center gap-2 px-6 py-2.5 bg-emerald-500 hover:bg-emerald-400 text-white rounded-xl font-medium transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-emerald-500/20"
                        >
                            {loading ? '创建中...' : '开始创作'}
                            <Sparkles className="w-4 h-4" />
                        </button>
                    )}
                </div>
            </motion.div>
        </motion.div>
    )
}
