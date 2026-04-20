'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { MessageSquarePlus, FolderPlus, ArrowRight } from 'lucide-react'
import { projectsApi } from '@/lib/api/services'
import type { Project } from '@/lib/api/types'

export function ChatEmptyState() {
    const router = useRouter()
    const [recent, setRecent] = useState<Project[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        projectsApi.list?.()
            .then((data: any) => {
                const items = Array.isArray(data) ? data : (data?.items ?? [])
                setRecent(items.slice(0, 6))
            })
            .finally(() => setLoading(false))
    }, [])

    if (loading) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500" />
            </div>
        )
    }

    if (recent.length === 0) {
        return (
            <div className="flex items-center justify-center h-full p-8">
                <Card className="max-w-md">
                    <CardHeader>
                        <div className="mb-3 inline-flex items-center justify-center w-12 h-12 rounded-full bg-emerald-500/10">
                            <MessageSquarePlus className="w-6 h-6 text-emerald-500" />
                        </div>
                        <CardTitle>开始你的第一个项目</CardTitle>
                        <CardDescription>
                            Agent 对话模式让你通过聊天创作 webtoon。先创建一个项目作为承载。
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <Button onClick={() => router.push('/projects?create=1')} className="w-full">
                            <FolderPlus className="w-4 h-4 mr-2" />
                            创建项目
                        </Button>
                    </CardContent>
                </Card>
            </div>
        )
    }

    return (
        <div className="max-w-3xl mx-auto p-8">
            <div className="mb-6">
                <h2 className="text-2xl font-semibold">选择项目开始对话</h2>
                <p className="text-sm text-muted-foreground mt-1">或者创建一个新项目</p>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
                {recent.map(p => (
                    <Card
                        key={p.id}
                        onClick={() => router.push(`/chat/${p.id}`)}
                        className="cursor-pointer hover:bg-accent/50 transition-colors"
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                                e.preventDefault()
                                router.push(`/chat/${p.id}`)
                            }
                        }}
                    >
                        <CardHeader>
                            <CardTitle className="text-base truncate">{p.name}</CardTitle>
                            {p.description ? (
                                <CardDescription className="line-clamp-2">{p.description}</CardDescription>
                            ) : null}
                        </CardHeader>
                        <CardContent>
                            <div className="text-xs text-emerald-500 inline-flex items-center">
                                开始对话 <ArrowRight className="w-3 h-3 ml-1" />
                            </div>
                        </CardContent>
                    </Card>
                ))}
                <Card
                    onClick={() => router.push('/projects?create=1')}
                    className="cursor-pointer border-dashed hover:bg-accent/50 transition-colors flex items-center justify-center p-8"
                    role="button" tabIndex={0}
                >
                    <div className="text-center">
                        <FolderPlus className="w-8 h-8 mx-auto mb-2 text-muted-foreground" />
                        <div className="text-sm">新建项目</div>
                    </div>
                </Card>
            </div>
        </div>
    )
}
