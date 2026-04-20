'use client'

import { useStudioStore } from '@/lib/store/studioStore'
import { useShallow } from 'zustand/react/shallow'
import { cn } from '@/lib/utils'
import { RenderJob } from '@/lib/schema/job'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { RefreshCw, AlertCircle, CheckCircle, Clock, Loader2, Eye, Wand2, FileText, Users, Map } from 'lucide-react'
import { useState } from 'react'
import { BundlePreviewModal } from '@/components/studio/modals/BundlePreviewModal'

/** Safely coerce a value that might be an object (e.g. {message: "..."}) to a display string */
function toDisplayString(val: unknown): string {
  if (val === null || val === undefined) return ''
  if (typeof val === 'string') return val
  if (typeof val === 'object' && val !== null) {
    if ('message' in val && typeof (val as any).message === 'string') return (val as any).message
    try { return JSON.stringify(val) } catch { return String(val) }
  }
  return String(val)
}

const STATUS_CONFIG = {
    Queued: { icon: Clock, color: 'bg-yellow-500', label: '排队中' },
    Running: { icon: Loader2, color: 'bg-blue-500', label: '渲染中' },
    Succeeded: { icon: CheckCircle, color: 'bg-emerald-500', label: '成功' },
    Failed: { icon: AlertCircle, color: 'bg-red-500', label: '失败' },
}

// 分镜生成阶段配置
const STORYBOARD_STAGES = {
    parse: { label: '解析剧本', icon: FileText, description: '提取角色、场景和剧情节拍' },
    character_chain: { label: '角色处理', icon: Users, description: '入库角色资产并提取 FaceID' },
    scene_chain: { label: '场景处理', icon: Map, description: '入库场景资产并生成控制图' },
    plan: { label: '分镜计划', icon: Wand2, description: '生成分镜计划' },
    bind: { label: '资产绑定', icon: Wand2, description: '绑定资产到分镜' },
    done: { label: '完成', icon: CheckCircle, description: '分镜生成完成' },
}

// 分镜任务进度组件
function StoryboardJobProgress() {
    const { storyboardJob } = useStudioStore(
    useShallow(s => ({ storyboardJob: s.storyboardJob }))
  )

    if (!storyboardJob) return null

    const isRunning = storyboardJob.status === 'running'
    const isSucceeded = storyboardJob.status === 'succeeded'
    const isFailed = storyboardJob.status === 'failed'

    const stageConfig = STORYBOARD_STAGES[storyboardJob.stage as keyof typeof STORYBOARD_STAGES] || {
        label: storyboardJob.stage,
        icon: Loader2,
        description: storyboardJob.message || ''
    }
    const StageIcon = stageConfig.icon

    return (
        <div className={cn(
            'p-3 rounded-lg border transition-all text-sm mb-2',
            isRunning && 'bg-gradient-to-r from-blue-500/10 to-cyan-500/10 border-blue-500/30',
            isSucceeded && 'bg-emerald-500/10 border-emerald-500/30',
            isFailed && 'bg-red-500/10 border-red-500/30'
        )}>
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    <Wand2 className={cn(
                        'w-4 h-4',
                        isRunning && 'text-blue-400',
                        isSucceeded && 'text-emerald-400',
                        isFailed && 'text-red-400'
                    )} />
                    <span className="font-medium">AI 分镜生成</span>
                    <Badge variant="outline" className={cn(
                        'text-xs',
                        isRunning && 'border-blue-500/30 text-blue-400',
                        isSucceeded && 'border-emerald-500/30 text-emerald-400',
                        isFailed && 'border-red-500/30 text-red-400'
                    )}>
                        {isRunning ? stageConfig.label : (isSucceeded ? '完成' : '失败')}
                    </Badge>
                </div>
                <span className="text-xs text-ink-dim">
                    {new Date(storyboardJob.updatedAt).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                </span>
            </div>

            {/* 进度条 */}
            {isRunning && (
                <div className="space-y-1 mb-2">
                    <div className="flex justify-between text-xs text-ink-muted">
                        <span className="flex items-center gap-1">
                            <StageIcon className="w-3 h-3" />
                            {stageConfig.description || toDisplayString(storyboardJob.message) || '处理中...'}
                        </span>
                        <span>{storyboardJob.progress.toFixed(0)}%</span>
                    </div>
                    <div className="h-1.5 bg-panel rounded-full overflow-hidden">
                        <div
                            className="h-full bg-gradient-to-r from-blue-500 to-cyan-500 transition-all duration-300"
                            style={{ width: `${storyboardJob.progress}%` }}
                        />
                    </div>
                </div>
            )}

            {/* 阶段指示器 */}
            {isRunning && (
                <div className="flex items-center gap-1 mt-2">
                    {Object.entries(STORYBOARD_STAGES).slice(0, -1).map(([key, config], index) => {
                        const isActive = storyboardJob.stage === key
                        const isPast = Object.keys(STORYBOARD_STAGES).indexOf(storyboardJob.stage) > index
                        return (
                            <div
                                key={key}
                                className={cn(
                                    'h-1 flex-1 rounded-full transition-all',
                                    isPast && 'bg-blue-500',
                                    isActive && 'bg-blue-400 animate-pulse',
                                    !isPast && !isActive && 'bg-white/10'
                                )}
                                title={config.label}
                            />
                        )
                    })}
                </div>
            )}

            {/* 成功消息 */}
            {isSucceeded && (
                <div className="text-xs text-emerald-400 flex items-center gap-1">
                    <CheckCircle className="w-3 h-3" />
                    分镜生成完成，请在弹窗中预览并确认
                </div>
            )}

            {/* 错误消息 */}
            {isFailed && (
                <div className="text-xs text-red-400 flex items-center gap-1">
                    <AlertCircle className="w-3 h-3" />
                    {toDisplayString(storyboardJob.message) || '生成失败，请重试'}
                </div>
            )}
        </div>
    )
}

export function JobsConsole() {
    const { getJobsForChapter, retryJob, selectPanel, panelList, storyboardJob } = useStudioStore(
    useShallow(s => ({ getJobsForChapter: s.getJobsForChapter, retryJob: s.retryJob, selectPanel: s.selectPanel, panelList: s.panelList, storyboardJob: s.storyboardJob }))
  )

    const jobs = getJobsForChapter()
    const [previewExportId, setPreviewExportId] = useState<string | null>(null)

    const handlePreview = (manifestUrl: string) => {
        // Extract export_id from url: .../exports/{chapter_id}/{export_id}/manifest.json
        // Regex: \/exports\/[^\/]+\/([^\/]+)\/manifest\.json
        const match = manifestUrl.match(/\/exports\/[^/]+\/([^/]+)\/manifest\.json/)
        if (match && match[1]) {
            setPreviewExportId(match[1])
        }
    }

    // 按时间倒序
    const sortedJobs = [...jobs].sort(
        (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    )

    const getPanelIndex = (panelId: string | undefined) => {
        if (!panelId) return '-'
        const panel = panelList.find((p) => p.id === panelId)
        return panel ? panel.index + 1 : '?'
    }

    // 没有任务时的空状态
    const hasJobs = sortedJobs.length > 0 || storyboardJob

    if (!hasJobs) {
        return (
            <div className="h-full flex items-center justify-center text-ink-muted">
                <div className="text-center">
                    <Clock className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p className="text-sm">暂无任务</p>
                    <p className="text-xs opacity-70">点击"AI 分镜"或"渲染"开始</p>
                </div>
            </div>
        )
    }

    return (
        <ScrollArea className="h-full">
            <div className="p-3 space-y-2">
                {/* 分镜任务进度（置顶显示） */}
                <StoryboardJobProgress />

                {/* 渲染任务列表 */}
                {sortedJobs.map((job) => (
                    <JobItem
                        key={job.id}
                        job={job}
                        panelIndex={getPanelIndex(job.panelId)}
                        onRetry={() => retryJob(job.id)}
                        onSelect={() => job.panelId && selectPanel(job.panelId)}
                        onPreview={handlePreview}
                    />
                ))}
            </div>

            <BundlePreviewModal
                exportId={previewExportId}
                open={!!previewExportId}
                onOpenChange={(open) => !open && setPreviewExportId(null)}
            />
        </ScrollArea>
    )
}

function JobItem({
    job,
    panelIndex,
    onRetry,
    onSelect,
    onPreview,
}: {
    job: RenderJob
    panelIndex: number | string
    onRetry: () => void

    onSelect: () => void
    onPreview?: (manifestUrl: string) => void
}) {
    const config = STATUS_CONFIG[job.status]
    const Icon = config.icon
    const isRunning = job.status === 'Running'
    const isFailed = job.status === 'Failed'
    const isExport = job.type === 'export' || job.type === 'bundle' // Handle export jobs

    const formatTime = (isoString: string) => {
        const date = new Date(isoString)
        return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    }

    // Special rendering for Export jobs
    if (isExport) {
        return (
            <div className={cn(
                'p-3 rounded-lg border transition-all text-sm',
                'bg-panel/50 border-purple-500/30 hover:border-purple-500/50',
                isFailed && 'border-red-500/30 bg-red-500/5'
            )}>
                <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                        <Icon
                            className={cn(
                                'w-4 h-4',
                                isRunning && 'animate-spin text-purple-400',
                                job.status === 'Succeeded' && 'text-emerald-400',
                                isFailed && 'text-red-400'
                            )}
                        />
                        <span className="font-medium">Bundle Export</span>
                        {isRunning && (
                            <Badge variant="outline" className="text-xs border-purple-500/30 text-purple-400">
                                PACKAGING
                            </Badge>
                        )}
                    </div>
                    <span className="text-xs text-ink-dim">{formatTime(job.createdAt)}</span>
                </div>

                <div className="space-y-2">
                    {/* Progress with message */}
                    {(isRunning || job.status === 'Queued') && (
                        <div className="space-y-1">
                            <div className="flex justify-between text-xs text-ink-muted">
                                <span>{toDisplayString(job.message) || 'Processing...'}</span>
                                <span>{(job.progress * 100).toFixed(0)}%</span>
                            </div>
                            <div className="h-1.5 bg-panel rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-purple-500 transition-all duration-300"
                                    style={{ width: `${job.progress * 100}%` }}
                                />
                            </div>
                        </div>
                    )}

                    {/* Success: Download Link */}
                    {job.status === 'Succeeded' && job.output?.bundle_url && (
                        <div className="flex items-center gap-4">
                            <a
                                href={job.output.bundle_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-purple-400 hover:text-purple-300 hover:underline flex items-center gap-1"
                            >
                                <CheckCircle className="w-3 h-3" />
                                下载 Bundle ZIP
                            </a>
                            {job.output.manifest_url && (
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation()
                                        if (job.output?.manifest_url) {
                                            onPreview?.(job.output.manifest_url)
                                        }
                                    }}
                                    className="text-xs text-ink-muted hover:text-ink hover:underline flex items-center gap-1"
                                >
                                    <Eye className="w-3 h-3" />
                                    预览内容
                                </button>
                            )}
                        </div>
                    )}

                    {/* Error Message */}
                    {isFailed && (
                        <div className="text-xs text-red-400 flex items-center gap-1">
                            <AlertCircle className="w-3 h-3" />
                            {toDisplayString(job.error) || 'Export failed'}
                        </div>
                    )}
                </div>
            </div>
        )
    }

    return (
        <div
            className={cn(
                'p-3 rounded-lg border transition-all cursor-pointer',
                'bg-panel/50 border-panel-border hover:border-accent/50',
                isFailed && 'border-red-500/30 bg-red-500/5'
            )}
            onClick={onSelect}
        >
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    <Icon
                        className={cn(
                            'w-4 h-4',
                            isRunning && 'animate-spin text-blue-400',
                            job.status === 'Succeeded' && 'text-emerald-400',
                            isFailed && 'text-red-400',
                            job.status === 'Queued' && 'text-yellow-400'
                        )}
                    />
                    <span className="font-medium text-sm">Panel #{panelIndex}</span>
                    <Badge variant="outline" className="text-xs">
                        {job.provider}
                    </Badge>
                </div>
                <span className="text-xs text-ink-dim">{formatTime(job.createdAt)}</span>
            </div>

            {/* 进度条 */}
            {(isRunning || job.status === 'Queued') && (
                <div className="h-1.5 bg-panel rounded-full overflow-hidden mb-2">
                    <div
                        className={cn(
                            'h-full transition-all duration-300',
                            isRunning ? 'bg-blue-500' : 'bg-yellow-500'
                        )}
                        style={{ width: `${job.progress * 100}%` }}
                    />
                </div>
            )}

            {/* 错误信息 */}
            {isFailed && job.error && (
                <div className="text-xs text-red-400 mb-2 flex items-center gap-1">
                    <AlertCircle className="w-3 h-3" />
                    {toDisplayString(job.error)}
                </div>
            )}

            {/* 操作按钮 */}
            {isFailed && (
                <Button
                    variant="outline"
                    size="sm"
                    className="w-full h-7 text-xs"
                    onClick={(e) => {
                        e.stopPropagation()
                        onRetry()
                    }}
                >
                    <RefreshCw className="w-3 h-3 mr-1" />
                    重试
                </Button>
            )}

            {/* 成功状态显示 QA 分数 */}
            {job.status === 'Succeeded' && job.qa && (
                <div className="text-xs text-ink-muted flex items-center gap-2">
                    <span>质量分数: {(job.qa.score * 100).toFixed(0)}%</span>
                    {job.qa.issues.length > 0 && (
                        <span className="text-yellow-400">
                            {job.qa.issues.length} 个小问题
                        </span>
                    )}
                </div>
            )}
        </div>
    )
}
