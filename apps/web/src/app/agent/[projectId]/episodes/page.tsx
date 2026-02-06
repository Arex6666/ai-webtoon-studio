'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { Film, Loader2, ArrowLeft, Sparkles, Play } from 'lucide-react'
import Link from 'next/link'

import { projectsApi, conversationsApi } from '@/lib/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

interface Episode {
    number: number
    title: string
    summary: string
    status?: 'pending' | 'writing' | 'completed'
}

interface ProjectData {
    id: string
    name: string
    outline_text?: string
    episodes?: Episode[]
}

export default function EpisodesPage() {
    const params = useParams()
    const router = useRouter()
    const projectId = params.projectId as string

    const [project, setProject] = useState<ProjectData | null>(null)
    const [episodes, setEpisodes] = useState<Episode[]>([])
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        const loadProjectAndEpisodes = async () => {
            try {
                // 加载项目信息
                const projectData = await projectsApi.get(projectId)
                setProject(projectData as ProjectData)

                // 从项目的对话历史中获取大纲和集数信息
                const conversations = await conversationsApi.listByProject(projectId, 20, 0)

                if (conversations && conversations.length > 0) {
                    // 找到消息最多的对话（主对话）
                    const mainConv = conversations.reduce((best, conv) =>
                        (conv.message_count > best.message_count) ? conv : best
                        , conversations[0])

                    // 从对话中提取集数信息
                    const messages = await conversationsApi.getMessages(mainConv.id, 100, 0)

                    // 查找包含大纲卡片的消息
                    const outlineMsg = messages?.find(m => {
                        const cardData = m.entities_json?.card
                        return cardData?.type === 'outline'
                    })

                    if (outlineMsg) {
                        // 从大纲内容中解析集数
                        const parsedEpisodes = parseEpisodesFromOutline(outlineMsg.content)
                        setEpisodes(parsedEpisodes)
                    } else {
                        // 默认3集
                        setEpisodes([
                            { number: 1, title: '第1集', summary: '开篇', status: 'pending' },
                            { number: 2, title: '第2集', summary: '发展', status: 'pending' },
                            { number: 3, title: '第3集', summary: '高潮与结局', status: 'pending' },
                        ])
                    }
                }
            } catch (e) {
                console.error('Failed to load project:', e)
                setError(e instanceof Error ? e.message : '加载失败')
            } finally {
                setIsLoading(false)
            }
        }

        loadProjectAndEpisodes()
    }, [projectId])

    // 从大纲文本解析集数
    function parseEpisodesFromOutline(outlineText: string): Episode[] {
        const episodes: Episode[] = []

        // 匹配: 第1集：标题 或 第一集：标题
        const patterns = [
            /第(\d+)集[：:]\s*([^\n-]+)(?:\s*[-–]\s*([^\n]+))?/g,
            /第([一二三四五六七八九十]+)集[：:]\s*([^\n-]+)(?:\s*[-–]\s*([^\n]+))?/g,
        ]

        const chineseNums: Record<string, number> = {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
        }

        for (const pattern of patterns) {
            let match
            while ((match = pattern.exec(outlineText)) !== null) {
                let num: number
                if (isNaN(Number(match[1]))) {
                    num = chineseNums[match[1]] || 1
                } else {
                    num = parseInt(match[1])
                }

                const title = match[2]?.trim() || `第${num}集`
                const summary = match[3]?.trim() || title

                if (!episodes.find(e => e.number === num)) {
                    episodes.push({
                        number: num,
                        title: `第${num}集：${title}`,
                        summary,
                        status: 'pending'
                    })
                }
            }
        }

        episodes.sort((a, b) => a.number - b.number)

        // 如果没找到，返回默认
        if (episodes.length === 0) {
            return [
                { number: 1, title: '第1集', summary: '开篇', status: 'pending' },
                { number: 2, title: '第2集', summary: '发展', status: 'pending' },
                { number: 3, title: '第3集', summary: '高潮与结局', status: 'pending' },
            ]
        }

        return episodes
    }

    const handleEpisodeClick = (episode: Episode) => {
        router.push(`/agent/${projectId}/episodes/${episode.number}`)
    }

    if (isLoading) {
        return (
            <div className="flex-1 h-full bg-[#000000] flex items-center justify-center">
                <div className="flex items-center gap-3 text-zinc-500 text-sm">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    <span>加载分集信息...</span>
                </div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="flex-1 h-full bg-[#000000] flex items-center justify-center">
                <div className="text-red-400 text-sm">{error}</div>
            </div>
        )
    }

    return (
        <div className="flex-1 h-full bg-[#000000] overflow-auto">
            <div className="max-w-4xl mx-auto p-8">
                {/* Header */}
                <div className="mb-8">
                    <Link
                        href={`/agent/${projectId}`}
                        className="inline-flex items-center gap-2 text-zinc-500 hover:text-zinc-300 text-sm mb-4 transition-colors"
                    >
                        <ArrowLeft className="h-4 w-4" />
                        返回对话
                    </Link>

                    <h1 className="text-2xl font-bold text-white mb-2">
                        {project?.name || '未命名项目'}
                    </h1>
                    <p className="text-zinc-500">
                        选择一集开始创作剧本。Agent 将基于你的大纲和偏好，智能生成完整的分镜剧本。
                    </p>
                </div>

                {/* Episodes Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {episodes.map((episode) => (
                        <Card
                            key={episode.number}
                            className="group cursor-pointer bg-zinc-900/50 border-zinc-800 hover:border-emerald-500/50 hover:bg-zinc-900 transition-all duration-300"
                            onClick={() => handleEpisodeClick(episode)}
                        >
                            <CardHeader className="pb-3">
                                <div className="flex items-center justify-between">
                                    <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
                                        <Film className="h-5 w-5" />
                                    </div>
                                    <Badge
                                        variant="outline"
                                        className={
                                            episode.status === 'completed'
                                                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
                                                : episode.status === 'writing'
                                                    ? 'border-yellow-500/30 bg-yellow-500/10 text-yellow-400'
                                                    : 'border-zinc-700 bg-zinc-800/50 text-zinc-500'
                                        }
                                    >
                                        {episode.status === 'completed' ? '已完成' :
                                            episode.status === 'writing' ? '编写中' : '待创作'}
                                    </Badge>
                                </div>
                                <CardTitle className="text-base font-semibold text-white mt-3">
                                    {episode.title}
                                </CardTitle>
                                <CardDescription className="text-xs text-zinc-500 line-clamp-2">
                                    {episode.summary}
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="pt-0">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="w-full justify-center gap-2 text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10"
                                >
                                    {episode.status === 'completed' ? (
                                        <>
                                            <Play className="h-4 w-4" />
                                            查看剧本
                                        </>
                                    ) : (
                                        <>
                                            <Sparkles className="h-4 w-4" />
                                            开始创作
                                        </>
                                    )}
                                </Button>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            </div>
        </div>
    )
}
