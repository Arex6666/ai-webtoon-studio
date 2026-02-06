'use client'

import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Download, Film, Clock } from "lucide-react"
import { useStudioStore } from "@/lib/store/studioStore"
import { calculateTotalDuration } from "@/lib/schema/timeline"
import { ClipRow } from "./ClipRow"

export function TimelinePanel() {
  const {
    projectId,
    chapterId,
    timelineByChapter,
    updateTimelineSettings,
    enqueueExport,
    buildExportSpec,
  } = useStudioStore()

  const key = projectId && chapterId ? `${projectId}:${chapterId}` : null
  const timeline = key ? timelineByChapter[key] : null
  const clips = timeline?.clips || []
  const totalDuration = calculateTotalDuration(clips)

  const handleExport = () => {
    const spec = buildExportSpec()
    if (spec) {
      // 下载 JSON
      const blob = new Blob([JSON.stringify(spec, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `export-spec-${chapterId}.json`
      a.click()
      URL.revokeObjectURL(url)
    }
  }

  if (!timeline) {
    return (
      <div className="h-full flex items-center justify-center text-muted-foreground text-sm">
        请先进入章节工作台
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      {/* 顶部汇总条 */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-panel-border">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5 text-sm">
            <Film className="w-4 h-4 text-muted-foreground" />
            <span className="font-medium">{clips.length}</span>
            <span className="text-muted-foreground">个片段</span>
          </div>
          <div className="flex items-center gap-1.5 text-sm">
            <Clock className="w-4 h-4 text-muted-foreground" />
            <span className="font-medium">{totalDuration.toFixed(1)}</span>
            <span className="text-muted-foreground">秒</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* FPS 默认值 */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-muted-foreground">默认FPS:</span>
            <Select
              value={String(timeline.settings.fpsDefault)}
              onValueChange={(v) => updateTimelineSettings({ fpsDefault: parseInt(v) })}
            >
              <SelectTrigger className="w-16 h-7 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="6">6</SelectItem>
                <SelectItem value="8">8</SelectItem>
                <SelectItem value="12">12</SelectItem>
                <SelectItem value="24">24</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* 画幅 */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-muted-foreground">画幅:</span>
            <Select
              value={timeline.settings.aspect}
              onValueChange={(v) => updateTimelineSettings({ aspect: v as '9:16' | '16:9' | '1:1' })}
            >
              <SelectTrigger className="w-16 h-7 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="9:16">9:16</SelectItem>
                <SelectItem value="16:9">16:9</SelectItem>
                <SelectItem value="1:1">1:1</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* 导出按钮 */}
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs"
            onClick={handleExport}
            disabled={clips.length === 0}
          >
            <Download className="w-3.5 h-3.5 mr-1.5" />
            导出 ExportSpec
          </Button>
        </div>
      </div>

      {/* Clip 列表 */}
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1">
          {clips.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              从 Storyboard 选择一个分镜，点击 "+ Timeline" 添加片段
            </div>
          ) : (
            clips.map((clip, index) => (
              <ClipRow
                key={clip.id}
                clip={clip}
                index={index}
                isFirst={index === 0}
                isLast={index === clips.length - 1}
              />
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
