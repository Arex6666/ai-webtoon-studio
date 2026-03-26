'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
    Film, Loader2, CheckCircle2, AlertCircle, Play,
    Sparkles, Clock, Zap, ChevronLeft, ChevronRight,
    Layers, RefreshCw, Download
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { env } from '@/lib/utils/env'

/* ─────────── types ─────────── */

export interface PanelImage {
    index: number
    url: string
    label: string
}

export interface VideoJobState {
    job_id: string
    image_url: string
    panel_index: number
    status: 'queued' | 'running' | 'succeeded' | 'failed'
    progress: number
    video_url?: string
    error?: string
}

export type VideoCardPhase = 'select' | 'generating' | 'done'

export interface VideoCardData {
    phase: VideoCardPhase
    panels: PanelImage[]
    selectedIndices: number[]
    motionPrompt: string
    durationSec: number
    /** Per-panel durations (index → seconds), from LLM script data. Falls back to durationSec. */
    panelDurations?: Record<number, number>
    jobs: VideoJobState[]
}

interface VideoCardProps {
    data: VideoCardData
    projectId: string
    episodeNum: number
    onDataChange: (data: VideoCardData) => void
    /** 当所有视频完成后，用户点击"合成视频" */
    onCompose?: (videoUrls: string[]) => void
}

/* ─────────── component ─────────── */

export function VideoCard({ data, projectId, episodeNum, onDataChange, onCompose }: VideoCardProps) {
    const stripRef = useRef<HTMLDivElement>(null)
    const pollRef = useRef<NodeJS.Timeout | null>(null)

    useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

    const update = (patch: Partial<VideoCardData>) => onDataChange({ ...data, ...patch })

    const togglePanel = (idx: number) => {
        const sel = data.selectedIndices.includes(idx)
            ? data.selectedIndices.filter(i => i !== idx)
            : [...data.selectedIndices, idx]
        update({ selectedIndices: sel })
    }

    const scrollStrip = (dir: 'left' | 'right') =>
        stripRef.current?.scrollBy({ left: dir === 'left' ? -200 : 200, behavior: 'smooth' })

    /* ───── API: start generation ───── */
    const handleGenerate = async () => {
        if (data.selectedIndices.length === 0) return

        const selectedUrls = data.selectedIndices.map(i => data.panels[i].url)
        const perImageDurations = data.panelDurations
            ? data.selectedIndices.map(i => data.panelDurations![i] ?? data.durationSec)
            : undefined
        update({ phase: 'generating' })

        try {
            const resp = await fetch(
                `${env.API_BASE_URL}/api/v1/agent/episode/${episodeNum}/generate-video`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        project_id: projectId,
                        image_urls: selectedUrls,
                        motion_prompt: data.motionPrompt,
                        duration_sec: data.durationSec,
                        duration_per_image: perImageDurations,
                        provider: 'doubao',
                    }),
                }
            )
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
            const result = await resp.json()

            const jobs: VideoJobState[] = result.jobs.map((j: any, i: number) => ({
                job_id: j.job_id,
                image_url: j.image_url,
                panel_index: data.selectedIndices[i],
                status: j.status || 'queued',
                progress: 0,
            }))
            update({ phase: 'generating', jobs })
            startPolling(jobs.map(j => j.job_id))
        } catch (e: any) {
            // show error inline
            update({
                phase: 'generating',
                jobs: [{
                    job_id: 'error',
                    image_url: '',
                    panel_index: 0,
                    status: 'failed',
                    progress: 0,
                    error: e.message || '请求失败',
                }],
            })
        }
    }

    const startPolling = useCallback((jobIds: string[]) => {
        if (pollRef.current) clearInterval(pollRef.current)
        pollRef.current = setInterval(async () => {
            let allDone = true
            const updated = await Promise.all(
                jobIds.map(async id => {
                    try {
                        const r = await fetch(`${env.API_BASE_URL}/api/v1/agent/episode/video-jobs/${id}`)
                        if (!r.ok) return null
                        const d = await r.json()
                        if (d.status !== 'succeeded' && d.status !== 'failed') allDone = false
                        return d as VideoJobState
                    } catch { allDone = false; return null }
                })
            )

            // merge updated jobs
            const mergedJobs = data.jobs.map(j => {
                const u = updated.find(u2 => u2 && u2.job_id === j.job_id)
                return u ? { ...j, ...u } : j
            })

            onDataChange({
                ...data,
                jobs: mergedJobs,
                phase: allDone ? 'done' : 'generating',
            })

            if (allDone && pollRef.current) clearInterval(pollRef.current)
        }, 3000)
    }, [data, onDataChange])

    /* ───── derived ───── */
    const doneCount = data.jobs.filter(j => j.status === 'succeeded').length
    const failedCount = data.jobs.filter(j => j.status === 'failed').length
    const successVideos = data.jobs.filter(j => j.status === 'succeeded' && j.video_url).map(j => j.video_url!)

    /* ───── render ───── */
    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={cn(
                'mt-3 rounded-xl overflow-hidden',
                'border border-cyan-500/20',
                'bg-gradient-to-b from-cyan-500/[0.04] to-transparent'
            )}
        >
            {/* card header */}
            <div className="flex items-center gap-2.5 px-4 py-3 border-b border-white/[0.04]">
                <div className="w-8 h-8 rounded-lg bg-cyan-500/10 flex items-center justify-center ring-1 ring-cyan-500/20">
                    <Film className="w-4 h-4 text-cyan-400" />
                </div>
                <div className="flex-1 min-w-0">
                    <span className="text-[13px] font-medium text-zinc-200">视频生成</span>
                    <span className="ml-2 text-[11px] text-zinc-600">豆包 · 图生视频</span>
                </div>
                {data.phase === 'generating' && (
                    <span className="text-[11px] text-cyan-400 flex items-center gap-1">
                        <Loader2 className="w-3 h-3 animate-spin" /> 生成中
                    </span>
                )}
                {data.phase === 'done' && (
                    <span className="text-[11px] text-emerald-400 flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" /> 完成 {doneCount}/{data.jobs.length}
                    </span>
                )}
            </div>

            {/* ═══════ PHASE: SELECT ═══════ */}
            {data.phase === 'select' && (
                <div className="p-4 space-y-4">
                    {/* filmstrip */}
                    <div>
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-[12px] text-zinc-400">
                                选择分镜 <span className="text-zinc-600">{data.selectedIndices.length}/{data.panels.length}</span>
                            </span>
                            {data.panels.length > 3 && (
                                <div className="flex gap-1">
                                    <button onClick={() => scrollStrip('left')} className="p-0.5 text-zinc-600 hover:text-zinc-400 cursor-pointer"><ChevronLeft className="w-3.5 h-3.5" /></button>
                                    <button onClick={() => scrollStrip('right')} className="p-0.5 text-zinc-600 hover:text-zinc-400 cursor-pointer"><ChevronRight className="w-3.5 h-3.5" /></button>
                                </div>
                            )}
                        </div>
                        <div ref={stripRef} className="flex gap-2 overflow-x-auto hide-scrollbar pb-1">
                            {data.panels.map(p => {
                                const sel = data.selectedIndices.includes(p.index)
                                return (
                                    <button
                                        key={p.index}
                                        onClick={() => togglePanel(p.index)}
                                        className={cn(
                                            'relative flex-shrink-0 w-[100px] rounded-lg overflow-hidden cursor-pointer transition-all duration-200 ring-1',
                                            sel ? 'ring-cyan-500/60 shadow-[0_0_10px_-3px_rgba(6,182,212,0.3)]' : 'ring-white/[0.06] hover:ring-white/[0.12]'
                                        )}
                                    >
                                        <div className="aspect-[3/4] bg-zinc-800">
                                            <img src={p.url} alt={p.label} className={cn('w-full h-full object-cover transition-all', sel ? 'brightness-100' : 'brightness-60 hover:brightness-80')} />
                                        </div>
                                        <div className={cn('absolute top-1 right-1 w-4 h-4 rounded-full flex items-center justify-center transition-all',
                                            sel ? 'bg-cyan-500' : 'bg-black/40 ring-1 ring-white/20'
                                        )}>
                                            {sel ? <CheckCircle2 className="w-2.5 h-2.5 text-white" /> : <span className="w-1.5 h-1.5 rounded-full bg-white/30" />}
                                        </div>
                                        <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/70 to-transparent px-1.5 pb-1 pt-3">
                                            <span className="text-[10px] text-zinc-300">{p.label}</span>
                                            {data.panelDurations?.[p.index] && (
                                                <span className="ml-1 text-[9px] text-cyan-400/70">{data.panelDurations[p.index]}s</span>
                                            )}
                                        </div>
                                    </button>
                                )
                            })}
                        </div>
                    </div>

                    {/* settings row */}
                    <div className="flex gap-3">
                        <div className="flex-1">
                            <label className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1 block">运动提示词</label>
                            <input
                                type="text"
                                value={data.motionPrompt}
                                onChange={e => update({ motionPrompt: e.target.value })}
                                className="w-full bg-white/[0.03] border border-white/[0.06] rounded-lg px-2.5 py-1.5 text-[12px] text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:border-cyan-500/30"
                                placeholder="描述镜头运动..."
                            />
                        </div>
                        <div className="w-20">
                            <label className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1 block flex items-center gap-1"><Clock className="w-2.5 h-2.5" /> 时长</label>
                            <select
                                value={data.durationSec}
                                onChange={e => update({ durationSec: Number(e.target.value) })}
                                className="w-full bg-white/[0.03] border border-white/[0.06] rounded-lg px-2 py-1.5 text-[12px] text-zinc-300 focus:outline-none cursor-pointer"
                            >
                                {[3, 4, 5, 6, 7, 8, 10].map(v => <option key={v} value={v}>{v}s</option>)}
                            </select>
                        </div>
                    </div>

                    {/* CTA */}
                    <button
                        onClick={handleGenerate}
                        disabled={data.selectedIndices.length === 0}
                        className={cn(
                            'w-full flex items-center justify-center gap-2 py-2 rounded-lg text-[13px] font-medium cursor-pointer',
                            'bg-gradient-to-r from-cyan-600 to-cyan-500 text-white',
                            'hover:from-cyan-500 hover:to-cyan-400',
                            'disabled:opacity-30 disabled:cursor-not-allowed',
                            'transition-all shadow-[0_1px_10px_-3px_rgba(6,182,212,0.3)]'
                        )}
                    >
                        <Sparkles className="w-4 h-4" />
                        生成 {data.selectedIndices.length} 个分镜视频
                    </button>
                </div>
            )}

            {/* ═══════ PHASE: GENERATING / DONE ═══════ */}
            {(data.phase === 'generating' || data.phase === 'done') && (
                <div className="p-4 space-y-2">
                    {data.jobs.map((job, idx) => (
                        <div
                            key={job.job_id}
                            className={cn(
                                'flex items-center gap-2.5 p-2.5 rounded-lg border transition-all',
                                job.status === 'succeeded' ? 'bg-emerald-500/[0.04] border-emerald-500/10' :
                                job.status === 'failed' ? 'bg-red-500/[0.04] border-red-500/10' :
                                'bg-white/[0.02] border-white/[0.04]'
                            )}
                        >
                            {/* thumb */}
                            <div className="w-12 h-12 rounded-lg overflow-hidden bg-zinc-800 flex-shrink-0 ring-1 ring-white/[0.06]">
                                {job.status === 'succeeded' && job.video_url ? (
                                    <a href={job.video_url} target="_blank" rel="noreferrer" className="relative block w-full h-full group">
                                        <img src={job.image_url} alt="" className="w-full h-full object-cover" />
                                        <div className="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                                            <Play className="w-4 h-4 text-white" />
                                        </div>
                                    </a>
                                ) : (
                                    <img src={job.image_url} alt="" className="w-full h-full object-cover" />
                                )}
                            </div>

                            {/* info */}
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-[11px] text-zinc-300 font-medium">
                                        分镜 {job.panel_index + 1}
                                    </span>
                                    {job.status === 'queued' && <span className="text-[10px] text-zinc-500">队列中</span>}
                                    {job.status === 'running' && (
                                        <span className="text-[10px] text-cyan-400 flex items-center gap-1">
                                            <Loader2 className="w-2.5 h-2.5 animate-spin" /> {Math.round(job.progress * 100)}%
                                        </span>
                                    )}
                                    {job.status === 'succeeded' && <span className="text-[10px] text-emerald-400">✓ 完成</span>}
                                    {job.status === 'failed' && <span className="text-[10px] text-red-400">✗ 失败</span>}
                                </div>
                                <div className="h-[2px] bg-zinc-800 rounded-full overflow-hidden">
                                    <motion.div
                                        className={cn('h-full rounded-full',
                                            job.status === 'succeeded' ? 'bg-emerald-500' :
                                            job.status === 'failed' ? 'bg-red-500' :
                                            'bg-cyan-500'
                                        )}
                                        animate={{ width: `${job.progress * 100}%` }}
                                        transition={{ duration: 0.4 }}
                                    />
                                </div>
                                {job.error && <p className="text-[10px] text-red-400/70 mt-0.5 truncate">{job.error}</p>}
                            </div>
                        </div>
                    ))}

                    {/* compose button — shown when done and has 2+ videos */}
                    {data.phase === 'done' && successVideos.length >= 2 && onCompose && (
                        <motion.button
                            initial={{ opacity: 0, y: 8 }}
                            animate={{ opacity: 1, y: 0 }}
                            onClick={() => onCompose(successVideos)}
                            className={cn(
                                'w-full flex items-center justify-center gap-2 py-2.5 mt-2 rounded-lg text-[13px] font-medium cursor-pointer',
                                'bg-gradient-to-r from-purple-600 to-pink-500 text-white',
                                'hover:from-purple-500 hover:to-pink-400',
                                'transition-all shadow-[0_1px_12px_-3px_rgba(139,92,246,0.3)]'
                            )}
                        >
                            <Layers className="w-4 h-4" />
                            合成 {successVideos.length} 个视频
                        </motion.button>
                    )}

                    {/* single video done */}
                    {data.phase === 'done' && successVideos.length === 1 && (
                        <a
                            href={successVideos[0]}
                            target="_blank"
                            rel="noreferrer"
                            className="flex items-center justify-center gap-2 py-2 mt-1 rounded-lg text-[12px] text-emerald-400 bg-emerald-500/[0.06] hover:bg-emerald-500/10 border border-emerald-500/10 cursor-pointer transition-colors"
                        >
                            <Play className="w-3.5 h-3.5" /> 播放视频
                        </a>
                    )}
                </div>
            )}
        </motion.div>
    )
}
