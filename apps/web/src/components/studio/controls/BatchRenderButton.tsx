'use client'

import { useState, useEffect, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from '@/components/ui/tooltip'
import { chaptersApi } from '@/lib/api/services'
import {
    Play,
    Loader2,
    Check,
    AlertTriangle,
    RefreshCw,
    Pause,
    Link
} from 'lucide-react'

type RenderState = 'idle' | 'checking' | 'queued' | 'running' | 'partial_failed' | 'succeeded' | 'blocked'

interface RenderStatus {
    total_jobs: number
    completed_jobs: number
    failed_jobs: number
    running_jobs: number
    progress: number
    is_complete: boolean
}

interface BatchRenderButtonProps {
    chapterId: string
    canRender?: boolean
    pendingAssetsCount?: number
    onOpenAssetsLock?: () => void
    onRenderStart?: () => void
    onRenderComplete?: () => void
}

export function BatchRenderButton({
    chapterId,
    canRender = true,
    pendingAssetsCount = 0,
    onOpenAssetsLock,
    onRenderStart,
    onRenderComplete
}: BatchRenderButtonProps) {
    const [state, setState] = useState<RenderState>('idle')
    const [status, setStatus] = useState<RenderStatus | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null)

    // 检查渲染状态
    const checkStatus = useCallback(async () => {
        try {
            const result = await chaptersApi.getRenderStatus(chapterId)
            setStatus(result)

            // 更新状态
            if (result.is_complete) {
                if (result.failed_jobs > 0) {
                    setState('partial_failed')
                } else if (result.completed_jobs > 0) {
                    setState('succeeded')
                    onRenderComplete?.()
                } else {
                    setState('idle')
                }
                // 停止轮询
                if (pollingInterval) {
                    clearInterval(pollingInterval)
                    setPollingInterval(null)
                }
            } else if (result.running_jobs > 0 || result.total_jobs > result.completed_jobs + result.failed_jobs) {
                setState('running')
            }
        } catch (error) {
            console.error('Failed to check render status:', error)
        }
    }, [chapterId, pollingInterval, onRenderComplete])

    // 初始化时检查状态
    useEffect(() => {
        checkStatus()
    }, [chapterId])

    // 清理轮询
    useEffect(() => {
        return () => {
            if (pollingInterval) {
                clearInterval(pollingInterval)
            }
        }
    }, [pollingInterval])

    // 开始渲染
    const handleRenderAll = async () => {
        if (!canRender || pendingAssetsCount > 0) {
            onOpenAssetsLock?.()
            return
        }

        setState('queued')
        setError(null)

        try {
            const result = await chaptersApi.renderAll(chapterId, {
                provider: 'comfyui',
                max_retries: 3
            })

            if (!result.can_render) {
                setState('blocked')
                setError(result.pending_assets.join(', '))
                return
            }

            if (result.job_count === 0) {
                setState('idle')
                return
            }

            setState('running')
            onRenderStart?.()

            // 开始轮询状态
            const interval = setInterval(checkStatus, 2000)
            setPollingInterval(interval)

        } catch (error: any) {
            setState('idle')
            setError(error.message || '渲染启动失败')
        }
    }

    // 重试失败的
    const handleRetryFailed = async () => {
        setState('queued')
        try {
            await chaptersApi.renderAll(chapterId, {
                provider: 'comfyui',
                force_rerender: false,
                max_retries: 3
            })
            setState('running')

            const interval = setInterval(checkStatus, 2000)
            setPollingInterval(interval)
        } catch (error) {
            setState('partial_failed')
        }
    }

    // 根据状态渲染按钮
    const renderButton = () => {
        const isBlocked = !canRender || pendingAssetsCount > 0

        switch (state) {
            case 'idle':
            case 'checking':
                return (
                    <TooltipProvider>
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    onClick={handleRenderAll}
                                    disabled={state === 'checking'}
                                    variant={isBlocked ? 'outline' : 'default'}
                                    className={isBlocked ? 'border-amber-500/50' : ''}
                                >
                                    {isBlocked ? (
                                        <Link className="w-4 h-4 mr-2" />
                                    ) : (
                                        <Play className="w-4 h-4 mr-2" />
                                    )}
                                    {isBlocked ? '确认资产绑定' : '渲染全部'}
                                </Button>
                            </TooltipTrigger>
                            {isBlocked && (
                                <TooltipContent>
                                    <p>{pendingAssetsCount} 个资产待确认，请先完成绑定</p>
                                </TooltipContent>
                            )}
                        </Tooltip>
                    </TooltipProvider>
                )

            case 'queued':
                return (
                    <Button disabled>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        排队中...
                    </Button>
                )

            case 'running':
                return (
                    <Button disabled variant="outline">
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        渲染中 {status?.completed_jobs || 0}/{status?.total_jobs || 0}
                        {status && (
                            <Badge variant="secondary" className="ml-2">
                                {status.progress.toFixed(0)}%
                            </Badge>
                        )}
                    </Button>
                )

            case 'partial_failed':
                return (
                    <div className="flex items-center gap-2">
                        <Button onClick={handleRetryFailed} variant="destructive">
                            <RefreshCw className="w-4 h-4 mr-2" />
                            重试失败的 {status?.failed_jobs || 0} 格
                        </Button>
                        <Badge variant="outline" className="text-green-500">
                            <Check className="w-3 h-3 mr-1" />
                            {status?.completed_jobs || 0} 成功
                        </Badge>
                    </div>
                )

            case 'succeeded':
                return (
                    <div className="flex items-center gap-2">
                        <Button onClick={handleRenderAll} variant="outline">
                            <RefreshCw className="w-4 h-4 mr-2" />
                            重新渲染
                        </Button>
                        <Badge variant="outline" className="text-green-500">
                            <Check className="w-3 h-3 mr-1" />
                            {status?.completed_jobs || 0}/{status?.total_jobs || 0} 完成
                        </Badge>
                    </div>
                )

            case 'blocked':
                return (
                    <TooltipProvider>
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button onClick={onOpenAssetsLock} variant="outline" className="border-red-500/50">
                                    <AlertTriangle className="w-4 h-4 mr-2 text-red-500" />
                                    资产未就绪
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                                <p>{error || '请先确认资产绑定'}</p>
                            </TooltipContent>
                        </Tooltip>
                    </TooltipProvider>
                )

            default:
                return null
        }
    }

    return (
        <div className="flex items-center gap-2">
            {renderButton()}
        </div>
    )
}
