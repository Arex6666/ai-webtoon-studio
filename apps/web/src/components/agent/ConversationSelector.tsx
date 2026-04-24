'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
    DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'
import { Button } from '@/components/ui/button'
import { ChevronDown, MessageSquare } from 'lucide-react'
import { conversationsApi, type Conversation } from '@/lib/api/services'

export interface ConversationSelectorProps {
    projectId: string
    currentConversationId: string | null
}

export function ConversationSelector({
    projectId,
    currentConversationId,
}: ConversationSelectorProps) {
    const router = useRouter()
    const searchParams = useSearchParams()
    const [open, setOpen] = useState(false)
    const [conversations, setConversations] = useState<Conversation[]>([])
    const [loaded, setLoaded] = useState(false)

    useEffect(() => {
        if (!open || loaded) return
        let cancelled = false
        const load = async () => {
            try {
                const list = await conversationsApi.listByProject(projectId, 50, 0)
                if (cancelled) return
                setConversations(Array.isArray(list) ? list : [])
            } catch {
                if (!cancelled) setConversations([])
            } finally {
                if (!cancelled) setLoaded(true)
            }
        }
        load()
        return () => {
            cancelled = true
        }
    }, [open, loaded, projectId])

    const current = conversations.find(c => c.id === currentConversationId) ?? null
    const triggerLabel = current?.title ?? '选择对话'

    const handleSelect = (id: string) => {
        const params = new URLSearchParams(searchParams?.toString() ?? '')
        params.set('conversation', id)
        router.push(`?${params.toString()}`)
    }

    return (
        <DropdownMenu open={open} onOpenChange={setOpen}>
            <DropdownMenuTrigger asChild>
                <Button
                    variant="ghost"
                    size="sm"
                    className="text-xs text-zinc-300 hover:bg-zinc-800"
                >
                    <MessageSquare className="h-3.5 w-3.5 mr-1.5" />
                    <span
                        className="truncate"
                        style={{ maxWidth: 160 }}
                    >
                        {triggerLabel}
                    </span>
                    <ChevronDown className="h-3.5 w-3.5 ml-1.5 opacity-70" />
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-[280px]">
                {conversations.length === 0 ? (
                    <div className="px-3 py-6 text-center text-xs text-muted-foreground">
                        无其他对话
                    </div>
                ) : (
                    conversations.map((conv, idx) => {
                        const isCurrent = conv.id === currentConversationId
                        const title = conv.title ?? conv.id.slice(0, 8)
                        const count = conv.message_count ?? 0
                        return (
                            <div key={conv.id}>
                                {idx > 0 && <DropdownMenuSeparator />}
                                <DropdownMenuItem
                                    onSelect={() => handleSelect(conv.id)}
                                    className={`flex flex-col items-start gap-0.5 py-2 ${
                                        isCurrent ? 'bg-accent' : ''
                                    }`}
                                >
                                    <span className="truncate w-full text-sm">
                                        {title}
                                    </span>
                                    <span className="text-xs text-muted-foreground">
                                        {count} 条消息
                                    </span>
                                </DropdownMenuItem>
                            </div>
                        )
                    })
                )}
            </DropdownMenuContent>
        </DropdownMenu>
    )
}
