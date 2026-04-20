/**
 * WebSocket 客户端
 * 支持真实 WebSocket 连接和 Mock 模式
 */

import { WsEvent } from './events'
import { startMockJob, startMockVideoJob, startMockExportJob } from './mockWsServer'
import { RenderJob } from '../schema/job'
import { VideoJob } from '../schema/videoJob'
import { Clip } from '../schema/clip'
import { ExportJob, ExportSpec } from '../schema/exportSpec'
import { getRealWsClient, RealWsClient } from './realWsClient'
import { useStudioStore } from '../store/studioStore'

type EventHandler = (event: WsEvent) => void

interface WsConnection {
    subscribeChapter: (
        projectId: string,
        chapterId: string,
        onEvent: EventHandler
    ) => () => void
    startRenderJob: (job: RenderJob) => () => void
    startVideoJob: (videoJob: VideoJob, clip: Clip) => () => void
    startExportJob: (exportJob: ExportJob, exportSpec: ExportSpec) => () => void
    disconnect: () => void
}

// 是否使用真实 WebSocket（可通过环境变量控制）
const USE_REAL_WEBSOCKET = process.env.NEXT_PUBLIC_USE_REAL_WS !== 'false'

// 当前连接状态
let currentConnection: WsConnection | null = null
let eventHandlers: Map<string, EventHandler> = new Map()
let activeJobCancellers: Map<string, () => void> = new Map()
let realWsClient: RealWsClient | null = null

/**
 * 连接到 WebSocket
 * 优先使用真实 WebSocket，失败时回退到 Mock
 */
export function connect(): WsConnection {
    if (currentConnection) {
        return currentConnection
    }

    // 初始化真实 WebSocket 客户端
    if (USE_REAL_WEBSOCKET) {
        try {
            realWsClient = getRealWsClient()
            useStudioStore.setState({ wsConnected: true })
        } catch (error) {
            console.warn('[WS] Failed to initialize real WebSocket, using mock:', error)
            useStudioStore.setState({ wsConnected: false })
        }
    }

    const connection: WsConnection = {
        /**
         * 订阅章节的渲染事件
         */
        subscribeChapter: (projectId, chapterId, onEvent) => {
            const key = `${projectId}:${chapterId}`
            eventHandlers.set(key, onEvent)

            // 如果使用真实 WebSocket，建立连接
            if (realWsClient) {
                return realWsClient.subscribeChapter(chapterId, onEvent)
            }

            // 返回取消订阅函数（Mock 模式）
            return () => {
                eventHandlers.delete(key)
            }
        },

        /**
         * 启动一个渲染任务
         * 真实模式：通过后端 API 启动任务，WS 接收进度
         * Mock 模式：本地模拟进度
         */
        startRenderJob: (job) => {
            const emit: EventHandler = (event) => {
                // 广播给所有订阅者
                const key = `${job.projectId}:${job.chapterId}`
                const handler = eventHandlers.get(key)
                if (handler) {
                    handler(event)
                }
            }

            // 真实 WS 模式下，通过统一 Job API 触发后端任务
            if (realWsClient && realWsClient.isConnected()) {
                import('@/lib/api/jobApi').then(({ jobApi }) => {
                    jobApi.create({
                        type: 'image',
                        target_id: job.panelId || '',
                        provider: job.provider || 'mock',
                        params: { chapter_id: job.chapterId },
                    }).catch(err => console.error('[WS] Failed to create image job:', err))
                })
                return () => { }
            }

            // Mock 模式
            const cancel = startMockJob(job, emit)
            activeJobCancellers.set(job.id, cancel)

            return cancel
        },

        /**
         * 启动一个视频生成任务
         */
        startVideoJob: (videoJob, clip) => {
            const emit: EventHandler = (event) => {
                const key = `${clip.projectId}:${clip.chapterId}`
                const handler = eventHandlers.get(key)
                if (handler) {
                    handler(event)
                }
            }

            // 真实 WS 模式下，通过统一 Job API 触发后端任务
            if (realWsClient && realWsClient.isConnected()) {
                import('@/lib/api/jobApi').then(({ jobApi }) => {
                    const startFrameUrl =
                        typeof clip.startFrame === 'string'
                            ? clip.startFrame
                            : clip.startFrame?.url || ''
                    const endFrameUrl =
                        typeof clip.endFrame === 'string'
                            ? clip.endFrame
                            : clip.endFrame?.url
                    const defaultModel =
                        clip.provider === 'tongyi'
                            ? 'wanx2.1-i2v-plus'
                            : clip.provider === 'doubao'
                                ? 'jimeng-video-v1'
                                : undefined

                    jobApi.create({
                        type: 'video',
                        target_id: clip.id || '',
                        provider: clip.provider || 'mock',
                        params: {
                            start_frame_url: startFrameUrl,
                            end_frame_url: clip.motionMode === 'dual_keyframe' ? endFrameUrl : undefined,
                            motion_prompt: clip.motionPrompt || '',
                            negative_prompt: clip.negative || '',
                            motion_mode: clip.motionMode || 'single_keyframe',
                            duration_sec: clip.durationSec || 3,
                            fps: clip.fps || 24,
                            width: clip.startFrame?.w || 1080,
                            height: clip.startFrame?.h || 1920,
                            resolution: `${clip.startFrame?.w || 1080}x${clip.startFrame?.h || 1920}`,
                            motion_strength: 0.5,
                            prompt_extend: true,
                            model: defaultModel,
                            source: 'ws_client',
                        },
                    }).catch(err => console.error('[WS] Failed to create video job:', err))
                })
                return () => { }
            }

            // Mock 模式
            const cancel = startMockVideoJob(videoJob, clip, emit)
            activeJobCancellers.set(videoJob.id, cancel)

            return cancel
        },

        /**
         * 启动一个导出任务
         */
        startExportJob: (exportJob, exportSpec) => {
            const emit: EventHandler = (event) => {
                const key = `${exportSpec.projectId}:${exportSpec.chapterId}`
                const handler = eventHandlers.get(key)
                if (handler) {
                    handler(event)
                }
            }

            // 真实 WS 模式下，通过统一 Job API 触发后端任务
            if (realWsClient && realWsClient.isConnected()) {
                import('@/lib/api/jobApi').then(({ jobApi }) => {
                    jobApi.create({
                        type: 'export',
                        target_id: exportSpec.chapterId || '',
                        provider: 'local',
                        params: { export_type: 'strip_png' },
                    }).catch(err => console.error('[WS] Failed to create export job:', err))
                })
                return () => { }
            }

            // Mock 模式
            const cancel = startMockExportJob(exportJob, exportSpec, emit)
            activeJobCancellers.set(exportJob.id, cancel)

            return cancel
        },

        /**
         * 断开连接
         */
        disconnect: () => {
            // 断开真实 WebSocket
            if (realWsClient) {
                realWsClient.disconnect()
                realWsClient = null
            }

            useStudioStore.setState({ wsConnected: false })

            // 取消所有 Mock 任务
            activeJobCancellers.forEach((cancel) => cancel())
            activeJobCancellers.clear()
            eventHandlers.clear()
            currentConnection = null
        },
    }

    currentConnection = connection
    return connection
}

/**
 * 获取当前连接
 */
export function getConnection(): WsConnection | null {
    return currentConnection
}

/**
 * 断开当前连接
 */
export function disconnect(): void {
    if (currentConnection) {
        currentConnection.disconnect()
    }
}

/**
 * 检查是否使用真实 WebSocket
 */
export function isUsingRealWebSocket(): boolean {
    return realWsClient !== null && realWsClient.isConnected()
}
