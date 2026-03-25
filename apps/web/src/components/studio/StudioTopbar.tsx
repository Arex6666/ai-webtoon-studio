'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Save, Play, Download, Upload, ChevronDown, Zap, Sparkles, ArrowLeft, Wand2, Film, Loader2 } from "lucide-react"
import { useStudioStore } from '@/lib/store/studioStore'
import { useShallow } from 'zustand/react/shallow'
import { useToast } from '@/hooks/use-toast'
import { ImportModal } from './modals/ImportModal'
import { BatchRenderButton } from './controls/BatchRenderButton'
import { RenderProvider } from '@/lib/schema/job'
import { chaptersApi, renderApi } from '@/lib/api/services'
import type { PanelSummary } from '@/lib/api/types'
import { useStoryboardGeneration } from '@/hooks/useStoryboardGeneration'

interface StudioTopbarProps {
  projectId: string
  chapterId: string
  projectName?: string
  chapterTitle?: string
}

const PROVIDERS: { value: RenderProvider; label: string; icon: React.ReactNode }[] = [
  { value: 'mock', label: 'Mock (测试)', icon: <Zap className="w-4 h-4" /> },
  { value: 'comfyui', label: 'ComfyUI', icon: <Sparkles className="w-4 h-4" /> },
  { value: 'keling', label: 'Keling 可灵', icon: <Sparkles className="w-4 h-4" /> },
  { value: 'tongyi', label: '通义万相', icon: <Sparkles className="w-4 h-4" /> },
  { value: 'doubao', label: '豆包', icon: <Sparkles className="w-4 h-4" /> },
]

export function StudioTopbar({ projectId, chapterId, projectName, chapterTitle }: StudioTopbarProps) {
  const {
    saveChapterDraft,
    exportChapterSpec,
    enqueueRender,
    selectedPanelId,
    panelList,
    script,
    setPanelList,
    selectPanel,
    canRender,
    pendingAssetsCount,
  } = useStudioStore(
    useShallow(s => ({ saveChapterDraft: s.saveChapterDraft, exportChapterSpec: s.exportChapterSpec, enqueueRender: s.enqueueRender, selectedPanelId: s.selectedPanelId, panelList: s.panelList, script: s.script, setPanelList: s.setPanelList, selectPanel: s.selectPanel, canRender: s.canRender, pendingAssetsCount: s.pendingAssetsCount }))
  )
  const { toast } = useToast()
  const [showImportModal, setShowImportModal] = useState(false)
  const [selectedProvider, setSelectedProvider] = useState<RenderProvider>('mock')
  const [batchVideoRunning, setBatchVideoRunning] = useState(false)
  // const [isGenerating, setIsGenerating] = useState(false) // Moved to hook

  // 工作流状态判断
  const hasScript = script.trim().length > 0
  const hasPanels = panelList.length > 0
  const hasSelection = !!selectedPanelId

  const handleSave = () => {
    saveChapterDraft()
    toast({
      title: "草稿已保存",
      description: "您的更改已保存到本地存储",
    })
  }

  const handleExport = () => {
    if (!hasPanels) {
      toast({
        title: "没有可导出的数据",
        description: "请先生成分镜",
        variant: "destructive",
      })
      return
    }

    const json = exportChapterSpec()
    if (!json) {
      toast({
        title: "导出失败",
        description: "没有可导出的数据",
        variant: "destructive",
      })
      return
    }

    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `chapter-${chapterId}-spec.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)

    toast({
      title: "导出成功",
      description: `已下载 chapter-${chapterId}-spec.json`,
    })
  }

  const handleExportStripPNG = async () => {
    const renderedPanels = panelList.filter(p => p.status === 'Rendered')

    if (renderedPanels.length === 0) {
      toast({
        title: "没有可导出的分镜",
        description: "请先渲染分镜后再导出",
        variant: "destructive",
      })
      return
    }

    toast({
      title: "开始导出...",
      description: `正在合成 ${renderedPanels.length} 格分镜`,
    })

    try {
      // P0: Call strip export API
      const response = await fetch(`/api/v1/export/strip`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chapter_id: chapterId,
          output_width: 1080,
          gap: 0,
          background_color: '#FFFFFF',
          direct_download: false
        })
      })

      if (!response.ok) {
        throw new Error('导出失败')
      }

      const result = await response.json()

      if (result.success && result.download_url) {
        // Download the file
        window.open(result.download_url, '_blank')

        toast({
          title: "导出成功",
          description: `已生成 ${result.panel_count} 格长条漫 PNG`,
        })
      } else {
        throw new Error(result.error || '导出失败')
      }

    } catch (error) {
      toast({
        title: "导出失败",
        description: error instanceof Error ? error.message : "请检查网络连接后重试",
        variant: "destructive",
      })
    }
  }

  const handleBatchVideo = async () => {
    const { panelList, createJob } = useStudioStore.getState()
    const rendered = panelList.filter(p => p.status === 'Rendered')

    if (rendered.length === 0) {
      toast({ title: '无可用面板', description: '请先渲染面板图片' })
      return
    }

    if (!confirm(`将为 ${rendered.length} 个已渲染面板生成视频，确认？`)) return

    setBatchVideoRunning(true)
    try {
      const CONCURRENCY = 5
      for (let i = 0; i < rendered.length; i += CONCURRENCY) {
        const batch = rendered.slice(i, i + CONCURRENCY)
        await Promise.allSettled(
          batch.map(async (panel) => {
            // Use panel.id as clip target — the backend video worker
            // will resolve the start frame from the panel's preview
            const clipId = panel.id
            return createJob('video', clipId, 'doubao', {
              start_frame_url: panel.previewUrl || '',
              motion_prompt: panel.description || '',
              duration_sec: 3,
              fps: 24,
            })
          })
        )
      }
      toast({ title: '批量视频已启动', description: `${rendered.length} 个任务已提交` })
    } catch (e) {
      toast({ title: '批量视频失败', description: String(e), variant: 'destructive' })
    } finally {
      setBatchVideoRunning(false)
    }
  }

  // 使用共享 Hook
  const { isGenerating, generateStoryboard } = useStoryboardGeneration()

  const handleAIStoryboard = async () => {
    await generateStoryboard(selectedProvider)
  }

  const handleRenderCurrent = () => {
    if (!selectedPanelId) {
      toast({
        title: "请先选择分镜",
        description: "点击故事板中的分镜卡片来选择要渲染的分镜",
        variant: "destructive",
      })
      return
    }

    enqueueRender([selectedPanelId], selectedProvider)
    toast({
      title: "渲染任务已创建",
      description: `分镜已加入渲染队列 (${selectedProvider})`,
    })
  }

  const handleRenderAll = () => {
    const allPanelIds = panelList.map(p => p.id)
    if (allPanelIds.length === 0) {
      toast({
        title: "没有分镜可渲染",
        description: "请先生成分镜",
        variant: "destructive",
      })
      return
    }

    if (!confirm(`确定要批量渲染所有 ${allPanelIds.length} 个分镜吗？这可能需要一些时间。`)) {
      return
    }

    enqueueRender(allPanelIds, selectedProvider)
    toast({
      title: "批量渲染已启动",
      description: `${allPanelIds.length} 个分镜已加入渲染队列`,
    })
  }

  const currentProvider = PROVIDERS.find(p => p.value === selectedProvider)

  return (
    <>
      <div className="h-14 border-b border-white/5 bg-muted/5 flex items-center justify-between px-4">
        {/* 左侧：面包屑与标题 */}
        <div className="flex items-center gap-3 text-sm">
          <Link href={`/projects/${projectId}`}>
            <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full text-muted-foreground hover:text-foreground transition-colors">
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div className="flex items-center gap-2">
            <span className="font-medium text-muted-foreground hidden md:inline-block hover:text-foreground transition-colors cursor-default">
              {projectName || "加载中..."}
            </span>
            <span className="text-muted-foreground/50 hidden md:inline-block">/</span>
            <span className="font-semibold text-foreground/90 truncate max-w-[200px]">
              {chapterTitle || "加载中..."}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Provider Selector */}
          <Select value={selectedProvider} onValueChange={(v) => setSelectedProvider(v as RenderProvider)}>
            <SelectTrigger className="h-8 w-[130px] text-xs bg-muted/20 border-white/5">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PROVIDERS.map((p) => (
                <SelectItem key={p.value} value={p.value}>
                  <div className="flex items-center gap-2">
                    {p.icon}
                    <span>{p.label}</span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* 分隔线 */}
          <div className="w-px h-6 bg-white/10" />

          {/* 主按钮：AI 分镜 (工作流第一步) */}
          <Button
            size="sm"
            onClick={handleAIStoryboard}
            disabled={!hasScript || isGenerating}
            className="h-8 px-4 text-xs bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-white shadow-lg shadow-emerald-500/20 gap-2 disabled:opacity-50 disabled:shadow-none"
          >
            <Wand2 className="w-3.5 h-3.5" />
            {isGenerating ? 'AI 分镜中...' : 'AI 分镜'}
          </Button>

          {/* 分隔线 */}
          <div className="w-px h-6 bg-white/10" />

          {/* 组1：文件操作 */}
          <div className="flex items-center bg-muted/10 rounded-lg p-0.5 border border-white/5">
            <Button size="sm" variant="ghost" className="h-7 px-2.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/20 transition-colors" onClick={handleSave}>
              <Save className="mr-1 h-3 w-3" />
              保存
            </Button>
            <div className="w-px h-3 bg-white/10" />
            <Button size="sm" variant="ghost" className="h-7 px-2.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/20 transition-colors" onClick={() => setShowImportModal(true)}>
              <Upload className="mr-1 h-3 w-3" />
              导入
            </Button>
            <div className="w-px h-3 bg-white/10" />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 px-2.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/20 transition-colors disabled:opacity-40"
                  disabled={!hasPanels}
                >
                  <Download className="mr-1 h-3 w-3" />
                  导出
                  <ChevronDown className="ml-1 h-3 w-3" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48">
                <DropdownMenuItem onClick={handleExport}>
                  <Download className="mr-2 h-4 w-4" />
                  导出 JSON 规格
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleExportStripPNG} disabled={panelList.filter(p => p.status === 'Rendered').length === 0}>
                  <Download className="mr-2 h-4 w-4" />
                  导出长条漫 PNG
                  <span className="ml-auto text-xs text-muted-foreground">
                    {panelList.filter(p => p.status === 'Rendered').length}格
                  </span>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => useStudioStore.getState().enqueueExport()}>
                  <Download className="mr-2 h-4 w-4" />
                  导出视频/Bundle (后台任务)
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          {/* 组2：渲染控制 (S3-08: 使用 BatchRenderButton) */}
          {hasPanels && (
            <BatchRenderButton
              chapterId={chapterId}
              canRender={canRender}
              pendingAssetsCount={pendingAssetsCount}
              onOpenAssetsLock={() => {
                // 切换到资产锁定 tab
                useStudioStore.setState({
                  showAssetsLockPanel: true,
                  activeInspectorTab: 'assets-lock'
                })
              }}
              onRenderStart={() => {
                toast({
                  title: "渲染已启动",
                  description: "正在渲染所有分镜...",
                })
              }}
              onRenderComplete={() => {
                toast({
                  title: "渲染完成",
                  description: "所有分镜已渲染完成",
                })
              }}
            />
          )}

          {/* 批量视频：为所有已渲染面板生成视频 */}
          {hasPanels && (
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5 border-violet-500/30 text-violet-400 hover:bg-violet-500/10"
              onClick={handleBatchVideo}
              disabled={batchVideoRunning}
            >
              {batchVideoRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Film className="w-4 h-4" />}
              批量视频
            </Button>
          )}
        </div>
      </div>

      <ImportModal open={showImportModal} onOpenChange={setShowImportModal} />
    </>
  )
}
