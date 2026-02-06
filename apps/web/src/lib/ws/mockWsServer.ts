/**
 * Mock WebSocket Server
 * 模拟渲染任务的进度推送，用于前端开发测试
 */

import { RenderJob } from '../schema/job'
import { ExtendedLayerPack, createExtendedLayerPack } from '../schema/layerPack'
import { FixPlan } from '../schema/fixPlan'
import { VideoJob } from '../schema/videoJob'
import { Clip, ClipOutput } from '../schema/clip'
import { ExportJob, ExportSpec } from '../schema/exportSpec'
import { WsEvent, createWsEvent } from './events'

// 配置参数
const CONFIG = {
    progressInterval: 300, // 进度更新间隔 (ms)
    progressSteps: 10, // 总共多少步完成
    failureRate: 0.15, // 15% 失败率
    startDelay: 200, // 开始前延迟 (ms)
}

const FIX_CONFIG = {
    progressInterval: 250,
    progressSteps: 8,
    failureRate: 0.10, // 修复任务失败率更低
    startDelay: 150,
}

// Video Job 配置
const VIDEO_CONFIG = {
    progressInterval: 250,
    progressSteps: 12,
    failureRate: 0.12,
    startDelay: 150,
}

// Export Job 配置
const EXPORT_CONFIG = {
    progressInterval: 200,
    progressSteps: 8,
    failureRate: 0.05,
    startDelay: 100,
}

// 随机失败原因
const FAILURE_REASONS = [
    'Character consistency check failed',
    'Style profile mismatch detected',
    'Low quality score: composition issues',
    'Background generation timeout',
    'NSFW content detected',
    'Memory allocation error',
]

// 随机 QA 问题
const QA_ISSUES = [
    'Hand anatomy slightly off',
    'Background perspective inconsistent',
    'Character expression could be stronger',
    'Lighting direction mismatch',
    'Text legibility issue in speech bubble',
    'Color consistency with previous panel',
]

/**
 * 启动 Mock 渲染任务
 * @param job 渲染任务
 * @param emit 事件回调函数
 */
export function startMockJob(
    job: RenderJob,
    emit: (event: WsEvent) => void
): () => void {
    let cancelled = false

    const checkCancelled = () => cancelled

    const run = async () => {
        // 1. 发送 job_created
        emit(createWsEvent('job_created', { job }))

        // 2. 等待开始
        await delay(CONFIG.startDelay)
        if (checkCancelled()) return

        // 3. 发送 panel_status Queued
        emit(createWsEvent('panel_status', { panelId: job.panelId, status: 'Queued' }))

        // 4. 等待一小段时间后开始 Running
        await delay(300)
        if (checkCancelled()) return

        emit(createWsEvent('job_status', { jobId: job.id, status: 'Running' }))
        emit(createWsEvent('panel_status', { panelId: job.panelId, status: 'Running' }))

        // 5. 发送进度更新
        for (let i = 1; i <= CONFIG.progressSteps; i++) {
            await delay(CONFIG.progressInterval)
            if (checkCancelled()) return

            const progress = i / CONFIG.progressSteps
            emit(createWsEvent('job_progress', { jobId: job.id, progress }))
        }

        // 6. 判断成功或失败
        const shouldFail = Math.random() < CONFIG.failureRate

        if (shouldFail) {
            const errorReason = FAILURE_REASONS[Math.floor(Math.random() * FAILURE_REASONS.length)]
            emit(createWsEvent('job_status', { jobId: job.id, status: 'Failed', error: errorReason }))
            emit(createWsEvent('panel_status', { panelId: job.panelId, status: 'NeedsFix' }))
        } else {
            emit(createWsEvent('job_status', { jobId: job.id, status: 'Succeeded' }))
            emit(createWsEvent('panel_status', { panelId: job.panelId, status: 'Rendered' }))

            // 生成 ExtendedLayerPack（带正确的 outputs 结构）
            const layerPack = createExtendedLayerPack(job.panelId, job.id, job.provider)

            // 添加 QA 结果到 layerPack
            const qaScore = 0.6 + Math.random() * 0.35
            const issueCount = Math.floor(Math.random() * 3)
            const issues = shuffleArray(QA_ISSUES).slice(0, issueCount)
            layerPack.qa = { score: qaScore, issues }

            emit(createWsEvent('layerpack_ready', { panelId: job.panelId, layerPack }))

            emit(createWsEvent('qa_result', {
                panelId: job.panelId,
                jobId: job.id,
                score: qaScore,
                issues,
            }))
        }
    }

    run()

    return () => {
        cancelled = true
    }
}

/**
 * 启动 Mock 修复任务
 * @param job 渲染任务
 * @param fixPlan 修复计划
 * @param emit 事件回调函数
 */
export function startMockFixJob(
    job: RenderJob,
    fixPlan: FixPlan,
    emit: (event: WsEvent) => void
): () => void {
    let cancelled = false

    const checkCancelled = () => cancelled

    const run = async () => {
        emit(createWsEvent('job_created', { job }))

        await delay(FIX_CONFIG.startDelay)
        if (checkCancelled()) return

        emit(createWsEvent('panel_status', { panelId: job.panelId, status: 'Queued' }))

        await delay(200)
        if (checkCancelled()) return

        emit(createWsEvent('job_status', { jobId: job.id, status: 'Running' }))
        emit(createWsEvent('panel_status', { panelId: job.panelId, status: 'Running' }))

        for (let i = 1; i <= FIX_CONFIG.progressSteps; i++) {
            await delay(FIX_CONFIG.progressInterval)
            if (checkCancelled()) return

            const progress = i / FIX_CONFIG.progressSteps
            emit(createWsEvent('job_progress', { jobId: job.id, progress }))
        }

        const shouldFail = Math.random() < FIX_CONFIG.failureRate

        if (shouldFail) {
            const errorReason = 'Fix operation failed: ' + FAILURE_REASONS[Math.floor(Math.random() * FAILURE_REASONS.length)]
            emit(createWsEvent('job_status', { jobId: job.id, status: 'Failed', error: errorReason }))
            emit(createWsEvent('panel_status', { panelId: job.panelId, status: 'NeedsFix' }))
        } else {
            emit(createWsEvent('job_status', { jobId: job.id, status: 'Succeeded' }))
            emit(createWsEvent('panel_status', { panelId: job.panelId, status: 'Rendered' }))

            // 根据 strategy 生成不同的 LayerPack
            const layerPack = createExtendedLayerPack(job.panelId, job.id, job.provider)

            // 修复任务的 QA 分数更高，issues 更少
            const qaScore = 0.75 + Math.random() * 0.2 // 0.75 ~ 0.95
            const issueCount = Math.floor(Math.random() * 2) // 0 ~ 1 issues
            const issues = shuffleArray(QA_ISSUES).slice(0, issueCount)
            layerPack.qa = { score: qaScore, issues }

            emit(createWsEvent('layerpack_ready', { panelId: job.panelId, layerPack }))

            emit(createWsEvent('qa_result', {
                panelId: job.panelId,
                jobId: job.id,
                score: qaScore,
                issues,
            }))
        }
    }

    run()

    return () => {
        cancelled = true
    }
}

// 辅助函数

function delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms))
}

function shuffleArray<T>(array: T[]): T[] {
    const result = [...array]
    for (let i = result.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1))
            ;[result[i], result[j]] = [result[j], result[i]]
    }
    return result
}

/**
 * 启动 Mock 视频生成任务
 */
export function startMockVideoJob(
    videoJob: VideoJob,
    clip: Clip,
    emit: (event: WsEvent) => void
): () => void {
    let cancelled = false
    const checkCancelled = () => cancelled

    const run = async () => {
        // 1. 发送 video_job_created
        emit(createWsEvent('video_job_created', { videoJob, clipId: clip.id }))

        await delay(VIDEO_CONFIG.startDelay)
        if (checkCancelled()) return

        // 2. 发送 clip_status Queued
        emit(createWsEvent('clip_status', { clipId: clip.id, status: 'Queued' }))

        await delay(200)
        if (checkCancelled()) return

        // 3. Running
        emit(createWsEvent('video_job_status', {
            videoJobId: videoJob.id,
            clipId: clip.id,
            status: 'Running'
        }))
        emit(createWsEvent('clip_status', { clipId: clip.id, status: 'Running' }))

        // 4. 进度更新
        for (let i = 1; i <= VIDEO_CONFIG.progressSteps; i++) {
            await delay(VIDEO_CONFIG.progressInterval)
            if (checkCancelled()) return

            const progress = i / VIDEO_CONFIG.progressSteps
            emit(createWsEvent('video_job_progress', {
                videoJobId: videoJob.id,
                clipId: clip.id,
                progress
            }))
        }

        // 5. 判断成功或失败
        const shouldFail = Math.random() < VIDEO_CONFIG.failureRate

        if (shouldFail) {
            const errorReason = 'Video generation failed: ' +
                FAILURE_REASONS[Math.floor(Math.random() * FAILURE_REASONS.length)]
            emit(createWsEvent('video_job_status', {
                videoJobId: videoJob.id,
                clipId: clip.id,
                status: 'Failed',
                error: errorReason
            }))
            emit(createWsEvent('clip_status', { clipId: clip.id, status: 'Failed' }))
        } else {
            emit(createWsEvent('video_job_status', {
                videoJobId: videoJob.id,
                clipId: clip.id,
                status: 'Succeeded'
            }))
            emit(createWsEvent('clip_status', { clipId: clip.id, status: 'Succeeded' }))

            // 生成 mock 视频输出
            const output: ClipOutput = {
                videoUrl: `https://samplelib.com/lib/preview/mp4/sample-5s.mp4`,
                previewUrl: `https://picsum.photos/seed/${clip.id}-preview/512/896`,
                frames: Array.from({ length: 8 }, (_, i) =>
                    `https://picsum.photos/seed/${clip.id}-frame-${i}/512/896`
                ),
            }

            emit(createWsEvent('clip_output_ready', { clipId: clip.id, output }))
        }
    }

    run()
    return () => { cancelled = true }
}

/**
 * 启动 Mock 导出任务
 */
export function startMockExportJob(
    exportJob: ExportJob,
    exportSpec: ExportSpec,
    emit: (event: WsEvent) => void
): () => void {
    let cancelled = false
    const checkCancelled = () => cancelled

    const run = async () => {
        // 1. 发送 export_job_created
        emit(createWsEvent('export_job_created', {
            exportJobId: exportJob.id,
            chapterId: exportJob.chapterId
        }))

        await delay(EXPORT_CONFIG.startDelay)
        if (checkCancelled()) return

        // 2. Running
        emit(createWsEvent('export_job_status', {
            exportJobId: exportJob.id,
            status: 'Running'
        }))

        // 3. 进度更新
        for (let i = 1; i <= EXPORT_CONFIG.progressSteps; i++) {
            await delay(EXPORT_CONFIG.progressInterval)
            if (checkCancelled()) return

            const progress = i / EXPORT_CONFIG.progressSteps
            emit(createWsEvent('export_job_progress', {
                exportJobId: exportJob.id,
                progress
            }))
        }

        // 4. 判断成功或失败
        const shouldFail = Math.random() < EXPORT_CONFIG.failureRate

        if (shouldFail) {
            emit(createWsEvent('export_job_status', {
                exportJobId: exportJob.id,
                status: 'Failed',
                error: 'Export failed: insufficient resources'
            }))
        } else {
            emit(createWsEvent('export_job_status', {
                exportJobId: exportJob.id,
                status: 'Succeeded'
            }))
            emit(createWsEvent('export_ready', {
                exportJobId: exportJob.id,
                exportSpec
            }))
        }
    }

    run()
    return () => { cancelled = true }
}
