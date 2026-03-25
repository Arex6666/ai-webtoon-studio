'use client'

import { useState } from 'react'
import { useShallow } from 'zustand/react/shallow'
import { useStudioStore } from '@/lib/store/studioStore'
import { useJobTracker } from '@/hooks/useJobTracker'
import { canGenerateClip } from '@/lib/schema/clip'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Progress } from '@/components/ui/progress'
import {
  Film,
  Play,
  ImageIcon,
  AlertCircle,
  CheckCircle2,
  Loader2,
  XCircle,
  Upload,
} from 'lucide-react'

const PROVIDER_OPTIONS = [
  { value: 'doubao', label: '豆包' },
  { value: 'mock', label: 'Mock (测试)' },
  { value: 'comfyui', label: 'ComfyUI' },
]

const DURATION_OPTIONS = [2, 3, 4, 5]
const FPS_OPTIONS = [16, 24, 30]

const MOTION_MODE_OPTIONS = [
  { value: 'single_keyframe', label: '单关键帧' },
  { value: 'dual_keyframe', label: '双关键帧 (首尾帧)' },
]

type MotionMode = 'single_keyframe' | 'dual_keyframe'

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; className: string }> = {
    queued:    { label: '排队中', className: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' },
    running:   { label: '生成中', className: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
    succeeded: { label: '已完成', className: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' },
    failed:    { label: '失败', className: 'bg-red-500/20 text-red-400 border-red-500/30' },
    canceled:  { label: '已取消', className: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30' },
  }
  const entry = map[status] ?? { label: status, className: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30' }
  return (
    <Badge variant="outline" className={`text-xs ${entry.className}`}>
      {entry.label}
    </Badge>
  )
}

export default function VideoTab() {
  const { selectedPanelId, panelList, createJob } = useStudioStore(
    useShallow(s => ({
      selectedPanelId: s.selectedPanelId,
      panelList: s.panelList,
      createJob: s.createJob,
    }))
  )

  const panel = panelList.find(p => p.id === selectedPanelId)
  const isRendered = panel?.status === 'Rendered'
  const panelPreviewUrl = panel?.previewUrl

  const [motionPrompt, setMotionPrompt] = useState('')
  const [motionMode, setMotionMode] = useState<MotionMode>('single_keyframe')
  const [endFrameUrl, setEndFrameUrl] = useState('')
  const [durationSec, setDurationSec] = useState(3)
  const [fps, setFps] = useState(24)
  const [provider, setProvider] = useState('doubao')
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const jobState = useJobTracker(activeJobId)

  // Build a minimal clip-like object to reuse canGenerateClip logic.
  // startFrame is intentionally null here so canGenerateClip falls back to
  // the second argument (panelPreviewUrl). endFrame uses the asset variant
  // when the user supplies a URL in dual_keyframe mode.
  const pseudoClip = {
    id: selectedPanelId ?? '',
    projectId: '',
    chapterId: '',
    panelId: selectedPanelId ?? '',
    layerPackId: null,
    type: 'motion_clip' as const,
    startFrame: null,
    endFrame: motionMode === 'dual_keyframe' && endFrameUrl
      ? ({ type: 'asset' as const, assetId: '', url: endFrameUrl, w: 800, h: 600 })
      : null,
    motionMode,
    cameraPlan: undefined,
    durationSec,
    fps,
    provider: provider as any,
    motionPrompt,
    negative: '',
    seedMode: 'new' as const,
    status: 'Idle' as const,
    progress: 0,
    createdAt: '',
    updatedAt: '',
  }

  const { canGenerate, reason } = canGenerateClip(pseudoClip, panelPreviewUrl)

  const isJobActive = activeJobId !== null && !jobState.isComplete
  const isJobRunning = jobState.status === 'running' || jobState.status === 'queued'

  const handleGenerateVideo = async () => {
    if (!selectedPanelId || !panelPreviewUrl || !canGenerate) return

    setIsSubmitting(true)
    setSubmitError(null)

    try {
      const params: Record<string, unknown> = {
        start_frame_url: panelPreviewUrl,
        motion_prompt: motionPrompt,
        motion_mode: motionMode,
        duration_sec: durationSec,
        fps,
      }

      if (motionMode === 'dual_keyframe' && endFrameUrl) {
        params.end_frame_url = endFrameUrl
      }

      const jobId = await createJob('video', selectedPanelId, provider, params)
      setActiveJobId(jobId)
    } catch (e) {
      const msg = e instanceof Error ? e.message : '生成失败，请重试'
      setSubmitError(msg)
      console.error('Video generation failed:', e)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleReset = () => {
    setActiveJobId(null)
    setSubmitError(null)
  }

  // --- Empty / unrendered states ---

  if (!selectedPanelId) {
    return (
      <div className="h-full flex items-center justify-center text-muted-foreground p-4">
        <div className="text-center">
          <Film className="w-8 h-8 mx-auto mb-2 opacity-40" />
          <p className="text-sm">请选择一个面板</p>
        </div>
      </div>
    )
  }

  if (!isRendered) {
    return (
      <div className="h-full flex items-center justify-center p-4">
        <div className="text-center space-y-3">
          <AlertCircle className="w-8 h-8 mx-auto text-yellow-400 opacity-70" />
          <p className="text-sm text-muted-foreground">请先渲染此面板图片</p>
          <p className="text-xs text-muted-foreground opacity-60">
            面板状态: <span className="font-medium">{panel?.status ?? '未知'}</span>
          </p>
        </div>
      </div>
    )
  }

  // --- Main form ---

  return (
    <ScrollArea className="h-full">
      <div className="p-4 space-y-5">

        {/* Header */}
        <div className="flex items-center justify-between">
          <h3 className="font-medium text-sm flex items-center gap-2">
            <Film className="w-4 h-4" />
            视频生成
          </h3>
          {activeJobId && <StatusBadge status={jobState.status} />}
        </div>

        <Separator />

        {/* Start Frame Preview */}
        <div className="space-y-2">
          <Label className="text-xs text-muted-foreground flex items-center gap-1.5">
            <ImageIcon className="w-3 h-3" />
            起始帧（当前面板）
          </Label>
          {panelPreviewUrl ? (
            <div className="relative rounded-md overflow-hidden border border-border bg-black aspect-video">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={panelPreviewUrl}
                alt="起始帧预览"
                className="w-full h-full object-contain"
              />
              <div className="absolute bottom-1 right-1">
                <Badge variant="outline" className="text-[10px] bg-black/60 border-white/20 text-white/80">
                  起始帧
                </Badge>
              </div>
            </div>
          ) : (
            <div className="rounded-md border border-dashed border-border bg-muted/30 aspect-video flex items-center justify-center">
              <p className="text-xs text-muted-foreground">无预览图</p>
            </div>
          )}
        </div>

        {/* Motion Mode */}
        <div className="space-y-2">
          <Label className="text-xs text-muted-foreground">运动模式</Label>
          <Select
            value={motionMode}
            onValueChange={(v) => setMotionMode(v as MotionMode)}
            disabled={isJobRunning}
          >
            <SelectTrigger className="bg-background border-border text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {MOTION_MODE_OPTIONS.map(opt => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* End Frame Upload (dual_keyframe only) */}
        {motionMode === 'dual_keyframe' && (
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground flex items-center gap-1.5">
              <Upload className="w-3 h-3" />
              结束帧 URL
            </Label>
            <input
              type="text"
              value={endFrameUrl}
              onChange={(e) => setEndFrameUrl(e.target.value)}
              placeholder="https://... 或留空"
              disabled={isJobRunning}
              className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
            />
            {endFrameUrl && (
              <div className="relative rounded-md overflow-hidden border border-border bg-black aspect-video">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={endFrameUrl}
                  alt="结束帧预览"
                  className="w-full h-full object-contain"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                />
                <div className="absolute bottom-1 right-1">
                  <Badge variant="outline" className="text-[10px] bg-black/60 border-white/20 text-white/80">
                    结束帧
                  </Badge>
                </div>
              </div>
            )}
          </div>
        )}

        <Separator />

        {/* Motion Prompt */}
        <div className="space-y-2">
          <Label className="text-xs text-muted-foreground">运镜描述</Label>
          <Textarea
            value={motionPrompt}
            onChange={(e) => setMotionPrompt(e.target.value)}
            placeholder="描述镜头运动，例如：缓慢推进，从远景到近景..."
            className="min-h-[72px] bg-background border-border text-sm resize-none"
            disabled={isJobRunning}
          />
        </div>

        {/* Duration & FPS */}
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">时长</Label>
            <Select
              value={String(durationSec)}
              onValueChange={(v) => setDurationSec(parseInt(v))}
              disabled={isJobRunning}
            >
              <SelectTrigger className="bg-background border-border text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DURATION_OPTIONS.map(d => (
                  <SelectItem key={d} value={String(d)}>{d} 秒</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">FPS</Label>
            <Select
              value={String(fps)}
              onValueChange={(v) => setFps(parseInt(v))}
              disabled={isJobRunning}
            >
              <SelectTrigger className="bg-background border-border text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {FPS_OPTIONS.map(f => (
                  <SelectItem key={f} value={String(f)}>{f} fps</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Provider */}
        <div className="space-y-2">
          <Label className="text-xs text-muted-foreground">生成器</Label>
          <Select
            value={provider}
            onValueChange={setProvider}
            disabled={isJobRunning}
          >
            <SelectTrigger className="bg-background border-border text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PROVIDER_OPTIONS.map(opt => (
                <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <Separator />

        {/* Readiness hint */}
        {!isJobActive && !submitError && (
          <div className={`p-3 rounded-lg border text-sm flex items-start gap-2 ${
            canGenerate
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
              : 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400'
          }`}>
            {canGenerate
              ? <CheckCircle2 className="w-4 h-4 mt-0.5 flex-shrink-0" />
              : <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />}
            <span>{canGenerate ? '准备就绪，可以生成视频' : reason}</span>
          </div>
        )}

        {/* Error message */}
        {submitError && (
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 flex items-start gap-2 text-sm text-red-400">
            <XCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>{submitError}</span>
          </div>
        )}

        {/* Progress (active job) */}
        {isJobActive && (
          <div className="space-y-2 p-3 rounded-lg bg-blue-500/10 border border-blue-500/30">
            <div className="flex items-center justify-between text-sm">
              <span className="text-blue-400 flex items-center gap-1.5">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                {jobState.message ?? '生成中...'}
              </span>
              <span className="text-blue-300 text-xs tabular-nums">
                {Math.round(jobState.progress * 100)}%
              </span>
            </div>
            <Progress value={jobState.progress * 100} max={100} />
          </div>
        )}

        {/* Succeeded result */}
        {activeJobId && jobState.status === 'succeeded' && (
          <div className="space-y-3 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
            <div className="flex items-center gap-2 text-sm text-emerald-400">
              <CheckCircle2 className="w-4 h-4" />
              视频生成成功
            </div>
            {jobState.result?.video_url && (
              <a
                href={String(jobState.result.video_url)}
                target="_blank"
                rel="noopener noreferrer"
                className="block text-xs text-blue-400 underline truncate"
              >
                {String(jobState.result.video_url)}
              </a>
            )}
            <Button
              size="sm"
              variant="outline"
              className="w-full text-xs h-7"
              onClick={handleReset}
            >
              重新生成
            </Button>
          </div>
        )}

        {/* Failed result */}
        {activeJobId && jobState.status === 'failed' && (
          <div className="space-y-2 p-3 rounded-lg bg-red-500/10 border border-red-500/30">
            <div className="flex items-center gap-2 text-sm text-red-400">
              <XCircle className="w-4 h-4" />
              生成失败{jobState.error ? `：${jobState.error}` : ''}
            </div>
            <Button
              size="sm"
              variant="outline"
              className="w-full text-xs h-7"
              onClick={handleReset}
            >
              重试
            </Button>
          </div>
        )}

        {/* Primary CTA */}
        {(!activeJobId || jobState.isComplete) && jobState.status !== 'succeeded' && (
          <Button
            size="default"
            className="w-full gap-2 bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50"
            onClick={activeJobId ? handleReset : handleGenerateVideo}
            disabled={!canGenerate || isSubmitting || isJobRunning}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                提交中...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                生成视频
              </>
            )}
          </Button>
        )}

      </div>
    </ScrollArea>
  )
}
