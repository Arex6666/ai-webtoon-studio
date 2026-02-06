'use client'

import { useState } from "react"
import { Panel, Group, Separator } from "react-resizable-panels"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ScriptEditor } from "./left/ScriptEditor"
import { AssetBrowser } from "./left/AssetBrowser"
import { StoryboardView } from "./center/StoryboardView"
import { CanvasStage } from "./center/CanvasStage"
import { InspectorTabs } from "./right/InspectorTabs"
import { TimelineDock } from "./bottom/TimelineDock"
import { ChevronUp, ChevronDown } from "lucide-react"

export function StudioLayout() {
  // 底部面板高度状态 (可折叠)
  const [bottomExpanded, setBottomExpanded] = useState(true)
  const bottomHeight = bottomExpanded ? 250 : 40

  return (
    <div className="flex-1 w-full min-w-0 overflow-y-auto flex flex-col" style={{ minHeight: '100vh' }}>
      {/* Main Content Area - 固定最小高度 */}
      <div className="min-h-[500px] flex-shrink-0 overflow-hidden" style={{ height: 'calc(100vh - 260px)' }}>
        <Group orientation="horizontal" className="h-full">
          {/* Left panel: Script + Assets */}
          <Panel
            defaultSize={20}
            minSize={15}
            maxSize={35}
            collapsible={true}
            collapsedSize={0}
            className="flex flex-col min-w-0"
          >
            <Tabs defaultValue="script" className="h-full flex flex-col">
              <TabsList className="w-full justify-start rounded-none border-b border-panel-border bg-panel/50 p-0 h-10">
                <TabsTrigger value="script" className="h-full rounded-none border-b-2 border-transparent data-[state=active]:border-accent data-[state=active]:bg-panel py-2 text-xs px-4">剧本</TabsTrigger>
                <TabsTrigger value="assets" className="h-full rounded-none border-b-2 border-transparent data-[state=active]:border-accent data-[state=active]:bg-panel py-2 text-xs px-4">资产</TabsTrigger>
              </TabsList>
              <TabsContent value="script" className="flex-1 overflow-hidden m-0 p-0 relative h-full">
                <ScriptEditor />
              </TabsContent>
              <TabsContent value="assets" className="flex-1 overflow-hidden m-0 p-0 relative h-full">
                <AssetBrowser />
              </TabsContent>
            </Tabs>
          </Panel>

          <Separator className="w-1 bg-panel-border hover:bg-accent/50 transition-colors z-10" />

          {/* Center panel: Storyboard + Canvas */}
          <Panel defaultSize={40} minSize={30} maxSize={75} className="flex flex-col relative min-w-0">
            <Tabs defaultValue="storyboard" className="h-full flex flex-col">
              <TabsList className="w-full justify-start rounded-none border-b border-panel-border bg-panel/50 p-0 h-10 z-10">
                <TabsTrigger value="storyboard" className="h-full rounded-none border-b-2 border-transparent data-[state=active]:border-accent data-[state=active]:bg-panel py-2 text-xs px-4">故事板</TabsTrigger>
                <TabsTrigger value="canvas" className="h-full rounded-none border-b-2 border-transparent data-[state=active]:border-accent data-[state=active]:bg-panel py-2 text-xs px-4">画布</TabsTrigger>
              </TabsList>
              <TabsContent value="storyboard" className="flex-1 overflow-hidden m-0 p-0 relative h-full">
                <StoryboardView />
              </TabsContent>
              <TabsContent value="canvas" className="flex-1 overflow-hidden m-0 p-0 relative h-full">
                <CanvasStage />
              </TabsContent>
            </Tabs>
          </Panel>

          <Separator className="w-1 bg-panel-border hover:bg-accent/50 transition-colors z-10" />

          {/* Right panel: Inspector */}
          <Panel
            defaultSize={40}
            minSize={20}
            maxSize={50}
            collapsible={true}
            collapsedSize={0}
            className="flex flex-col min-w-0"
          >
            <InspectorTabs />
          </Panel>
        </Group>
      </div>

      {/* Bottom Panel: Timeline & Jobs - 固定高度区域 */}
      <div
        className="border-t border-panel-border bg-panel/30 flex flex-col transition-all duration-200"
        style={{ height: bottomHeight }}
      >
        {/* 折叠/展开按钮 */}
        <button
          onClick={() => setBottomExpanded(!bottomExpanded)}
          className="absolute right-4 -top-3 z-20 p-1 rounded bg-panel border border-panel-border hover:bg-accent/20 transition-colors"
          style={{ position: 'relative', alignSelf: 'flex-end', marginTop: -12, marginRight: 8 }}
        >
          {bottomExpanded ? (
            <ChevronDown className="w-4 h-4 text-muted-foreground" />
          ) : (
            <ChevronUp className="w-4 h-4 text-muted-foreground" />
          )}
        </button>

        {/* 时间轴内容 */}
        <div className="flex-1 overflow-hidden">
          <TimelineDock />
        </div>
      </div>
    </div>
  )
}
