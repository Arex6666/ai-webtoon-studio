'use client'

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import {
  Play,
  RefreshCw,
  Trash2,
  ChevronUp,
  ChevronDown,
  Focus,
  Check,
  X,
  Loader2,
  AlertCircle
} from "lucide-react"
import { Clip, ClipStatus, canGenerateClip } from "@/lib/schema/clip"
import { Provider, providerLabels } from "@/lib/schema/provider"
import { useStudioStore } from "@/lib/store/studioStore"
import { useShallow } from "zustand/react/shallow"
import { memo } from "react"

interface ClipRowProps {
  clip: Clip
  index: number
  isFirst: boolean
  isLast: boolean
}

const statusConfig: Record<ClipStatus, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
  Idle: { label: '待生成', variant: 'outline' },
  Queued: { label: '排队中', variant: 'secondary' },
  Running: { label: '生成中', variant: 'default' },
  Succeeded: { label: '已完成', variant: 'default' },
  Failed: { label: '失败', variant: 'destructive' },
}

export const ClipRow = memo(function ClipRow({ clip, index, isFirst, isLast }: ClipRowProps) {
  const {
    updateClip,
    removeClip,
    reorderClip,
    createJob,
    selectClip,
    selectPanel,
    selectedClipId,
    panelSpecs,
    unifiedJobs,
  } = useStudioStore(
    useShallow(s => ({
      updateClip: s.updateClip,
      removeClip: s.removeClip,
      reorderClip: s.reorderClip,
      createJob: s.createJob,
      selectClip: s.selectClip,
      selectPanel: s.selectPanel,
      selectedClipId: s.selectedClipId,
      panelSpecs: s.panelSpecs,
      unifiedJobs: s.unifiedJobs,
    }))
  )

  const isSelected = selectedClipId === clip.id
  const panelSpec = panelSpecs[clip.panelId]
  const panelTitle = panelSpec?.scene?.location || `Panel ${clip.panelId}`

  // Prefer live unified job state when available, fall back to clip fields
  const unifiedJob = unifiedJobs[clip.id]
  const liveStatus = unifiedJob
    ? (unifiedJob.status as ClipStatus)
    : clip.status
  const liveProgress = unifiedJob ? unifiedJob.progress : clip.progress

  const status = statusConfig[liveStatus] ?? statusConfig[clip.status]
  const isRunning = liveStatus === 'Running' || liveStatus === 'Queued'

  const handleGenerate = async () => {
    updateClip(clip.id, { status: 'Queued', progress: 0 })
    await createJob('video', clip.id, clip.provider, {
      durationSec: clip.durationSec,
      fps: clip.fps,
      motionPrompt: clip.motionPrompt,
    })
  }

  // 使用 canGenerateClip 验证
  const { canGenerate, reason } = canGenerateClip(clip)
  const showGenerateButton = liveStatus === 'Idle' || liveStatus === 'Failed'

  return (
    <div
      className={`flex items-center gap-2 p-2 rounded-md border transition-colors ${isSelected ? 'border-accent bg-accent/10' : 'border-transparent hover:bg-muted/50'
        }`}
      onClick={() => selectClip(clip.id)}
    >
      {/* 序号 */}
      <div className="w-6 text-center text-xs text-muted-foreground">
        {index + 1}
      </div>

      {/* Panel 信息 */}
      <div className="w-24 truncate text-xs">
        {panelTitle}
      </div>

      {/* 关键帧状态指示器 */}
      <TooltipProvider>
        <div className="flex items-center gap-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <span className={`text-xs font-mono ${clip.startFrame ? 'text-emerald-400' : 'text-yellow-400'}`}>
                S{clip.startFrame ? '✓' : '!'}
              </span>
            </TooltipTrigger>
            <TooltipContent>
              <p>{clip.startFrame ? '起始帧已设置' : '未设置起始帧'}</p>
            </TooltipContent>
          </Tooltip>

          {clip.motionMode === 'dual_keyframe' && (
            <Tooltip>
              <TooltipTrigger asChild>
                <span className={`text-xs font-mono ${clip.endFrame ? 'text-emerald-400' : 'text-yellow-400'}`}>
                  E{clip.endFrame ? '✓' : '!'}
                </span>
              </TooltipTrigger>
              <TooltipContent>
                <p>{clip.endFrame ? '结束帧已设置' : '未设置结束帧'}</p>
              </TooltipContent>
            </Tooltip>
          )}
        </div>
      </TooltipProvider>

      {/* 时长 */}
      <Input
        type="number"
        value={clip.durationSec}
        onChange={(e) => updateClip(clip.id, { durationSec: parseFloat(e.target.value) || 1 })}
        className="w-16 h-7 text-xs"
        min={0.5}
        max={10}
        step={0.5}
        onClick={(e) => e.stopPropagation()}
      />
      <span className="text-xs text-muted-foreground">秒</span>

      {/* FPS */}
      <Select
        value={String(clip.fps)}
        onValueChange={(v) => updateClip(clip.id, { fps: parseInt(v) })}
      >
        <SelectTrigger className="w-16 h-7 text-xs" onClick={(e) => e.stopPropagation()}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="6">6fps</SelectItem>
          <SelectItem value="8">8fps</SelectItem>
          <SelectItem value="12">12fps</SelectItem>
          <SelectItem value="24">24fps</SelectItem>
        </SelectContent>
      </Select>

      {/* Provider */}
      <Select
        value={clip.provider}
        onValueChange={(v) => updateClip(clip.id, { provider: v as Provider })}
      >
        <SelectTrigger className="w-24 h-7 text-xs" onClick={(e) => e.stopPropagation()}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {Object.entries(providerLabels).map(([key, label]) => (
            <SelectItem key={key} value={key}>{label}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* 状态 & 进度 */}
      <div className="w-20 flex items-center gap-1">
        <Badge variant={status.variant} className="text-xs h-5">
          {liveStatus === 'Running' && <Loader2 className="w-3 h-3 mr-1 animate-spin" />}
          {liveStatus === 'Succeeded' && <Check className="w-3 h-3 mr-1" />}
          {liveStatus === 'Failed' && <X className="w-3 h-3 mr-1" />}
          {status.label}
        </Badge>
      </div>

      {/* 进度条 */}
      {isRunning && (
        <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-accent transition-all"
            style={{ width: `${liveProgress * 100}%` }}
          />
        </div>
      )}

      {/* 操作按钮 */}
      <div className="flex items-center gap-1 ml-auto">
        {showGenerateButton && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <span>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-6 px-2 text-xs"
                    disabled={!canGenerate}
                    onClick={(e) => {
                      e.stopPropagation()
                      if (canGenerate) {
                        handleGenerate()
                      }
                    }}
                  >
                    <Play className="w-3 h-3 mr-1" />
                    生成
                  </Button>
                </span>
              </TooltipTrigger>
              {!canGenerate && reason && (
                <TooltipContent>
                  <p className="flex items-center gap-1">
                    <AlertCircle className="w-3 h-3" />
                    {reason}
                  </p>
                </TooltipContent>
              )}
            </Tooltip>
          </TooltipProvider>
        )}

        {liveStatus === 'Failed' && (
          <Button
            size="sm"
            variant="outline"
            className="h-6 px-2 text-xs"
            onClick={(e) => {
              e.stopPropagation()
              handleGenerate()
            }}
          >
            <RefreshCw className="w-3 h-3 mr-1" />
            重试
          </Button>
        )}

        <Button
          size="sm"
          variant="ghost"
          className="h-6 w-6 p-0"
          onClick={(e) => {
            e.stopPropagation()
            selectPanel(clip.panelId)
          }}
          title="定位到面板"
        >
          <Focus className="w-3 h-3" />
        </Button>

        <Button
          size="sm"
          variant="ghost"
          className="h-6 w-6 p-0"
          disabled={isFirst}
          onClick={(e) => {
            e.stopPropagation()
            reorderClip(clip.id, 'up')
          }}
        >
          <ChevronUp className="w-3 h-3" />
        </Button>

        <Button
          size="sm"
          variant="ghost"
          className="h-6 w-6 p-0"
          disabled={isLast}
          onClick={(e) => {
            e.stopPropagation()
            reorderClip(clip.id, 'down')
          }}
        >
          <ChevronDown className="w-3 h-3" />
        </Button>

        <Button
          size="sm"
          variant="ghost"
          className="h-6 w-6 p-0 text-destructive hover:text-destructive"
          onClick={(e) => {
            e.stopPropagation()
            removeClip(clip.id)
          }}
        >
          <Trash2 className="w-3 h-3" />
        </Button>
      </div>
    </div>
  )
})
