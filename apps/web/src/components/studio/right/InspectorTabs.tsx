'use client'

import { useStudioStore } from "@/lib/store/studioStore"
import { useShallow } from "zustand/react/shallow"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { InspectorFormProvider } from "./InspectorFormProvider"
import { ShotTab } from "./ShotTab"
import { CastTab } from "./CastTab"
import { AssetsTab } from "./AssetsTab"
import { InspectorLayers } from "./InspectorLayers"
import VideoTab from "./VideoTab"
import { FileText, MousePointerClick } from "lucide-react"

export function InspectorTabs() {
  const {
    selectedPanelId,
    selectedClipId,
    panelList,
    activeInspectorTab,
  } = useStudioStore(
    useShallow(s => ({
      selectedPanelId: s.selectedPanelId,
      selectedClipId: s.selectedClipId,
      panelList: s.panelList,
      activeInspectorTab: s.activeInspectorTab,
    }))
  )

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

  // 空状态 2：有分镜但未选中
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
          <TabsList className="w-full justify-start rounded-none border-b border-white/5 h-10 p-0 overflow-x-auto flex-nowrap scrollbar-hide bg-muted/10">
            <TabsTrigger value="shot" className={tabClass}>镜头</TabsTrigger>
            <TabsTrigger value="cast" className={tabClass}>角色</TabsTrigger>
            <TabsTrigger value="assets" className={tabClass}>资产</TabsTrigger>
            <TabsTrigger value="layers" className={tabClass}>图层</TabsTrigger>
            <TabsTrigger value="video" className={tabClass}>视频</TabsTrigger>
          </TabsList>

          {showPanelInspector ? (
            <>
              <TabsContent value="shot" className="flex-1 overflow-auto m-0">
                <ShotTab />
              </TabsContent>
              <TabsContent value="cast" className="flex-1 overflow-auto m-0">
                <CastTab />
              </TabsContent>
              <TabsContent value="assets" className="flex-1 overflow-auto m-0">
                <AssetsTab />
              </TabsContent>
              <TabsContent value="layers" className="flex-1 overflow-auto m-0">
                <InspectorLayers />
              </TabsContent>
              <TabsContent value="video" className="flex-1 overflow-auto m-0">
                <VideoTab />
              </TabsContent>
            </>
          ) : (
            <>
              {['shot', 'cast', 'assets', 'layers', 'video'].map((tab) => (
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
        </Tabs>
      </div>
    </InspectorFormProvider>
  )
}
