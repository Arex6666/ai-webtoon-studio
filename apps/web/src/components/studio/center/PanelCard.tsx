'use client'

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils/cn"
import { useStudioStore } from "@/lib/store/studioStore"
import { Loader2, Clock, CheckCircle, AlertCircle, FileEdit, Plus, Image as ImageIcon, Sparkles, RefreshCw } from "lucide-react"

interface PanelCardProps {
  panel: {
    id: string
    index: number
    title: string
    description?: string
    location?: string
    shotType?: string
    duration?: number
    status: 'Draft' | 'Queued' | 'Running' | 'Rendered' | 'NeedsFix'
    previewUrl?: string  // P0: 渲染预览图 URL
  }
  selected: boolean
  onClick: () => void
  onDoubleClick?: () => void
}

const STATUS_CONFIG = {
  Draft: {
    icon: FileEdit,
    gradient: 'from-slate-600 to-slate-700',
    textColor: 'text-slate-50',
    label: '草稿',
    animate: false,
    glow: 'slate',
  },
  Queued: {
    icon: Clock,
    gradient: 'from-amber-500 to-orange-500',
    textColor: 'text-amber-50',
    label: '排队中',
    animate: false,
    glow: 'amber',
  },
  Running: {
    icon: Loader2,
    gradient: 'from-indigo-500 to-blue-500',
    textColor: 'text-indigo-50',
    label: '渲染中',
    animate: true,
    glow: 'indigo',
  },
  Rendered: {
    icon: CheckCircle,
    gradient: 'from-emerald-500 to-teal-500',
    textColor: 'text-emerald-50',
    label: '完成',
    animate: false,
    glow: 'emerald',
  },
  NeedsFix: {
    icon: AlertCircle,
    gradient: 'from-rose-500 to-pink-500',
    textColor: 'text-rose-50',
    label: '需修复',
    animate: false,
    glow: 'rose',
  },
}

export function PanelCard({ panel, selected, onClick, onDoubleClick }: PanelCardProps) {
  const { jobs, addPanelAsClip, setStudioData, chapterId } = useStudioStore()

  // 查找当前面板的运行中任务以获取进度
  const activeJob = Object.values(jobs).find(
    job => job.panelId === panel.id && (job.status === 'Running' || job.status === 'Queued')
  )
  const progress = activeJob?.progress || 0
  const isRunning = panel.status === 'Running'

  // 渲染按钮状态
  const canRender = panel.status === 'Draft' || panel.status === 'NeedsFix'
  const renderJob = Object.values(jobs).find(job => job.panelId === panel.id && job.status === 'Running')

  const handleRender = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!chapterId) return

    try {
      const { renderApi, chaptersApi } = await import('@/lib/api/services')
      await renderApi.renderPanel(panel.id, true)

      // 轻量刷新一次，确保 preview_url 能尽快落到 UI
      const studioData = await chaptersApi.getStudio(chapterId)
      setStudioData(studioData)
    } catch (err) {
      console.error('Failed to render panel:', err)
      alert('生成面板图失败: ' + (err instanceof Error ? err.message : '未知错误'))
    }
  }

  const config = STATUS_CONFIG[panel.status] || STATUS_CONFIG.Draft
  const Icon = config.icon

  return (
    <div
      className={cn(
        "group relative flex gap-4 p-4 rounded-2xl transition-all duration-300 cursor-pointer select-none",
        // Glass morphism base
        "bg-gradient-to-br from-white/[0.03] to-transparent",
        "backdrop-blur-sm",
        "border border-white/[0.06]",
        // Hover state
        "hover:bg-white/[0.05] hover:border-white/[0.1] hover:shadow-lg hover:shadow-emerald-500/5",
        // Selected state with gradient border
        selected && "bg-emerald-500/5 border-emerald-500/30 ring-1 ring-emerald-500/20 shadow-lg shadow-emerald-500/5",
        // Error state
        panel.status === 'NeedsFix' && "border-red-500/30 bg-red-500/5"
      )}
      onClick={onClick}
      onDoubleClick={onDoubleClick}
    >
      {/* Selected gradient accent bar */}
      {selected && (
        <div className="absolute left-0 top-2 bottom-2 w-1 rounded-full bg-gradient-to-b from-emerald-500 via-emerald-500/80 to-emerald-500/40" />
      )}

      {/* Running Progress Background */}
      {isRunning && (
        <div className="absolute inset-0 rounded-2xl overflow-hidden z-0 pointer-events-none">
          <div
            className="absolute inset-y-0 left-0 bg-gradient-to-r from-blue-500/10 to-transparent transition-all duration-500"
            style={{ width: `${progress * 100}%` }}
          />
          {/* Shimmer effect */}
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/[0.02] to-transparent animate-shimmer" />
        </div>
      )}

      {/* Left: Thumbnail */}
      <div className="flex flex-col gap-2 relative z-10">
        {/* Panel number badge */}
        <div className="flex items-center">
          <span className="inline-flex items-center justify-center w-7 h-5 rounded-md bg-gradient-to-br from-slate-700/40 to-slate-800/20 border border-slate-700/30 text-[10px] font-mono font-bold text-slate-400">
            #{String(panel.index + 1).padStart(2, '0')}
          </span>
        </div>

        {/* Thumbnail - Larger size */}
        <div className="relative w-32 aspect-video rounded-xl overflow-hidden bg-gradient-to-br from-black/30 to-black/50 border border-white/[0.06] flex items-center justify-center shadow-inner group-hover:border-white/[0.1] transition-colors">
          {panel.previewUrl ? (
            <img
              src={panel.previewUrl}
              alt={panel.title}
              className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = 'none'
              }}
            />
          ) : (
            <div className="flex flex-col items-center gap-1">
              <ImageIcon className="w-5 h-5 text-white/10" />
              <span className="text-[9px] text-white/20">待渲染</span>
            </div>
          )}

          {/* Render progress overlay */}
          {isRunning && (
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent flex flex-col items-center justify-end pb-2">
              <div className="w-3/4 h-1 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-400 to-blue-500 rounded-full transition-all duration-300"
                  style={{ width: `${progress * 100}%` }}
                />
              </div>
              <span className="text-[10px] text-white font-medium mt-1">
                {Math.round(progress * 100)}%
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Center: Content */}
      <div className="flex-1 min-w-0 flex flex-col gap-2 py-0.5 relative z-10">
        {/* Header row */}
        <div className="flex items-start justify-between gap-3">
          <span className="text-sm font-semibold text-foreground/90 group-hover:text-foreground transition-colors line-clamp-1">
            {panel.title}
          </span>

          {/* Status Badge - Pill with gradient */}
          <Badge
            className={cn(
              "shrink-0 h-5 px-2 text-[10px] font-medium border-0 shadow-sm",
              "bg-gradient-to-r",
              config.gradient,
              config.textColor
            )}
          >
            <Icon className={cn("w-3 h-3 mr-1", config.animate && "animate-spin")} />
            {config.label}
          </Badge>
        </div>

        {/* Description */}
        <p className="text-xs text-muted-foreground/70 leading-relaxed line-clamp-2 group-hover:text-muted-foreground/80 transition-colors">
          {panel.description || "未填写描述"}
        </p>

        {/* Meta chips */}
        <div className="flex items-center gap-1.5 flex-wrap mt-auto pt-1">
          {panel.shotType && (
            <span className="inline-flex items-center text-[10px] px-2 py-0.5 rounded-md bg-gradient-to-r from-white/[0.05] to-transparent border border-white/[0.06] text-muted-foreground/70">
              {panel.shotType}
            </span>
          )}
          {panel.duration && (
            <span className="inline-flex items-center text-[10px] px-2 py-0.5 rounded-md bg-gradient-to-r from-white/[0.05] to-transparent border border-white/[0.06] text-muted-foreground/70">
              <Clock className="w-2.5 h-2.5 mr-1 opacity-60" />
              {panel.duration}s
            </span>
          )}
          {panel.location && panel.location !== 'Unknown Location' && (
            <span className="inline-flex items-center text-[10px] px-2 py-0.5 rounded-md bg-gradient-to-r from-white/[0.05] to-transparent border border-white/[0.06] text-muted-foreground/70 max-w-[120px] truncate">
              {panel.location}
            </span>
          )}
        </div>
      </div>

      {/* Action Buttons - Slide up on hover */}
      <div className="absolute right-3 bottom-3 opacity-0 translate-y-2 group-hover:opacity-100 group-hover:translate-y-0 transition-all duration-300 z-20 flex items-center gap-2">
        <Button
          size="icon"
          className={cn(
            "h-7 w-7 rounded-lg shadow-lg border-0",
            panel.previewUrl
              ? "bg-gradient-to-br from-indigo-500 to-blue-600 text-white hover:from-indigo-400 hover:to-blue-500"
              : "bg-gradient-to-br from-purple-500 to-fuchsia-600 text-white hover:from-purple-400 hover:to-fuchsia-500",
            !canRender && "opacity-60 cursor-not-allowed"
          )}
          onClick={handleRender}
          disabled={!canRender}
          title={panel.previewUrl ? "重新渲染" : "生成面板图"}
        >
          {renderJob ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : panel.previewUrl ? (
            <RefreshCw className="w-3.5 h-3.5" />
          ) : (
            <Sparkles className="w-3.5 h-3.5" />
          )}
        </Button>

        <Button
          size="icon"
          className="h-7 w-7 rounded-lg shadow-lg bg-gradient-to-br from-emerald-500 to-emerald-600 text-white hover:from-emerald-400 hover:to-emerald-500 border-0"
          onClick={(e) => {
            e.stopPropagation()
            addPanelAsClip(panel.id)
          }}
          title="Add to Timeline"
        >
          <Plus className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  )
}

