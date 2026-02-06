'use client'

import { useStudioStore } from '@/lib/store/studioStore'
import { createDefaultQAConfig, createDefaultRetryPolicy, PROVIDER_COST } from '@/lib/schema'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Slider } from '@/components/ui/slider'
import { Separator } from '@/components/ui/separator'
import { Input } from '@/components/ui/input'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { providerLabels } from '@/lib/schema/provider'
import {
    ShieldCheck, AlertTriangle, RotateCcw, DollarSign,
    ChevronUp, ChevronDown, Check, X
} from 'lucide-react'
import { useState } from 'react'

export function InspectorQA() {
    const { selectedClipId } = useStudioStore()

    // 模拟数据
    const [qaConfig] = useState(createDefaultQAConfig())
    const [retryPolicy] = useState(createDefaultRetryPolicy())
    const [lastQAScore] = useState<number | null>(null)
    const [lastQAIssues] = useState<string[]>([])

    if (!selectedClipId) {
        return (
            <div className="h-full flex items-center justify-center text-ink-muted p-4">
                <div className="text-center">
                    <ShieldCheck className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p className="text-sm">请选择一个 Clip</p>
                </div>
            </div>
        )
    }

    const budgetPercent = (retryPolicy.budget.costUsed / retryPolicy.budget.maxCost) * 100

    return (
        <ScrollArea className="h-full">
            <div className="p-4 space-y-5">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <h3 className="font-medium flex items-center gap-2">
                        <ShieldCheck className="w-4 h-4" />
                        质量控制 & 重试
                    </h3>
                </div>

                <Separator />

                {/* Last QA Result */}
                {lastQAScore !== null && (
                    <div className="p-3 rounded-lg bg-panel-hover border border-panel-border">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-sm font-medium">最近 QA 结果</span>
                            <Badge
                                variant="outline"
                                className={lastQAScore >= 0.8 ? 'text-emerald-400' : lastQAScore >= 0.6 ? 'text-yellow-400' : 'text-red-400'}
                            >
                                {Math.round(lastQAScore * 100)}%
                            </Badge>
                        </div>
                        {lastQAIssues.length > 0 && (
                            <div className="space-y-1 mt-2">
                                {lastQAIssues.map((issue, i) => (
                                    <div key={i} className="flex items-start gap-2 text-xs text-ink-muted">
                                        <AlertTriangle className="w-3 h-3 mt-0.5 text-yellow-400 shrink-0" />
                                        {issue}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* QA Threshold */}
                <div className="space-y-2">
                    <div className="flex items-center justify-between">
                        <Label className="text-xs text-ink-muted">质量阈值</Label>
                        <span className="text-xs text-ink-muted">{Math.round(qaConfig.threshold * 100)}%</span>
                    </div>
                    <Slider
                        value={[qaConfig.threshold]}
                        min={0.5}
                        max={0.95}
                        step={0.05}
                        className="w-full"
                    />
                    <p className="text-xs text-ink-dim">低于此分数将触发重试或进入待修复</p>
                </div>

                <Separator />

                {/* Retry Policy */}
                <div className="space-y-3">
                    <Label className="text-xs text-ink-muted flex items-center gap-1.5">
                        <RotateCcw className="w-3 h-3" />
                        重试策略
                    </Label>

                    {/* Max Attempts */}
                    <div className="flex items-center justify-between">
                        <span className="text-sm">最大尝试次数</span>
                        <Input
                            type="number"
                            value={retryPolicy.maxAttempts}
                            min={1}
                            max={5}
                            className="w-16 h-7 text-center bg-canvas border-panel-border"
                        />
                    </div>

                    {/* On Low Score */}
                    <div className="flex items-center justify-between">
                        <span className="text-sm">低分处理</span>
                        <Select value={retryPolicy.onLowScore}>
                            <SelectTrigger className="w-28 h-7 bg-canvas border-panel-border">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="retry">自动重试</SelectItem>
                                <SelectItem value="needs_fix">标记待修复</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Auto Fix Strategy */}
                    <div className="flex items-center justify-between">
                        <span className="text-sm">自动修复策略</span>
                        <Select value={retryPolicy.autoFixStrategy}>
                            <SelectTrigger className="w-28 h-7 bg-canvas border-panel-border">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="inpaint">局部修复</SelectItem>
                                <SelectItem value="redraw_char">重绘角色</SelectItem>
                                <SelectItem value="redraw_bg">重绘背景</SelectItem>
                                <SelectItem value="reroll">重新抽卡</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                </div>

                <Separator />

                {/* Budget */}
                <div className="space-y-3">
                    <Label className="text-xs text-ink-muted flex items-center gap-1.5">
                        <DollarSign className="w-3 h-3" />
                        预算控制
                    </Label>

                    <div className="flex items-center justify-between text-sm">
                        <span>已用 / 最大</span>
                        <span className="font-mono">
                            {retryPolicy.budget.costUsed} / {retryPolicy.budget.maxCost}
                        </span>
                    </div>

                    <div className="h-2 bg-panel-hover rounded-full overflow-hidden">
                        <div
                            className={`h-full transition-all ${budgetPercent > 80 ? 'bg-red-500' : budgetPercent > 50 ? 'bg-yellow-500' : 'bg-emerald-500'
                                }`}
                            style={{ width: `${Math.min(budgetPercent, 100)}%` }}
                        />
                    </div>
                </div>

                <Separator />

                {/* Provider Chain */}
                <div className="space-y-3">
                    <Label className="text-xs text-ink-muted">Provider 优先级链</Label>
                    <div className="space-y-1">
                        {retryPolicy.providerChain.map((provider, index) => (
                            <div
                                key={provider}
                                className="flex items-center justify-between p-2 rounded bg-panel-hover"
                            >
                                <div className="flex items-center gap-2">
                                    <span className="text-xs text-ink-dim w-5">{index + 1}.</span>
                                    <span className="text-sm">{providerLabels[provider]}</span>
                                    <Badge variant="outline" className="text-xs">
                                        成本 {PROVIDER_COST[provider]}
                                    </Badge>
                                </div>
                                <div className="flex gap-1">
                                    <Button size="sm" variant="ghost" className="h-6 w-6 p-0" disabled={index === 0}>
                                        <ChevronUp className="w-3 h-3" />
                                    </Button>
                                    <Button size="sm" variant="ghost" className="h-6 w-6 p-0" disabled={index === retryPolicy.providerChain.length - 1}>
                                        <ChevronDown className="w-3 h-3" />
                                    </Button>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </ScrollArea>
    )
}
