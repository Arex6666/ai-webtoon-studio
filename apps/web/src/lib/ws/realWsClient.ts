/**
 * Real WebSocket Client - 真实 WebSocket 连接
 * 连接到后端 /api/v1/ws/jobs 端点
 */

import { WsEvent } from './events'

type EventHandler = (event: WsEvent) => void

interface ReconnectConfig {
    maxRetries: number
    baseDelay: number
    maxDelay: number
}

const DEFAULT_RECONNECT: ReconnectConfig = {
    maxRetries: 10,
    baseDelay: 1000,
    maxDelay: 30000,
}

export class RealWsClient {
    private ws: WebSocket | null = null
    private url: string
    private chapterId: string | null = null
    private eventHandler: EventHandler | null = null

    private reconnectAttempts = 0
    private reconnectConfig: ReconnectConfig
    private heartbeatInterval: ReturnType<typeof setInterval> | null = null
    private reconnectTimeout: ReturnType<typeof setTimeout> | null = null

    private isConnecting = false
    private isIntentionallyClosed = false

    constructor(baseUrl?: string, reconnectConfig?: Partial<ReconnectConfig>) {
        // 构建 WebSocket URL
        const apiUrl = baseUrl || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        this.url = apiUrl.replace(/^http/, 'ws')
        this.reconnectConfig = { ...DEFAULT_RECONNECT, ...reconnectConfig }
    }

    /**
     * 连接到 WebSocket 服务
     */
    connect(chapterId?: string, onEvent?: EventHandler): void {
        if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
            console.log('[RealWS] Already connected or connecting')
            return
        }

        this.isConnecting = true
        this.isIntentionallyClosed = false
        this.chapterId = chapterId || null
        this.eventHandler = onEvent || null

        const wsUrl = this.chapterId
            ? `${this.url}/api/v1/ws/jobs?chapter_id=${this.chapterId}`
            : `${this.url}/api/v1/ws/jobs`

        console.log(`[RealWS] Connecting to ${wsUrl}`)

        try {
            this.ws = new WebSocket(wsUrl)

            this.ws.onopen = this.handleOpen.bind(this)
            this.ws.onmessage = this.handleMessage.bind(this)
            this.ws.onerror = this.handleError.bind(this)
            this.ws.onclose = this.handleClose.bind(this)
        } catch (error) {
            console.error('[RealWS] Connection error:', error)
            this.isConnecting = false
            this.scheduleReconnect()
        }
    }

    /**
     * 订阅特定章节
     */
    subscribeChapter(chapterId: string, onEvent: EventHandler): () => void {
        this.chapterId = chapterId
        this.eventHandler = onEvent

        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            // 发送订阅消息
            this.ws.send(JSON.stringify({
                type: 'subscribe',
                chapter_id: chapterId,
            }))
        } else {
            // 重新连接
            this.connect(chapterId, onEvent)
        }

        // 返回取消订阅函数
        return () => {
            this.eventHandler = null
        }
    }

    /**
     * 断开连接
     */
    disconnect(): void {
        this.isIntentionallyClosed = true
        this.stopHeartbeat()
        this.clearReconnectTimeout()

        if (this.ws) {
            this.ws.close()
            this.ws = null
        }

        this.eventHandler = null
        this.chapterId = null
        this.reconnectAttempts = 0
        console.log('[RealWS] Disconnected')
    }

    /**
     * 获取连接状态
     */
    isConnected(): boolean {
        return this.ws !== null && this.ws.readyState === WebSocket.OPEN
    }

    // === Private Methods ===

    private handleOpen(): void {
        console.log('[RealWS] Connected')
        this.isConnecting = false
        this.reconnectAttempts = 0
        this.startHeartbeat()

        // 如果有 chapterId，发送订阅
        if (this.chapterId) {
            this.ws?.send(JSON.stringify({
                type: 'subscribe',
                chapter_id: this.chapterId,
            }))
        }
    }

    private handleMessage(event: MessageEvent): void {
        try {
            const data = JSON.parse(event.data)

            // 处理 pong 心跳响应
            if (data.type === 'pong') {
                return
            }

            // 处理订阅确认
            if (data.type === 'subscribed') {
                console.log(`[RealWS] Subscribed to chapter: ${data.chapter_id}`)
                return
            }

            // 转发事件到处理器
            if (this.eventHandler) {
                const wsEvent = this.transformToWsEvent(data)
                if (wsEvent) {
                    this.eventHandler(wsEvent)
                }
            }
        } catch (error) {
            console.error('[RealWS] Failed to parse message:', error)
        }
    }

    private handleError(error: Event): void {
        console.error('[RealWS] Error:', error)
        this.isConnecting = false
    }

    private handleClose(event: CloseEvent): void {
        console.log(`[RealWS] Closed: code=${event.code}, reason=${event.reason}`)
        this.isConnecting = false
        this.stopHeartbeat()

        if (!this.isIntentionallyClosed) {
            this.scheduleReconnect()
        }
    }

    private scheduleReconnect(): void {
        if (this.reconnectAttempts >= this.reconnectConfig.maxRetries) {
            console.error('[RealWS] Max reconnect attempts reached')
            return
        }

        // 指数退避
        const delay = Math.min(
            this.reconnectConfig.baseDelay * Math.pow(2, this.reconnectAttempts),
            this.reconnectConfig.maxDelay
        )

        console.log(`[RealWS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1})`)

        this.reconnectTimeout = setTimeout(() => {
            this.reconnectAttempts++
            this.connect(this.chapterId || undefined, this.eventHandler || undefined)
        }, delay)
    }

    private clearReconnectTimeout(): void {
        if (this.reconnectTimeout) {
            clearTimeout(this.reconnectTimeout)
            this.reconnectTimeout = null
        }
    }

    private startHeartbeat(): void {
        this.stopHeartbeat()

        // 每 30 秒发送心跳
        this.heartbeatInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'ping' }))
            }
        }, 30000)
    }

    private stopHeartbeat(): void {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval)
            this.heartbeatInterval = null
        }
    }

    /**
     * 将后端事件转换为前端 WsEvent 格式
     */
    private transformToWsEvent(data: Record<string, unknown>): WsEvent | null {
        const eventType = data.event || data.type
        const ts = new Date().toISOString()

        switch (eventType) {
            case 'job_status_update':
                // Map to job_progress or job_status based on progress
                if (typeof data.progress === 'number' && data.progress < 1) {
                    return {
                        type: 'job_progress',
                        ts,
                        payload: {
                            jobId: data.job_id as string,
                            progress: data.progress as number,
                        },
                    }
                }
                return {
                    type: 'job_status',
                    ts,
                    payload: {
                        jobId: data.job_id as string,
                        status: this.mapJobStatus(data.status as string),
                        error: data.error as string | undefined,
                    },
                }

            case 'panel_update':
                return {
                    type: 'panel_status',
                    ts,
                    payload: {
                        panelId: data.panel_id as string,
                        status: this.mapPanelStatus(data.render_status as string),
                    },
                }

            case 'video_job_progress':
                if (typeof data.progress === 'number' && data.progress < 1) {
                    return {
                        type: 'video_job_progress',
                        ts,
                        payload: {
                            videoJobId: data.job_id as string,
                            clipId: data.clip_id as string,
                            progress: data.progress as number,
                        },
                    }
                }
                return {
                    type: 'video_job_status',
                    ts,
                    payload: {
                        videoJobId: data.job_id as string,
                        clipId: data.clip_id as string,
                        status: this.mapJobStatus(data.status as string),
                        error: data.error as string | undefined,
                    },
                }

            case 'storyboard_progress':
                return {
                    type: 'storyboard_progress',
                    ts,
                    payload: {
                        jobId: data.job_id as string,
                        stage: data.stage as 'validating' | 'analyzing' | 'planning' | 'generating' | 'writing_db' | 'done',
                        progress: data.progress as number,
                        message: data.message as string | undefined,
                        panelIndex: data.panel_index as number | undefined,
                        totalPanels: data.total_panels as number | undefined,
                    },
                }

            case 'storyboard_done':
                return {
                    type: 'storyboard_done',
                    ts,
                    payload: {
                        jobId: data.job_id as string,
                        chapterId: data.chapter_id as string,
                        panelsCount: data.panels_count as number,
                        firstPanelId: data.first_panel_id as string,
                    },
                }

            case 'storyboard_error':
                return {
                    type: 'storyboard_error',
                    ts,
                    payload: {
                        jobId: data.job_id as string,
                        chapterId: data.chapter_id as string,
                        errorCode: data.error_code as string,
                        message: data.message as string,
                    },
                }

            default:
                console.log('[RealWS] Unknown event type:', eventType)
                return null
        }
    }

    private mapJobStatus(status: string): 'Queued' | 'Running' | 'Succeeded' | 'Failed' {
        const statusMap: Record<string, 'Queued' | 'Running' | 'Succeeded' | 'Failed'> = {
            pending: 'Queued',
            queued: 'Queued',
            processing: 'Running',
            running: 'Running',
            completed: 'Succeeded',
            succeeded: 'Succeeded',
            success: 'Succeeded',
            failed: 'Failed',
            error: 'Failed',
        }
        return statusMap[status?.toLowerCase()] || 'Queued'
    }

    private mapPanelStatus(status: string): 'Draft' | 'Queued' | 'Running' | 'Rendered' | 'NeedsFix' {
        const statusMap: Record<string, 'Draft' | 'Queued' | 'Running' | 'Rendered' | 'NeedsFix'> = {
            draft: 'Draft',
            pending: 'Queued',
            queued: 'Queued',
            rendering: 'Running',
            running: 'Running',
            rendered: 'Rendered',
            completed: 'Rendered',
            failed: 'NeedsFix',
            needsfix: 'NeedsFix',
        }
        return statusMap[status?.toLowerCase()] || 'Draft'
    }
}

// 全局实例
let _realWsClient: RealWsClient | null = null

export function getRealWsClient(): RealWsClient {
    if (!_realWsClient) {
        _realWsClient = new RealWsClient()
    }
    return _realWsClient
}

export function disconnectRealWs(): void {
    if (_realWsClient) {
        _realWsClient.disconnect()
        _realWsClient = null
    }
}
