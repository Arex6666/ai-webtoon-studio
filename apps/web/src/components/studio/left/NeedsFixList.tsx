'use client'

import { useStudioStore } from '@/lib/store/studioStore'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { AlertCircle, Wand2, ArrowRight } from 'lucide-react'

export function NeedsFixList() {
    const {
        needsFixPanelIds,
        panelList,
        selectPanel,
        openFixModal,
    } = useStudioStore()

    if (needsFixPanelIds.length === 0) {
        return (
            <div className="h-full flex items-center justify-center text-ink-muted p-4">
                <div className="text-center">
                    <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p className="text-sm">没有需要修复的面板</p>
                </div>
            </div>
        )
    }

    const getPanelIndex = (panelId: string) => {
        const panel = panelList.find(p => p.id === panelId)
        return panel ? panel.index + 1 : '?'
    }

    return (
        <ScrollArea className="h-full">
            <div className="p-3 space-y-2">
                <div className="text-xs text-ink-muted mb-3">
                    {needsFixPanelIds.length} 个面板需要修复
                </div>

                {needsFixPanelIds.map((panelId) => (
                    <div
                        key={panelId}
                        className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 hover:border-red-500/50 transition-colors"
                    >
                        <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                                <AlertCircle className="w-4 h-4 text-red-400" />
                                <span className="font-medium">Panel #{getPanelIndex(panelId)}</span>
                            </div>
                            <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => selectPanel(panelId)}
                                className="h-6 text-xs"
                            >
                                <ArrowRight className="w-3 h-3" />
                            </Button>
                        </div>

                        <div className="flex gap-2">
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={() => {
                                    selectPanel(panelId)
                                    openFixModal(panelId, 'inpaint')
                                }}
                                className="flex-1 h-7 text-xs border-red-500/30 hover:bg-red-500/10"
                            >
                                <Wand2 className="w-3 h-3 mr-1" />
                                修复
                            </Button>
                        </div>
                    </div>
                ))}
            </div>
        </ScrollArea>
    )
}
