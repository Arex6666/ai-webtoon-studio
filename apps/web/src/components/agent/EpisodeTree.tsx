'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
    FileText, Image as ImageIcon, Layers, Sparkles, Play,
    ChevronDown, ChevronRight, Check, AlertCircle, Clock, Loader2
} from 'lucide-react'
import { cn } from '@/lib/utils'

export type PhaseStatus = 'pending' | 'draft' | 'locked' | 'rendering' | 'done' | 'fixing'

export interface Phase {
    id: string
    name: string
    status: PhaseStatus
    pendingCount?: number
}

export interface Episode {
    id: string
    number: number
    title: string
    phases: Phase[]
}

const defaultPhases: Phase[] = [
    { id: 'script', name: '剧本', status: 'pending' },
    { id: 'storyboard', name: '分镜', status: 'pending' },
    { id: 'assets', name: '资产', status: 'pending' },
    { id: 'render', name: '生成', status: 'pending' },
    { id: 'qa', name: '质检', status: 'pending' },
    { id: 'export', name: '成片', status: 'pending' },
]

const statusConfig: Record<PhaseStatus, { icon: React.ElementType; color: string; bg: string }> = {
    pending: { icon: Clock, color: 'text-[#71717A]', bg: 'bg-[#27272A]' },
    draft: { icon: FileText, color: 'text-[#F59E0B]', bg: 'bg-[#F59E0B]/20' },
    locked: { icon: Check, color: 'text-[#10B981]', bg: 'bg-[#10B981]/20' },
    rendering: { icon: Loader2, color: 'text-[#06B6D4]', bg: 'bg-[#06B6D4]/20' },
    done: { icon: Check, color: 'text-[#10B981]', bg: 'bg-[#10B981]/20' },
    fixing: { icon: AlertCircle, color: 'text-[#F43F5E]', bg: 'bg-[#F43F5E]/20' },
}

interface EpisodeTreeProps {
    episodes: Episode[]
    selectedEpisode: string | null
    selectedPhase: string | null
    onSelectEpisode: (id: string) => void
    onSelectPhase: (episodeId: string, phaseId: string) => void
    onAddEpisode: () => void
}

export function EpisodeTree({
    episodes,
    selectedEpisode,
    selectedPhase,
    onSelectEpisode,
    onSelectPhase,
    onAddEpisode
}: EpisodeTreeProps) {
    const [expandedEpisodes, setExpandedEpisodes] = useState<Set<string>>(new Set([episodes[0]?.id]))

    const toggleEpisode = (id: string) => {
        const newExpanded = new Set(expandedEpisodes)
        if (newExpanded.has(id)) {
            newExpanded.delete(id)
        } else {
            newExpanded.add(id)
        }
        setExpandedEpisodes(newExpanded)
    }

    return (
        <div className="h-full flex flex-col bg-[#0C0C0C] border-r border-[#27272A]">
            {/* Header */}
            <div className="h-14 flex items-center justify-between px-4 border-b border-[#27272A]">
                <span className="font-heading text-sm font-semibold text-[#FAFAFA]">剧集</span>
                <motion.button
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.9 }}
                    onClick={onAddEpisode}
                    className="w-7 h-7 flex items-center justify-center rounded-lg bg-[#10B981]/20 text-[#10B981] hover:bg-[#10B981]/30 transition-colors duration-200 cursor-pointer"
                >
                    <span className="text-lg leading-none font-heading">+</span>
                </motion.button>
            </div>

            {/* Episode List */}
            <div className="flex-1 overflow-y-auto py-2">
                {episodes.map((episode) => {
                    const isExpanded = expandedEpisodes.has(episode.id)
                    const isSelected = selectedEpisode === episode.id
                    const pendingCount = episode.phases.reduce((sum, p) => sum + (p.pendingCount || 0), 0)

                    return (
                        <div key={episode.id}>
                            {/* Episode Header */}
                            <motion.button
                                whileHover={{ backgroundColor: 'rgba(39, 39, 42, 0.5)' }}
                                onClick={() => {
                                    onSelectEpisode(episode.id)
                                    toggleEpisode(episode.id)
                                }}
                                className={cn(
                                    "w-full flex items-center gap-2 px-3 py-2.5 text-left transition-colors duration-200 cursor-pointer",
                                    isSelected ? "bg-[#18181B]" : ""
                                )}
                            >
                                <motion.div
                                    animate={{ rotate: isExpanded ? 90 : 0 }}
                                    transition={{ duration: 0.15 }}
                                >
                                    <ChevronRight className="w-4 h-4 text-[#71717A]" />
                                </motion.div>
                                <span className="text-lg">📺</span>
                                <span className="flex-1 font-heading text-sm text-[#FAFAFA]">
                                    第{episode.number}集
                                </span>
                                {pendingCount > 0 && (
                                    <span className="px-1.5 py-0.5 text-[10px] font-heading bg-[#F59E0B]/20 text-[#F59E0B] rounded">
                                        {pendingCount}
                                    </span>
                                )}
                            </motion.button>

                            {/* Phases */}
                            <AnimatePresence>
                                {isExpanded && (
                                    <motion.div
                                        initial={{ height: 0, opacity: 0 }}
                                        animate={{ height: 'auto', opacity: 1 }}
                                        exit={{ height: 0, opacity: 0 }}
                                        transition={{ duration: 0.2 }}
                                        className="overflow-hidden"
                                    >
                                        {episode.phases.map((phase, idx) => {
                                            const config = statusConfig[phase.status]
                                            const isPhaseSelected = selectedEpisode === episode.id && selectedPhase === phase.id
                                            const isLast = idx === episode.phases.length - 1

                                            return (
                                                <motion.button
                                                    key={phase.id}
                                                    whileHover={{ backgroundColor: 'rgba(39, 39, 42, 0.3)' }}
                                                    onClick={() => onSelectPhase(episode.id, phase.id)}
                                                    className={cn(
                                                        "w-full flex items-center gap-2 pl-10 pr-3 py-2 text-left transition-colors duration-200 cursor-pointer",
                                                        isPhaseSelected
                                                            ? "bg-[#10B981]/10 border-l-2 border-[#10B981]"
                                                            : "border-l-2 border-transparent"
                                                    )}
                                                >
                                                    {/* Connector Line */}
                                                    <div className="relative w-4 h-full">
                                                        <div className={cn(
                                                            "absolute left-1 top-0 bottom-0 w-px bg-[#3F3F46]",
                                                            isLast && "h-1/2"
                                                        )} />
                                                        <div className="absolute left-1 top-1/2 w-3 h-px bg-[#3F3F46]" />
                                                    </div>

                                                    {/* Status Icon */}
                                                    <motion.div
                                                        whileHover={{ scale: 1.1 }}
                                                        className={cn(
                                                            "w-6 h-6 rounded-md flex items-center justify-center",
                                                            config.bg, config.color
                                                        )}
                                                    >
                                                        {phase.status === 'rendering' ? (
                                                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                                        ) : (
                                                            <config.icon className="w-3.5 h-3.5" />
                                                        )}
                                                    </motion.div>

                                                    {/* Phase Name */}
                                                    <span className={cn(
                                                        "flex-1 text-sm font-body",
                                                        isPhaseSelected ? "text-[#10B981]" : "text-[#A1A1AA]"
                                                    )}>
                                                        {phase.name}
                                                    </span>

                                                    {/* Pending Badge */}
                                                    {phase.pendingCount && phase.pendingCount > 0 && (
                                                        <span className="px-1.5 py-0.5 text-[10px] font-heading bg-[#F43F5E]/20 text-[#F43F5E] rounded">
                                                            {phase.pendingCount}
                                                        </span>
                                                    )}
                                                </motion.button>
                                            )
                                        })}
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </div>
                    )
                })}
            </div>
        </div>
    )
}
