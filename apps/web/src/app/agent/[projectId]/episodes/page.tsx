'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { Film, Loader2, ArrowLeft, Sparkles, Play, Upload, ExternalLink } from 'lucide-react'
import Link from 'next/link'

import { projectsApi, conversationsApi } from '@/lib/api'
import { agentApi } from '@/lib/api/services'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/hooks/use-toast'

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
    const { toast } = useToast()

    const [project, setProject] = useState<ProjectData | null>(null)
    const [episodes, setEpisodes] = useState<Episode[]>([])
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [mainConvId, setMainConvId] = useState<string | null>(null)
    const [bulkProgress, setBulkProgress] = useState<{ done: number; total: number } | null>(null)

    useEffect(() => {
        const loadProjectAndEpisodes = async () => {
            try {
                // 加载项目信息
                const projectData = await projectsApi.get(projectId)
                setProject(projectData as ProjectData)

                // 从项目的对话历史中获取大纲和集数信息
                const conversations = await conversationsApi.listByProject(projectId, 20, 0)

                if (conversations && conversations.length > 0) {
                    // 找到消息最多的主对话（排除已绑定到具体分集的对话）
                    const mainConvs = conversations.filter((c: any) => !c.episode_number)
                    const pool = mainConvs.length > 0 ? mainConvs : conversations
                    const mainConv = pool.reduce((best: any, conv: any) =>
                        (conv.message_count > best.message_count) ? conv : best
                        , pool[0])

                    setMainConvId(mainConv.id)

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

    // ─── Bulk commit: for each episode, read cached pipeline data from its conversation ───
    // and send full payload. Episodes that haven't been generated yet fall back to lean payload.
    const handleCommitAll = useCallback(async () => {
        if (!mainConvId) {
            toast({ title: '缺少对话上下文', description: '请先在主对话中生成大纲', variant: 'destructive' })
            return
        }
        if (episodes.length === 0) {
            toast({ title: '暂无分集可提交', variant: 'destructive' })
            return
        }

        setBulkProgress({ done: 0, total: episodes.length })
        const failures: Array<{ num: number; reason: string }> = []
        const skeletalOnly: number[] = []
        let successCount = 0

        for (let i = 0; i < episodes.length; i++) {
            const ep = episodes[i]
            try {
                // Step 1: locate this episode's conversation
                const episodeConv = await conversationsApi.getOrCreateEpisode(projectId, ep.number)

                // Step 2: read cached pipeline data (script_data + panel_images) from message history
                let scriptData: any = null
                let panelImages: Record<string, string> = {}

                if (episodeConv.message_count > 0) {
                    const episodeMessages = await conversationsApi.getMessages(episodeConv.id, 100, 0)
                    const pipelineMsg = [...(episodeMessages || [])].reverse().find((m: any) =>
                        m.entities_json?.card?.type === 'episode_pipeline'
                    )
                    if (pipelineMsg?.entities_json?.card) {
                        scriptData = pipelineMsg.entities_json.card.script_data ?? null
                        panelImages = pipelineMsg.entities_json.card.panel_images ?? {}
                    }
                }

                // Step 3: build payload. Full if cached data present; lean fallback otherwise.
                let payload: Parameters<typeof agentApi.commitToStudio>[1]
                if (scriptData && Array.isArray(scriptData.panels) && scriptData.panels.length > 0) {
                    payload = {
                        conversation_id: episodeConv.id,
                        episode_number: ep.number,
                        episode_title: scriptData.episode_title ?? ep.title ?? '',
                        outline_summary: scriptData.story_summary ?? ep.summary ?? '',
                        art_style: scriptData.art_style ?? {},
                        characters: (scriptData.characters ?? []).map((c: any) => ({
                            name: c.name,
                            visual_prompt: c.visual_prompt ?? c.description ?? '',
                            temp_image_url: c.image_url,
                            appearance_traits: [],
                            personality_traits: [],
                            wardrobe_notes: undefined,
                        })),
                        scenes: (scriptData.scenes ?? []).map((s: any) => ({
                            name: s.name,
                            visual_prompt: s.visual_prompt ?? s.description ?? '',
                            temp_image_url: s.image_url,
                            time_of_day: undefined,
                            weather: undefined,
                            mood: undefined,
                        })),
                        panels: (scriptData.panels ?? []).map((p: any, idx: number) => ({
                            id: p.id,
                            order: idx,
                            scene_name: p.scene_name,
                            characters: p.characters ?? [],
                            scene_description: p.scene_description ?? '',
                            dialogue: p.dialogue,
                            shot_type: 'MS',
                            camera_angle: 'eye-level',
                            emotion: undefined,
                            composition: p.composition,
                            temp_image_url: panelImages[p.id] ?? p.image_url,
                        })),
                    }
                } else {
                    // Lean fallback: creates a skeletal chapter only. User must commit from
                    // episode detail page to populate panels/characters/scenes.
                    skeletalOnly.push(ep.number)
                    payload = {
                        conversation_id: episodeConv.id,
                        episode_number: ep.number,
                        episode_title: ep.title ?? '',
                        outline_summary: ep.summary ?? '',
                    }
                }

                await agentApi.commitToStudio(projectId, payload)
                successCount += 1
            } catch (e) {
                const reason = e instanceof Error ? e.message : String(e)
                failures.push({ num: ep.number, reason })
                toast({
                    title: `第${ep.number}集提交失败`,
                    description: reason,
                    variant: 'destructive',
                })
            }
            setBulkProgress({ done: i + 1, total: episodes.length })
        }

        setBulkProgress(null)

        // Summary toast
        if (failures.length === 0) {
            const skeletalNote = skeletalOnly.length > 0
                ? `其中第 ${skeletalOnly.join('、')} 集尚未生成剧本，仅创建了章节骨架，请进入各集详情页完善后再次提交。`
                : ''
            toast({
                title: '全部提交完成',
                description: `${successCount}/${episodes.length} 集已提交到 Studio。${skeletalNote}`,
            })
        } else {
            toast({
                title: `${successCount}/${episodes.length} 成功`,
                description: `失败: 第 ${failures.map(f => f.num).join('、')} 集`,
                variant: 'destructive',
            })
        }
    }, [episodes, mainConvId, projectId, toast])

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

                    <div className="flex items-start justify-between gap-4">
                        <div>
                            <h1 className="text-2xl font-bold text-white mb-2">
                                {project?.name || '未命名项目'}
                            </h1>
                            <p className="text-zinc-500">
                                选择一集开始创作剧本。Agent 将基于你的大纲和偏好，智能生成完整的分镜剧本。
                            </p>
                        </div>
                        <Button
                            onClick={handleCommitAll}
                            disabled={!mainConvId || bulkProgress !== null || episodes.length === 0}
                            variant="secondary"
                            size="sm"
                            className="shrink-0 bg-emerald-600 hover:bg-emerald-700 text-white border-0"
                            title={
                                !mainConvId
                                    ? '缺少对话上下文'
                                    : '将所有分集提交到 Studio；未生成剧本的分集仅会创建章节骨架'
                            }
                        >
                            {bulkProgress ? (
                                <>
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    提交中 {bulkProgress.done}/{bulkProgress.total}
                                </>
                            ) : (
                                <>
                                    <Upload className="h-4 w-4 mr-2" />
                                    一键提交全部到 Studio
                                </>
                            )}
                        </Button>
                    </div>
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
                            <CardContent className="pt-0 flex flex-col gap-2">
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
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="w-full justify-center gap-2 border-zinc-700 text-zinc-400 hover:bg-zinc-800 hover:text-white"
                                    onClick={(e) => {
                                        e.stopPropagation()
                                        router.push(`/agent/${projectId}/episodes/${episode.number}`)
                                    }}
                                >
                                    <ExternalLink className="h-3.5 w-3.5" />
                                    打开详情
                                </Button>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            </div>
        </div>
    )
}
