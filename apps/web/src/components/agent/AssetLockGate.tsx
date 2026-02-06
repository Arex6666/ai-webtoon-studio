'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
    AlertTriangle, User, MapPin, Package, RefreshCw,
    Search, Sparkles, Check, X, ChevronRight
} from 'lucide-react'
import { cn } from '@/lib/utils'

export interface PendingAsset {
    id: string
    type: 'character' | 'scene' | 'prop'
    name: string
    panelId: string
    panelNumber: number
    thumbnail?: string
    suggestions?: {
        id: string
        name: string
        thumbnail?: string
        match: number // 0-100
    }[]
}

interface AssetLockGateProps {
    pendingAssets: PendingAsset[]
    onReuse: (assetId: string, reuseId: string) => void
    onGenerate: (assetId: string) => void
    onSelect: (assetId: string) => void
    onSkip: (assetId: string) => void
    onConfirmAll: () => void
}

const typeConfig = {
    character: { icon: User, color: '#F43F5E', label: '角色' },
    scene: { icon: MapPin, color: '#3B82F6', label: '场景' },
    prop: { icon: Package, color: '#F59E0B', label: '物品' },
}

export function AssetLockGate({
    pendingAssets,
    onReuse,
    onGenerate,
    onSelect,
    onSkip,
    onConfirmAll
}: AssetLockGateProps) {
    const [expandedAsset, setExpandedAsset] = useState<string | null>(pendingAssets[0]?.id)

    if (pendingAssets.length === 0) {
        return null
    }

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-[#0C0C0C] border border-[#F59E0B]/30 rounded-xl overflow-hidden"
        >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-[#27272A] bg-[#F59E0B]/5">
                <div className="flex items-center gap-3">
                    <motion.div
                        animate={{ rotate: [0, 10, -10, 0] }}
                        transition={{ duration: 0.5, repeat: Infinity, repeatDelay: 2 }}
                        className="w-9 h-9 rounded-lg bg-[#F59E0B]/20 flex items-center justify-center"
                    >
                        <AlertTriangle className="w-5 h-5 text-[#F59E0B]" />
                    </motion.div>
                    <div>
                        <h3 className="font-heading text-sm font-semibold text-[#FAFAFA]">待确认资产</h3>
                        <p className="text-xs text-[#71717A] font-body">确认后才能进入生成阶段</p>
                    </div>
                </div>
                <span className="px-3 py-1 rounded-full bg-[#F59E0B]/20 text-sm font-heading font-medium text-[#F59E0B]">
                    {pendingAssets.length}
                </span>
            </div>

            {/* Pending Assets List */}
            <div className="max-h-80 overflow-y-auto">
                {pendingAssets.map((asset, idx) => {
                    const config = typeConfig[asset.type]
                    const isExpanded = expandedAsset === asset.id

                    return (
                        <div key={asset.id} className="border-b border-[#27272A] last:border-b-0">
                            {/* Asset Row */}
                            <button
                                onClick={() => setExpandedAsset(isExpanded ? null : asset.id)}
                                className={cn(
                                    "w-full flex items-center gap-3 px-4 py-3 text-left transition-colors duration-200 cursor-pointer",
                                    isExpanded ? "bg-[#18181B]" : "hover:bg-[#18181B]/50"
                                )}
                            >
                                {/* Icon */}
                                <div
                                    className="w-10 h-10 rounded-lg flex items-center justify-center"
                                    style={{ backgroundColor: `${config.color}20` }}
                                >
                                    {asset.thumbnail ? (
                                        <img src={asset.thumbnail} alt={asset.name} className="w-full h-full object-cover rounded-lg" />
                                    ) : (
                                        <config.icon className="w-5 h-5" style={{ color: config.color }} />
                                    )}
                                </div>

                                {/* Info */}
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2">
                                        <span className="font-body text-sm text-[#FAFAFA] truncate">{asset.name}</span>
                                        <span className="px-1.5 py-0.5 rounded text-[10px] font-heading" style={{ backgroundColor: `${config.color}20`, color: config.color }}>
                                            {config.label}
                                        </span>
                                    </div>
                                    <span className="text-xs text-[#71717A] font-heading">第{asset.panelNumber}格</span>
                                </div>

                                {/* Expand Arrow */}
                                <motion.div animate={{ rotate: isExpanded ? 90 : 0 }} transition={{ duration: 0.15 }}>
                                    <ChevronRight className="w-4 h-4 text-[#71717A]" />
                                </motion.div>
                            </button>

                            {/* Expanded Content */}
                            <AnimatePresence>
                                {isExpanded && (
                                    <motion.div
                                        initial={{ height: 0, opacity: 0 }}
                                        animate={{ height: 'auto', opacity: 1 }}
                                        exit={{ height: 0, opacity: 0 }}
                                        transition={{ duration: 0.2 }}
                                        className="overflow-hidden bg-[#18181B]"
                                    >
                                        <div className="px-4 pb-4 space-y-3">
                                            {/* Suggestions */}
                                            {asset.suggestions && asset.suggestions.length > 0 && (
                                                <div>
                                                    <span className="text-xs text-[#71717A] font-heading mb-2 block">复用推荐</span>
                                                    <div className="space-y-2">
                                                        {asset.suggestions.map((sug) => (
                                                            <motion.button
                                                                key={sug.id}
                                                                whileHover={{ scale: 1.01 }}
                                                                whileTap={{ scale: 0.99 }}
                                                                onClick={() => onReuse(asset.id, sug.id)}
                                                                className="w-full flex items-center gap-3 p-2 bg-[#27272A] hover:bg-[#3F3F46] rounded-lg transition-colors duration-200 cursor-pointer"
                                                            >
                                                                <div className="w-8 h-8 rounded bg-[#3F3F46] flex items-center justify-center overflow-hidden">
                                                                    {sug.thumbnail ? (
                                                                        <img src={sug.thumbnail} alt={sug.name} className="w-full h-full object-cover" />
                                                                    ) : (
                                                                        <config.icon className="w-4 h-4 text-[#71717A]" />
                                                                    )}
                                                                </div>
                                                                <span className="flex-1 text-left text-sm font-body text-[#FAFAFA]">{sug.name}</span>
                                                                <span className="text-xs font-heading text-[#10B981]">{sug.match}% 匹配</span>
                                                            </motion.button>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}

                                            {/* Action Buttons */}
                                            <div className="flex gap-2">
                                                <motion.button
                                                    whileHover={{ scale: 1.02 }}
                                                    whileTap={{ scale: 0.98 }}
                                                    onClick={() => onGenerate(asset.id)}
                                                    className="flex-1 flex items-center justify-center gap-2 py-2 bg-[#10B981] hover:bg-[#059669] text-white rounded-lg text-sm font-heading font-medium transition-colors duration-200 cursor-pointer glow-emerald"
                                                >
                                                    <Sparkles className="w-4 h-4" />
                                                    生成候选
                                                </motion.button>
                                                <motion.button
                                                    whileHover={{ scale: 1.02 }}
                                                    whileTap={{ scale: 0.98 }}
                                                    onClick={() => onSelect(asset.id)}
                                                    className="flex-1 flex items-center justify-center gap-2 py-2 bg-[#27272A] hover:bg-[#3F3F46] text-[#FAFAFA] border border-[#3F3F46] rounded-lg text-sm font-heading font-medium transition-colors duration-200 cursor-pointer"
                                                >
                                                    <Search className="w-4 h-4" />
                                                    手动选择
                                                </motion.button>
                                            </div>

                                            {/* Skip */}
                                            <button
                                                onClick={() => onSkip(asset.id)}
                                                className="w-full text-center text-xs text-[#71717A] hover:text-[#FAFAFA] transition-colors duration-200 cursor-pointer"
                                            >
                                                跳过此资产
                                            </button>
                                        </div>
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </div>
                    )
                })}
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-[#27272A] bg-[#000000]/50">
                <motion.button
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.99 }}
                    onClick={onConfirmAll}
                    className="w-full flex items-center justify-center gap-2 py-3 bg-[#10B981] hover:bg-[#059669] text-white rounded-xl font-heading font-semibold transition-colors duration-200 cursor-pointer glow-emerald"
                >
                    <Check className="w-5 h-5" />
                    全部确认并继续
                </motion.button>
            </div>
        </motion.div>
    )
}
