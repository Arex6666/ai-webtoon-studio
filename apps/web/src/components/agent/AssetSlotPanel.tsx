'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
    User, MapPin, Package, Palette, Plus, Lock, Unlock,
    RefreshCw, ExternalLink, Check, ChevronDown, Loader2
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { AssetPicker, Asset } from './AssetPicker'

export interface AssetBinding {
    id: string
    type: 'character' | 'scene' | 'prop' | 'style'
    name: string
    thumbnail?: string
    locked: boolean
    version?: number
}

interface SlotConfig {
    type: 'character' | 'scene' | 'prop' | 'style'
    label: string
    icon: React.ElementType
    color: string
    multiple: boolean
}

const slotConfigs: SlotConfig[] = [
    { type: 'character', label: '角色', icon: User, color: '#F43F5E', multiple: true },
    { type: 'scene', label: '场景', icon: MapPin, color: '#3B82F6', multiple: false },
    { type: 'prop', label: '物品', icon: Package, color: '#F59E0B', multiple: true },
    { type: 'style', label: '风格锚点', icon: Palette, color: '#8B5CF6', multiple: true },
]

interface AssetSlotProps {
    config: SlotConfig
    bindings: AssetBinding[]
    onAdd: () => void
    onRemove: (id: string) => void
    onToggleLock: (id: string) => void
    onRegenerate: (id: string) => void
    onOpenLibrary: (id: string) => void
    regeneratingId: string | null
}

function AssetSlot({ config, bindings, onAdd, onRemove, onToggleLock, onRegenerate, onOpenLibrary, regeneratingId }: AssetSlotProps) {
    const [expanded, setExpanded] = useState(true)
    const slotBindings = bindings.filter(b => b.type === config.type)

    return (
        <div className="border-b border-[#27272A] last:border-b-0">
            {/* Slot Header */}
            <button
                onClick={() => setExpanded(!expanded)}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-[#18181B] transition-colors duration-200 cursor-pointer"
            >
                <div
                    className="w-8 h-8 rounded-lg flex items-center justify-center"
                    style={{ backgroundColor: `${config.color}20` }}
                >
                    <config.icon className="w-4 h-4" style={{ color: config.color }} />
                </div>
                <span className="flex-1 text-left font-heading text-sm font-medium text-[#FAFAFA]">
                    {config.label}
                </span>
                {slotBindings.length > 0 && (
                    <span className="px-2 py-0.5 rounded text-xs font-heading" style={{ backgroundColor: `${config.color}20`, color: config.color }}>
                        {slotBindings.length}
                    </span>
                )}
                <motion.div animate={{ rotate: expanded ? 180 : 0 }} transition={{ duration: 0.15 }}>
                    <ChevronDown className="w-4 h-4 text-[#71717A]" />
                </motion.div>
            </button>

            {/* Slot Content */}
            <AnimatePresence>
                {expanded && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden"
                    >
                        <div className="px-4 pb-3 space-y-2">
                            {/* Bindings */}
                            {slotBindings.map((binding) => {
                                const isRegenerating = regeneratingId === binding.id

                                return (
                                    <motion.div
                                        key={binding.id}
                                        initial={{ opacity: 0, x: -10 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        className="flex items-center gap-2 p-2 bg-[#18181B] rounded-lg border border-[#27272A] group"
                                    >
                                        {/* Thumbnail */}
                                        <div className="w-10 h-10 rounded-lg bg-[#27272A] flex items-center justify-center overflow-hidden">
                                            {binding.thumbnail ? (
                                                <img src={binding.thumbnail} alt={binding.name} className="w-full h-full object-cover" />
                                            ) : (
                                                <config.icon className="w-5 h-5 text-[#52525B]" />
                                            )}
                                        </div>

                                        {/* Name */}
                                        <div className="flex-1 min-w-0">
                                            <span className="text-sm font-body text-[#FAFAFA] truncate block">{binding.name}</span>
                                            {binding.version && (
                                                <span className="text-xs text-[#71717A] font-heading">v{binding.version}</span>
                                            )}
                                        </div>

                                        {/* Actions */}
                                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                                            <motion.button
                                                whileHover={{ scale: 1.1 }}
                                                whileTap={{ scale: 0.9 }}
                                                onClick={() => onRegenerate(binding.id)}
                                                disabled={isRegenerating}
                                                className="p-1.5 rounded-md hover:bg-[#27272A] text-[#71717A] hover:text-[#FAFAFA] transition-colors cursor-pointer disabled:opacity-50"
                                                title="生成候选"
                                            >
                                                {isRegenerating ? (
                                                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                                ) : (
                                                    <RefreshCw className="w-3.5 h-3.5" />
                                                )}
                                            </motion.button>
                                            <motion.button
                                                whileHover={{ scale: 1.1 }}
                                                whileTap={{ scale: 0.9 }}
                                                onClick={() => onOpenLibrary(binding.id)}
                                                className="p-1.5 rounded-md hover:bg-[#27272A] text-[#71717A] hover:text-[#FAFAFA] transition-colors cursor-pointer"
                                                title="替换资产"
                                            >
                                                <ExternalLink className="w-3.5 h-3.5" />
                                            </motion.button>
                                        </div>

                                        {/* Lock Button */}
                                        <motion.button
                                            whileHover={{ scale: 1.1 }}
                                            whileTap={{ scale: 0.9 }}
                                            onClick={() => onToggleLock(binding.id)}
                                            className={cn(
                                                "p-1.5 rounded-md transition-colors cursor-pointer",
                                                binding.locked
                                                    ? "bg-[#10B981]/20 text-[#10B981]"
                                                    : "bg-[#27272A] text-[#71717A] hover:text-[#FAFAFA]"
                                            )}
                                            title={binding.locked ? "已锁定" : "点击锁定"}
                                        >
                                            {binding.locked ? <Lock className="w-3.5 h-3.5" /> : <Unlock className="w-3.5 h-3.5" />}
                                        </motion.button>
                                    </motion.div>
                                )
                            })}

                            {/* Add Button */}
                            {(config.multiple || slotBindings.length === 0) && (
                                <motion.button
                                    whileHover={{ scale: 1.01 }}
                                    whileTap={{ scale: 0.99 }}
                                    onClick={onAdd}
                                    className="w-full flex items-center justify-center gap-2 py-2 border border-dashed border-[#3F3F46] rounded-lg text-[#71717A] hover:text-[#FAFAFA] hover:border-[#52525B] transition-colors duration-200 cursor-pointer"
                                >
                                    <Plus className="w-4 h-4" />
                                    <span className="text-sm font-body">添加{config.label}</span>
                                </motion.button>
                            )}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}

interface AssetSlotPanelProps {
    panelId: string
    panelNumber: number
    bindings: AssetBinding[]
    onBindingChange: (bindings: AssetBinding[]) => void
}

export function AssetSlotPanel({ panelId, panelNumber, bindings, onBindingChange }: AssetSlotPanelProps) {
    const [pickerOpen, setPickerOpen] = useState(false)
    const [pickerType, setPickerType] = useState<AssetBinding['type']>('character')
    const [pickerMode, setPickerMode] = useState<'add' | 'replace'>('add')
    const [replaceBindingId, setReplaceBindingId] = useState<string | null>(null)
    const [regeneratingId, setRegeneratingId] = useState<string | null>(null)
    const [toast, setToast] = useState<string | null>(null)

    const showToast = (message: string) => {
        setToast(message)
        setTimeout(() => setToast(null), 2500)
    }

    const handleAdd = (type: AssetBinding['type']) => {
        setPickerType(type)
        setPickerMode('add')
        setReplaceBindingId(null)
        setPickerOpen(true)
    }

    const handleRemove = (id: string) => {
        onBindingChange(bindings.filter(b => b.id !== id))
    }

    const handleToggleLock = (id: string) => {
        onBindingChange(bindings.map(b =>
            b.id === id ? { ...b, locked: !b.locked } : b
        ))
        const binding = bindings.find(b => b.id === id)
        if (binding) {
            showToast(binding.locked ? `已解锁 ${binding.name}` : `已锁定 ${binding.name}`)
        }
    }

    const handleRegenerate = async (id: string) => {
        setRegeneratingId(id)
        // Simulate API call
        await new Promise(resolve => setTimeout(resolve, 1500))
        setRegeneratingId(null)
        showToast('已生成 3 个候选资产')
    }

    const handleOpenLibrary = (id: string) => {
        const binding = bindings.find(b => b.id === id)
        if (binding) {
            setPickerType(binding.type)
            setPickerMode('replace')
            setReplaceBindingId(id)
            setPickerOpen(true)
        }
    }

    const handleAssetSelect = (asset: Asset) => {
        if (pickerMode === 'add') {
            const newBinding: AssetBinding = {
                id: `${asset.type}_${Date.now()}`,
                type: asset.type,
                name: asset.name,
                thumbnail: asset.thumbnail,
                locked: false,
                version: 1
            }
            onBindingChange([...bindings, newBinding])
            showToast(`已添加 ${asset.name}`)
        } else if (pickerMode === 'replace' && replaceBindingId) {
            onBindingChange(bindings.map(b =>
                b.id === replaceBindingId
                    ? { ...b, name: asset.name, thumbnail: asset.thumbnail, version: (b.version || 0) + 1 }
                    : b
            ))
            showToast(`已替换为 ${asset.name}`)
        }
        setPickerOpen(false)
    }

    return (
        <>
            <div className="bg-[#0C0C0C] border border-[#27272A] rounded-xl overflow-hidden">
                {/* Header */}
                <div className="flex items-center justify-between px-4 py-3 border-b border-[#27272A] bg-[#000000]/50">
                    <div className="flex items-center gap-2">
                        <span className="font-heading text-sm font-semibold text-[#FAFAFA]">资产绑定</span>
                        <span className="px-2 py-0.5 rounded bg-[#27272A] text-xs font-heading text-[#71717A]">
                            第{panelNumber}格
                        </span>
                    </div>
                    {bindings.every(b => b.locked) && bindings.length > 0 && (
                        <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-[#10B981]/20 text-xs font-heading text-[#10B981]">
                            <Check className="w-3 h-3" />
                            全部已锁定
                        </span>
                    )}
                </div>

                {/* Slots */}
                <div>
                    {slotConfigs.map((config) => (
                        <AssetSlot
                            key={config.type}
                            config={config}
                            bindings={bindings}
                            onAdd={() => handleAdd(config.type)}
                            onRemove={handleRemove}
                            onToggleLock={handleToggleLock}
                            onRegenerate={handleRegenerate}
                            onOpenLibrary={handleOpenLibrary}
                            regeneratingId={regeneratingId}
                        />
                    ))}
                </div>
            </div>

            {/* Asset Picker Modal */}
            <AssetPicker
                type={pickerType}
                isOpen={pickerOpen}
                onClose={() => setPickerOpen(false)}
                onSelect={handleAssetSelect}
                onCreate={() => {
                    setPickerOpen(false)
                    showToast('新建资产功能开发中')
                }}
            />

            {/* Toast Notification */}
            <AnimatePresence>
                {toast && (
                    <motion.div
                        initial={{ opacity: 0, y: 50 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 50 }}
                        className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 px-4 py-2.5 bg-[#18181B] border border-[#3F3F46] rounded-xl shadow-xl"
                    >
                        <span className="text-sm font-body text-[#FAFAFA]">{toast}</span>
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    )
}
