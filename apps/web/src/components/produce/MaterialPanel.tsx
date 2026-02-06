'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
    Layers, Wand2, Volume2, Image as ImageIcon,
    ChevronDown, Plus, Eye, EyeOff, Lock, Trash2, GripVertical
} from 'lucide-react'
import { cn } from '@/lib/utils'

type TabId = 'storyboard' | 'layers' | 'effects' | 'audio'

interface Layer {
    id: string
    name: string
    type: 'character' | 'background' | 'foreground' | 'effect'
    visible: boolean
    locked: boolean
    thumbnail?: string
}

interface MaterialPanelProps {
    panelId: string
    layers: Layer[]
    onLayerChange: (layers: Layer[]) => void
    onAddLayer: (type: Layer['type']) => void
}

const tabConfig: { id: TabId; label: string; icon: React.ElementType }[] = [
    { id: 'storyboard', label: '分镜', icon: ImageIcon },
    { id: 'layers', label: '图层', icon: Layers },
    { id: 'effects', label: '动效', icon: Wand2 },
    { id: 'audio', label: '音频', icon: Volume2 },
]

const layerTypeConfig = {
    character: { label: '角色', color: '#F43F5E' },
    background: { label: '背景', color: '#3B82F6' },
    foreground: { label: '前景', color: '#F59E0B' },
    effect: { label: '特效', color: '#8B5CF6' },
}

export function MaterialPanel({ panelId, layers, onLayerChange, onAddLayer }: MaterialPanelProps) {
    const [activeTab, setActiveTab] = useState<TabId>('layers')

    const toggleVisibility = (id: string) => {
        onLayerChange(layers.map(l => l.id === id ? { ...l, visible: !l.visible } : l))
    }

    const toggleLock = (id: string) => {
        onLayerChange(layers.map(l => l.id === id ? { ...l, locked: !l.locked } : l))
    }

    const removeLayer = (id: string) => {
        onLayerChange(layers.filter(l => l.id !== id))
    }

    return (
        <div className="h-full flex flex-col bg-[#0C0C0C] border-r border-[#27272A]">
            {/* Tabs */}
            <div className="flex border-b border-[#27272A]">
                {tabConfig.map((tab) => (
                    <motion.button
                        key={tab.id}
                        whileHover={{ backgroundColor: 'rgba(39, 39, 42, 0.5)' }}
                        onClick={() => setActiveTab(tab.id)}
                        className={cn(
                            "flex-1 flex flex-col items-center gap-1 py-3 text-xs font-heading transition-colors cursor-pointer border-b-2",
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
            <div className="flex-1 overflow-y-auto">
                <AnimatePresence mode="wait">
                    {activeTab === 'layers' && (
                        <motion.div
                            key="layers"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="p-3"
                        >
                            {/* Layer List */}
                            <div className="space-y-2">
                                {layers.map((layer, idx) => {
                                    const config = layerTypeConfig[layer.type]
                                    return (
                                        <motion.div
                                            key={layer.id}
                                            initial={{ opacity: 0, x: -10 }}
                                            animate={{ opacity: 1, x: 0 }}
                                            transition={{ delay: idx * 0.03 }}
                                            className={cn(
                                                "flex items-center gap-2 p-2 rounded-lg border transition-all duration-200 group",
                                                layer.visible
                                                    ? "bg-[#18181B] border-[#27272A]"
                                                    : "bg-[#18181B]/50 border-[#27272A]/50 opacity-60"
                                            )}
                                        >
                                            {/* Drag Handle */}
                                            <GripVertical className="w-4 h-4 text-[#3F3F46] cursor-grab" />

                                            {/* Thumbnail */}
                                            <div
                                                className="w-8 h-8 rounded flex items-center justify-center text-[10px] font-heading font-bold"
                                                style={{ backgroundColor: `${config.color}20`, color: config.color }}
                                            >
                                                {config.label[0]}
                                            </div>

                                            {/* Name */}
                                            <span className="flex-1 text-sm font-body text-[#FAFAFA] truncate">
                                                {layer.name}
                                            </span>

                                            {/* Actions */}
                                            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                                <button
                                                    onClick={() => toggleVisibility(layer.id)}
                                                    className="p-1 rounded hover:bg-[#27272A] text-[#71717A] hover:text-[#FAFAFA] transition-colors cursor-pointer"
                                                >
                                                    {layer.visible ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
                                                </button>
                                                <button
                                                    onClick={() => toggleLock(layer.id)}
                                                    className={cn(
                                                        "p-1 rounded transition-colors cursor-pointer",
                                                        layer.locked ? "text-[#F59E0B]" : "text-[#71717A] hover:text-[#FAFAFA] hover:bg-[#27272A]"
                                                    )}
                                                >
                                                    <Lock className="w-3.5 h-3.5" />
                                                </button>
                                                <button
                                                    onClick={() => removeLayer(layer.id)}
                                                    className="p-1 rounded hover:bg-[#F43F5E]/20 text-[#71717A] hover:text-[#F43F5E] transition-colors cursor-pointer"
                                                >
                                                    <Trash2 className="w-3.5 h-3.5" />
                                                </button>
                                            </div>
                                        </motion.div>
                                    )
                                })}
                            </div>

                            {/* Add Layer */}
                            <div className="mt-4 pt-4 border-t border-[#27272A]">
                                <div className="text-xs text-[#71717A] font-heading mb-2">添加图层</div>
                                <div className="grid grid-cols-2 gap-2">
                                    {Object.entries(layerTypeConfig).map(([type, config]) => (
                                        <motion.button
                                            key={type}
                                            whileHover={{ scale: 1.02 }}
                                            whileTap={{ scale: 0.98 }}
                                            onClick={() => onAddLayer(type as Layer['type'])}
                                            className="flex items-center justify-center gap-1.5 py-2 rounded-lg border border-dashed border-[#3F3F46] hover:border-[#52525B] text-[#71717A] hover:text-[#FAFAFA] transition-colors cursor-pointer"
                                        >
                                            <Plus className="w-3.5 h-3.5" />
                                            <span className="text-xs font-heading">{config.label}</span>
                                        </motion.button>
                                    ))}
                                </div>
                            </div>
                        </motion.div>
                    )}

                    {activeTab === 'storyboard' && (
                        <motion.div
                            key="storyboard"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="p-4 text-center"
                        >
                            <ImageIcon className="w-8 h-8 mx-auto text-[#3F3F46] mb-2" />
                            <p className="text-sm text-[#71717A] font-body">当前分镜预览</p>
                        </motion.div>
                    )}

                    {activeTab === 'effects' && (
                        <motion.div
                            key="effects"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="p-4 text-center"
                        >
                            <Wand2 className="w-8 h-8 mx-auto text-[#3F3F46] mb-2" />
                            <p className="text-sm text-[#71717A] font-body">动效库</p>
                        </motion.div>
                    )}

                    {activeTab === 'audio' && (
                        <motion.div
                            key="audio"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="p-4 text-center"
                        >
                            <Volume2 className="w-8 h-8 mx-auto text-[#3F3F46] mb-2" />
                            <p className="text-sm text-[#71717A] font-body">音频轨道</p>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    )
}
