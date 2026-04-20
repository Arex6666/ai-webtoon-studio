'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
    X, Film, Loader2, CheckCircle2, AlertCircle,
    Play, Sparkles, ChevronLeft, ChevronRight, Clock, Zap
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { env } from '@/lib/utils/env'

/* ─────────── types ─────────── */

interface VideoJob {
    job_id: string
    image_url: string
    status: 'queued' | 'running' | 'succeeded' | 'failed'
    progress: number
    video_url?: string
    error?: string
}

interface PanelVideoMeta {
    camera_move?: string
    shot_type?: string
    actions?: string
    mood?: string
    weather?: string
    time_of_day?: string
    composition_notes?: string[]
    visual_prompt?: string
    lens_hint?: string
    duration_sec?: number
}

interface VideoGenerateDialogProps {
    isOpen: boolean
    onClose: () => void
    projectId: string
    episodeNum: number
    imageUrls: string[]
    panelMetadata?: PanelVideoMeta[]
}

/* ─────────── component ─────────── */

export function VideoGenerateDialog({
    isOpen,
    onClose,
    projectId,
    episodeNum,
    imageUrls,
    panelMetadata,
}: VideoGenerateDialogProps) {
    const [selectedImages, setSelectedImages] = useState<string[]>([])
    const [motionPrompt, setMotionPrompt] = useState('缓慢推进，镜头微微摇动，营造氛围感')
    const [durationSec, setDurationSec] = useState(5)
    const [isGenerating, setIsGenerating] = useState(false)
    const [jobs, setJobs] = useState<VideoJob[]>([])
    const [error, setError] = useState<string | null>(null)
    const pollRef = useRef<NodeJS.Timeout | null>(null)
    const stripRef = useRef<HTMLDivElement>(null)

    // 初始化全选
    useEffect(() => {
        if (isOpen && imageUrls.length > 0) setSelectedImages([...imageUrls])
    }, [isOpen, imageUrls])

    useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

    const toggleImage = (url: string) =>
        setSelectedImages(prev =>
            prev.includes(url) ? prev.filter(u => u !== url) : [...prev, url]
        )

    const scrollStrip = (dir: 'left' | 'right') => {
        stripRef.current?.scrollBy({ left: dir === 'left' ? -220 : 220, behavior: 'smooth' })
    }

    /* ───── API ───── */

    const handleGenerate = async () => {
        if (selectedImages.length === 0) return
        setIsGenerating(true)
        setError(null)

        try {
            const resp = await fetch(
                `${env.API_BASE_URL}/api/v1/agent/episode/${episodeNum}/generate-video`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        project_id: projectId,
                        image_urls: selectedImages,
                        motion_prompt: motionPrompt,
                        duration_sec: durationSec,
                        provider: 'doubao',
                        // 传入分镜结构化数据，只包含被选中图片对应的元数据
                        ...(panelMetadata && {
                            panel_metadata: selectedImages.map(url => {
                                const idx = imageUrls.indexOf(url)
                                return idx >= 0 && idx < panelMetadata.length
                                    ? panelMetadata[idx]
                                    : {}
                            }),
                        }),
                    }),
                }
            )
            if (!resp.ok) {
                const e = await resp.json().catch(() => ({ detail: '请求失败' }))
                throw new Error(e.detail || `HTTP ${resp.status}`)
            }
            const data = await resp.json()
            const newJobs: VideoJob[] = data.jobs.map((j: any) => ({
                job_id: j.job_id,
                image_url: j.image_url,
                status: j.status || 'queued',
                progress: 0,
            }))
            setJobs(newJobs)
            startPolling(newJobs.map(j => j.job_id))
        } catch (e: any) {
            setError(e.message || '视频生成请求失败')
            setIsGenerating(false)
        }
    }

    const startPolling = useCallback((jobIds: string[]) => {
        if (pollRef.current) clearInterval(pollRef.current)
        pollRef.current = setInterval(async () => {
            let allDone = true
            const updated = await Promise.all(
                jobIds.map(async (id) => {
                    try {
                        const r = await fetch(`${env.API_BASE_URL}/api/v1/agent/episode/video-jobs/${id}`)
                        if (!r.ok) return null
                        const d = await r.json()
                        if (d.status !== 'succeeded' && d.status !== 'failed') allDone = false
                        return d as VideoJob
                    } catch { allDone = false; return null }
                })
            )
            setJobs(prev => {
                const m = new Map(prev.map(j => [j.job_id, j]))
                updated.forEach(j => { if (j) m.set(j.job_id, j) })
                return Array.from(m.values())
            })
            if (allDone) { clearInterval(pollRef.current!); setIsGenerating(false) }
        }, 3000)
    }, [])

    /* ───── derived ───── */
    const done = jobs.filter(j => j.status === 'succeeded').length
    const failed = jobs.filter(j => j.status === 'failed').length

    if (!isOpen) return null

    /* ───── render ───── */
    return (
        <AnimatePresence>
            <motion.div
                key="video-backdrop"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md"
                onClick={e => { if (e.target === e.currentTarget && !isGenerating) onClose() }}
            >
                <motion.div
                    key="video-dialog"
                    initial={{ opacity: 0, y: 24, scale: 0.96 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 24, scale: 0.96 }}
                    transition={{ type: 'spring', stiffness: 400, damping: 32 }}
                    className={cn(
                        'w-[600px] max-h-[85vh] flex flex-col overflow-hidden',
                        'rounded-2xl border border-white/[0.06]',
                        'bg-gradient-to-b from-zinc-900/95 to-[#09090B]/98',
                        'shadow-[0_25px_60px_-12px_rgba(0,0,0,0.7)]',
                        'backdrop-blur-xl'
                    )}
                >
                    {/* ──── header ──── */}
                    <div className="relative flex items-center gap-3.5 px-6 py-5 border-b border-white/[0.06]">
                        {/* accent glow */}
                        <div className="absolute inset-x-0 -top-px h-px bg-gradient-to-r from-transparent via-cyan-500/40 to-transparent" />

                        <div className="relative w-11 h-11 rounded-xl bg-gradient-to-br from-cyan-500/20 to-purple-600/20 flex items-center justify-center ring-1 ring-white/[0.08]">
                            <Film className="w-5 h-5 text-cyan-400" />
                            <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-emerald-500 ring-2 ring-zinc-900" />
                        </div>

                        <div className="flex-1 min-w-0">
                            <h2 className="text-[15px] font-semibold text-zinc-100 tracking-tight">
                                生成视频
                            </h2>
                            <p className="text-[11px] text-zinc-500 mt-0.5 flex items-center gap-1.5">
                                <Zap className="w-3 h-3 text-cyan-500" />
                                豆包视频大模型 · 图生视频
                            </p>
                        </div>

                        {!isGenerating && (
                            <button
                                onClick={onClose}
                                className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-200 hover:bg-white/[0.06] transition-all duration-200 cursor-pointer"
                            >
                                <X className="w-4 h-4" />
                            </button>
                        )}
                    </div>

                    {/* ──── body ──── */}
                    <div className="flex-1 overflow-y-auto custom-scrollbar">
                        {jobs.length === 0 ? (
                            /* ── selection mode ── */
                            <div className="p-6 space-y-5">

                                {/* filmstrip header */}
                                <div className="flex items-center justify-between">
                                    <span className="text-[13px] font-medium text-zinc-300">
                                        选择分镜
                                        <span className="ml-2 text-[11px] text-zinc-600 font-normal">
                                            {selectedImages.length}/{imageUrls.length} 已选
                                        </span>
                                    </span>
                                    {imageUrls.length > 3 && (
                                        <div className="flex items-center gap-1">
                                            <button
                                                onClick={() => scrollStrip('left')}
                                                className="p-1 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05] transition-colors cursor-pointer"
                                            >
                                                <ChevronLeft className="w-3.5 h-3.5" />
                                            </button>
                                            <button
                                                onClick={() => scrollStrip('right')}
                                                className="p-1 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.05] transition-colors cursor-pointer"
                                            >
                                                <ChevronRight className="w-3.5 h-3.5" />
                                            </button>
                                        </div>
                                    )}
                                </div>

                                {imageUrls.length === 0 ? (
                                    <div className="flex items-center gap-2.5 px-4 py-3.5 rounded-xl bg-amber-500/[0.06] border border-amber-500/10 text-amber-400/80 text-[12px]">
                                        <AlertCircle className="w-4 h-4 flex-shrink-0" />
                                        剧本中未检测到分镜图片，请先完成剧本生成
                                    </div>
                                ) : (
                                    /* filmstrip */
                                    <div
                                        ref={stripRef}
                                        className="flex gap-2.5 overflow-x-auto pb-2 snap-x snap-mandatory hide-scrollbar"
                                    >
                                        {imageUrls.map((url, idx) => {
                                            const selected = selectedImages.includes(url)
                                            return (
                                                <motion.button
                                                    key={idx}
                                                    whileTap={{ scale: 0.97 }}
                                                    onClick={() => toggleImage(url)}
                                                    className={cn(
                                                        'group relative flex-shrink-0 snap-start',
                                                        'w-[140px] rounded-xl overflow-hidden cursor-pointer',
                                                        'transition-all duration-250',
                                                        'ring-1',
                                                        selected
                                                            ? 'ring-cyan-500/70 shadow-[0_0_15px_-3px_rgba(6,182,212,0.25)]'
                                                            : 'ring-white/[0.06] hover:ring-white/[0.15]'
                                                    )}
                                                >
                                                    {/* image */}
                                                    <div className="aspect-[3/4] bg-zinc-800">
                                                        <img
                                                            src={url}
                                                            alt={`分镜 ${idx + 1}`}
                                                            className={cn(
                                                                'w-full h-full object-cover transition-all duration-250',
                                                                selected ? 'brightness-100' : 'brightness-75 group-hover:brightness-90'
                                                            )}
                                                        />
                                                    </div>

                                                    {/* badge */}
                                                    <div className={cn(
                                                        'absolute top-1.5 right-1.5 w-5 h-5 rounded-full flex items-center justify-center transition-all duration-200',
                                                        selected
                                                            ? 'bg-cyan-500 shadow-[0_0_8px_rgba(6,182,212,0.4)]'
                                                            : 'bg-black/50 ring-1 ring-white/20'
                                                    )}>
                                                        {selected ? (
                                                            <CheckCircle2 className="w-3 h-3 text-white" />
                                                        ) : (
                                                            <span className="w-2 h-2 rounded-full bg-white/30" />
                                                        )}
                                                    </div>

                                                    {/* label */}
                                                    <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent px-2.5 pb-2 pt-5">
                                                        <span className="text-[11px] font-medium text-zinc-200">
                                                            分镜 {idx + 1}
                                                        </span>
                                                    </div>
                                                </motion.button>
                                            )
                                        })}
                                    </div>
                                )}

                                {/* ── settings ── */}
                                <div className="space-y-4 pt-1">
                                    {/* motion prompt */}
                                    <div>
                                        <label className="text-[12px] font-medium text-zinc-400 mb-1.5 block tracking-wide uppercase">
                                            运动提示词
                                        </label>
                                        <textarea
                                            value={motionPrompt}
                                            onChange={e => setMotionPrompt(e.target.value)}
                                            rows={2}
                                            className={cn(
                                                'w-full rounded-xl px-3.5 py-2.5 text-[13px] text-zinc-200',
                                                'bg-white/[0.03] border border-white/[0.06]',
                                                'placeholder:text-zinc-600 resize-none',
                                                'focus:outline-none focus:border-cyan-500/30 focus:ring-1 focus:ring-cyan-500/10',
                                                'transition-all duration-200'
                                            )}
                                            placeholder="描述期望的镜头运动效果..."
                                        />
                                    </div>

                                    {/* duration */}
                                    <div>
                                        <div className="flex items-center justify-between mb-2">
                                            <label className="text-[12px] font-medium text-zinc-400 tracking-wide uppercase flex items-center gap-1.5">
                                                <Clock className="w-3 h-3" />
                                                视频时长
                                            </label>
                                            <span className="text-[13px] font-semibold text-cyan-400 tabular-nums">
                                                {durationSec}s
                                            </span>
                                        </div>
                                        <div className="relative">
                                            <input
                                                type="range"
                                                min={3}
                                                max={10}
                                                step={1}
                                                value={durationSec}
                                                onChange={e => setDurationSec(Number(e.target.value))}
                                                className="w-full h-1.5 rounded-full appearance-none cursor-pointer bg-zinc-800 accent-cyan-500
                                                    [&::-webkit-slider-thumb]:appearance-none
                                                    [&::-webkit-slider-thumb]:w-4
                                                    [&::-webkit-slider-thumb]:h-4
                                                    [&::-webkit-slider-thumb]:rounded-full
                                                    [&::-webkit-slider-thumb]:bg-cyan-400
                                                    [&::-webkit-slider-thumb]:shadow-[0_0_8px_rgba(6,182,212,0.5)]
                                                    [&::-webkit-slider-thumb]:cursor-pointer
                                                    [&::-webkit-slider-thumb]:border-2
                                                    [&::-webkit-slider-thumb]:border-zinc-900"
                                            />
                                            <div className="flex justify-between mt-1.5 text-[10px] text-zinc-600">
                                                <span>3s</span>
                                                <span>5s</span>
                                                <span>8s</span>
                                                <span>10s</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            /* ── progress mode ── */
                            <div className="p-6 space-y-3">
                                {/* summary bar */}
                                <div className="flex items-center justify-between px-3.5 py-2.5 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                                    <span className="text-[12px] text-zinc-400">
                                        生成进度
                                    </span>
                                    <div className="flex items-center gap-3 text-[12px]">
                                        {done > 0 && (
                                            <span className="text-emerald-400 flex items-center gap-1">
                                                <CheckCircle2 className="w-3 h-3" /> {done}
                                            </span>
                                        )}
                                        {failed > 0 && (
                                            <span className="text-red-400 flex items-center gap-1">
                                                <AlertCircle className="w-3 h-3" /> {failed}
                                            </span>
                                        )}
                                        <span className="text-zinc-500">{done + failed}/{jobs.length}</span>
                                    </div>
                                </div>

                                {/* job cards */}
                                {jobs.map((job, idx) => (
                                    <div
                                        key={job.job_id}
                                        className={cn(
                                            'flex items-center gap-3 p-3 rounded-xl transition-all duration-200',
                                            'border',
                                            job.status === 'succeeded'
                                                ? 'bg-emerald-500/[0.04] border-emerald-500/10'
                                                : job.status === 'failed'
                                                ? 'bg-red-500/[0.04] border-red-500/10'
                                                : 'bg-white/[0.02] border-white/[0.04]'
                                        )}
                                    >
                                        {/* thumbnail */}
                                        <div className="w-14 h-[52px] rounded-lg overflow-hidden bg-zinc-800 flex-shrink-0 ring-1 ring-white/[0.06]">
                                            <img src={job.image_url} alt="" className="w-full h-full object-cover" />
                                        </div>

                                        {/* info */}
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center justify-between mb-1.5">
                                                <span className="text-[12px] text-zinc-300 font-medium">
                                                    分镜 {idx + 1}
                                                </span>
                                                {job.status === 'queued' && (
                                                    <span className="text-[11px] text-zinc-500 flex items-center gap-1">
                                                        <span className="w-1.5 h-1.5 rounded-full bg-zinc-500 animate-pulse" /> 队列中
                                                    </span>
                                                )}
                                                {job.status === 'running' && (
                                                    <span className="text-[11px] text-cyan-400 flex items-center gap-1">
                                                        <Loader2 className="w-3 h-3 animate-spin" />
                                                        {Math.round(job.progress * 100)}%
                                                    </span>
                                                )}
                                                {job.status === 'succeeded' && (
                                                    <span className="text-[11px] text-emerald-400 flex items-center gap-1">
                                                        <CheckCircle2 className="w-3 h-3" /> 完成
                                                    </span>
                                                )}
                                                {job.status === 'failed' && (
                                                    <span className="text-[11px] text-red-400 flex items-center gap-1">
                                                        <AlertCircle className="w-3 h-3" /> 失败
                                                    </span>
                                                )}
                                            </div>

                                            {/* progress track */}
                                            <div className="h-[3px] bg-zinc-800/80 rounded-full overflow-hidden">
                                                <motion.div
                                                    className={cn(
                                                        'h-full rounded-full',
                                                        job.status === 'succeeded'
                                                            ? 'bg-gradient-to-r from-emerald-500 to-emerald-400'
                                                            : job.status === 'failed'
                                                            ? 'bg-red-500'
                                                            : 'bg-gradient-to-r from-cyan-500 to-cyan-400'
                                                    )}
                                                    initial={{ width: 0 }}
                                                    animate={{ width: `${job.progress * 100}%` }}
                                                    transition={{ duration: 0.5, ease: 'easeOut' }}
                                                />
                                            </div>

                                            {job.error && (
                                                <p className="text-[10px] text-red-400/80 mt-1 truncate">{job.error}</p>
                                            )}
                                        </div>

                                        {/* action */}
                                        {job.status === 'succeeded' && job.video_url && (
                                            <a
                                                href={job.video_url}
                                                target="_blank"
                                                rel="noreferrer"
                                                className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors cursor-pointer ring-1 ring-emerald-500/20"
                                            >
                                                <Play className="w-3.5 h-3.5" />
                                            </a>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}

                        {/* error */}
                        {error && (
                            <div className="mx-6 mb-4 flex items-start gap-2.5 px-4 py-3 rounded-xl bg-red-500/[0.06] border border-red-500/10 text-[12px] text-red-400">
                                <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                                <span>{error}</span>
                            </div>
                        )}
                    </div>

                    {/* ──── footer ──── */}
                    <div className="relative px-6 py-4 border-t border-white/[0.06] flex items-center justify-end gap-3">
                        {/* accent glow bottom */}
                        <div className="absolute inset-x-0 -top-px h-px bg-gradient-to-r from-transparent via-white/[0.04] to-transparent" />

                        {jobs.length === 0 ? (
                            <>
                                <button
                                    onClick={onClose}
                                    className="px-4 py-2 rounded-xl text-[13px] text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.04] transition-all duration-200 cursor-pointer"
                                >
                                    取消
                                </button>
                                <button
                                    onClick={handleGenerate}
                                    disabled={selectedImages.length === 0 || isGenerating}
                                    className={cn(
                                        'flex items-center gap-2 px-5 py-2.5 rounded-xl text-[13px] font-medium',
                                        'bg-gradient-to-r from-cyan-600 to-cyan-500 text-white',
                                        'hover:from-cyan-500 hover:to-cyan-400',
                                        'disabled:opacity-30 disabled:cursor-not-allowed',
                                        'transition-all duration-200 cursor-pointer',
                                        'shadow-[0_1px_12px_-2px_rgba(6,182,212,0.3)]',
                                        'hover:shadow-[0_2px_20px_-4px_rgba(6,182,212,0.5)]'
                                    )}
                                >
                                    {isGenerating ? (
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                    ) : (
                                        <Sparkles className="w-4 h-4" />
                                    )}
                                    生成 {selectedImages.length} 个视频
                                </button>
                            </>
                        ) : (
                            <button
                                onClick={() => {
                                    if (pollRef.current) clearInterval(pollRef.current)
                                    setJobs([])
                                    setIsGenerating(false)
                                    onClose()
                                }}
                                disabled={isGenerating}
                                className={cn(
                                    'px-5 py-2.5 rounded-xl text-[13px] transition-all duration-200 cursor-pointer',
                                    isGenerating
                                        ? 'text-zinc-600'
                                        : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04]'
                                )}
                            >
                                {isGenerating ? '生成中…' : '完成'}
                            </button>
                        )}
                    </div>
                </motion.div>
            </motion.div>
        </AnimatePresence>
    )
}
