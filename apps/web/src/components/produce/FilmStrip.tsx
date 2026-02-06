'use client'

import { useState, useRef } from 'react'
import { motion } from 'framer-motion'
import { Check, AlertTriangle, Loader2, ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

export type PanelStatus = 'pending' | 'generating' | 'done' | 'error' | 'qa'

export interface FilmPanel {
    id: string
    number: number
    thumbnail?: string
    status: PanelStatus
    qaIssues?: number
}

interface FilmStripProps {
    panels: FilmPanel[]
    selectedId: string | null
    onSelect: (id: string) => void
}

const statusConfig: Record<PanelStatus, { icon: React.ElementType; color: string; bg: string }> = {
    pending: { icon: () => <span className="w-2 h-2 rounded-full bg-[#52525B]" />, color: '#52525B', bg: 'bg-[#18181B]' },
    generating: { icon: Loader2, color: '#06B6D4', bg: 'bg-[#06B6D4]/10' },
    done: { icon: Check, color: '#10B981', bg: 'bg-[#10B981]/10' },
    error: { icon: AlertTriangle, color: '#F43F5E', bg: 'bg-[#F43F5E]/10' },
    qa: { icon: AlertTriangle, color: '#F59E0B', bg: 'bg-[#F59E0B]/10' },
}

export function FilmStrip({ panels, selectedId, onSelect }: FilmStripProps) {
    const scrollRef = useRef<HTMLDivElement>(null)
    const [canScrollLeft, setCanScrollLeft] = useState(false)
    const [canScrollRight, setCanScrollRight] = useState(true)

    const checkScroll = () => {
        if (scrollRef.current) {
            const { scrollLeft, scrollWidth, clientWidth } = scrollRef.current
            setCanScrollLeft(scrollLeft > 0)
            setCanScrollRight(scrollLeft < scrollWidth - clientWidth - 10)
        }
    }

    const scroll = (direction: 'left' | 'right') => {
        if (scrollRef.current) {
            const scrollAmount = 200
            scrollRef.current.scrollBy({
                left: direction === 'left' ? -scrollAmount : scrollAmount,
                behavior: 'smooth'
            })
        }
    }

    return (
        <div className="h-full flex flex-col bg-[#0C0C0C] border-l border-[#27272A]">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-[#27272A]">
                <span className="font-heading text-sm font-semibold text-[#FAFAFA]">分镜胶片</span>
                <span className="text-xs text-[#71717A] font-heading">{panels.length} 格</span>
            </div>

            {/* Film Strip */}
            <div className="relative flex-1">
                {/* Scroll Left */}
                {canScrollLeft && (
                    <motion.button
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        onClick={() => scroll('left')}
                        className="absolute left-0 top-0 bottom-0 z-10 w-8 bg-gradient-to-r from-[#0C0C0C] to-transparent flex items-center justify-center cursor-pointer"
                    >
                        <ChevronLeft className="w-5 h-5 text-[#71717A]" />
                    </motion.button>
                )}

                {/* Panels */}
                <div
                    ref={scrollRef}
                    onScroll={checkScroll}
                    className="flex gap-3 p-4 overflow-x-auto scrollbar-hide"
                >
                    {panels.map((panel, idx) => {
                        const config = statusConfig[panel.status]
                        const isSelected = selectedId === panel.id

                        return (
                            <motion.button
                                key={panel.id}
                                initial={{ opacity: 0, scale: 0.9 }}
                                animate={{ opacity: 1, scale: 1 }}
                                transition={{ delay: idx * 0.03 }}
                                whileHover={{ scale: 1.03 }}
                                whileTap={{ scale: 0.97 }}
                                onClick={() => onSelect(panel.id)}
                                className={cn(
                                    "relative flex-shrink-0 w-20 rounded-xl overflow-hidden border-2 transition-all duration-200 cursor-pointer",
                                    isSelected
                                        ? "border-[#10B981] ring-2 ring-[#10B981]/30"
                                        : "border-[#27272A] hover:border-[#3F3F46]"
                                )}
                            >
                                {/* Thumbnail */}
                                <div className="aspect-[9/16] bg-[#18181B]">
                                    {panel.thumbnail ? (
                                        <img src={panel.thumbnail} alt={`Panel ${panel.number}`} className="w-full h-full object-cover" />
                                    ) : (
                                        <div className="w-full h-full flex items-center justify-center">
                                            <span className="text-2xl font-heading font-bold text-[#27272A]">{panel.number}</span>
                                        </div>
                                    )}
                                </div>

                                {/* Status Badge */}
                                <div
                                    className={cn(
                                        "absolute top-1 right-1 w-5 h-5 rounded-full flex items-center justify-center",
                                        config.bg
                                    )}
                                >
                                    {panel.status === 'generating' ? (
                                        <Loader2 className="w-3 h-3 animate-spin" style={{ color: config.color }} />
                                    ) : (
                                        <config.icon className="w-3 h-3" style={{ color: config.color }} />
                                    )}
                                </div>

                                {/* QA Issues */}
                                {panel.qaIssues && panel.qaIssues > 0 && (
                                    <div className="absolute bottom-1 left-1 px-1.5 py-0.5 bg-[#F59E0B]/20 rounded text-[10px] font-heading text-[#F59E0B]">
                                        {panel.qaIssues}
                                    </div>
                                )}

                                {/* Panel Number */}
                                <div className="absolute bottom-1 right-1 px-1.5 py-0.5 bg-black/60 backdrop-blur-sm rounded text-[10px] font-heading text-white">
                                    #{panel.number}
                                </div>
                            </motion.button>
                        )
                    })}
                </div>

                {/* Scroll Right */}
                {canScrollRight && (
                    <motion.button
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        onClick={() => scroll('right')}
                        className="absolute right-0 top-0 bottom-0 z-10 w-8 bg-gradient-to-l from-[#0C0C0C] to-transparent flex items-center justify-center cursor-pointer"
                    >
                        <ChevronRight className="w-5 h-5 text-[#71717A]" />
                    </motion.button>
                )}
            </div>
        </div>
    )
}
