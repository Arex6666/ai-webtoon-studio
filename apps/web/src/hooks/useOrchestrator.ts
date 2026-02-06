import { useState, useCallback, useRef } from 'react'
import { orchestratorApi } from '@/lib/api/orchestrator'
import { Message, AgentMode } from '@/components/studio/chat/DirectorChat'
import { useToast } from '@/components/ui/use-toast'

interface UseOrchestratorProps {
    projectId: string
    sessionId: string
}

export function useOrchestrator({ projectId, sessionId }: UseOrchestratorProps) {
    const [messages, setMessages] = useState<Message[]>([])
    const [isTyping, setIsTyping] = useState(false)
    const [sessionState, setSessionState] = useState<any>(null)
    const [currentMode, setCurrentMode] = useState<AgentMode>('director')
    const { toast } = useToast()

    // AbortController for stream cancellation if needed
    const abortControllerRef = useRef<AbortController | null>(null)

    const refreshStatus = useCallback(async () => {
        try {
            const status = await orchestratorApi.getSessionStatus(sessionId, projectId)
            setSessionState(status)
            // Update mode based on stage if applicable
            // e.g. status.stage === 'scripting' -> 'scriptwriter'
        } catch (e) {
            console.error("Failed to refresh status", e)
        }
    }, [sessionId, projectId])

    const sendMessage = useCallback(async (content: string) => {
        // Optimistic User Message
        const userMsg: Message = {
            id: Date.now().toString(),
            role: 'user',
            content,
            timestamp: Date.now()
        }
        setMessages(prev => [...prev, userMsg])
        setIsTyping(true)

        try {
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/orchestrator/chat/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: content,
                    session_id: sessionId,
                    project_id: projectId
                })
            })

            if (!response.ok || !response.body) {
                throw new Error('Network response was not ok')
            }

            const reader = response.body.getReader()
            const decoder = new TextDecoder()
            let aiMsgId = (Date.now() + 1).toString()
            let aiContent = ""

            // Initial AI Message placeholder
            setMessages(prev => [...prev, {
                id: aiMsgId,
                role: 'assistant',
                content: '',
                timestamp: Date.now(),
                mode: currentMode
            }])

            while (true) {
                const { value, done } = await reader.read()
                if (done) break

                const chunk = decoder.decode(value)
                const lines = chunk.split('\n\n')

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6)
                        if (data === '[DONE]') {
                            setIsTyping(false)
                            refreshStatus() // Refresh state after turn
                            break
                        }
                        aiContent += data

                        // Update the last message
                        setMessages(prev => prev.map(msg =>
                            msg.id === aiMsgId ? { ...msg, content: aiContent } : msg
                        ))
                    }
                }
            }

        } catch (error) {
            console.error('Chat error:', error)
            setIsTyping(false)
            toast({
                title: "发送失败",
                description: "无法连接到智能体服务",
                variant: "destructive"
            })
        }
    }, [sessionId, projectId, currentMode, toast, refreshStatus])

    // Handlers for specific actions
    const createStoryboard = async (prompt: string) => {
        try {
            const res = await orchestratorApi.createStoryboard(sessionId, projectId, prompt)
            if (res.success) {
                refreshStatus()
                return res.data
            } else {
                throw new Error(res.message)
            }
        } catch (e: any) {
            toast({ title: "创建失败", description: e.message, variant: "destructive" })
        }
    }

    return {
        messages,
        isTyping,
        sendMessage,
        sessionState,
        refreshStatus,
        currentMode,
        actions: {
            createStoryboard
        }
    }
}
