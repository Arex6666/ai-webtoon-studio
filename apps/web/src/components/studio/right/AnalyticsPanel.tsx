'use client'

import { createMockAnalytics, type Analytics } from '@/lib/schema/analytics'
import { providerLabels } from '@/lib/schema/provider'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Progress } from '@/components/ui/progress'
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table'
import { BarChart3, RefreshCw, DollarSign, CheckCircle, AlertTriangle, XCircle } from 'lucide-react'
import { useState } from 'react'

export function AnalyticsPanel() {
    // 模拟分析数据
    const [analytics, setAnalytics] = useState<Analytics>(createMockAnalytics('chapter-1'))
    const [loading, setLoading] = useState(false)

    const handleRecompute = () => {
        setLoading(true)
        // 模拟重新计算
        setTimeout(() => {
            setAnalytics(createMockAnalytics('chapter-1'))
            setLoading(false)
        }, 1000)
    }

    const summary = analytics.chapterSummary
    const successRate = summary.totalClips > 0
        ? (summary.succeeded / summary.totalClips) * 100
        : 0

    return (
        <ScrollArea className="h-full">
            <div className="p-4 space-y-5">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <h3 className="font-medium flex items-center gap-2">
                        <BarChart3 className="w-4 h-4" />
                        成本与质量仪表盘
                    </h3>
                    <Button size="sm" variant="outline" onClick={handleRecompute} disabled={loading}>
                        <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
                        重新计算
                    </Button>
                </div>

                <Separator />

                {/* Chapter Summary */}
                <div className="grid grid-cols-4 gap-3">
                    <div className="p-3 rounded-lg bg-panel-hover text-center">
                        <DollarSign className="w-5 h-5 mx-auto mb-1 text-yellow-400" />
                        <div className="text-2xl font-bold">{summary.totalCost}</div>
                        <div className="text-xs text-ink-muted">总成本</div>
                    </div>
                    <div className="p-3 rounded-lg bg-panel-hover text-center">
                        <BarChart3 className="w-5 h-5 mx-auto mb-1 text-blue-400" />
                        <div className="text-2xl font-bold">{Math.round(summary.avgScore * 100)}%</div>
                        <div className="text-xs text-ink-muted">平均分</div>
                    </div>
                    <div className="p-3 rounded-lg bg-panel-hover text-center">
                        <CheckCircle className="w-5 h-5 mx-auto mb-1 text-emerald-400" />
                        <div className="text-2xl font-bold">{Math.round(successRate)}%</div>
                        <div className="text-xs text-ink-muted">成功率</div>
                    </div>
                    <div className="p-3 rounded-lg bg-panel-hover text-center">
                        <RefreshCw className="w-5 h-5 mx-auto mb-1 text-orange-400" />
                        <div className="text-2xl font-bold">{summary.totalRetries}</div>
                        <div className="text-xs text-ink-muted">重试次数</div>
                    </div>
                </div>

                {/* Status Breakdown */}
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-1.5">
                        <CheckCircle className="w-4 h-4 text-emerald-400" />
                        <span className="text-sm">{summary.succeeded} 成功</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <AlertTriangle className="w-4 h-4 text-yellow-400" />
                        <span className="text-sm">{summary.needsFix} 待修复</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <XCircle className="w-4 h-4 text-red-400" />
                        <span className="text-sm">{summary.failed} 失败</span>
                    </div>
                </div>

                <Separator />

                {/* By Provider */}
                <div className="space-y-3">
                    <h4 className="text-sm font-medium">按 Provider 统计</h4>
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Provider</TableHead>
                                <TableHead className="text-right">成本</TableHead>
                                <TableHead className="text-right">平均分</TableHead>
                                <TableHead className="text-right">成功率</TableHead>
                                <TableHead className="text-right">任务数</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {analytics.byProvider.map(stat => (
                                <TableRow key={stat.provider}>
                                    <TableCell>
                                        <Badge variant="outline">
                                            {providerLabels[stat.provider as keyof typeof providerLabels] || stat.provider}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-right">{stat.costUsed}</TableCell>
                                    <TableCell className="text-right">{Math.round(stat.avgScore * 100)}%</TableCell>
                                    <TableCell className="text-right">
                                        <span className={stat.successRate >= 0.8 ? 'text-emerald-400' : 'text-yellow-400'}>
                                            {Math.round(stat.successRate * 100)}%
                                        </span>
                                    </TableCell>
                                    <TableCell className="text-right">{stat.jobCount}</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>

                <Separator />

                {/* By Character */}
                <div className="space-y-3">
                    <h4 className="text-sm font-medium">按角色资产统计</h4>
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>角色</TableHead>
                                <TableHead className="text-right">成本</TableHead>
                                <TableHead className="text-right">平均分</TableHead>
                                <TableHead className="text-right">成功率</TableHead>
                                <TableHead className="text-right">使用次数</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {analytics.byCharacter.map(stat => (
                                <TableRow key={stat.assetId}>
                                    <TableCell>{stat.assetName}</TableCell>
                                    <TableCell className="text-right">{stat.costUsed}</TableCell>
                                    <TableCell className="text-right">{Math.round(stat.avgScore * 100)}%</TableCell>
                                    <TableCell className="text-right">
                                        <span className={stat.successRate >= 0.8 ? 'text-emerald-400' : 'text-yellow-400'}>
                                            {Math.round(stat.successRate * 100)}%
                                        </span>
                                    </TableCell>
                                    <TableCell className="text-right">{stat.usageCount}</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>

                <div className="text-xs text-ink-dim text-right">
                    计算时间: {new Date(analytics.computedAt).toLocaleString()}
                </div>
            </div>
        </ScrollArea>
    )
}
