import { useState } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { LayoutGrid, Image as ImageIcon, Settings, Play, Download, Share2, Pause, Maximize2 } from "lucide-react"
import { cn } from "@/lib/utils"

// 临时导入 StoryboardView，后续替换为增强版
import { StoryboardView } from "../center/StoryboardView"

interface CreativeCanvasProps {
    storyboard: any
    onPanelSelect: (panelId: string) => void
}

export function CreativeCanvas({ storyboard, onPanelSelect }: CreativeCanvasProps) {
    const [activeTab, setActiveTab] = useState("storyboard")
    const [isPlaying, setIsPlaying] = useState(false)

    return (
        <div className="flex flex-col h-full bg-[#020617] relative font-sans">
            {/* Top Bar - Glassmorphism */}
            <div className="h-14 border-b border-slate-800/50 bg-slate-900/80 backdrop-blur-md flex items-center justify-between px-5 sticky top-0 z-10">
                <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full">
                    <TabsList className="h-full bg-transparent p-0 gap-1">
                        {[
                            { value: "storyboard", icon: LayoutGrid, label: "分镜预览" },
                            { value: "assets", icon: ImageIcon, label: "资产管理" },
                            { value: "settings", icon: Settings, label: "渲染设置" },
                        ].map((tab) => (
                            <TabsTrigger
                                key={tab.value}
                                value={tab.value}
                                className={cn(
                                    "h-full rounded-none px-4 text-sm font-medium transition-all cursor-pointer",
                                    "border-b-2 border-transparent data-[state=active]:border-emerald-400",
                                    "text-slate-400 data-[state=active]:text-slate-50",
                                    "hover:text-slate-200 hover:bg-slate-800/50"
                                )}
                            >
                                <tab.icon className="w-4 h-4 mr-2" />
                                {tab.label}
                            </TabsTrigger>
                        ))}
                    </TabsList>
                </Tabs>

                <div className="flex items-center gap-1.5">
                    <button
                        className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors cursor-pointer"
                        title="分享"
                    >
                        <Share2 className="w-4 h-4" />
                    </button>
                    <button
                        className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors cursor-pointer"
                        title="导出"
                    >
                        <Download className="w-4 h-4" />
                    </button>
                    <button
                        className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors cursor-pointer"
                        title="全屏"
                    >
                        <Maximize2 className="w-4 h-4" />
                    </button>
                    <div className="w-px h-5 bg-slate-700 mx-1" />
                    <button
                        onClick={() => setIsPlaying(!isPlaying)}
                        className={cn(
                            "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all cursor-pointer",
                            isPlaying
                                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30"
                                : "bg-emerald-500 text-white hover:bg-emerald-400 shadow-lg shadow-emerald-500/20"
                        )}
                    >
                        {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                        {isPlaying ? "暂停" : "预览"}
                    </button>
                </div>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-hidden relative">
                <Tabs value={activeTab} className="h-full">
                    <TabsContent value="storyboard" className="h-full m-0 p-0">
                        <div className="absolute inset-0 overflow-y-auto p-8 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-900 via-[#020617] to-[#020617]">
                            <div className="max-w-4xl mx-auto">
                                {/* 漫画容器 - 高级卡片效果 */}
                                <div className="bg-slate-900/80 rounded-2xl border border-slate-800/50 shadow-2xl shadow-black/50 overflow-hidden backdrop-blur-sm">
                                    {/* 页眉 */}
                                    <div className="h-16 border-b border-slate-800/50 flex items-center justify-between px-6 bg-slate-900/50">
                                        <div className="flex items-center gap-3">
                                            <div className="w-3 h-3 rounded-full bg-red-500/80" />
                                            <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
                                            <div className="w-3 h-3 rounded-full bg-green-500/80" />
                                        </div>
                                        <span className="font-mono text-xs text-slate-500 uppercase tracking-widest">Chapter 01</span>
                                        <span className="font-mono text-[10px] text-slate-600">AI WEBTOON STUDIO</span>
                                    </div>

                                    {/* 分镜内容 */}
                                    <div className="p-6">
                                        <StoryboardView />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </TabsContent>

                    <TabsContent value="assets" className="h-full m-0 p-0 flex items-center justify-center">
                        <div className="text-center">
                            <div className="w-16 h-16 rounded-2xl bg-slate-800/50 border border-slate-700/50 flex items-center justify-center mx-auto mb-4">
                                <ImageIcon className="w-8 h-8 text-slate-600" />
                            </div>
                            <p className="text-slate-500 font-mono text-sm">资产绑定界面开发中...</p>
                        </div>
                    </TabsContent>

                    <TabsContent value="settings" className="h-full m-0 p-0 flex items-center justify-center">
                        <div className="text-center">
                            <div className="w-16 h-16 rounded-2xl bg-slate-800/50 border border-slate-700/50 flex items-center justify-center mx-auto mb-4">
                                <Settings className="w-8 h-8 text-slate-600" />
                            </div>
                            <p className="text-slate-500 font-mono text-sm">全局渲染设置...</p>
                        </div>
                    </TabsContent>
                </Tabs>
            </div>
        </div>
    )
}
