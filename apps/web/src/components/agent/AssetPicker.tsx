'use client'

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
    X, Search, User, MapPin, Package, Palette,
    Plus, Check, Filter, Clock, Star
} from 'lucide-react'
import { cn } from '@/lib/utils'

export interface Asset {
    id: string
    type: 'character' | 'scene' | 'prop' | 'style'
    name: string
    thumbnail?: string
    tags?: string[]
    createdAt?: number
    usageCount?: number
}

interface AssetPickerProps {
    type: 'character' | 'scene' | 'prop' | 'style'
    isOpen: boolean
    onClose: () => void
    onSelect: (asset: Asset) => void
    onCreate?: () => void
}

const typeConfig = {
    character: { icon: User, label: '角色', color: '#F43F5E' },
    scene: { icon: MapPin, label: '场景', color: '#3B82F6' },
    prop: { icon: Package, label: '物品', color: '#F59E0B' },
    style: { icon: Palette, label: '风格', color: '#8B5CF6' },
}

// Demo assets
const demoAssets: Asset[] = [
    { id: '1', type: 'character', name: '林知夏', tags: ['女主', '都市'], usageCount: 12 },
    { id: '2', type: 'character', name: '李云飞', tags: ['男主', '霸总'], usageCount: 8 },
    { id: '3', type: 'character', name: '王小雨', tags: ['闺蜜', '配角'], usageCount: 5 },
    { id: '4', type: 'scene', name: '雨夜旧书店', tags: ['室内', '温馨'], usageCount: 6 },
    { id: '5', type: 'scene', name: '都市天际线', tags: ['室外', '都市'], usageCount: 4 },
    { id: '6', type: 'scene', name: '咖啡馆', tags: ['室内', '约会'], usageCount: 3 },
    { id: '7', type: 'prop', name: '红色围巾', tags: ['服饰', '信物'], usageCount: 7 },
    { id: '8', type: 'prop', name: '旧书', tags: ['物品', '过去'], usageCount: 2 },
    { id: '9', type: 'style', name: '韩漫写实', tags: ['写实', '精美'], usageCount: 15 },
    { id: '10', type: 'style', name: '暖色调', tags: ['色调', '温馨'], usageCount: 10 },
    { id: '11', type: 'style', name: '电影感', tags: ['质感', '高级'], usageCount: 8 },
]

type SortOption = 'recent' | 'popular' | 'name'

export function AssetPicker({ type, isOpen, onClose, onSelect, onCreate }: AssetPickerProps) {
    const [search, setSearch] = useState('')
    const [sort, setSort] = useState<SortOption>('recent')
    const [selectedId, setSelectedId] = useState<string | null>(null)

    const config = typeConfig[type]

    // Filter and sort assets
    const filteredAssets = demoAssets
        .filter(a => a.type === type)
        .filter(a =>
            a.name.toLowerCase().includes(search.toLowerCase()) ||
            a.tags?.some(t => t.toLowerCase().includes(search.toLowerCase()))
        )
        .sort((a, b) => {
            if (sort === 'popular') return (b.usageCount || 0) - (a.usageCount || 0)
            if (sort === 'name') return a.name.localeCompare(b.name)
            return 0 // recent - keep original order
        })

    const handleConfirm = () => {
        const asset = filteredAssets.find(a => a.id === selectedId)
        if (asset) {
            onSelect(asset)
            onClose()
        }
    }

    // Reset on close
    useEffect(() => {
        if (!isOpen) {
            setSearch('')
            setSelectedId(null)
        }
    }, [isOpen])

    return (
        <AnimatePresence>
            {isOpen && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="fixed inset-0 z-50 flex items-center justify-center p-4"
                >
                    {/* Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={onClose}
                        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                    />

                    {/* Modal */}
                    <motion.div
                        initial={{ scale: 0.95, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        exit={{ scale: 0.95, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="relative w-full max-w-lg bg-[#0C0C0C] border border-[#27272A] rounded-2xl shadow-2xl overflow-hidden"
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between px-5 py-4 border-b border-[#27272A]">
                            <div className="flex items-center gap-3">
                                <div
                                    className="w-9 h-9 rounded-lg flex items-center justify-center"
                                    style={{ backgroundColor: `${config.color}20` }}
                                >
                                    <config.icon className="w-5 h-5" style={{ color: config.color }} />
                                </div>
                                <h2 className="font-heading font-semibold text-[#FAFAFA]">选择{config.label}</h2>
                            </div>
                            <motion.button
                                whileHover={{ scale: 1.1 }}
                                whileTap={{ scale: 0.9 }}
                                onClick={onClose}
                                className="p-2 rounded-lg text-[#71717A] hover:text-[#FAFAFA] hover:bg-[#27272A] transition-colors cursor-pointer"
                            >
                                <X className="w-5 h-5" />
                            </motion.button>
                        </div>

                        {/* Search & Filter */}
                        <div className="px-5 py-3 border-b border-[#27272A] flex gap-3">
                            <div className="flex-1 relative">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#71717A]" />
                                <input
                                    type="text"
                                    value={search}
                                    onChange={(e) => setSearch(e.target.value)}
                                    placeholder={`搜索${config.label}...`}
                                    className="input pl-10 py-2 text-sm"
                                />
                            </div>
                            <div className="flex bg-[#18181B] border border-[#3F3F46] rounded-lg p-1">
                                {[
                                    { id: 'recent' as const, icon: Clock, label: '最近' },
                                    { id: 'popular' as const, icon: Star, label: '常用' },
                                ].map(({ id, icon: Icon, label }) => (
                                    <motion.button
                                        key={id}
                                        whileHover={{ scale: 1.02 }}
                                        whileTap={{ scale: 0.98 }}
                                        onClick={() => setSort(id)}
                                        className={cn(
                                            "px-3 py-1.5 rounded-md text-xs font-heading transition-colors cursor-pointer flex items-center gap-1.5",
                                            sort === id
                                                ? "bg-[#10B981] text-white"
                                                : "text-[#71717A] hover:text-[#FAFAFA]"
                                        )}
                                    >
                                        <Icon className="w-3.5 h-3.5" />
                                        {label}
                                    </motion.button>
                                ))}
                            </div>
                        </div>

                        {/* Asset Grid */}
                        <div className="p-5 max-h-[320px] overflow-y-auto">
                            <div className="grid grid-cols-4 gap-3">
                                {filteredAssets.map((asset) => (
                                    <motion.button
                                        key={asset.id}
                                        whileHover={{ scale: 1.03 }}
                                        whileTap={{ scale: 0.97 }}
                                        onClick={() => setSelectedId(asset.id)}
                                        className={cn(
                                            "relative p-3 rounded-xl border transition-all duration-200 cursor-pointer text-center",
                                            selectedId === asset.id
                                                ? "bg-[#10B981]/10 border-[#10B981] ring-1 ring-[#10B981]"
                                                : "bg-[#18181B] border-[#27272A] hover:border-[#3F3F46]"
                                        )}
                                    >
                                        {/* Thumbnail */}
                                        <div
                                            className="w-12 h-12 mx-auto rounded-lg flex items-center justify-center mb-2"
                                            style={{ backgroundColor: `${config.color}20` }}
                                        >
                                            {asset.thumbnail ? (
                                                <img src={asset.thumbnail} alt={asset.name} className="w-full h-full object-cover rounded-lg" />
                                            ) : (
                                                <config.icon className="w-6 h-6" style={{ color: config.color }} />
                                            )}
                                        </div>

                                        {/* Name */}
                                        <span className="text-xs font-body text-[#FAFAFA] truncate block">{asset.name}</span>

                                        {/* Usage count */}
                                        {asset.usageCount && (
                                            <span className="text-[10px] text-[#71717A] font-heading mt-0.5 block">
                                                使用 {asset.usageCount} 次
                                            </span>
                                        )}

                                        {/* Selected checkmark */}
                                        {selectedId === asset.id && (
                                            <motion.div
                                                initial={{ scale: 0 }}
                                                animate={{ scale: 1 }}
                                                className="absolute -top-1 -right-1 w-5 h-5 bg-[#10B981] rounded-full flex items-center justify-center"
                                            >
                                                <Check className="w-3 h-3 text-white" />
                                            </motion.div>
                                        )}
                                    </motion.button>
                                ))}

                                {/* Create New */}
                                {onCreate && (
                                    <motion.button
                                        whileHover={{ scale: 1.03 }}
                                        whileTap={{ scale: 0.97 }}
                                        onClick={onCreate}
                                        className="p-3 rounded-xl border border-dashed border-[#3F3F46] hover:border-[#10B981] transition-colors cursor-pointer text-center"
                                    >
                                        <div className="w-12 h-12 mx-auto rounded-lg bg-[#27272A] flex items-center justify-center mb-2">
                                            <Plus className="w-6 h-6 text-[#71717A]" />
                                        </div>
                                        <span className="text-xs font-body text-[#71717A]">新建</span>
                                    </motion.button>
                                )}
                            </div>

                            {filteredAssets.length === 0 && (
                                <div className="text-center py-8">
                                    <config.icon className="w-10 h-10 mx-auto text-[#3F3F46] mb-3" />
                                    <p className="text-sm text-[#71717A] font-body">没有找到匹配的{config.label}</p>
                                </div>
                            )}
                        </div>

                        {/* Footer */}
                        <div className="px-5 py-4 border-t border-[#27272A] flex justify-end gap-3">
                            <motion.button
                                whileHover={{ scale: 1.02 }}
                                whileTap={{ scale: 0.98 }}
                                onClick={onClose}
                                className="px-5 py-2.5 rounded-xl text-sm font-heading font-medium text-[#71717A] hover:text-[#FAFAFA] hover:bg-[#27272A] transition-colors cursor-pointer"
                            >
                                取消
                            </motion.button>
                            <motion.button
                                whileHover={{ scale: 1.02 }}
                                whileTap={{ scale: 0.98 }}
                                onClick={handleConfirm}
                                disabled={!selectedId}
                                className={cn(
                                    "px-5 py-2.5 rounded-xl text-sm font-heading font-semibold transition-all cursor-pointer",
                                    selectedId
                                        ? "bg-[#10B981] hover:bg-[#059669] text-white glow-emerald"
                                        : "bg-[#27272A] text-[#52525B] cursor-not-allowed"
                                )}
                            >
                                确认选择
                            </motion.button>
                        </div>
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>
    )
}
