'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
    FileText, Code, History, Lock, Sparkles, ExternalLink,
    CheckCircle2, AlertCircle, ChevronDown
} from 'lucide-react'
import { cn } from '@/lib/utils'

type TabId = 'planning' | 'spec' | 'history'

interface PlanningPanelProps {
    episodeNumber: number
    currentPhase: string
    phaseStatus: 'draft' | 'locked' | 'pending'
    onLock: () => void
    onGenerate: () => void
    onOpenStudio: () => void
}

export function PlanningPanel({
    episodeNumber,
    currentPhase,
    phaseStatus,
    onLock,
    onGenerate,
    onOpenStudio
}: PlanningPanelProps) {
    const [activeTab, setActiveTab] = useState<TabId>('planning')

    const tabs: { id: TabId; label: string; icon: React.ElementType }[] = [
        { id: 'planning', label: '策划文档', icon: FileText },
        { id: 'spec', label: '结构化 Spec', icon: Code },
        { id: 'history', label: '变更记录', icon: History },
    ]

    return (
        <div className="h-full flex flex-col bg-[#0C0C0C] border-l border-[#27272A]">
            {/* Status Bar */}
            <div className="h-14 flex items-center justify-between px-4 border-b border-[#27272A] bg-[#000000]/50">
                <div className="flex items-center gap-3">
                    <span className="text-sm text-[#71717A] font-body">当前集:</span>
                    <span className="font-heading font-semibold text-[#FAFAFA]">第{episodeNumber}集</span>
                    <div className="w-px h-4 bg-[#3F3F46]" />
                    <span className={cn(
                        "px-2 py-0.5 rounded text-xs font-heading font-medium",
                        phaseStatus === 'locked' && "bg-[#10B981]/20 text-[#10B981]",
                        phaseStatus === 'draft' && "bg-[#F59E0B]/20 text-[#F59E0B]",
                        phaseStatus === 'pending' && "bg-[#27272A] text-[#71717A]"
                    )}>
                        {currentPhase} · {phaseStatus === 'locked' ? '已锁定' : phaseStatus === 'draft' ? '草稿' : '待处理'}
                    </span>
                </div>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-[#27272A]">
                {tabs.map((tab) => (
                    <motion.button
                        key={tab.id}
                        whileHover={{ backgroundColor: 'rgba(39, 39, 42, 0.5)' }}
                        onClick={() => setActiveTab(tab.id)}
                        className={cn(
                            "flex items-center gap-2 px-4 py-3 text-sm font-heading font-medium border-b-2 transition-colors duration-200 cursor-pointer",
                            activeTab === tab.id
                                ? "text-[#10B981] border-[#10B981]"
                                : "text-[#71717A] border-transparent hover:text-[#FAFAFA]"
                        )}
                    >
                        <tab.icon className="w-4 h-4" />
                        {tab.label}
                    </motion.button>
                ))}
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4">
                <AnimatePresence mode="wait">
                    {activeTab === 'planning' && (
                        <motion.div
                            key="planning"
                            initial={{ opacity: 0, x: 10 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -10 }}
                            className="space-y-4"
                        >
                            <h2 className="font-heading text-lg font-bold text-[#FAFAFA] mb-4 flex items-center gap-2">
                                <span className="text-xl">📋</span> 策划大纲
                            </h2>

                            {[
                                { num: 1, title: '故事概要', color: 'bg-[#3B82F6]/20 text-[#3B82F6]', content: '在这里输入或由 AI 生成故事的整体概要...' },
                                { num: 2, title: '角色设定', color: 'bg-[#8B5CF6]/20 text-[#8B5CF6]', content: null },
                                { num: 3, title: '风格定义', color: 'bg-[#F59E0B]/20 text-[#F59E0B]', content: null },
                            ].map((section) => (
                                <motion.section
                                    key={section.num}
                                    whileHover={{ borderColor: 'rgba(63, 63, 70, 0.8)' }}
                                    className="p-4 rounded-xl bg-[#18181B] border border-[#27272A] transition-all duration-200"
                                >
                                    <h3 className="font-heading text-sm font-semibold text-[#FAFAFA] mb-2 flex items-center gap-2">
                                        <span className={cn("w-6 h-6 rounded flex items-center justify-center text-xs", section.color)}>
                                            {section.num}
                                        </span>
                                        {section.title}
                                    </h3>
                                    {section.content && (
                                        <p className="text-sm text-[#71717A] font-body leading-relaxed">{section.content}</p>
                                    )}
                                    {section.num === 2 && (
                                        <div className="flex items-center gap-2 text-sm text-[#71717A] font-body">
                                            <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-pink-500 to-rose-500 flex items-center justify-center text-white text-xs font-heading">林</span>
                                            <span>林知夏 - 主角</span>
                                        </div>
                                    )}
                                    {section.num === 3 && (
                                        <div className="flex flex-wrap gap-2">
                                            {['韩漫风格', '暖色调', '都市背景'].map((tag) => (
                                                <span key={tag} className="px-2 py-1 bg-[#27272A] rounded text-xs text-[#71717A] font-body">{tag}</span>
                                            ))}
                                        </div>
                                    )}
                                </motion.section>
                            ))}
                        </motion.div>
                    )}

                    {activeTab === 'spec' && (
                        <motion.div
                            key="spec"
                            initial={{ opacity: 0, x: 10 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -10 }}
                            className="font-heading text-sm"
                        >
                            <div className="p-4 rounded-xl bg-[#18181B] border border-[#27272A]">
                                <pre className="text-[#71717A] font-body whitespace-pre-wrap text-sm">
                                    {`{
  "episode": ${episodeNumber},
  "title": "初遇",
  "style": "韩漫写实",
  "panels": [
    {
      "id": "panel_1",
      "type": "establishing",
      "scene": "雨夜旧书店",
      "characters": ["林知夏"]
    }
  ]
}`}
                                </pre>
                            </div>
                        </motion.div>
                    )}

                    {activeTab === 'history' && (
                        <motion.div
                            key="history"
                            initial={{ opacity: 0, x: 10 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -10 }}
                            className="space-y-3"
                        >
                            {[
                                { text: '更新了第3格的镜头语言', time: '2 分钟前' },
                                { text: '添加了角色「林知夏」', time: '5 分钟前' },
                            ].map((item, idx) => (
                                <motion.div
                                    key={idx}
                                    whileHover={{ borderColor: 'rgba(16, 185, 129, 0.3)' }}
                                    className="p-3 rounded-xl bg-[#18181B] border border-[#27272A] transition-colors duration-200"
                                >
                                    <div className="flex items-center gap-2 mb-1">
                                        <CheckCircle2 className="w-4 h-4 text-[#10B981]" />
                                        <span className="text-sm text-[#FAFAFA] font-body">{item.text}</span>
                                    </div>
                                    <span className="text-xs text-[#71717A] font-heading">{item.time}</span>
                                </motion.div>
                            ))}
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>

            {/* Action Buttons */}
            <div className="p-4 border-t border-[#27272A] bg-[#0C0C0C]/50 space-y-2">
                <div className="flex gap-2">
                    <motion.button
                        whileHover={{ scale: 1.01 }}
                        whileTap={{ scale: 0.99 }}
                        onClick={onLock}
                        disabled={phaseStatus === 'locked'}
                        className={cn(
                            "flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-heading font-medium transition-all duration-200 cursor-pointer",
                            phaseStatus === 'locked'
                                ? "bg-[#10B981]/20 text-[#10B981] border border-[#10B981]/30"
                                : "bg-[#27272A] hover:bg-[#3F3F46] text-[#FAFAFA] border border-[#3F3F46]"
                        )}
                    >
                        <Lock className="w-4 h-4" />
                        {phaseStatus === 'locked' ? '已锁定' : '确认并锁定'}
                    </motion.button>
                    <motion.button
                        whileHover={{ scale: 1.01 }}
                        whileTap={{ scale: 0.99 }}
                        onClick={onGenerate}
                        className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-[#10B981] hover:bg-[#059669] text-white rounded-xl text-sm font-heading font-medium transition-all duration-200 cursor-pointer glow-emerald"
                    >
                        <Sparkles className="w-4 h-4" />
                        一键生成
                    </motion.button>
                </div>
                <motion.button
                    whileHover={{ scale: 1.005 }}
                    whileTap={{ scale: 0.995 }}
                    onClick={onOpenStudio}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-[#27272A] hover:bg-[#3F3F46] text-[#FAFAFA] border border-[#3F3F46] rounded-xl text-sm font-heading font-medium transition-all duration-200 cursor-pointer"
                >
                    <ExternalLink className="w-4 h-4" />
                    打开 Studio 高级编辑
                </motion.button>
            </div>
        </div>
    )
}
