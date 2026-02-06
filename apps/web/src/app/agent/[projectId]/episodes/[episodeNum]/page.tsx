'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { Loader2, ArrowLeft, FileText } from 'lucide-react'
import Link from 'next/link'

import { AgentChat, AgentMessage } from '@/components/agent/AgentChat'
import { conversationsApi } from '@/lib/api'
import { env } from '@/lib/utils/env'
import { Button } from '@/components/ui/button'

export default function EpisodeConversationPage() {
    const params = useParams()
    const router = useRouter()
    const projectId = params.projectId as string
    const episodeNum = parseInt(params.episodeNum as string)

    const [messages, setMessages] = useState<AgentMessage[]>([])
    const [isTyping, setIsTyping] = useState(false)
    const [conversationId, setConversationId] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [outlineContext, setOutlineContext] = useState<string>('')
    const [scriptGenerated, setScriptGenerated] = useState(false)

    const loadStartedRef = useRef(false)
    const hasAutoTriggered = useRef(false)

    // 加载对话历史和上下文
    useEffect(() => {
        if (loadStartedRef.current) return
        loadStartedRef.current = true

        const loadEpisodeConversation = async () => {
            try {
                console.log(`[Episode ${episodeNum}] Loading conversation...`)

                // 1. 从主对话获取大纲上下文
                const conversations = await conversationsApi.listByProject(projectId, 20, 0)

                if (conversations && conversations.length > 0) {
                    // 找到主对话（没有 episode_number 且消息最多的）
                    const mainConvs = conversations.filter(c => !c.episode_number)
                    if (mainConvs.length > 0) {
                        const mainConv = mainConvs.reduce((best, conv) =>
                            (conv.message_count > best.message_count) ? conv : best
                            , mainConvs[0])

                        // 获取主对话消息作为上下文
                        const mainMessages = await conversationsApi.getMessages(mainConv.id, 100, 0)

                        // 提取大纲内容
                        const outlineMsg = mainMessages?.find(m => m.entities_json?.card?.type === 'outline')
                        if (outlineMsg) {
                            setOutlineContext(outlineMsg.content)
                        }
                    }
                }

                // 2. 获取或创建分集对话（持久化）
                const episodeConv = await conversationsApi.getOrCreateEpisode(projectId, episodeNum)
                setConversationId(episodeConv.id)
                console.log(`[Episode ${episodeNum}] Got episode conversation:`, episodeConv.id,
                    `(${episodeConv.message_count} messages)`)

                // 3. 加载分集对话的历史消息
                if (episodeConv.message_count > 0) {
                    const episodeMessages = await conversationsApi.getMessages(episodeConv.id, 100, 0)
                    if (episodeMessages && episodeMessages.length > 0) {
                        console.log(`[Episode ${episodeNum}] Loading ${episodeMessages.length} history messages`)

                        // 转换为 AgentMessage 格式
                        const historyMessages: AgentMessage[] = episodeMessages.map((msg, idx) => ({
                            id: msg.id || `history-${idx}`,
                            role: msg.role as 'user' | 'assistant' | 'system',
                            content: msg.content,
                            timestamp: new Date(msg.created_at).getTime(),
                            card: msg.entities_json?.card,
                        }))

                        setMessages(historyMessages)

                        // 如果历史中已有剧本，标记为已生成
                        const hasScript = historyMessages.some(m =>
                            m.card?.type === 'script' || m.content.includes('分镜')
                        )
                        if (hasScript) {
                            setScriptGenerated(true)
                            hasAutoTriggered.current = true
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

    // 保存消息
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

    // 自动触发剧本生成
    useEffect(() => {
        if (
            !hasAutoTriggered.current &&
            !isLoading &&
            conversationId &&
            outlineContext &&
            messages.length === 0
        ) {
            hasAutoTriggered.current = true
            handleGenerateScript()
        }
    }, [isLoading, conversationId, outlineContext, messages.length])

    // 生成完整剧本
    const handleGenerateScript = async () => {
        const welcomeMsg: AgentMessage = {
            id: 'welcome',
            role: 'assistant',
            content: `你好！我是 **Arex**。现在让我为你创作**第${episodeNum}集**的完整分镜剧本...\n\n正在分析大纲内容，生成故事梗概、剧本亮点、美术风格、角色设定、场景列表和详细分镜...`,
            timestamp: Date.now(),
        }
        setMessages([welcomeMsg])
        await saveMessage('assistant', welcomeMsg.content)

        setIsTyping(true)

        try {
            // 调用后端生成完整剧本
            const resp = await fetch(`${env.API_BASE_URL}/api/v1/agent/episode/${episodeNum}/script`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project_id: projectId,
                    episode_number: episodeNum,
                    outline_text: outlineContext,
                }),
            })

            if (!resp.ok) {
                const errData = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }))
                const errorMsg: AgentMessage = {
                    id: 'error',
                    role: 'assistant',
                    content: `抱歉，剧本生成失败：${errData.detail || resp.statusText}\n\n请检查后端服务是否正常运行，然后重试。`,
                    timestamp: Date.now(),
                }
                setMessages(prev => [...prev, errorMsg])
                return
            }

            const data = await resp.json()
            displayScriptResult(data)
        } catch (e) {
            const errorMsg: AgentMessage = {
                id: 'error',
                role: 'assistant',
                content: `抱歉，无法连接到后端服务：${e instanceof Error ? e.message : '网络错误'}\n\n请确保 API 服务 (端口 8000) 已启动。`,
                timestamp: Date.now(),
            }
            setMessages(prev => [...prev, errorMsg])
        } finally {
            setIsTyping(false)
        }
    }

    // 显示剧本结果
    function displayScriptResult(script: any) {
        const scriptContent = formatScriptAsMarkdown(script)

        const scriptMsg: AgentMessage = {
            id: 'script',
            role: 'assistant',
            content: scriptContent,
            timestamp: Date.now(),
        }

        setMessages(prev => [...prev, scriptMsg])
        saveMessage('assistant', scriptContent, { type: 'episode_script', episode: episodeNum })
        setScriptGenerated(true)
    }

    // 将剧本格式化为 Markdown
    function formatScriptAsMarkdown(script: any): string {
        const title = script.episode_title || `第${episodeNum}集`
        const summary = script.story_summary || '暂无梗概'
        const artStyle = script.art_style || {}

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
                // 显示生成的角色图片
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
                // 显示生成的场景图片
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
                const sceneDesc = p.scene_description || p.scene || ''
                const cameraMove = p.camera_movement || p.camera || ''
                const voiceChar = p.voice_character || p.voice || ''

                md += `| 属性 | 内容 |\n|------|------|\n`
                md += `| **画面描述** | ${sceneDesc} |\n`
                md += `| **构图设计** | ${p.composition || ''} |\n`
                md += `| **运镜调度** | ${cameraMove} |\n`
                md += `| **配音角色** | ${voiceChar} |\n`
                md += `| **台词内容** | ${p.dialogue || ''} |\n\n`
            })
        }

        return md
    }

    const handleSendMessage = async (content: string) => {
        const userMsg: AgentMessage = {
            id: Date.now().toString(),
            role: 'user',
            content,
            timestamp: Date.now(),
        }
        setMessages(prev => [...prev, userMsg])
        await saveMessage('user', content)

        setIsTyping(true)

        try {
            // 调用后端对话 API
            const resp = await fetch(`${env.API_BASE_URL}/api/v1/conversations/${conversationId}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: content,
                    context: { episode_number: episodeNum, project_id: projectId },
                }),
            })

            let aiContent: string
            if (resp.ok) {
                const data = await resp.json()
                aiContent = data.response || data.content || data.message || '收到你的反馈，我会进行调整。'
            } else {
                aiContent = '抱歉，处理您的消息时出现问题。请稍后再试。'
            }

            const aiMsg: AgentMessage = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: aiContent,
                timestamp: Date.now(),
            }
            setMessages(prev => [...prev, aiMsg])
            await saveMessage('assistant', aiContent)
        } catch (e) {
            const aiMsg: AgentMessage = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: `抱歉，无法连接到后端服务。请检查 API 是否正常运行。`,
                timestamp: Date.now(),
            }
            setMessages(prev => [...prev, aiMsg])
        } finally {
            setIsTyping(false)
        }
    }

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
        <div className="flex-1 h-full bg-[#000000] flex flex-col overflow-hidden">
            {/* Header */}
            <div className="flex items-center gap-4 px-6 py-4 border-b border-zinc-800/50">
                <Link
                    href={`/agent/${projectId}/episodes`}
                    className="p-2 rounded-lg hover:bg-zinc-800 transition-colors"
                >
                    <ArrowLeft className="h-5 w-5 text-zinc-400" />
                </Link>
                <div>
                    <h1 className="text-lg font-semibold text-white">第{episodeNum}集</h1>
                    <p className="text-xs text-zinc-500">剧本创作对话</p>
                </div>
                {scriptGenerated && (
                    <div className="ml-auto flex gap-2">
                        <Button variant="outline" size="sm" className="text-xs">
                            <FileText className="h-3.5 w-3.5 mr-1.5" />
                            导出剧本
                        </Button>
                    </div>
                )}
            </div>

            {/* Chat */}
            <div className="flex-1 overflow-hidden">
                <AgentChat
                    messages={messages}
                    onSendMessage={handleSendMessage}
                    onCardAction={() => { }}
                    isTyping={isTyping}
                />
            </div>
        </div>
    )
}
