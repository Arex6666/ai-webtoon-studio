'use client'

import { useState } from 'react'
import { useStudioStore } from "@/lib/store/studioStore"
import { PanelCard } from "./PanelCard"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Button } from "@/components/ui/button"
import { Sparkles, Upload, FileText, Layers, Loader2 } from "lucide-react"
import { useStoryboardGeneration } from "@/hooks/useStoryboardGeneration"
import { PanelEditorModal } from "../modals/PanelEditorModal"

export function StoryboardView() {
  const { panelList, selectedPanelId, selectPanel } = useStudioStore()
  const { isGenerating, generateStoryboard } = useStoryboardGeneration()
  const [editingPanelId, setEditingPanelId] = useState<string | null>(null)

  // 空状态：没有分镜
  if (panelList.length === 0) {
    return (
      <div className="h-full flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-white/5 bg-gradient-to-r from-panel/50 to-transparent">
          <h3 className="font-semibold text-foreground/80">故事板</h3>
        </div>

        {/* Empty state with premium design */}
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="max-w-md text-center space-y-6 relative">
            {/* Decorative gradient orbs */}
            <div className="absolute top-0 -right-20 w-40 h-40 bg-accent/5 rounded-full blur-3xl" />
            <div className="absolute bottom-0 -left-10 w-32 h-32 bg-accent/3 rounded-full blur-2xl" />

            {/* Icon */}
            <div className="relative mx-auto">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-slate-700/30 to-slate-800/10 border border-slate-700/20 flex items-center justify-center">
                <Layers className="w-9 h-9 text-slate-500" />
              </div>
              <div className="absolute inset-0 bg-emerald-500/10 rounded-2xl blur-xl" />
            </div>

            {/* Title & Description */}
            <div className="space-y-3 relative">
              <h2 className="text-xl font-semibold text-foreground/90">还没有分镜</h2>
              <p className="text-sm text-muted-foreground leading-relaxed">
                先在左侧粘贴剧本，然后点击「AI 分镜」自动生成分镜。
                <br />
                AI 将拆分镜头、识别人物与场景，并创建渲染计划。
              </p>
            </div>

            {/* Actions */}
            <div className="flex flex-col sm:flex-row gap-3 justify-center relative">
              <Button
                onClick={() => generateStoryboard('mock')}
                disabled={isGenerating}
                className="bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500 text-white gap-2 px-5 shadow-lg shadow-emerald-500/20"
              >
                {isGenerating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                {isGenerating ? 'AI 生成中...' : 'AI 分镜'}
              </Button>
              <Button variant="outline" className="border-white/10 text-muted-foreground hover:text-foreground hover:bg-white/5 gap-2">
                <Upload className="w-4 h-4" />
                导入分镜 JSON
              </Button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // 正常状态：有分镜
  return (
    <div className="h-full flex flex-col">
      {/* Enhanced header with count badge */}
      <div className="p-4 border-b border-white/5 bg-gradient-to-r from-panel/50 to-transparent flex items-center justify-between">
        <h3 className="font-semibold text-foreground/80">故事板</h3>
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-gradient-to-r from-slate-700/30 to-slate-800/10 border border-slate-700/20 text-slate-400">
          <Layers className="w-3 h-3" />
          {panelList.length} 个分镜
        </span>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-3 space-y-3 max-w-4xl mx-auto w-full">
          {panelList.map((panel, index) => (
            <PanelCard
              key={panel.id || `panel-${index}`}
              panel={panel}
              selected={selectedPanelId === panel.id}
              onClick={() => selectPanel(panel.id)}
              onDoubleClick={() => setEditingPanelId(panel.id)}
            />
          ))}
        </div>
      </ScrollArea>
      <PanelEditorModal
        panelId={editingPanelId}
        onClose={() => setEditingPanelId(null)}
      />
    </div>
  )
}

