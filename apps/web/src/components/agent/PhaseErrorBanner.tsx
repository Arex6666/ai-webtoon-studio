'use client'

import { AlertCircle, RotateCcw, SkipForward } from 'lucide-react'
import { Button } from '@/components/ui/button'

export interface PhaseErrorBannerProps {
    phase: string
    message: string
    onRetry: () => void
    onSkip?: () => void
}

export function PhaseErrorBanner({ phase, message, onRetry, onSkip }: PhaseErrorBannerProps) {
    return (
        <div className="flex items-start gap-3 p-3 rounded bg-red-500/10 border border-red-500/30">
            <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-red-300">{phase} 阶段失败</p>
                <p className="text-xs text-red-400/80 mt-0.5 break-words">{message}</p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
                <Button size="sm" variant="outline" onClick={onRetry} className="gap-1">
                    <RotateCcw className="w-3.5 h-3.5" />
                    重试
                </Button>
                {onSkip && (
                    <Button size="sm" variant="ghost" onClick={onSkip} className="gap-1">
                        <SkipForward className="w-3.5 h-3.5" />
                        跳过
                    </Button>
                )}
            </div>
        </div>
    )
}
