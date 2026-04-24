'use client'

import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import { Loader2, ArrowLeft, Sparkles, FileText, Film, Play } from 'lucide-react'
import Link from 'next/link'

import { AgentChat, AgentMessage } from '@/components/agent/AgentChat'
import { EpisodeTree } from '@/components/agent/EpisodeTree'
import { PhaseErrorBanner } from '@/components/agent/PhaseErrorBanner'
import { VideoCard, VideoCardData, PanelImage, PanelMeta } from '@/components/agent/VideoCard'
import { conversationsApi, api } from '@/lib/api'
import { agentApi } from '@/lib/api/services'
import { Button } from '@/components/ui/button'
import { useToast } from '@/hooks/use-toast'
import { useEpisodeTreeData } from '@/hooks/useEpisodeTreeData'
import { useScriptStream } from '@/hooks/useScriptStream'
import {
    EpisodeScriptData,
    generatePanelImages,
    refineEpisode,
} from '@/lib/api/episodeApi'

type EpisodePhase = 'loading' | 'script' | 'confirm' | 'panels' | 'video' | 'done'

export default function EpisodeConversationPage() {
    const params = useParams()
    const router = useRouter()
    const searchParams = useSearchParams()
    const projectId = params.projectId as string
    const episodeNum = parseInt(params.episodeNum as string)

    // Episode tree data (left sidebar)
    const { episodes } = useEpisodeTreeData(projectId)
    const [selectedPhaseId, setSelectedPhaseId] = useState<string | null>(null)

    const currentEpisodeId = useMemo(
        () => episodes.find(e => e.number === episodeNum)?.id ?? null,
        [episodes, episodeNum]
    )

    // Core state
    const [messages, setMessages] = useState<AgentMessage[]>([])
    const [isTyping, setIsTyping] = useState(false)
    const [conversationId, setConversationId] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [outlineContext, setOutlineContext] = useState<string>('')

    // Phase pipeline state
    const [phase, setPhase] = useState<EpisodePhase>('loading')
    const [scriptData, setScriptData] = useState<EpisodeScriptData | null>(null)
    const [panelImages, setPanelImages] = useState<Record<string, string>>({})
    const [panelProgress, setPanelProgress] = useState<{ done: number; total: number } | null>(null)
    const [generationError, setGenerationError] = useState<string | null>(null)

    const videoCardDataRef = useRef<VideoCardData | null>(null)
    const loadStartedRef = useRef(false)
    const hasAutoTriggered = useRef(false)

    // Open-in-Studio state
    const { toast } = useToast()
    const [committing, setCommitting] = useState(false)

    // SSE script stream
    const {
        status: streamStatus,
        phase: streamPhase,
        pct: streamPct,
        data: streamData,
        error: streamError,
        start: startStream,
    } = useScriptStream(api.baseUrl)

    const handleOpenInStudio = useCallback(async () => {
        if (!conversationId) {
            toast({ title: '缺少对话上下文', variant: 'destructive' })
            return
        }
        if (!scriptData) {
            toast({ title: '剧本尚未生成', variant: 'destructive' })
            return
        }
        setCommitting(true)
        try {
            const payload = {
                conversation_id: conversationId,
                episode_number: episodeNum,
                episode_title: scriptData.episode_title ?? '',
                outline_summary: scriptData.story_summary ?? '',
                art_style: scriptData.art_style ?? {},
                characters: (scriptData.characters ?? []).map((c) => ({
                    name: c.name,
                    visual_prompt: c.visual_prompt ?? c.description ?? '',
                    temp_image_url: c.image_url,
                    appearance_traits: [] as string[],
                    personality_traits: [] as string[],
                    wardrobe_notes: undefined as string | undefined,
                })),
                scenes: (scriptData.scenes ?? []).map((s) => ({
                    name: s.name,
                    visual_prompt: s.visual_prompt ?? s.description ?? '',
                    temp_image_url: s.image_url,
                    time_of_day: undefined as string | undefined,
                    weather: undefined as string | undefined,
                    mood: undefined as string | undefined,
                })),
                panels: (scriptData.panels ?? []).map((p, idx) => ({
                    id: p.id,
                    order: idx,
                    scene_name: p.scene_name,
                    characters: p.characters ?? [],
                    scene_description: p.scene_description ?? '',
                    dialogue: p.dialogue,
                    shot_type: 'MS',
                    camera_angle: 'eye-level',
                    emotion: undefined as string | undefined,
                    composition: p.composition,
                    temp_image_url: panelImages[p.id] ?? p.image_url,
                })),
            }
            const result = await agentApi.commitToStudio(projectId, payload)
            if (result.status === 'already_exists') {
                toast({ title: '已打开已有章节', description: result.chapter_title })
            } else {
                toast({
                    title: '已创建章节',
                    description: `${result.created_panels} 分镜 · ${result.created_assets.characters} 角色 · ${result.created_assets.scenes} 场景`,
                })
                if (result.warnings.length > 0) {
                    toast({
                        title: '部分图片未能保存',
                        description: `${result.warnings.length} 条警告，可在 Studio 手动上传`,
                    })
                }
            }
            router.push(result.studio_url)
        } catch (err) {
            toast({
                title: '提交失败',
                description: err instanceof Error ? err.message : String(err),
                variant: 'destructive',
            })
        } finally {
            setCommitting(false)
        }
    }, [conversationId, episodeNum, scriptData, panelImages, projectId, router, toast])

    // ─── EpisodeTree callbacks ───
    const handleSelectEpisode = useCallback((id: string) => {
        const ep = episodes.find(e => e.id === id)
        if (!ep) return
        if (ep.number === episodeNum) return
        router.push(`/agent/${projectId}/episodes/${ep.number}`)
    }, [episodes, episodeNum, projectId, router])

    const handleSelectPhase = useCallback((episodeId: string, phaseId: string) => {
        setSelectedPhaseId(phaseId)
        if (episodeId !== currentEpisodeId) {
            const ep = episodes.find(e => e.id === episodeId)
            if (ep) {
                router.push(`/agent/${projectId}/episodes/${ep.number}?phase=${phaseId}`)
            }
            return
        }
        document.getElementById(`phase-${phaseId}`)?.scrollIntoView({
            behavior: 'smooth',
            block: 'start',
        })
    }, [episodes, currentEpisodeId, projectId, router])

    const handleAddEpisode = useCallback(() => {
        const maxNum = Math.max(0, ...episodes.map(e => e.number))
        router.push(`/agent/${projectId}/episodes/${maxNum + 1}`)
    }, [episodes, projectId, router])

    // ─── React to ?phase= query param for cross-page scroll ───
    useEffect(() => {
        const phaseParam = searchParams?.get('phase')
        if (!phaseParam) return
        setSelectedPhaseId(phaseParam)
        const timer = setTimeout(() => {
            document.getElementById(`phase-${phaseParam}`)?.scrollIntoView({
                behavior: 'smooth',
                block: 'start',
            })
        }, 100)
        return () => clearTimeout(timer)
    }, [searchParams, scriptData])

    // ─── Load conversation history and context ───
    useEffect(() => {
        if (loadStartedRef.current) return
        loadStartedRef.current = true

        const loadEpisodeConversation = async () => {
            try {
                console.log(`[Episode ${episodeNum}] Loading conversation...`)

                // 1. Get outline context from main conversation
                const conversations = await conversationsApi.listByProject(projectId, 20, 0)
                if (conversations && conversations.length > 0) {
                    const mainConvs = conversations.filter((c: any) => !c.episode_number)
                    if (mainConvs.length > 0) {
                        const mainConv = mainConvs.reduce((best: any, conv: any) =>
                            (conv.message_count > best.message_count) ? conv : best
                            , mainConvs[0])
                        const mainMessages = await conversationsApi.getMessages(mainConv.id, 100, 0)
                        const outlineMsg = mainMessages?.find((m: any) => m.entities_json?.card?.type === 'outline')
                        if (outlineMsg) {
                            setOutlineContext(outlineMsg.content)
                        }
                    }
                }

                // 2. Get or create episode conversation
                const episodeConv = await conversationsApi.getOrCreateEpisode(projectId, episodeNum)
                setConversationId(episodeConv.id)

                // 3. Load history and restore phase
                if (episodeConv.message_count > 0) {
                    const episodeMessages = await conversationsApi.getMessages(episodeConv.id, 100, 0)
                    if (episodeMessages && episodeMessages.length > 0) {
                        const historyMessages: AgentMessage[] = episodeMessages.map((msg: any, idx: number) => ({
                            id: msg.id || `history-${idx}`,
                            role: msg.role as 'user' | 'assistant' | 'system',
                            content: msg.content,
                            timestamp: new Date(msg.created_at).getTime(),
                            card: msg.entities_json?.card || msg.entities_json,
                        }))

                        setMessages(historyMessages)

                        // Restore phase from last pipeline message
                        const pipelineMsg = [...historyMessages].reverse().find(m =>
                            m.card?.type === 'episode_pipeline'
                        )
                        if (pipelineMsg?.card) {
                            const savedPhase = pipelineMsg.card.phase as EpisodePhase
                            setPhase(savedPhase)
                            if (pipelineMsg.card.script_data) {
                                setScriptData(pipelineMsg.card.script_data)
                            }
                            if (pipelineMsg.card.panel_images) {
                                setPanelImages(pipelineMsg.card.panel_images)
                            }
                            hasAutoTriggered.current = true
                        } else {
                            // Check for stale mock data
                            const hasMockData = historyMessages.some(m =>
                                m.content.includes('主角A') && m.content.includes('场景环境描述')
                            )
                            if (hasMockData) {
                                setMessages([])
                            }
                        }
                    }
                }
            } catch (error) {
                console.error(`[Episode ${episodeNum}] Failed to load:`, error)
            } finally {
                setIsLoading(false)
            }
        }

        loadEpisodeConversation()
    }, [projectId, episodeNum])

    // ─── Save message helper ───
    const saveMessage = useCallback(async (
        role: 'user' | 'assistant' | 'system',
        content: string,
        metadata?: Record<string, any>
    ) => {
        if (!conversationId) return
        try {
            await conversationsApi.saveMessage(conversationId, role, content, metadata)
        } catch (error) {
            console.error('Failed to save message:', error)
        }
    }, [conversationId])

    // ─── Auto-trigger script generation ───
    useEffect(() => {
        if (
            !hasAutoTriggered.current &&
            !isLoading &&
            conversationId &&
            outlineContext &&
            phase === 'loading'
        ) {
            hasAutoTriggered.current = true
            setPhase('script')
            handleGenerateScript()
        }
    }, [isLoading, conversationId, outlineContext, phase])

    // ─── Phase 1: Generate script + character/scene images (SSE) ───
    const handleGenerateScript = async () => {
        setGenerationError(null)
        setPhase('script')

        const welcomeMsg: AgentMessage = {
            id: 'welcome',
            role: 'assistant',
            content: `你好！我是 **Arex**。正在为你创作**第${episodeNum}集**的完整分镜剧本...\n\n正在分析大纲，生成剧本、角色图和场景图...`,
            timestamp: Date.now(),
        }
        setMessages([welcomeMsg])
        await saveMessage('assistant', welcomeMsg.content)

        setIsTyping(true)

        await startStream(episodeNum, {
            project_id: projectId,
            episode_number: episodeNum,
            outline_text: outlineContext,
        })
    }

    // ─── React to SSE done/error events ───
    useEffect(() => {
        if (streamStatus === 'done' && streamData && streamData.panels) {
            const data = streamData as EpisodeScriptData
            setScriptData(data)

            const scriptContent = formatScriptAsMarkdown(data)
            const scriptMsg: AgentMessage = {
                id: 'script',
                role: 'assistant',
                content: scriptContent,
                timestamp: Date.now(),
            }
            setMessages(prev => [...prev.filter(m => m.id !== 'script'), scriptMsg])
            setPhase('confirm')
            setIsTyping(false)

            // Persist pipeline state
            saveMessage('assistant', scriptContent, {
                type: 'episode_pipeline',
                phase: 'confirm',
                script_data: data,
            }).catch(err => console.error('Failed to persist script:', err))
        } else if (streamStatus === 'error') {
            const errorText = streamError || '网络错误'
            setGenerationError(errorText)
            setIsTyping(false)

            const errorMsg: AgentMessage = {
                id: 'error-' + Date.now(),
                role: 'assistant',
                content: `剧本生成失败：**${errorText}**\n\n请检查后端配置后点击下方按钮重试。`,
                timestamp: Date.now(),
            }
            setMessages(prev => [...prev, errorMsg])
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [streamStatus, streamData, streamError])

    // ─── Phase 2→3: Confirm assets and generate panel first frames ───
    const handleConfirmAssets = async () => {
        if (!scriptData) return
        setPhase('panels')
        setGenerationError(null)

        const progressMsg: AgentMessage = {
            id: 'panel-progress',
            role: 'assistant',
            content: `正在生成分镜首帧... (0/${scriptData.panels.length})`,
            timestamp: Date.now(),
        }
        setMessages(prev => [...prev, progressMsg])
        setIsTyping(true)
        setPanelProgress({ done: 0, total: scriptData.panels.length })

        try {
            const result = await generatePanelImages(episodeNum, {
                project_id: projectId,
                art_style: scriptData.art_style,
                characters: scriptData.characters,
                scenes: scriptData.scenes,
                panels: scriptData.panels.map(p => ({
                    id: p.id,
                    scene_name: p.scene_name,
                    scene_description: p.scene_description,
                    composition: p.composition,
                    camera_movement: p.camera_movement,
                    characters: p.characters,
                })),
            })

            // Collect results
            const images: Record<string, string> = {}
            const failed: string[] = []
            for (const pr of result.panels) {
                if (pr.status === 'success' && pr.image_url) {
                    images[pr.id] = pr.image_url
                } else {
                    failed.push(pr.id)
                }
            }
            setPanelImages(images)

            const successCount = Object.keys(images).length
            const statusLine = failed.length === 0
                ? `分镜首帧全部生成完成！共 **${successCount}** 张。`
                : `分镜首帧生成完成：**${successCount}** 张成功，**${failed.length}** 张失败（${failed.join(', ')}）。`

            // Build image grid in markdown
            const imageLines = Object.entries(images)
                .map(([panelId, url]) => `![分镜${panelId}](${url})`)
                .join('\n\n')

            const hintLine = failed.length === 0
                ? `可以点击下方按钮生成视频，或通过对话调整分镜内容。`
                : `你可以说"重新生成 ${failed[0]}"来重试，或直接生成视频。`

            const resultContent = `${statusLine}\n\n${imageLines}\n\n${hintLine}`

            // Update script markdown with panel images
            const updatedMarkdown = formatScriptAsMarkdown(scriptData, images)
            setMessages(prev => [
                ...prev.filter(m => m.id !== 'panel-progress').map(m =>
                    m.id === 'script' ? { ...m, content: updatedMarkdown } : m
                ),
                {
                    id: 'panel-result',
                    role: 'assistant' as const,
                    content: resultContent,
                    timestamp: Date.now(),
                },
            ])

            const nextPhase = failed.length === 0 ? 'video' : 'panels'
            setPhase(nextPhase)

            // Persist
            await saveMessage('assistant', resultContent, {
                type: 'episode_pipeline',
                phase: nextPhase,
                script_data: scriptData,
                panel_images: images,
            })
        } catch (e: any) {
            setGenerationError(e.message || '分镜首帧生成失败')
            const errorMsg: AgentMessage = {
                id: 'panel-error',
                role: 'assistant',
                content: `分镜首帧生成失败：**${e.message}**\n\n请点击下方按钮重试。`,
                timestamp: Date.now(),
            }
            setMessages(prev => prev.filter(m => m.id !== 'panel-progress').concat(errorMsg))
        } finally {
            setIsTyping(false)
            setPanelProgress(null)
        }
    }

    // ─── Format script as Markdown ───
    function formatScriptAsMarkdown(script: any, images?: Record<string, string>): string {
        const title = script.episode_title || script.episodeTitle || `第${episodeNum}集`
        const summary = script.story_summary || script.storySummary || '暂无梗概'
        const artStyle = script.art_style || script.artStyle || {}

        let md = `# ${title}\n\n`
        md += `## 📖 故事梗概\n\n${summary}\n\n`

        if (script.highlights?.length > 0) {
            md += `## ✨ 剧本亮点\n\n`
            script.highlights.forEach((h: any, i: number) => {
                md += `### ${h.title || `亮点${i + 1}`}\n${h.description || ''}\n\n`
            })
        }

        md += `## 🎨 美术风格\n\n`
        md += `| 属性 | 描述 |\n|------|------|\n`
        md += `| **基础画风** | ${artStyle.base_style || artStyle.baseStyle || '韩漫二次元'} |\n`
        md += `| **色调** | ${artStyle.color_tone || artStyle.colorTone || '柔和温暖'} |\n`
        md += `| **氛围** | ${artStyle.atmosphere || '细腻唯美'} |\n\n`

        if (script.characters?.length > 0) {
            md += `## 👥 角色列表\n\n`
            script.characters.forEach((c: any) => {
                md += `### ${c.name || '未命名角色'}\n`
                const imageUrl = c.image_url || c.imageUrl
                if (imageUrl) {
                    md += `![${c.name}角色图](${imageUrl})\n\n`
                }
                md += `${c.description || ''}\n`
                const visualPrompt = c.visual_prompt || c.visualPrompt
                if (visualPrompt) {
                    md += `\n> **绘画提示词**: ${visualPrompt}\n`
                }
                md += `\n`
            })
        }

        if (script.scenes?.length > 0) {
            md += `## 🗺️ 场景列表\n\n`
            script.scenes.forEach((s: any) => {
                md += `### ${s.name || '未命名场景'}\n`
                const imageUrl = s.image_url || s.imageUrl
                if (imageUrl) {
                    md += `![${s.name}场景图](${imageUrl})\n\n`
                }
                md += `${s.description || ''}\n`
                const visualPrompt = s.visual_prompt || s.visualPrompt
                if (visualPrompt) {
                    md += `\n> **绘画提示词**: ${visualPrompt}\n`
                }
                md += `\n`
            })
        }

        if (script.panels?.length > 0) {
            md += `## 🎬 分镜剧本\n\n`
            md += `共 **${script.panels.length}** 个分镜\n\n`

            script.panels.forEach((p: any) => {
                md += `### 分镜 ${p.id}\n\n`

                const imgUrl = images?.[p.id] || p.image_url || p.imageUrl
                if (imgUrl) {
                    md += `![分镜${p.id}](${imgUrl})\n\n`
                }

                const sceneDesc = p.scene_description || p.scene || ''
                const sceneName = p.scene_name || p.sceneName || ''
                const cameraMove = p.camera_movement || p.camera || ''
                const voiceChar = p.voice_character || p.voice || ''
                const chars = p.characters || []
                const duration = p.duration_sec || p.durationSec || 5

                md += `| 属性 | 内容 |\n|------|------|\n`
                if (sceneName) md += `| **场景** | ${sceneName} |\n`
                if (chars.length > 0) md += `| **角色** | ${chars.join('、')} |\n`
                md += `| **画面描述** | ${sceneDesc} |\n`
                md += `| **构图设计** | ${p.composition || ''} |\n`
                md += `| **运镜调度** | ${cameraMove} |\n`
                md += `| **时长** | ${duration}秒 |\n`
                md += `| **配音角色** | ${voiceChar} |\n`
                md += `| **台词内容** | ${p.dialogue || ''} |\n\n`
            })
        }

        return md
    }

    // ─── Compose keywords ───
    const COMPOSE_KEYWORDS = ['合成视频', '合成', '拼接视频', '拼接', '合并视频', '合并']
    const isComposeIntent = (text: string) => COMPOSE_KEYWORDS.some(kw => text.includes(kw))

    // ─── VideoCard callbacks ───
    const handleVideoDataChange = useCallback((newData: VideoCardData) => {
        videoCardDataRef.current = newData
        if (newData.phase === 'done') {
            setPhase('done')
        }
        setMessages(prev => prev.map(msg => {
            if (msg.id === 'video-card-msg') {
                return {
                    ...msg,
                    customContent: (
                        <VideoCard
                            data={newData}
                            projectId={projectId}
                            episodeNum={episodeNum}
                            onDataChange={handleVideoDataChange}
                            onCompose={handleCompose}
                        />
                    )
                }
            }
            return msg
        }))
    }, [projectId, episodeNum])

    const handleCompose = useCallback((videoUrls: string[]) => {
        const composeMsg: AgentMessage = {
            id: 'compose-' + Date.now(),
            role: 'assistant',
            content: `正在合成 **${videoUrls.length}** 个分镜视频…\n\n> 合成功能需要后端 FFmpeg 服务支持。视频链接：\n${videoUrls.map((u, i) => `> ${i + 1}. [分镜视频 ${i + 1}](${u})`).join('\n')}`,
            timestamp: Date.now(),
        }
        setMessages(prev => [...prev, composeMsg])
        saveMessage('assistant', composeMsg.content)
    }, [saveMessage])

    // ─── Start video generation ───
    const handleStartVideoGeneration = () => {
        if (!scriptData) return
        const panels: PanelImage[] = scriptData.panels
            .filter(p => panelImages[p.id])
            .map((p, i) => ({
                index: i,
                url: panelImages[p.id],
                label: `分镜 ${p.id}`,
            }))

        if (panels.length === 0) return

        // Build per-panel duration map and structured metadata from script data
        const panelDurations: Record<number, number> = {}
        const panelMetas: Record<number, PanelMeta> = {}
        const panelsWithImages = scriptData.panels.filter(p => panelImages[p.id])
        panelsWithImages.forEach((p, i) => {
            if (p.duration_sec) panelDurations[i] = p.duration_sec
            panelMetas[i] = {
                camera_movement: p.camera_movement,
                composition: p.composition,
                scene_description: p.scene_description,
                time_of_day: p.time_of_day,
                weather: p.weather,
                duration_sec: p.duration_sec,
            }
        })

        const initialData: VideoCardData = {
            phase: 'select',
            panels,
            selectedIndices: panels.map(p => p.index),
            motionPrompt: scriptData.panels[0]?.camera_movement || '缓慢推进，镜头微微摇动',
            durationSec: 5,
            panelDurations: Object.keys(panelDurations).length > 0 ? panelDurations : undefined,
            panelMetas: Object.keys(panelMetas).length > 0 ? panelMetas : undefined,
            jobs: [],
        }
        videoCardDataRef.current = initialData

        const videoMsg: AgentMessage = {
            id: 'video-card-msg',
            role: 'assistant',
            content: `分镜首帧已就绪，共 **${panels.length}** 张。请选择要生成视频的分镜，调整参数后点击开始。`,
            timestamp: Date.now(),
            customContent: (
                <VideoCard
                    data={initialData}
                    projectId={projectId}
                    episodeNum={episodeNum}
                    onDataChange={handleVideoDataChange}
                    onCompose={handleCompose}
                />
            ),
        }
        setMessages(prev => [...prev, videoMsg])
        setPhase('video')
    }

    // ─── Handle user messages (route through refine or video) ───
    const handleSendMessage = async (content: string) => {
        const userMsg: AgentMessage = {
            id: Date.now().toString(),
            role: 'user',
            content,
            timestamp: Date.now(),
        }
        setMessages(prev => [...prev, userMsg])
        await saveMessage('user', content)

        // Conversational refinement (confirm / panels / video phases)
        if (scriptData && (phase === 'confirm' || phase === 'panels' || phase === 'video' || phase === 'done')) {
            // Compose intent shortcut
            if (isComposeIntent(content) && phase === 'done') {
                const data = videoCardDataRef.current
                if (data?.phase === 'done') {
                    const urls = data.jobs.filter(j => j.status === 'succeeded' && j.video_url).map(j => j.video_url!)
                    if (urls.length >= 2) {
                        handleCompose(urls)
                        return
                    }
                }
            }

            setIsTyping(true)
            try {
                const result = await refineEpisode(episodeNum, phase, content, {
                    art_style: scriptData.art_style,
                    characters: scriptData.characters,
                    scenes: scriptData.scenes,
                    panels: scriptData.panels,
                })

                // Display LLM reply
                const replyMsg: AgentMessage = {
                    id: 'refine-' + Date.now(),
                    role: 'assistant',
                    content: result.reply,
                    timestamp: Date.now(),
                }
                setMessages(prev => [...prev, replyMsg])
                await saveMessage('assistant', result.reply)

                // Apply updates
                if (result.updates) {
                    const updated = { ...scriptData }
                    if (result.updates.characters) {
                        for (const uc of result.updates.characters) {
                            const idx = updated.characters.findIndex(c => c.name === uc.name)
                            if (idx >= 0) updated.characters[idx] = { ...updated.characters[idx], ...uc }
                            else updated.characters.push(uc)
                        }
                    }
                    if (result.updates.scenes) {
                        for (const us of result.updates.scenes) {
                            const idx = updated.scenes.findIndex(s => s.name === us.name)
                            if (idx >= 0) updated.scenes[idx] = { ...updated.scenes[idx], ...us }
                            else updated.scenes.push(us)
                        }
                    }
                    if (result.updates.panels) {
                        for (const up of result.updates.panels) {
                            const idx = updated.panels.findIndex(p => p.id === up.id)
                            if (idx >= 0) updated.panels[idx] = { ...updated.panels[idx], ...up }
                        }
                    }
                    if (result.updates.art_style) {
                        updated.art_style = { ...updated.art_style, ...result.updates.art_style }
                    }
                    setScriptData(updated)

                    // Re-render script markdown
                    const updatedMarkdown = formatScriptAsMarkdown(updated, panelImages)
                    setMessages(prev => prev.map(m =>
                        m.id === 'script' ? { ...m, content: updatedMarkdown } : m
                    ))

                    // Persist
                    await saveMessage('assistant', '', {
                        type: 'episode_pipeline',
                        phase,
                        script_data: updated,
                        panel_images: panelImages,
                    })

                    // Notify about items needing image regeneration
                    const needsRegen = [
                        ...(result.updates.characters?.filter(c => c.regenerate_image) || []).map(c => c.name),
                        ...(result.updates.scenes?.filter(s => s.regenerate_image) || []).map(s => s.name),
                    ]
                    if (needsRegen.length > 0) {
                        const regenMsg: AgentMessage = {
                            id: 'regen-' + Date.now(),
                            role: 'assistant',
                            content: `已更新：${needsRegen.join('、')}。描述已修改，图片将在确认后重新生成。`,
                            timestamp: Date.now(),
                        }
                        setMessages(prev => [...prev, regenMsg])
                    }
                }
            } catch (e: any) {
                const errMsg: AgentMessage = {
                    id: 'refine-err-' + Date.now(),
                    role: 'assistant',
                    content: `处理失败：${e.message || '请重试'}`,
                    timestamp: Date.now(),
                }
                setMessages(prev => [...prev, errMsg])
            } finally {
                setIsTyping(false)
            }
            return
        }

        // Default: no scriptData yet, general reply
        setIsTyping(true)
        setTimeout(() => {
            const aiMsg: AgentMessage = {
                id: 'chat-' + Date.now(),
                role: 'assistant',
                content: '请等待剧本生成完成后再进行对话交流。',
                timestamp: Date.now(),
            }
            setMessages(prev => [...prev, aiMsg])
            setIsTyping(false)
        }, 500)
    }

    // ─── Render ───

    if (isLoading) {
        return (
            <div className="flex-1 h-full bg-[#000000] flex items-center justify-center">
                <div className="flex items-center gap-3 text-zinc-500 text-sm">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    <span>正在加载第{episodeNum}集...</span>
                </div>
            </div>
        )
    }

    return (
        <div className="flex-1 h-full bg-[#000000] flex overflow-hidden">
            {/* Episode Tree Sidebar */}
            <div className="w-[280px] shrink-0 h-full">
                <EpisodeTree
                    episodes={episodes}
                    selectedEpisode={currentEpisodeId}
                    selectedPhase={selectedPhaseId}
                    onSelectEpisode={handleSelectEpisode}
                    onSelectPhase={handleSelectPhase}
                    onAddEpisode={handleAddEpisode}
                />
            </div>

            {/* Right Column */}
            <div className="flex-1 flex flex-col overflow-hidden relative">
                {/* Phase anchor: script (top of page / stream progress region) */}
                <div id="phase-script" className="scroll-mt-20" />

                {/* Header */}
                <div className="absolute top-0 left-0 right-0 z-30 flex items-center gap-4 px-6 py-4 border-b border-zinc-800/50 bg-[#000000]/90 backdrop-blur-md opacity-0 hover:opacity-100 transition-opacity duration-300">
                    <Link
                        href={`/agent/${projectId}/episodes`}
                        className="p-2 rounded-lg hover:bg-zinc-800 transition-colors"
                    >
                        <ArrowLeft className="h-5 w-5 text-zinc-400" />
                    </Link>
                    <div>
                        <h1 className="text-lg font-semibold text-white">第{episodeNum}集</h1>
                        <p className="text-xs text-zinc-500">
                            {phase === 'script' && '正在生成剧本...'}
                            {phase === 'confirm' && '等待确认角色与场景'}
                            {phase === 'panels' && '正在生成分镜首帧'}
                            {phase === 'video' && '视频生成'}
                            {phase === 'done' && '全部完成'}
                        </p>
                    </div>
                    <div className="ml-auto flex items-center gap-2">
                        {/* Phase anchor: export (next to the 导出剧本 button) */}
                        <div id="phase-export" className="scroll-mt-20" />
                        {scriptData && (
                            <Button
                                onClick={handleOpenInStudio}
                                disabled={committing || (scriptData.panels?.length ?? 0) === 0}
                                size="sm"
                                className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs"
                                title={
                                    (scriptData.panels?.length ?? 0) === 0
                                        ? '暂无分镜，无法打开 Studio'
                                        : '将本集的剧本、角色、场景、分镜提交到 Studio'
                                }
                            >
                                {committing ? (
                                    <>
                                        <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                                        提交中…
                                    </>
                                ) : (
                                    <>
                                        <Play className="h-3.5 w-3.5 mr-1.5" />
                                        在 Studio 打开
                                    </>
                                )}
                            </Button>
                        )}
                        {(phase === 'video' || phase === 'done') && (
                            <Button variant="outline" size="sm" className="text-xs">
                                <FileText className="h-3.5 w-3.5 mr-1.5" />
                                导出剧本
                            </Button>
                        )}
                    </div>
                </div>

                {/* Chat */}
                <div className="flex-1 overflow-hidden">
                    <AgentChat
                        messages={messages}
                        onSendMessage={handleSendMessage}
                        onCardAction={() => {}}
                        isTyping={isTyping}
                    />
                </div>

                {/* Phase anchors: storyboard + assets (mapped to confirm action bar) */}
                <div id="phase-storyboard" className="scroll-mt-20" />
                <div id="phase-assets" className="scroll-mt-20" />

                {/* Phase Action Bar */}
                {phase === 'confirm' && !isTyping && (
                    <div className="flex items-center justify-center gap-3 px-6 py-3 border-t border-zinc-800/50 bg-zinc-900/80">
                        <Button
                            className="bg-emerald-600 hover:bg-emerald-700 text-white text-sm"
                            onClick={handleConfirmAssets}
                        >
                            <Sparkles className="h-4 w-4 mr-2" />
                            确认角色与场景，开始生成分镜首帧
                        </Button>
                    </div>
                )}

                {streamStatus === 'streaming' && phase === 'script' && (
                    <div className="px-6 py-3 border-t border-zinc-800/50 bg-zinc-900/80">
                        <div className="space-y-2 max-w-2xl mx-auto">
                            <div className="flex items-center justify-between text-sm">
                                <span className="text-zinc-300 flex items-center gap-2">
                                    <Loader2 className="h-3.5 w-3.5 animate-spin text-emerald-400" />
                                    {streamPhase === 'analyzing' ? '分析剧情...' :
                                     streamPhase === 'writing' ? '生成剧本...' :
                                     streamPhase === 'finalizing' ? '整理结果...' : '准备中...'}
                                </span>
                                <span className="text-zinc-500">{streamPct}%</span>
                            </div>
                            <div className="h-1.5 rounded bg-zinc-800 overflow-hidden">
                                <div
                                    className="h-full bg-emerald-500 transition-all"
                                    style={{ width: `${streamPct}%` }}
                                />
                            </div>
                        </div>
                    </div>
                )}

                {/* Phase anchors: render + qa (mapped to panels progress / video start region) */}
                <div id="phase-render" className="scroll-mt-20" />
                <div id="phase-qa" className="scroll-mt-20" />

                {phase === 'panels' && panelProgress && (
                    <div className="flex items-center justify-center gap-3 px-6 py-3 border-t border-zinc-800/50 bg-zinc-900/80">
                        <Loader2 className="h-4 w-4 animate-spin text-emerald-400" />
                        <span className="text-sm text-zinc-400">
                            正在生成分镜首帧 ({panelProgress.done}/{panelProgress.total})
                        </span>
                    </div>
                )}

                {(phase === 'video') && !isTyping && !panelProgress && Object.keys(panelImages).length > 0 && (
                    <div className="flex items-center justify-center gap-3 px-6 py-3 border-t border-zinc-800/50 bg-zinc-900/80">
                        <Button
                            className="bg-emerald-600 hover:bg-emerald-700 text-white text-sm"
                            onClick={handleStartVideoGeneration}
                        >
                            <Film className="h-4 w-4 mr-2" />
                            生成全部视频
                        </Button>
                    </div>
                )}

                {streamError && !isTyping && (phase === 'script' || phase === 'loading') && (
                    <div className="px-6 py-3 border-t border-zinc-800/50 bg-zinc-900/60">
                        <PhaseErrorBanner
                            phase="剧本"
                            message={streamError}
                            onRetry={() => {
                                setGenerationError(null)
                                handleGenerateScript()
                            }}
                        />
                    </div>
                )}

                {generationError && !isTyping && phase === 'panels' && (
                    <div className="px-6 py-3 border-t border-zinc-800/50 bg-zinc-900/60">
                        <PhaseErrorBanner
                            phase="分镜生成"
                            message={generationError}
                            onRetry={() => {
                                setGenerationError(null)
                                handleConfirmAssets()
                            }}
                            onSkip={() => setGenerationError(null)}
                        />
                    </div>
                )}

                {generationError && !isTyping && phase !== 'panels' && phase !== 'script' && phase !== 'loading' && (
                    <div className="px-6 py-3 border-t border-zinc-800/50 bg-zinc-900/60">
                        <PhaseErrorBanner
                            phase="生成"
                            message={generationError}
                            onRetry={() => {
                                setGenerationError(null)
                                if (phase === 'confirm') handleConfirmAssets()
                            }}
                            onSkip={() => setGenerationError(null)}
                        />
                    </div>
                )}
            </div>
        </div>
    )
}
