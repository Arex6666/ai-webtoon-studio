'use client'

import { useState, useRef } from 'react'
import { motion } from 'framer-motion'
import {
    Play, Pause, Volume2, VolumeX, Music, Mic,
    ChevronLeft, ChevronRight, Plus, Trash2, GripHorizontal
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface TimelineTrack {
    id: string
    type: 'video' | 'audio' | 'music'
    name: string
    clips: {
        id: string
        start: number
        duration: number
        label: string
    }[]
    muted: boolean
}

interface TimelineProps {
    tracks: TimelineTrack[]
    currentTime: number
    duration: number
    isPlaying: boolean
    onTimeChange: (time: number) => void
    onTogglePlay: () => void
    onTrackMute: (trackId: string) => void
}

const trackTypeConfig = {
    video: { icon: Play, color: '#10B981', label: '视频' },
    audio: { icon: Mic, color: '#3B82F6', label: '配音' },
    music: { icon: Music, color: '#8B5CF6', label: '音乐' },
}

export function Timeline({
    tracks,
    currentTime,
    duration,
    isPlaying,
    onTimeChange,
    onTogglePlay,
    onTrackMute
}: TimelineProps) {
    const [zoom, setZoom] = useState(1) // 1 = 100%
    const timelineRef = useRef<HTMLDivElement>(null)

    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60)
        const secs = Math.floor(seconds % 60)
        return `${mins}:${secs.toString().padStart(2, '0')}`
    }

    const handleTimelineClick = (e: React.MouseEvent<HTMLDivElement>) => {
        if (timelineRef.current) {
            const rect = timelineRef.current.getBoundingClientRect()
            const x = e.clientX - rect.left
            const percentage = x / rect.width
            onTimeChange(percentage * duration)
        }
    }

    const pixelsPerSecond = 50 * zoom

    return (
        <div className="h-full flex flex-col bg-[#0C0C0C] border-t border-[#27272A]">
            {/* Controls */}
            <div className="flex items-center justify-between px-4 py-2 border-b border-[#27272A]">
                <div className="flex items-center gap-3">
                    {/* Playback */}
                    <motion.button
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        onClick={onTogglePlay}
                        className="p-2 rounded-lg bg-[#10B981] hover:bg-[#059669] text-white transition-colors cursor-pointer"
                    >
                        {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                    </motion.button>

                    {/* Time Display */}
                    <div className="flex items-center gap-2 text-sm font-heading">
                        <span className="text-[#FAFAFA]">{formatTime(currentTime)}</span>
                        <span className="text-[#52525B]">/</span>
                        <span className="text-[#71717A]">{formatTime(duration)}</span>
                    </div>
                </div>

                {/* Zoom */}
                <div className="flex items-center gap-2">
                    <motion.button
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        onClick={() => setZoom(Math.max(0.5, zoom - 0.25))}
                        className="p-1.5 rounded-lg text-[#71717A] hover:text-[#FAFAFA] hover:bg-[#27272A] transition-colors cursor-pointer"
                    >
                        <ChevronLeft className="w-4 h-4" />
                    </motion.button>
                    <span className="text-xs font-heading text-[#71717A] w-12 text-center">{Math.round(zoom * 100)}%</span>
                    <motion.button
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        onClick={() => setZoom(Math.min(3, zoom + 0.25))}
                        className="p-1.5 rounded-lg text-[#71717A] hover:text-[#FAFAFA] hover:bg-[#27272A] transition-colors cursor-pointer"
                    >
                        <ChevronRight className="w-4 h-4" />
                    </motion.button>
                </div>
            </div>

            {/* Timeline Content */}
            <div className="flex-1 flex overflow-hidden">
                {/* Track Labels */}
                <div className="w-32 flex-shrink-0 border-r border-[#27272A]">
                    {/* Time ruler placeholder */}
                    <div className="h-6 border-b border-[#27272A]" />

                    {/* Tracks */}
                    {tracks.map((track) => {
                        const config = trackTypeConfig[track.type]
                        return (
                            <div
                                key={track.id}
                                className="h-12 flex items-center gap-2 px-3 border-b border-[#27272A]"
                            >
                                <config.icon className="w-4 h-4" style={{ color: config.color }} />
                                <span className="flex-1 text-xs font-body text-[#FAFAFA] truncate">{track.name}</span>
                                <motion.button
                                    whileHover={{ scale: 1.1 }}
                                    whileTap={{ scale: 0.9 }}
                                    onClick={() => onTrackMute(track.id)}
                                    className={cn(
                                        "p-1 rounded transition-colors cursor-pointer",
                                        track.muted ? "text-[#F43F5E]" : "text-[#71717A] hover:text-[#FAFAFA]"
                                    )}
                                >
                                    {track.muted ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
                                </motion.button>
                            </div>
                        )
                    })}
                </div>

                {/* Timeline Ruler & Tracks */}
                <div className="flex-1 overflow-x-auto" ref={timelineRef} onClick={handleTimelineClick}>
                    <div style={{ width: `${duration * pixelsPerSecond}px`, minWidth: '100%' }}>
                        {/* Time Ruler */}
                        <div className="h-6 relative border-b border-[#27272A] bg-[#18181B]/50">
                            {Array.from({ length: Math.ceil(duration) + 1 }).map((_, i) => (
                                <div
                                    key={i}
                                    className="absolute top-0 bottom-0 flex flex-col items-center"
                                    style={{ left: `${i * pixelsPerSecond}px` }}
                                >
                                    <div className="w-px h-2 bg-[#3F3F46]" />
                                    <span className="text-[10px] font-heading text-[#52525B] mt-0.5">{i}s</span>
                                </div>
                            ))}

                            {/* Playhead */}
                            <motion.div
                                className="absolute top-0 bottom-0 w-0.5 bg-[#10B981] z-10"
                                style={{ left: `${currentTime * pixelsPerSecond}px` }}
                                animate={{ left: `${currentTime * pixelsPerSecond}px` }}
                                transition={{ duration: 0.1 }}
                            >
                                <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-3 h-3 bg-[#10B981] rotate-45" />
                            </motion.div>
                        </div>

                        {/* Tracks */}
                        {tracks.map((track) => {
                            const config = trackTypeConfig[track.type]
                            return (
                                <div key={track.id} className="h-12 relative border-b border-[#27272A]">
                                    {/* Clips */}
                                    {track.clips.map((clip) => (
                                        <motion.div
                                            key={clip.id}
                                            initial={{ opacity: 0, scale: 0.95 }}
                                            animate={{ opacity: 1, scale: 1 }}
                                            className="absolute top-1 bottom-1 rounded-lg border overflow-hidden cursor-pointer group"
                                            style={{
                                                left: `${clip.start * pixelsPerSecond}px`,
                                                width: `${clip.duration * pixelsPerSecond}px`,
                                                backgroundColor: `${config.color}20`,
                                                borderColor: `${config.color}40`,
                                            }}
                                        >
                                            <div className="absolute inset-0 flex items-center px-2">
                                                <GripHorizontal className="w-3 h-3 text-[#52525B] mr-1 opacity-0 group-hover:opacity-100 transition-opacity" />
                                                <span className="text-[10px] font-body truncate" style={{ color: config.color }}>
                                                    {clip.label}
                                                </span>
                                            </div>
                                        </motion.div>
                                    ))}

                                    {/* Playhead line */}
                                    <div
                                        className="absolute top-0 bottom-0 w-0.5 bg-[#10B981]/50 pointer-events-none"
                                        style={{ left: `${currentTime * pixelsPerSecond}px` }}
                                    />
                                </div>
                            )
                        })}
                    </div>
                </div>
            </div>
        </div>
    )
}
