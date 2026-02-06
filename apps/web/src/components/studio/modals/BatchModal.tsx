'use client'

import { createBatchQueue, computeBatchStats, type BatchQueue, type BatchQueueStatus } from '@/lib/schema/batchQueue'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Slider } from '@/components/ui/slider'
import {
    Play, Pause, Square, RotateCcw, Check, X, AlertTriangle, Loader2, Layers
} from 'lucide-react'
import { useState } from 'react'

interface BatchModalProps {
    open: boolean
    onOpenChange: (open: boolean) => void
}

export function BatchModal({ open, onOpenChange }: BatchModalProps) {
    // 模拟批量队列数据
    const [queue, setQueue] = useState<BatchQueue | null>(null)
    const [concurrency, setConcurrency] = useState(2)
    const [stopOnNeedsFix, setStopOnNeedsFix] = useState(true)

    const handleStart = () => {
        // 模拟创建批量队列
        const mockQueue = createBatchQueue('chapter-1', [
            'clip-1', 'clip-2', 'clip-3', 'clip-4', 'clip-5'
        ])
        mockQueue.status = 'Running'
        mockQueue.controls = { concurrency, stopOnNeedsFix }
        setQueue(mockQueue)
        console.log('Starting batch render with concurrency:', concurrency)
    }

    const handlePause = () => {
        if (queue) {
            setQueue({ ...queue, status: 'Paused' })
        }
    }

    const handleResume = () => {
        if (queue) {
            setQueue({ ...queue, status: 'Running' })
        }
    }

    const handleCancel = () => {
        if (queue) {
            setQueue({ ...queue, status: 'Canceled' })
        }
    }

    const stats = queue ? computeBatchStats(queue.items) : null
    const progress = stats ? ((stats.done + stats.failed + stats.needsFix) / stats.total) * 100 : 0

    const statusConfig: Record<BatchQueueStatus, { label: string; color: string }> = {
        Idle: { label: '待开始', color: 'text-ink-muted' },
        Running: { label: '运行中', color: 'text-blue-400' },
        Paused: { label: '已暂停', color: 'text-yellow-400' },
        Completed: { label: '已完成', color: 'text-emerald-400' },
        Canceled: { label: '已取消', color: 'text-red-400' },
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-2xl">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Layers className="w-5 h-5" />
                        批量生成
                    </DialogTitle>
                </DialogHeader>

                <div className="space-y-5">
                    {/* 控制选项 */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <Label className="text-sm">并发数量</Label>
                            <div className="flex items-center gap-3">
                                <Slider
                                    value={[concurrency]}
                                    onValueChange={([v]) => setConcurrency(v)}
                                    min={1}
                                    max={5}
                                    step={1}
                                    className="w-32"
                                    disabled={queue?.status === 'Running'}
                                />
                                <span className="w-4 text-center">{concurrency}</span>
                            </div>
                        </div>

                        <div className="flex items-center justify-between">
                            <Label className="text-sm">遇到待修复时停止</Label>
                            <Switch
                                checked={stopOnNeedsFix}
                                onCheckedChange={setStopOnNeedsFix}
                                disabled={queue?.status === 'Running'}
                            />
                        </div>
                    </div>

                    <Separator />

                    {/* 状态和进度 */}
                    {queue && (
                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <span className="text-sm">状态</span>
                                <Badge variant="outline" className={statusConfig[queue.status].color}>
                                    {statusConfig[queue.status].label}
                                </Badge>
                            </div>

                            <Progress value={progress} className="h-2" />

                            <div className="grid grid-cols-5 gap-2 text-center text-xs">
                                <div className="p-2 rounded bg-panel-hover">
                                    <div className="font-semibold text-lg">{stats?.total || 0}</div>
                                    <div className="text-ink-muted">总数</div>
                                </div>
                                <div className="p-2 rounded bg-emerald-500/10">
                                    <div className="font-semibold text-lg text-emerald-400">{stats?.done || 0}</div>
                                    <div className="text-ink-muted">完成</div>
                                </div>
                                <div className="p-2 rounded bg-blue-500/10">
                                    <div className="font-semibold text-lg text-blue-400">{stats?.running || 0}</div>
                                    <div className="text-ink-muted">运行中</div>
                                </div>
                                <div className="p-2 rounded bg-yellow-500/10">
                                    <div className="font-semibold text-lg text-yellow-400">{stats?.needsFix || 0}</div>
                                    <div className="text-ink-muted">待修复</div>
                                </div>
                                <div className="p-2 rounded bg-red-500/10">
                                    <div className="font-semibold text-lg text-red-400">{stats?.failed || 0}</div>
                                    <div className="text-ink-muted">失败</div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* 队列列表 */}
                    {queue && (
                        <>
                            <Separator />
                            <ScrollArea className="h-48">
                                <div className="space-y-1">
                                    {queue.items.map((item, index) => (
                                        <div
                                            key={item.clipId}
                                            className="flex items-center justify-between p-2 rounded bg-panel-hover"
                                        >
                                            <div className="flex items-center gap-2">
                                                <span className="text-xs text-ink-dim w-6">{index + 1}.</span>
                                                <span className="text-sm">{item.clipId}</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                {item.status === 'running' && (
                                                    <Loader2 className="w-3 h-3 animate-spin text-blue-400" />
                                                )}
                                                {item.status === 'succeeded' && (
                                                    <Check className="w-3 h-3 text-emerald-400" />
                                                )}
                                                {item.status === 'failed' && (
                                                    <X className="w-3 h-3 text-red-400" />
                                                )}
                                                {item.status === 'needs_fix' && (
                                                    <AlertTriangle className="w-3 h-3 text-yellow-400" />
                                                )}
                                                <Badge variant="outline" className="text-xs">
                                                    {item.status}
                                                </Badge>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </ScrollArea>
                        </>
                    )}
                </div>

                <DialogFooter className="gap-2">
                    {!queue || queue.status === 'Idle' || queue.status === 'Completed' || queue.status === 'Canceled' ? (
                        <Button onClick={handleStart}>
                            <Play className="w-4 h-4 mr-1.5" />
                            开始批量生成
                        </Button>
                    ) : (
                        <>
                            {queue.status === 'Running' && (
                                <Button variant="outline" onClick={handlePause}>
                                    <Pause className="w-4 h-4 mr-1.5" />
                                    暂停
                                </Button>
                            )}
                            {queue.status === 'Paused' && (
                                <Button variant="outline" onClick={handleResume}>
                                    <Play className="w-4 h-4 mr-1.5" />
                                    继续
                                </Button>
                            )}
                            <Button variant="destructive" onClick={handleCancel}>
                                <Square className="w-4 h-4 mr-1.5" />
                                取消
                            </Button>
                        </>
                    )}
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
