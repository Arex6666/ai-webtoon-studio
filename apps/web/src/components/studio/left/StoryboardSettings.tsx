'use client'

import { useState } from 'react'
import { ChevronDown, ChevronRight, Settings2, Palette, Clock, Gauge } from 'lucide-react'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue
} from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { Label } from '@/components/ui/label'
import { useStudioStore } from '@/lib/store/studioStore'
import { useShallow } from 'zustand/react/shallow'

interface StoryboardConstraints {
    panelsMin: number
    panelsMax: number
    totalDurationMin: number
    totalDurationMax: number
    perPanelDurationMin: number
    perPanelDurationMax: number
}

interface StoryboardSettingsState {
    stylePreset: string
    constraints: StoryboardConstraints
}

const STYLE_PRESETS = [
    { id: 'default', name: '默认', description: '韩式条漫，温柔细腻' },
    { id: 'rainy_soft', name: '雨天柔和', description: '忧郁氛围，蓝色调' },
    { id: 'cinematic', name: '电影风格', description: '戏剧光影，高对比' },
]

const DEFAULT_CONSTRAINTS: StoryboardConstraints = {
    panelsMin: 4,
    panelsMax: 20,
    totalDurationMin: 30,
    totalDurationMax: 120,
    perPanelDurationMin: 1.5,
    perPanelDurationMax: 8,
}

export function StoryboardSettings() {
    const [isExpanded, setIsExpanded] = useState(false)
    const { storyboardSettings, setStoryboardSettings } = useStudioStore(
    useShallow(s => ({ storyboardSettings: s.storyboardSettings, setStoryboardSettings: s.setStoryboardSettings }))
  )

    // 使用 store 的值或默认值
    const settings: StoryboardSettingsState = storyboardSettings || {
        stylePreset: 'default',
        constraints: DEFAULT_CONSTRAINTS,
    }

    const updateSettings = (updates: Partial<StoryboardSettingsState>) => {
        setStoryboardSettings({
            ...settings,
            ...updates,
        })
    }

    const updateConstraints = (updates: Partial<StoryboardConstraints>) => {
        updateSettings({
            constraints: {
                ...settings.constraints,
                ...updates,
            },
        })
    }

    return (
        <div className="border-t border-white/5">
            {/* 折叠头部 */}
            <button
                className="w-full p-3 flex items-center justify-between text-sm text-muted-foreground hover:bg-white/5 transition-colors"
                onClick={() => setIsExpanded(!isExpanded)}
            >
                <div className="flex items-center gap-2">
                    <Settings2 className="w-4 h-4" />
                    <span>高级设置</span>
                </div>
                {isExpanded ? (
                    <ChevronDown className="w-4 h-4" />
                ) : (
                    <ChevronRight className="w-4 h-4" />
                )}
            </button>

            {/* 展开内容 */}
            {isExpanded && (
                <div className="p-4 space-y-5 bg-zinc-900/50 border-t border-white/5">
                    {/* 风格预设 */}
                    <div className="space-y-2">
                        <Label className="flex items-center gap-2 text-xs">
                            <Palette className="w-3 h-3" />
                            风格预设
                        </Label>
                        <Select
                            value={settings.stylePreset}
                            onValueChange={(value) => updateSettings({ stylePreset: value })}
                        >
                            <SelectTrigger className="h-8 text-xs">
                                <SelectValue placeholder="选择风格" />
                            </SelectTrigger>
                            <SelectContent>
                                {STYLE_PRESETS.map((preset) => (
                                    <SelectItem key={preset.id} value={preset.id}>
                                        <div className="flex flex-col">
                                            <span>{preset.name}</span>
                                            <span className="text-[10px] text-muted-foreground">
                                                {preset.description}
                                            </span>
                                        </div>
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* 分镜数量 */}
                    <div className="space-y-2">
                        <Label className="flex items-center gap-2 text-xs">
                            <Gauge className="w-3 h-3" />
                            分镜数量: {settings.constraints.panelsMin} - {settings.constraints.panelsMax}
                        </Label>
                        <div className="flex gap-2 items-center">
                            <span className="text-[10px] text-muted-foreground w-6">{settings.constraints.panelsMin}</span>
                            <Slider
                                value={[settings.constraints.panelsMin, settings.constraints.panelsMax]}
                                min={2}
                                max={50}
                                step={1}
                                onValueChange={([min, max]) => {
                                    updateConstraints({ panelsMin: min, panelsMax: max })
                                }}
                                className="flex-1"
                            />
                            <span className="text-[10px] text-muted-foreground w-6">{settings.constraints.panelsMax}</span>
                        </div>
                    </div>

                    {/* 总时长 */}
                    <div className="space-y-2">
                        <Label className="flex items-center gap-2 text-xs">
                            <Clock className="w-3 h-3" />
                            总时长: {settings.constraints.totalDurationMin}s - {settings.constraints.totalDurationMax}s
                        </Label>
                        <div className="flex gap-2 items-center">
                            <span className="text-[10px] text-muted-foreground w-8">{settings.constraints.totalDurationMin}s</span>
                            <Slider
                                value={[settings.constraints.totalDurationMin, settings.constraints.totalDurationMax]}
                                min={10}
                                max={300}
                                step={5}
                                onValueChange={([min, max]) => {
                                    updateConstraints({ totalDurationMin: min, totalDurationMax: max })
                                }}
                                className="flex-1"
                            />
                            <span className="text-[10px] text-muted-foreground w-8">{settings.constraints.totalDurationMax}s</span>
                        </div>
                    </div>

                    {/* 单镜头时长 */}
                    <div className="space-y-2">
                        <Label className="flex items-center gap-2 text-xs">
                            <Clock className="w-3 h-3" />
                            单镜头: {settings.constraints.perPanelDurationMin}s - {settings.constraints.perPanelDurationMax}s
                        </Label>
                        <div className="flex gap-2 items-center">
                            <span className="text-[10px] text-muted-foreground w-8">{settings.constraints.perPanelDurationMin}s</span>
                            <Slider
                                value={[settings.constraints.perPanelDurationMin, settings.constraints.perPanelDurationMax]}
                                min={0.5}
                                max={15}
                                step={0.5}
                                onValueChange={([min, max]) => {
                                    updateConstraints({ perPanelDurationMin: min, perPanelDurationMax: max })
                                }}
                                className="flex-1"
                            />
                            <span className="text-[10px] text-muted-foreground w-8">{settings.constraints.perPanelDurationMax}s</span>
                        </div>
                    </div>

                    {/* 提示文字 */}
                    <p className="text-[10px] text-muted-foreground/60 text-center italic">
                        不展开时使用默认设置
                    </p>
                </div>
            )}
        </div>
    )
}
