'use client'

import { useMemo, useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import { Check, Sparkles, Loader2 } from 'lucide-react'

import { AgentChat, AgentMessage } from '@/components/agent/AgentChat'
import { chaptersApi, apiPost, conversationsApi } from '@/lib/api'
import { env } from '@/lib/utils/env'

type AgentPhase = 'outline' | 'episode1_script'

export default function AgentWorkspacePage() {
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()
  const projectId = params.projectId as string

  // Get initial prompt from URL query params
  const initialPrompt = searchParams.get('prompt')
  const initialTemplate = searchParams.get('template')
  const initialMultiEpisode = searchParams.get('multi_episode') === 'true'

  const [messages, setMessages] = useState<AgentMessage[]>([])
  const [isTyping, setIsTyping] = useState(false)
  const [phase, setPhase] = useState<AgentPhase>('outline')
  const [outlineText, setOutlineText] = useState<string | null>(null)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [isLoadingHistory, setIsLoadingHistory] = useState(true)

  // Refs to prevent duplicate executions
  const loadStartedRef = useRef(false)
  const hasAutoTriggered = useRef(false)

  const outlineCardId = useMemo(() => 'outline_card', [])

  // Load existing conversation history on mount
  useEffect(() => {
    // Prevent duplicate execution (React Strict Mode runs useEffect twice)
    if (loadStartedRef.current) {
      console.log('[Agent] Skipping duplicate load')
      return
    }
    loadStartedRef.current = true

    const loadConversationHistory = async () => {
      try {
        console.log('[Agent] Loading conversation history for project:', projectId)

        // Get ALL conversations for this project (not just 1)
        const conversations = await conversationsApi.listByProject(projectId, 20, 0)
        console.log('[Agent] Found conversations:', conversations?.length || 0)

        if (conversations && conversations.length > 0) {
          // Select the conversation with most messages (it's the "real" one)
          const bestConv = conversations.reduce((best, conv) =>
            (conv.message_count > best.message_count) ? conv : best
            , conversations[0])

          setConversationId(bestConv.id)
          console.log('[Agent] Using conversation with most messages:', bestConv.id, 'msgs:', bestConv.message_count)

          // Load messages from the best conversation
          if (bestConv.message_count > 0) {
            const existingMessages = await conversationsApi.getMessages(bestConv.id, 100, 0)
            console.log('[Agent] Loaded messages:', existingMessages?.length || 0)

            if (existingMessages && existingMessages.length > 0) {
              // Convert backend messages to frontend format
              const loadedMessages: AgentMessage[] = existingMessages.map(msg => {
                // Try to restore card info from entities_json
                let entities = msg.entities_json
                if (typeof entities === 'string') {
                  try {
                    entities = JSON.parse(entities)
                  } catch (e) {
                    console.error('[Agent] Failed to parse entities_json:', e)
                    entities = {}
                  }
                }

                const cardData = entities?.card

                if (msg.role === 'assistant' && entities) {
                  console.log('[Agent] Message entities:', msg.id, entities)
                }

                let card: AgentMessage['card'] = undefined

                if (cardData && cardData.type === 'outline') {
                  card = {
                    id: cardData.id,
                    type: 'outline' as any,
                    title: cardData.title,
                    description: cardData.description,
                    actions: [
                      { id: 'confirm_outline', label: '确认大纲', icon: Check, variant: 'primary' },
                      { id: 'refine_outline', label: '继续完善', icon: Sparkles, variant: 'secondary' },
                    ],
                  }
                }

                return {
                  id: msg.id,
                  role: msg.role,
                  content: msg.content,
                  timestamp: new Date(msg.created_at).getTime(),
                  card,
                }
              })

              setMessages(loadedMessages)
              console.log('[Agent] Set messages:', loadedMessages.length)

              // Check if we have an outline in history
              const outlineMsg = loadedMessages.find(m => m.card?.type === 'outline')
              if (outlineMsg) {
                setOutlineText(outlineMsg.content)
                console.log('[Agent] Found existing outline')
              }
            }
          }
        } else {
          // Create a new conversation for this project
          console.log('[Agent] Creating new conversation for project:', projectId)
          const newConv = await conversationsApi.create({
            project_id: projectId,
            title: 'Agent 对话',
          })
          setConversationId(newConv.id)
          console.log('[Agent] Created new conversation:', newConv.id)
        }
      } catch (error) {
        console.error('[Agent] Failed to load conversation history:', error)
        // Create a new conversation on error
        try {
          const newConv = await conversationsApi.create({
            project_id: projectId,
            title: 'Agent 对话',
          })
          setConversationId(newConv.id)
        } catch (e) {
          console.error('[Agent] Failed to create conversation:', e)
        }
      } finally {
        setIsLoadingHistory(false)
      }
    }

    loadConversationHistory()
  }, [projectId])

  // Helper function to save message to backend
  const saveMessage = useCallback(async (
    role: 'user' | 'assistant' | 'system',
    content: string,
    metadata?: Record<string, any>
  ) => {
    if (!conversationId) {
      console.warn('[Agent] No conversation ID, cannot save message')
      return
    }

    try {
      console.log('[Agent] Saving message:', { role, content: content.substring(0, 50) + '...' })
      await conversationsApi.saveMessage(conversationId, role, content, metadata)
      console.log('[Agent] Message saved successfully')
    } catch (error) {
      console.error('[Agent] Failed to save message:', error)
    }
  }, [conversationId])

  // Generate outline function
  const handleGenerateOutline = useCallback(async (prompt: string, template: string | null, multiEpisode: boolean) => {
    const userMsg: AgentMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: prompt,
      timestamp: Date.now(),
    }
    setMessages(prev => [...prev, userMsg])

    // Save user message to backend
    await saveMessage('user', prompt)

    setIsTyping(true)

    try {
      const resp = await fetch(`${env.API_BASE_URL}/api/v1/agent/outline`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: prompt,
          template: template,
          multi_episode: multiEpisode,
        }),
      })

      if (!resp.ok) {
        throw new Error(await resp.text())
      }

      const data: { title: string; outlineText: string } = await resp.json()
      setOutlineText(data.outlineText)

      // Card data for persistence (without React components)
      const cardMetadata = {
        card: {
          id: outlineCardId,
          type: 'outline',
          title: data.title || '策划剧本大纲',
          description: '包含基础信息、角色设定、情节概要（可继续迭代）',
        }
      }

      const aiMsg: AgentMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.outlineText,
        timestamp: Date.now(),
        card: {
          id: outlineCardId,
          type: 'outline' as any,
          title: data.title || '策划剧本大纲',
          description: '包含基础信息、角色设定、情节概要（可继续迭代）',
          actions: [
            { id: 'confirm_outline', label: '确认大纲', icon: Check, variant: 'primary' },
            { id: 'refine_outline', label: '继续完善', icon: Sparkles, variant: 'secondary' },
          ],
        },
      }
      setMessages(prev => [...prev, aiMsg])

      // Save assistant message with card metadata
      await saveMessage('assistant', data.outlineText, cardMetadata)
    } catch (e) {
      const errorContent = `❌ 生成失败：${e instanceof Error ? e.message : String(e)}`
      setMessages(prev => [
        ...prev,
        {
          id: Date.now().toString(),
          role: 'system',
          content: errorContent,
          timestamp: Date.now(),
        },
      ])
      await saveMessage('system', errorContent)
    } finally {
      setIsTyping(false)
    }
  }, [saveMessage, outlineCardId])

  // Auto-trigger outline generation when page loads with an initial prompt
  useEffect(() => {
    // Only auto-trigger if:
    // 1. We have an initial prompt
    // 2. Haven't auto-triggered yet
    // 3. No existing messages (empty conversation)
    // 4. Finished loading history
    // 5. Have a conversation ID
    if (
      initialPrompt &&
      !hasAutoTriggered.current &&
      messages.length === 0 &&
      !isLoadingHistory &&
      conversationId
    ) {
      hasAutoTriggered.current = true
      console.log('[Agent] Auto-triggering outline generation')

      // Add welcome message first
      const welcomeMsg: AgentMessage = {
        id: 'welcome',
        role: 'assistant',
        content: '你好！我是 **Arex**，你的 AI 漫剧策划助手。让我根据你的创意来生成策划大纲...',
        timestamp: Date.now(),
      }
      setMessages([welcomeMsg])
      saveMessage('assistant', welcomeMsg.content)

      // Then trigger the outline generation
      setTimeout(() => {
        handleGenerateOutline(initialPrompt, initialTemplate, initialMultiEpisode)
      }, 500)
    }
  }, [initialPrompt, initialTemplate, initialMultiEpisode, isLoadingHistory, messages.length, conversationId, saveMessage, handleGenerateOutline])

  const handleSendMessage = async (content: string) => {
    console.log('[Agent] handleSendMessage called with:', content)
    console.log('[Agent] Current outlineText state:', outlineText ? `Length: ${outlineText.length}` : 'null')
    console.log('[Agent] Current messages count:', messages.length)

    // 如果已有大纲，使用 LLM 检测用户意图
    if (outlineText) {
      // 先添加用户消息到聊天
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
        // 调用 LLM 意图识别 API
        const intentResp = await fetch(`${env.API_BASE_URL}/api/v1/agent/intent`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_message: content,
            has_outline: true,
            conversation_context: messages.slice(-5).map(m => ({
              role: m.role,
              content: m.content.substring(0, 300)
            }))
          }),
        })

        if (intentResp.ok) {
          const { intent, confidence, reason } = await intentResp.json()
          console.log(`[Agent] LLM detected intent: ${intent} (confidence: ${confidence}, reason: ${reason})`)

          if (intent === 'confirm_outline' && confidence >= 0.6) {
            // 用户确认大纲
            await handleCardAction(outlineCardId, 'confirm_outline')
            return
          } else if (intent === 'refine_with_input' && confidence >= 0.5) {
            // 用户提供了具体修改方向，直接调用优化 API
            try {
              const refineResp = await fetch(`${env.API_BASE_URL}/api/v1/agent/refine-outline`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  original_outline: outlineText,
                  user_refinement: content,
                }),
              })

              if (refineResp.ok) {
                const { title, outlineText: newOutlineText, changes_summary } = await refineResp.json()

                // 更新大纲状态
                setOutlineText(newOutlineText)

                // 添加优化后的大纲卡片
                const cardMetadata = {
                  card: {
                    id: outlineCardId,
                    type: 'outline',
                    title: title || '策划剧本大纲（已优化）',
                    description: changes_summary,
                  }
                }

                const refinedMsg: AgentMessage = {
                  id: (Date.now() + 1).toString(),
                  role: 'assistant',
                  content: newOutlineText,
                  timestamp: Date.now(),
                  card: {
                    id: outlineCardId,
                    type: 'outline' as any,
                    title: title || '策划剧本大纲（已优化）',
                    description: changes_summary,
                    actions: [
                      { id: 'confirm_outline', label: '确认大纲', icon: Check, variant: 'primary' },
                      { id: 'refine_outline', label: '继续完善', icon: Sparkles, variant: 'secondary' },
                    ],
                  },
                }
                setMessages(prev => [...prev, refinedMsg])
                await saveMessage('assistant', newOutlineText, cardMetadata)
              } else {
                throw new Error('Refine API failed')
              }
            } catch (refineError) {
              console.error('[Agent] Refine outline failed:', refineError)
              const errorContent = '抱歉，优化大纲时出错了，请再试一次。'
              const errorMsg: AgentMessage = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: errorContent,
                timestamp: Date.now(),
              }
              setMessages(prev => [...prev, errorMsg])
              await saveMessage('assistant', errorContent)
            }
            setIsTyping(false)
            return
          } else if (intent === 'refine_outline' && confidence >= 0.5) {
            // 用户想修改但没说具体怎么改，询问方向
            const askContent = '好的，我们继续完善大纲。你希望重点优化：题材风格、角色关系、每集梗概，还是美术风格与镜头语言？'
            const askMsg: AgentMessage = {
              id: (Date.now() + 1).toString(),
              role: 'assistant',
              content: askContent,
              timestamp: Date.now(),
            }
            setMessages(prev => [...prev, askMsg])
            await saveMessage('assistant', askContent)
            setIsTyping(false)
            return
          } else if (intent === 'new_topic') {
            // 用户想重新开始
            const newTopicContent = '好的，让我们重新开始！请告诉我你新的创意想法。'
            const newTopicMsg: AgentMessage = {
              id: (Date.now() + 1).toString(),
              role: 'assistant',
              content: newTopicContent,
              timestamp: Date.now(),
            }
            setMessages(prev => [...prev, newTopicMsg])
            await saveMessage('assistant', newTopicContent)
            setOutlineText('')
            setPhase('outline')
            setIsTyping(false)
            return
          }
        }

        // 如果意图不明确或 API 失败，询问用户
        const clarifyContent = `我理解你的意思了。关于当前的大纲，你是想：\n\n1. **确认大纲** - 直接进入分集创作\n2. **继续完善** - 根据你的想法调整内容\n\n请告诉我你的选择~`
        const clarifyMsg: AgentMessage = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: clarifyContent,
          timestamp: Date.now(),
        }
        setMessages(prev => [...prev, clarifyMsg])
        await saveMessage('assistant', clarifyContent)

      } catch (e) {
        console.error('[Agent] Intent detection failed:', e)
        // 回退到简单响应
        const fallbackContent = `收到！你是想确认这份大纲，还是想继续完善？`
        const fallbackMsg: AgentMessage = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: fallbackContent,
          timestamp: Date.now(),
        }
        setMessages(prev => [...prev, fallbackMsg])
        await saveMessage('assistant', fallbackContent)
      } finally {
        setIsTyping(false)
      }
      return
    }

    // 没有大纲时，生成新大纲
    if (phase === 'outline') {
      await handleGenerateOutline(content, null, false)
    } else {
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
        const aiContent = '我已进入「第1集剧本」阶段。请补充你希望的节奏、分镜数量、旁白音色或任何细节，我会据此继续生成与优化。'
        const aiMsg: AgentMessage = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: aiContent,
          timestamp: Date.now(),
        }
        setMessages(prev => [...prev, aiMsg])
        await saveMessage('assistant', aiContent)
      } catch (e) {
        const errorContent = `❌ 生成失败：${e instanceof Error ? e.message : String(e)}`
        setMessages(prev => [
          ...prev,
          {
            id: Date.now().toString(),
            role: 'system',
            content: errorContent,
            timestamp: Date.now(),
          },
        ])
        await saveMessage('system', errorContent)
      } finally {
        setIsTyping(false)
      }
    }
  }

  const handleCardAction = async (cardId: string, actionId: string) => {
    if (cardId === outlineCardId && actionId === 'confirm_outline') {
      if (!outlineText) return

      setIsTyping(true)
      try {
        // 基于大纲为项目命名
        try {
          await apiPost(`/api/v1/projects/${projectId}/auto-name`, {
            outline_text: outlineText,
          })
        } catch {
          // 命名失败不阻断主流程
        }

        const successContent = '✅ 大纲已确认！即将进入分集创作页面，你可以选择任意一集开始详细剧本创作...'
        setMessages(prev => [
          ...prev,
          {
            id: Date.now().toString(),
            role: 'system',
            content: successContent,
            timestamp: Date.now(),
          },
        ])
        await saveMessage('system', successContent)

        // 跳转到分集选择页面（Agent 模式，不跳转到工作台）
        setTimeout(() => {
          router.push(`/agent/${projectId}/episodes`)
        }, 1500)

      } catch (e) {
        const errorContent = `❌ 操作失败：${e instanceof Error ? e.message : String(e)}`
        setMessages(prev => [
          ...prev,
          {
            id: Date.now().toString(),
            role: 'system',
            content: errorContent,
            timestamp: Date.now(),
          },
        ])
        await saveMessage('system', errorContent)
      } finally {
        setIsTyping(false)
      }

      return
    }


    if (cardId === outlineCardId && actionId === 'refine_outline') {
      const refineContent = '好的，我们继续完善策划大纲。你希望重点优化：题材风格、角色关系、每集梗概，还是美术风格与镜头语言？'
      setMessages(prev => [
        ...prev,
        {
          id: Date.now().toString(),
          role: 'assistant',
          content: refineContent,
          timestamp: Date.now(),
        },
      ])
      await saveMessage('assistant', refineContent)
      return
    }
  }

  // 删除消息
  const handleDeleteMessage = async (messageId: string) => {
    console.log('[Agent] Deleting message:', messageId)

    // 乐观更新：立即从UI移除
    setMessages(prev => prev.filter(msg => msg.id !== messageId))

    try {
      // 调用后端 API 持久化删除
      await conversationsApi.deleteMessage(messageId)
    } catch (e) {
      console.error('[Agent] Failed to delete message:', e)
      // 如果需要，可以在这里处理恢复逻辑，但为保持体验流畅暂不自动恢复
    }
  }

  // Show loading state while fetching history
  if (isLoadingHistory) {
    return (
      <div className="flex-1 h-full bg-[#000000] flex items-center justify-center">
        <div className="flex items-center gap-3 text-zinc-500 text-sm">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span>加载对话历史...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 h-full bg-[#000000] overflow-hidden">
      {/* GlobalNav is provided by AppShell, no need to render again */}
      <AgentChat
        messages={messages}
        onSendMessage={handleSendMessage}
        onCardAction={handleCardAction}
        onDeleteMessage={handleDeleteMessage}
        isTyping={isTyping}
        showEpisodesButton={!!outlineText}
        onGoToEpisodes={() => router.push(`/agent/${projectId}/episodes`)}
      />
    </div>
  )
}
