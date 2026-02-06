'use client'

import { useStudioStore } from '@/lib/store/studioStore'
import { ANCHOR_KIND_LABELS, type AnchorKind, type AnchorSpec, createMockControlImage } from '@/lib/schema/anchor'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Slider } from '@/components/ui/slider'
import { Separator } from '@/components/ui/separator'
import { SceneAnchorPanel } from '../panels/SceneAnchorPanel'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { Crosshair, Plus, Trash2, Image, Map, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'
import { useState } from 'react'

export function InspectorAnchors() {
    const { selectedPanelId, scenes } = useStudioStore()
    const [selectedKind, setSelectedKind] = useState<AnchorKind>('depth')

    // 模拟锚点数据（实际应从 store 获取）
    const anchors: AnchorSpec[] = []

    if (!selectedPanelId) {
        return (
            <div className="h-full flex items-center justify-center text-ink-muted p-4">
                <div className="text-center">
                    <Crosshair className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p className="text-sm">请选择一个面板</p>
                </div>
            </div>
        )
    }

    const handleGenerateAnchor = () => {
        // 生成 mock 控制图
        const controlImage = createMockControlImage(selectedPanelId, selectedKind)
        console.log('Generated anchor:', controlImage)
        // TODO: 调用 store.createMockAnchor
    }

    return (
        <ScrollArea className="h-full">
            <div className="p-4 space-y-5">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <h3 className="font-medium flex items-center gap-2">
                        <Map className="w-4 h-4" />
                        场景控制图
                    </h3>
                    <Badge variant="outline" className="text-xs">
                        {scenes.length} 场景
                    </Badge>
                </div>

                <Separator />

                {/* 场景列表 - 显示控制图状态 */}
                <div className="space-y-3">
                    <Label className="text-xs text-ink-muted flex items-center gap-1.5">
                        <Map className="w-3 h-3" />
                        场景资产 (控制图生成)
                    </Label>

                    {scenes.length === 0 ? (
                        <div className="p-6 text-center text-ink-muted border border-dashed border-panel-border rounded-lg">
                            <Map className="w-8 h-8 mx-auto mb-2 opacity-50" />
                            <p className="text-sm">暂无场景资产</p>
                            <p className="text-xs mt-1">运行 AI 分镜后自动提取场景</p>
                        </div>
                    ) : (
                        scenes.map(scene => (
                            <SceneAnchorPanel
                                key={scene.id}
                                assetId={scene.id}
                                assetName={scene.name}
                                onStatusChange={(status) => {
                                    console.log(`Scene ${scene.name} anchor status: ${status}`)
                                }}
                            />
                        ))
                    )}
                </div>

                <Separator />

                {/* 单镜头快速生成 */}
                <div className="space-y-3">
                    <Label className="text-xs text-ink-muted">快速生成控制图</Label>
                    <div className="flex gap-2">
                        <Select value={selectedKind} onValueChange={(v) => setSelectedKind(v as AnchorKind)}>
                            <SelectTrigger className="flex-1 bg-canvas border-panel-border">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {(Object.keys(ANCHOR_KIND_LABELS) as AnchorKind[]).map(kind => (
                                    <SelectItem key={kind} value={kind}>
                                        {ANCHOR_KIND_LABELS[kind].label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <Button size="sm" onClick={handleGenerateAnchor}>
                            <Plus className="w-3.5 h-3.5 mr-1" />
                            生成
                        </Button>
                    </div>
                    <p className="text-xs text-ink-dim">
                        {ANCHOR_KIND_LABELS[selectedKind].description}
                    </p>
                </div>
            </div>
        </ScrollArea>
    )
}

function AnchorCard({ anchor }: { anchor: AnchorSpec }) {
    return (
        <div className="p-3 rounded-lg border border-panel-border">
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="text-xs">
                        {ANCHOR_KIND_LABELS[anchor.kind].label}
                    </Badge>
                </div>
                <Button size="sm" variant="ghost" className="h-6 w-6 p-0 text-destructive">
                    <Trash2 className="w-3 h-3" />
                </Button>
            </div>

            {anchor.controlImage && (
                <div className="mb-2 rounded overflow-hidden bg-canvas">
                    <img
                        src={anchor.controlImage.url}
                        alt={anchor.kind}
                        className="w-full h-24 object-cover"
                    />
                </div>
            )}

            <div className="flex items-center gap-3">
                <span className="text-xs text-ink-dim w-16">
                    权重 {anchor.weight.toFixed(1)}
                </span>
                <Slider
                    value={[anchor.weight]}
                    min={0}
                    max={2}
                    step={0.1}
                    className="flex-1"
                />
            </div>
        </div>
    )
}
