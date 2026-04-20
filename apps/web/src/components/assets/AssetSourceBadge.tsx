'use client'

import { Bot } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import {
    Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from '@/components/ui/tooltip'

export interface AssetSourceBadgeProps {
    createdVia?: string | null
    sourceConversationId?: string | null
    size?: 'sm' | 'md'
}

export function AssetSourceBadge({ createdVia, sourceConversationId, size = 'md' }: AssetSourceBadgeProps) {
    if (createdVia !== 'agent') return null
    const sizeClass = size === 'sm' ? 'text-[10px] px-1.5 py-0.5' : 'text-xs px-2 py-0.5'

    return (
        <TooltipProvider delayDuration={150}>
            <Tooltip>
                <TooltipTrigger asChild>
                    <Badge variant="secondary" className={`inline-flex items-center gap-1 ${sizeClass}`}>
                        <Bot className="w-3 h-3" />
                        来自 Agent
                    </Badge>
                </TooltipTrigger>
                <TooltipContent>
                    {sourceConversationId
                        ? `由 Agent 对话 ${sourceConversationId.slice(0, 8)}… 创建`
                        : '由 Agent 对话创建'}
                </TooltipContent>
            </Tooltip>
        </TooltipProvider>
    )
}
