/** Chat page scoped to a specific project. */
'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import { ChatPanel } from '@/components/chat'
import { ChatProjectPicker } from '@/components/chat/ChatProjectPicker'
import { Button } from '@/components/ui/button'
import { projectsApi } from '@/lib/api/services'

function generateId(): string { return crypto.randomUUID() }

export default function ChatProjectPage() {
    const params = useParams()
    const router = useRouter()
    const searchParams = useSearchParams()
    const projectId = params.projectId as string

    const [conversationId, setConversationId] = useState<string | null>(null)
    const [, setProjectName] = useState<string>('')
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        if (!projectId) return
        projectsApi.get(projectId)
            .then((p: any) => setProjectName(p?.name ?? ''))
            .catch((e) => {
                const status = e?.status ?? 0
                if (status === 404) setError('项目不存在')
                else if (status === 403) setError('无权访问此项目')
                else setError('加载项目失败')
            })
    }, [projectId])

    useEffect(() => {
        const fromUrl = searchParams.get('conversation')
        setConversationId(fromUrl || generateId())
    }, [searchParams])

    if (error) {
        return (
            <div className="h-screen flex items-center justify-center flex-col gap-4">
                <p className="text-lg">{error}</p>
                <Button variant="outline" onClick={() => router.push('/chat')}>返回项目列表</Button>
            </div>
        )
    }

    if (!conversationId) {
        return (
            <div className="flex items-center justify-center h-screen">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500" />
            </div>
        )
    }

    return (
        <div className="h-screen flex flex-col bg-background">
            <nav className="border-b px-4 py-3 flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <h1 className="text-xl font-bold">AI Webtoon Studio</h1>
                    <span className="text-sm text-muted-foreground">Chat Mode</span>
                    <ChatProjectPicker currentProjectId={projectId} />
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm" onClick={() => setConversationId(generateId())}>
                        新对话
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => router.push(`/agent/${projectId}/episodes`)}>
                        查看集数
                    </Button>
                </div>
            </nav>
            <ChatPanel
                conversationId={conversationId}
                projectId={projectId}
                className="flex-1"
            />
        </div>
    )
}
