'use client'

import { useStudioStore } from "@/lib/store/studioStore"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { InspectorFormProvider } from "./InspectorFormProvider"
import { InspectorStory } from "./InspectorStory"
import { InspectorCast } from "./InspectorCast"
import { InspectorLayout } from "./InspectorLayout"
import { InspectorLayers } from "./InspectorLayers"
import { InspectorTimeline } from "./InspectorTimeline"
import { InspectorConsistency } from "./InspectorConsistency"
import { InspectorAnchors } from "./InspectorAnchors"
import { InspectorQA } from "./InspectorQA"
import { AssetsLockPanel } from "../panels/AssetsLockPanel"
import { FileText, MousePointerClick, Link } from "lucide-react"

export function InspectorTabs() {
  const {
    selectedPanelId,
    selectedClipId,
    panelList,
    chapterId,
    // S3-08: Assets lock state
    pendingAssetsCount,
    activeInspectorTab,
    canRender
  } = useStudioStore()

  // 空状态 1：没有分镜
  if (panelList.length === 0) {
    return (
      <div className="h-full flex flex-col">
        <div className="p-4 border-b border-white/5 bg-gradient-to-r from-panel/50 to-transparent">
          <h3 className="font-semibold text-foreground/80">属性面板</h3>
        </div>
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="text-center space-y-5 max-w-xs relative">
            {/* Decorative gradient orb */}
            <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 rounded-full blur-2xl" />

            {/* Icon with gradient */}
            <div className="relative mx-auto">
              <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-slate-700/30 to-slate-800/10 border border-slate-700/20 flex items-center justify-center">
                <FileText className="w-7 h-7 text-slate-500" />
              </div>
              <div className="absolute inset-0 bg-emerald-500/10 rounded-xl blur-lg" />
            </div>

            <div className="space-y-2 relative">
              <p className="text-sm font-semibold text-foreground/80">还没有分镜</p>
              <p className="text-xs text-muted-foreground leading-relaxed">
                请先粘贴剧本并生成分镜，然后在这里编辑分镜参数。
              </p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // 空状态 2：有分镜但未选中（但 assets-lock tab 可用）
  const showPanelInspector = selectedPanelId || selectedClipId

  // Tab 切换处理
  const handleTabChange = (value: string) => {
    useStudioStore.setState({ activeInspectorTab: value })
  }

  // Tab 样式类
  const tabClass = "text-xs px-3 min-w-fit h-full rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-muted/20 text-muted-foreground data-[state=active]:text-foreground whitespace-nowrap"

  return (
    <InspectorFormProvider>
      <div className="h-full flex flex-col min-h-0">
        <div className="p-4 border-b border-white/5 bg-gradient-to-r from-panel/50 to-transparent">
          <h3 className="font-semibold text-foreground/80">属性面板</h3>
        </div>
        <Tabs
          value={activeInspectorTab}
          onValueChange={handleTabChange}
          className="flex-1 flex flex-col min-h-0"
        >
          {/* S3-08: Tab 滚动 + AssetsLock Tab 带 badge */}
          <TabsList className="w-full justify-start rounded-none border-b border-white/5 h-10 p-0 overflow-x-auto flex-nowrap scrollbar-hide bg-muted/10">
            <TabsTrigger value="story" className={tabClass}>镜头</TabsTrigger>
            <TabsTrigger value="cast" className={tabClass}>角色</TabsTrigger>
            <TabsTrigger value="layout" className={tabClass}>构图</TabsTrigger>
            <TabsTrigger value="layers" className={tabClass}>图层</TabsTrigger>
            <TabsTrigger value="timeline" className={tabClass}>时间轴</TabsTrigger>

            {/* S3-08: 资产锁定 Tab (带 badge) */}
            <TabsTrigger value="assets-lock" className={`${tabClass} relative`}>
              <Link className="w-3 h-3 mr-1" />
              资产锁定
              {pendingAssetsCount > 0 && (
                <Badge
                  variant="destructive"
                  className="ml-1.5 h-4 min-w-[16px] px-1 text-[10px] font-medium"
                >
                  {pendingAssetsCount}
                </Badge>
              )}
            </TabsTrigger>

            <TabsTrigger value="consistency" className={tabClass}>一致性</TabsTrigger>
            <TabsTrigger value="anchors" className={tabClass}>控制图</TabsTrigger>
            <TabsTrigger value="qa" className={tabClass}>QA</TabsTrigger>
          </TabsList>

          {/* 分镜相关 tabs - 需要选中分镜 */}
          {showPanelInspector ? (
            <>
              <TabsContent value="story" className="flex-1 overflow-auto m-0">
                <InspectorStory />
              </TabsContent>
              <TabsContent value="cast" className="flex-1 overflow-auto m-0">
                <InspectorCast />
              </TabsContent>
              <TabsContent value="layout" className="flex-1 overflow-auto m-0">
                <InspectorLayout />
              </TabsContent>
              <TabsContent value="layers" className="flex-1 overflow-auto m-0">
                <InspectorLayers />
              </TabsContent>
              <TabsContent value="timeline" className="flex-1 overflow-auto m-0">
                <InspectorTimeline />
              </TabsContent>
              <TabsContent value="consistency" className="flex-1 overflow-auto m-0">
                <InspectorConsistency />
              </TabsContent>
              <TabsContent value="anchors" className="flex-1 overflow-auto m-0">
                <InspectorAnchors />
              </TabsContent>
              <TabsContent value="qa" className="flex-1 overflow-auto m-0">
                <InspectorQA />
              </TabsContent>
            </>
          ) : (
            // 未选中分镜时的空状态（但 assets-lock 可用）
            <>
              {['story', 'cast', 'layout', 'layers', 'timeline', 'consistency', 'anchors', 'qa'].map((tab) => (
                <TabsContent key={tab} value={tab} className="flex-1 overflow-auto m-0">
                  <div className="flex-1 flex items-center justify-center p-6">
                    <div className="text-center space-y-5 max-w-xs relative">
                      {/* Decorative orb */}
                      <div className="absolute -top-4 -right-8 w-20 h-20 bg-emerald-500/5 rounded-full blur-2xl" />

                      {/* Icon with gradient */}
                      <div className="relative mx-auto">
                        <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-slate-700/25 to-slate-800/10 border border-slate-700/20 flex items-center justify-center">
                          <MousePointerClick className="w-6 h-6 text-slate-500" />
                        </div>
                        <div className="absolute inset-0 bg-emerald-500/10 rounded-xl blur-lg" />
                      </div>

                      <div className="space-y-2 relative">
                        <p className="text-sm font-semibold text-foreground/80">请选择分镜</p>
                        <p className="text-xs text-muted-foreground leading-relaxed">
                          点击左侧故事板中的分镜卡片，即可在此查看和编辑详情。
                        </p>
                      </div>
                    </div>
                  </div>
                </TabsContent>
              ))}
            </>
          )}

          {/* S3-08: AssetsLock Tab - 不需要选中分镜 */}
          <TabsContent value="assets-lock" className="flex-1 overflow-auto m-0">
            {chapterId ? (
              <AssetsLockPanel
                chapterId={chapterId}
                onRenderReady={(ready) => {
                  useStudioStore.setState({ canRender: ready })
                }}
              />
            ) : (
              <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                请先选择章节
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </InspectorFormProvider>
  )
}
