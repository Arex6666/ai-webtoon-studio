'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import {
    Play, Pause, SkipBack, SkipForward, Maximize2,
    Type, Layers, Shield, ZoomIn, ZoomOut
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface PreviewCanvasProps {
    aspectRatio: '9:16' | '16:9' | '4:5' | '1:1'
    imageUrl?: string
    showSubtitles?: boolean
    showLayers?: boolean
    showSafeZone?: boolean
    isPlaying?: boolean
    onTogglePlay?: () => void
}

const aspectRatioStyles = {
    '9:16': 'aspect-[9/16] max-h-[70vh]',
    '16:9': 'aspect-video max-h-[50vh]',
    '4:5': 'aspect-[4/5] max-h-[65vh]',
    '1:1': 'aspect-square max-h-[60vh]',
}

export function PreviewCanvas({
    aspectRatio,
    imageUrl,
    showSubtitles = true,
    showLayers = false,
    showSafeZone = false,
    isPlaying = false,
    onTogglePlay
}: PreviewCanvasProps) {
    const [zoom, setZoom] = useState(100)

    return (
        <div className="h-full flex flex-col items-center justify-center p-6 bg-[#000000]">
            {/* Canvas Container */}
            <div className="relative flex items-center justify-center flex-1 w-full">
                <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    style={{ transform: `scale(${zoom / 100})` }}
                    className={cn(
                        "relative bg-[#18181B] rounded-lg overflow-hidden shadow-2xl border border-[#27272A]",
                        aspectRatioStyles[aspectRatio]
                    )}
                >
                    {/* Image or Placeholder */}
                    {imageUrl ? (
                        <img src={imageUrl} alt="Preview" className="w-full h-full object-cover" />
                    ) : (
                        <div className="absolute inset-0 flex items-center justify-center">
                            <div className="text-center">
                                <Play className="w-16 h-16 text-[#3F3F46] mx-auto mb-4" />
                                <p className="text-[#52525B] font-body text-sm">预览区域</p>
                            </div>
                        </div>
                    )}

                    {/* Safe Zone Overlay */}
                    {showSafeZone && (
                        <div className="absolute inset-0 pointer-events-none">
                            <div className="absolute inset-[10%] border-2 border-dashed border-[#10B981]/30 rounded" />
                            <div className="absolute top-2 left-2 px-2 py-0.5 bg-[#10B981]/20 rounded text-[10px] text-[#10B981] font-heading">
                                安全区
                            </div>
                        </div>
                    )}

                    {/* Layers Overlay */}
                    {showLayers && (
                        <div className="absolute inset-0 pointer-events-none">
                            <div className="absolute top-2 right-2 flex flex-col gap-1">
                                {['角色层', '背景层', '前景层'].map((layer, idx) => (
                                    <div
                                        key={layer}
                                        className="px-2 py-0.5 bg-black/60 backdrop-blur-sm rounded text-[10px] text-white font-heading"
                                    >
                                        {layer}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Subtitles */}
                    {showSubtitles && (
                        <div className="absolute bottom-4 left-4 right-4 text-center">
                            <div className="inline-block px-4 py-2 bg-black/70 backdrop-blur-sm rounded-lg">
                                <p className="text-white font-body text-sm">示例字幕文本</p>
                            </div>
                        </div>
                    )}
                </motion.div>
            </div>

            {/* Controls */}
            <div className="flex items-center justify-center gap-4 mt-6">
                {/* Playback */}
                <div className="flex items-center gap-2 bg-[#18181B] border border-[#27272A] rounded-xl p-1">
                    <motion.button
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        className="p-2 rounded-lg text-[#71717A] hover:text-[#FAFAFA] hover:bg-[#27272A] transition-colors cursor-pointer"
                    >
                        <SkipBack className="w-4 h-4" />
                    </motion.button>
                    <motion.button
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        onClick={onTogglePlay}
                        className="p-2 rounded-lg bg-[#10B981] hover:bg-[#059669] text-white transition-colors cursor-pointer"
                    >
                        {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                    </motion.button>
                    <motion.button
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        className="p-2 rounded-lg text-[#71717A] hover:text-[#FAFAFA] hover:bg-[#27272A] transition-colors cursor-pointer"
                    >
                        <SkipForward className="w-4 h-4" />
                    </motion.button>
                </div>

                {/* Zoom */}
                <div className="flex items-center gap-2 bg-[#18181B] border border-[#27272A] rounded-xl p-1">
                    <motion.button
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        onClick={() => setZoom(Math.max(50, zoom - 10))}
                        className="p-2 rounded-lg text-[#71717A] hover:text-[#FAFAFA] hover:bg-[#27272A] transition-colors cursor-pointer"
                    >
                        <ZoomOut className="w-4 h-4" />
                    </motion.button>
                    <span className="px-2 text-xs font-heading text-[#71717A] min-w-[40px] text-center">{zoom}%</span>
                    <motion.button
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        onClick={() => setZoom(Math.min(200, zoom + 10))}
                        className="p-2 rounded-lg text-[#71717A] hover:text-[#FAFAFA] hover:bg-[#27272A] transition-colors cursor-pointer"
                    >
                        <ZoomIn className="w-4 h-4" />
                    </motion.button>
                </div>

                {/* Fullscreen */}
                <motion.button
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.9 }}
                    className="p-2 bg-[#18181B] border border-[#27272A] rounded-xl text-[#71717A] hover:text-[#FAFAFA] hover:bg-[#27272A] transition-colors cursor-pointer"
                >
                    <Maximize2 className="w-4 h-4" />
                </motion.button>
            </div>

            {/* Toggle Buttons */}
            <div className="flex items-center gap-2 mt-4">
                {[
                    { id: 'subtitles', label: '字幕', icon: Type, active: showSubtitles },
                    { id: 'layers', label: '图层', icon: Layers, active: showLayers },
                    { id: 'safezone', label: '安全区', icon: Shield, active: showSafeZone },
                ].map(({ id, label, icon: Icon, active }) => (
                    <motion.button
                        key={id}
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        className={cn(
                            "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-heading transition-colors cursor-pointer",
                            active
                                ? "bg-[#10B981]/20 text-[#10B981]"
                                : "bg-[#18181B] text-[#71717A] hover:text-[#FAFAFA]"
                        )}
                    >
                        <Icon className="w-3.5 h-3.5" />
                        {label}
                    </motion.button>
                ))}
            </div>
        </div>
    )
}
