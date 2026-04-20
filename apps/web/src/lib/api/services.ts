/**
 * API 服务模块
 * 封装所有后端 API 调用
 */

import { apiGet, apiPost, apiPatch, apiPut, apiDelete } from './client'
import type {
    Project,
    Chapter,
    ChapterLayout,
    Panel,
    PanelSpec,
    Asset,
    AssetCreate,
    JobStatus,
    LayerPackMeta,
    BubbleSuggestion,
    BubbleUpdate,
    ComposeRequest,
    ChapterPreview,
    StudioData,
    ScriptSubmitResponse,
    ListResponse,
    MessageResponse,
} from './types'

// ============ Projects API ============

export const projectsApi = {
    list: (archived = false) =>
        apiGet<ListResponse<Project>>(`/api/v1/projects?archived=${archived}`),

    get: (id: string) =>
        apiGet<Project>(`/api/v1/projects/${id}`),

    create: (data: { name: string; description?: string; creation_method?: 'agent' | 'workbench' }) =>
        apiPost<Project>('/api/v1/projects', data),

    update: (id: string, data: Partial<Project>) =>
        apiPatch<Project>(`/api/v1/projects/${id}`, data),

    delete: (id: string) =>
        apiDelete<MessageResponse>(`/api/v1/projects/${id}`),
}

// ============ Chapters API ============

export const chaptersApi = {
    list: (projectId: string) =>
        apiGet<ListResponse<Chapter>>(`/api/v1/chapters/project/${projectId}`),

    get: (id: string) =>
        apiGet<Chapter>(`/api/v1/chapters/${id}`),

    create: (data: { project_id: string; title: string; description?: string }) =>
        apiPost<Chapter>('/api/v1/chapters', data),

    update: (id: string, data: Partial<Chapter>) =>
        apiPatch<Chapter>(`/api/v1/chapters/${id}`, data),

    updateLayout: (id: string, layout: ChapterLayout) =>
        apiPatch<{ message: string; revision: number }>(`/api/v1/chapters/${id}/layout`, layout),

    delete: (id: string) =>
        apiDelete<MessageResponse>(`/api/v1/chapters/${id}`),

    // Studio 聚合接口
    getStudio: (id: string) =>
        apiGet<StudioData>(`/api/v1/chapters/${id}/studio`),

    // 保存剧本（纯保存，不触发分镜）
    saveScript: (id: string, script: string) =>
        apiPut<{
            chapter_id: string
            script: string
            script_version: string
            word_count: number
        }>(`/api/v1/chapters/${id}/script/save`, { script }),

    // 创建 AI 分镜任务
    createStoryboard: (id: string, provider?: string) =>
        apiPost<{ job_id: string; status: string }>(`/api/v1/chapters/${id}/storyboard`, { provider }),

    // 提交剧本并自动分镜（旧接口，保留兼容）
    submitScript: (id: string, scriptText: string, styleHint = "korean_webtoon") =>
        apiPut<ScriptSubmitResponse>(
            `/api/v1/chapters/${id}/script?script_text=${encodeURIComponent(scriptText)}&style_hint=${styleHint}&auto_storyboard=true`
        ),

    // ===== S3-02: Draft API =====

    // 获取 Draft 详情
    getDraft: (draftId: string) =>
        apiGet<{
            id: string
            chapter_id: string
            job_id?: string
            status: string
            version: number
            panels: Array<{
                index: number
                title: string
                description: string
                shot_type?: string
                characters: string[]
                location?: string
            }>
            characters: Array<{
                name: string
                description?: string
                appearances: number
                matched_asset_id?: string
            }>
            scenes: Array<{
                name: string
                description?: string
                appearances: number
                matched_asset_id?: string
            }>
            generated_panels_count: number
            generated_characters_count: number
            generated_scenes_count: number
            created_at: string
        }>(`/api/v1/drafts/${draftId}`),

    // 应用 Draft (S3-04: 支持乐观锁)
    applyDraft: (draftId: string, options?: {
        panel_indices?: number[],
        create_missing_assets?: boolean,
        expected_storyboard_version?: number  // S3-04: 乐观锁
    }) =>
        apiPost<{
            success: boolean
            applied_panels_count: number
            created_assets_count: number
            new_version: number
            already_applied: boolean  // S3-04: 幂等标记
        }>(`/api/v1/drafts/${draftId}/apply`, options || {}),

    // 丢弃 Draft
    discardDraft: (draftId: string) =>
        apiPost<{ success: boolean; message: string }>(`/api/v1/drafts/${draftId}/discard`, {}),

    // 获取章节最新的待审核 Draft
    getLatestDraft: (chapterId: string) =>
        apiGet<{ draft: any | null }>(`/api/v1/drafts/chapter/${chapterId}/latest`),

    // 回滚分镜版本
    rollbackStoryboard: (chapterId: string, targetVersion?: number) =>
        apiPost<{
            success: boolean
            rolled_back_to_draft: string
            restored_panels_count: number
            new_version: number
        }>(`/api/v1/drafts/chapter/${chapterId}/rollback`, { target_storyboard_version: targetVersion }),

    // ===== S3-05: QA API =====

    // 获取 Draft QA 评分
    getDraftQA: (draftId: string) =>
        apiGet<{
            score: number
            passed: boolean
            error_count: number
            warning_count: number
            fixable_count: number
            issues: Array<{
                panel_index: number
                field: string
                severity: 'error' | 'warning' | 'info'
                message: string
                auto_fixable: boolean
                suggested_fix?: string
            }>
        }>(`/api/v1/drafts/${draftId}/qa`),

    // 自动修复 Draft 问题
    fixDraft: (draftId: string, issueIndices?: number[]) =>
        apiPost<{
            success: boolean
            fixed_count: number
            panels_modified: number[]
            new_score: number
        }>(`/api/v1/drafts/${draftId}/fix`, { issue_indices: issueIndices }),

    // ===== S3-06: Assets Lock API =====

    // 获取资产锁定状态
    getAssetsLock: (chapterId: string) =>
        apiGet<{
            chapter_id: string
            storyboard_version: number
            locked_at?: string
            characters: Record<string, any>
            scenes: Record<string, any>
            styles: Record<string, any>
            stats: {
                locked_characters: number
                locked_scenes: number
                locked_styles: number
                pending_count: number
            }
            can_render: boolean
        }>(`/api/v1/chapters/${chapterId}/assets-lock`),

    // ===== S3-07: Batch Render API =====

    // 一键渲染章节所有分镜
    renderAll: (chapterId: string, options?: {
        provider?: string
        panel_ids?: string[]
        force_rerender?: boolean
        max_retries?: number
    }) =>
        apiPost<{
            batch_id: string
            job_count: number
            skipped_count: number
            can_render: boolean
            pending_assets: string[]
        }>(`/api/v1/chapters/${chapterId}/render-all`, options || {}),

    // 获取渲染状态
    getRenderStatus: (chapterId: string) =>
        apiGet<{
            chapter_id: string
            batch_id?: string
            total_jobs: number
            completed_jobs: number
            failed_jobs: number
            running_jobs: number
            progress: number
            batch_started_at?: string
            is_complete: boolean
        }>(`/api/v1/chapters/${chapterId}/render-status`),
}

// ============ Panels API ============

export interface PanelAnalyzeResponse {
    success: boolean
    data?: {
        character_ids: string[]
        scene_id: string | null
        shot_type?: string
        camera_move?: string
        time_of_day?: string
        mood?: string
    }
    error?: string
}


export const panelsApi = {
    list: (chapterId: string) =>
        apiGet<ListResponse<Panel>>(`/api/v1/panels/chapter/${chapterId}`),

    get: (id: string) =>
        apiGet<Panel>(`/api/v1/panels/${id}`),

    create: (data: { chapter_id: string; spec?: PanelSpec }) =>
        apiPost<Panel>('/api/v1/panels', data),

    updateSpec: (id: string, spec: PanelSpec) =>
        apiPatch<MessageResponse>(`/api/v1/panels/${id}/spec`, spec),

    delete: (id: string) =>
        apiDelete<MessageResponse>(`/api/v1/panels/${id}`),

    batchCreate: (chapterId: string, count: number) =>
        apiPost<{ panel_ids: string[] }>(`/api/v1/panels/batch?chapter_id=${chapterId}&count=${count}`),

    analyze: (chapterId: string, text: string) =>
        apiPost<PanelAnalyzeResponse>('/api/v1/panels/analyze', { chapter_id: chapterId, text }),

    updateBindings: (
        panelId: string,
        payload: {
            slot: 'character' | 'scene' | 'prop'
            slot_index: number
            asset_id: string | null
            asset_version_id?: string | null
        }
    ) =>
        apiPatch<{
            panel_id: string
            spec_json: Record<string, unknown>
            chapter_bindings_updated: boolean
        }>(`/api/v1/panels/${panelId}/bindings`, payload),
}



// ============ Assets API ============

export const assetsApi = {
    list: (projectId: string, type?: string) =>
        apiGet<ListResponse<Asset>>(
            `/api/v1/assets/project/${projectId}${type ? `?asset_type=${type}` : ""}`
        ),

    get: (id: string) =>
        apiGet<Asset>(`/api/v1/assets/${id}`),

    create: (data: AssetCreate) =>
        apiPost<Asset>('/api/v1/assets', data),

    update: (id: string, data: Partial<Asset>) =>
        apiPatch<Asset>(`/api/v1/assets/${id}`, data),

    delete: (id: string) =>
        apiDelete<MessageResponse>(`/api/v1/assets/${id}`),

    regenerateReference: (id: string) =>
        apiPost<{ message: string; status: string }>(`/api/v1/assets/${id}/regenerate-reference`, {}),

    regenerateAnchor: (id: string) =>
        apiPost<{ message: string; status: string }>(`/api/v1/assets/${id}/regenerate-anchor`, {}),

    clearAll: (projectId: string, options?: { keepTypes?: string[]; hardDelete?: boolean }) =>
        apiDelete<{ message: string; deleted: { assets: number; props: number; outfits: number; relations: number } }>(
            `/api/v1/assets/project/${projectId}/clear`,
            { keep_types: options?.keepTypes || [], hard_delete: options?.hardDelete ?? true }
        ),

    /**
     * 使用豆包 AI 生成资产参考图
     * - 角色: 定妆照 (正面半身像)
     * - 场景: 空镜图 (无人背景)
     */
    generateImage: (id: string, styleHint = "韩漫风格") =>
        apiPost<{ success: boolean; image_url?: string; error?: string }>(
            `/api/v1/assets/${id}/generate-image`,
            { style_hint: styleHint }
        ),

    /**
     * 手动上传资产图片
     */
    uploadImage: async (id: string, file: File) => {
        const formData = new FormData()
        formData.append('file', file)
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/assets/${id}/upload-image`, {
            method: 'POST',
            body: formData,
        })
        if (!response.ok) {
            throw new Error('上传失败')
        }
        return response.json() as Promise<{ success: boolean; image_url?: string; error?: string }>
    },

    /**
     * 使用 LLM 生成资产描述
     */
    generateDescription: (id: string) =>
        apiPost<{ success: boolean; description?: string; error?: string }>(
            `/api/v1/assets/${id}/generate-description`,
            {}
        ),

    getUsage: (id: string, limit = 50) =>
        apiGet<{
            asset_id: string
            references: Array<{
                chapter_id: string
                chapter_title: string | null
                panel_id: string
                panel_order: number
                panel_preview_url: string | null
            }>
            total_count: number
        }>(`/api/v1/assets/${id}/usage?limit=${limit}`),
}

// ============ Props API (S5-04) ============

export const propsApi = {
    list: (projectId: string, category?: string) =>
        apiGet<ListResponse<any>>(`/api/v1/props/projects/${projectId}/props${category ? `?category=${category}` : ""}`),

    get: (id: string) =>
        apiGet<any>(`/api/v1/props/props/${id}`),

    create: (data: any) =>
        apiPost<any>('/api/v1/props/props', data),

    update: (id: string, data: any) =>
        apiPut<any>(`/api/v1/props/props/${id}`, data),

    delete: (id: string) =>
        apiDelete<{ ok: boolean }>(`/api/v1/props/props/${id}`),

    // Relations
    listRelations: (projectId: string, chapterId?: string) =>
        apiGet<ListResponse<any>>(
            `/api/v1/projects/${projectId}/relations${chapterId ? `?chapter_id=${chapterId}` : ""}`
        ),

    // LLM 自动提取物品
    extractPropsFromScript: (projectId: string, scriptText: string, chapterId?: string) =>
        apiPost<{
            props_created: number
            outfits_created: number
            relations_created: number
            message: string
        }>(`/api/v1/projects/${projectId}/extract-props`, {
            script_text: scriptText,
            chapter_id: chapterId
        }),
}


// ============ Render API ============

export const renderApi = {
    renderPanel: (panelId: string, forceRegenerate = false, provider?: string) =>
        apiPost<{ job_id: string; status: string }>('/api/v1/render/panel', {
            panel_id: panelId,
            force_regenerate: forceRegenerate,
            provider: provider,
        }),

    getJobStatus: (jobId: string) =>
        apiGet<JobStatus>(`/api/v1/render/job/${jobId}`),

    getPanelLayers: (panelId: string) =>
        apiGet<{ panel_id: string; status: string; layer_pack?: LayerPackMeta }>(
            `/api/v1/render/panel/${panelId}/layers`
        ),
}

// ============ Video API ============

export interface VideoJobRequest {
    clip_id: string
    provider?: 'tongyi' | 'doubao' | 'comfyui' | 'mock'
    motion_prompt?: string
    duration_sec?: number
}

export interface VideoJobResponse {
    job_id: string
    clip_id: string
    status: 'pending' | 'running' | 'succeeded' | 'failed'
    progress?: number
    output_url?: string
    error?: string
}

export const videoApi = {
    // 创建视频生成任务
    createJob: (request: VideoJobRequest) =>
        apiPost<{ job_id: string; status: string }>('/api/v1/video/generate', request),

    // 获取任务状态
    getJobStatus: (jobId: string) =>
        apiGet<VideoJobResponse>(`/api/v1/video/job/${jobId}`),

    // 批量生成章节视频
    generateChapter: (chapterId: string, provider?: string) =>
        apiPost<{ jobs: Array<{ clip_id: string; job_id: string }> }>(
            `/api/v1/video/chapter/${chapterId}/generate`,
            { provider }
        ),

    // 取消任务
    cancelJob: (jobId: string) =>
        apiPost<{ message: string }>(`/api/v1/video/job/${jobId}/cancel`, {}),
}

// ============ Provider API ============

export interface ProviderStatus {
    name: string
    type: 'image' | 'video'
    available: boolean
    configured: boolean
    models?: string[]
}

export const providerApi = {
    // 获取可用 Provider 列表
    list: () =>
        apiGet<{ providers: ProviderStatus[] }>('/api/v1/providers'),

    // 检查特定 Provider 健康状态
    checkHealth: (name: string) =>
        apiGet<{ name: string; healthy: boolean; latency_ms?: number }>(
            `/api/v1/providers/${name}/health`
        ),

    // 获取推荐 Provider
    getRecommended: (type: 'image' | 'video') =>
        apiGet<{ provider: string; reason: string }>(
            `/api/v1/providers/recommended?type=${type}`
        ),
}

// ============ Typeset API ============

export const typesetApi = {
    render: (panelId: string, useAutoPosition = true) =>
        apiPost<{ job_id: string; status: string }>('/api/v1/typeset/render', {
            panel_id: panelId,
            use_auto_position: useAutoPosition,
        }),

    suggestPositions: (panelId: string) =>
        apiPost<{ panel_id: string; suggestions: BubbleSuggestion[] }>(
            `/api/v1/typeset/suggest-positions?panel_id=${panelId}`
        ),

    addBubble: (panelId: string, text: string, style = "normal") =>
        apiPost<{ bubble_id: string }>(
            `/api/v1/typeset/bubble?panel_id=${panelId}&text=${encodeURIComponent(text)}&style=${style}`
        ),

    updateBubble: (data: BubbleUpdate) =>
        apiPatch<MessageResponse>('/api/v1/typeset/bubble', data),

    deleteBubble: (panelId: string, bubbleId: string) =>
        apiDelete<MessageResponse>(`/api/v1/typeset/bubble/${panelId}/${bubbleId}`),
}

// ============ Compose API ============

export const composeApi = {
    composeStrip: (data: ComposeRequest) =>
        apiPost<{ job_id: string; status: string }>('/api/v1/compose/strip', data),

    getJobStatus: (jobId: string) =>
        apiGet<JobStatus>(`/api/v1/compose/job/${jobId}`),

    getDownloadUrl: (chapterId: string) =>
        apiGet<{ download_url: string; expires_in: number }>(
            `/api/v1/compose/chapter/${chapterId}/download`
        ),

    preview: (chapterId: string) =>
        apiGet<ChapterPreview>(`/api/v1/compose/chapter/${chapterId}/preview`),
}

// ============ Jobs API (统一任务系统) ============

export const jobsApi = {
    // 图像生成任务
    createImageJob: (data: { panel_id: string; provider?: string; inputs?: Record<string, unknown> }) =>
        apiPost<{ job_id: string }>('/api/v1/jobs/image', data),

    // Anchor 生成任务
    createAnchorJob: (data: { panel_id: string; kind: string; source_image_url: string }) =>
        apiPost<{ job_id: string; anchor_id: string }>('/api/v1/jobs/anchor', data),

    // 视频生成任务
    createVideoJob: (data: {
        clip_id: string
        start_frame_url: string
        end_frame_url?: string
        motion_prompt: string
        duration_sec: number
        fps: number
        provider?: string
    }) =>
        apiPost<{ job_id: string }>('/api/v1/jobs/video', data),

    // 导出任务
    createExportJob: (data: { chapter_id: string; export_spec?: unknown }) =>
        apiPost<{ job_id: string }>('/api/v1/jobs/export', data),

    // 查询任务状态
    get: (jobId: string) =>
        apiGet<JobStatus>(`/api/v1/jobs/${jobId}`),

    // 列出章节任务
    listByChapter: (chapterId: string, type?: string) =>
        apiGet<ListResponse<JobStatus>>(
            `/api/v1/jobs/chapter/${chapterId}${type ? `?type=${type}` : ''}`
        ),

    // 取消任务
    cancel: (jobId: string) =>
        apiPost<MessageResponse>(`/api/v1/jobs/${jobId}/cancel`),
}

// ============ Timeline API ============

export const timelineApi = {
    get: (chapterId: string) =>
        apiGet<{ chapter_id: string; clips: unknown[]; settings: unknown }>(
            `/api/v1/chapters/${chapterId}/timeline`
        ),

    save: (chapterId: string, timeline: { clips: unknown[]; settings: unknown }) =>
        apiPost<MessageResponse>(`/api/v1/chapters/${chapterId}/timeline`, timeline),
}

// ============ Bindings API ============

export const bindingsApi = {
    get: (chapterId: string) =>
        apiGet<{
            chapter_id: string
            identity_asset_ids: string[]
            scene_asset_ids: string[]
            style_profile_id?: string
            anchor_ids: string[]
        }>(`/api/v1/chapters/${chapterId}/bindings`),

    save: (chapterId: string, bindings: {
        identity_asset_ids?: string[]
        scene_asset_ids?: string[]
        style_profile_id?: string
        anchor_ids?: string[]
    }) =>
        apiPost<MessageResponse>(`/api/v1/chapters/${chapterId}/bindings`, bindings),
}

// ============ Analytics API ============

export const analyticsApi = {
    getChapter: (chapterId: string) =>
        apiGet<{
            chapter_id: string
            by_provider: Array<{ provider: string; cost_used: number; avg_score: number; success_rate: number; job_count: number }>
            by_character: Array<{ asset_id: string; asset_name: string; cost_used: number; avg_score: number; usage_count: number }>
            chapter_summary: { total_cost: number; avg_score: number; total_clips: number; succeeded: number; needs_fix: number; failed: number }
        }>(`/api/v1/chapters/${chapterId}/analytics`),

    recompute: (chapterId: string) =>
        apiPost<MessageResponse>(`/api/v1/chapters/${chapterId}/analytics/recompute`),
}

// ============ Release API ============

export const releaseApi = {
    create: (chapterId: string, data: { release_version: string; notes?: string }) =>
        apiPost<{ release_id: string; bundle_url: string }>(
            `/api/v1/chapters/${chapterId}/release`,
            data
        ),

    get: (chapterId: string) =>
        apiGet<{
            id: string
            release_version: string
            bundle_url: string
            generated_at: string
        }>(`/api/v1/chapters/${chapterId}/release/latest`),

    list: (chapterId: string) =>
        apiGet<ListResponse<{ id: string; release_version: string; generated_at: string }>>(
            `/api/v1/chapters/${chapterId}/releases`
        ),
}

// ============ Identity API (角色 FaceID Embedding) ============

export const identityApi = {
    // 为角色提取 FaceID Embedding (上传定妆照)
    extractEmbedding: async (assetId: string, files: File[]): Promise<{
        asset_id: string
        status: string
        embedding_path?: string
        source_image_count: number
        message?: string
    }> => {
        const formData = new FormData()
        files.forEach((file, i) => formData.append('files', file))

        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}/api/v1/identity/extract/${assetId}`, {
            method: 'POST',
            body: formData,
        })
        if (!response.ok) throw new Error(await response.text())
        return response.json()
    },

    // 获取 Embedding 状态
    getStatus: (assetId: string) =>
        apiGet<{
            asset_id: string
            status: 'none' | 'pending' | 'ready' | 'failed'
            embedding_path?: string
            source_image_count: number
            message?: string
        }>(`/api/v1/identity/status/${assetId}`),

    // 删除 Embedding
    deleteEmbedding: (assetId: string) =>
        apiDelete<{ success: boolean; message: string }>(`/api/v1/identity/embedding/${assetId}`),

    // 比较两张图片的人脸相似度
    compareSimilarity: async (file1: File, file2: File, threshold = 0.6): Promise<{
        similarity: number
        is_match: boolean
        threshold: number
    }> => {
        const formData = new FormData()
        formData.append('file1', file1)
        formData.append('file2', file2)

        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}/api/v1/identity/compare?threshold=${threshold}`, {
            method: 'POST',
            body: formData,
        })
        if (!response.ok) throw new Error(await response.text())
        return response.json()
    },

    // 检测图片与角色的一致性
    checkConsistency: async (assetId: string, file: File, threshold = 0.6): Promise<{
        asset_id: string
        similarity: number
        is_match: boolean
        threshold: number
        quality_score?: number
    }> => {
        const formData = new FormData()
        formData.append('file', file)

        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}/api/v1/identity/check/${assetId}?threshold=${threshold}`, {
            method: 'POST',
            body: formData,
        })
        if (!response.ok) throw new Error(await response.text())
        return response.json()
    },
}

// ============ Scene Anchor API (场景控制图生成) ============

export const sceneAnchorApi = {
    // 为场景生成锚点（上传空镜图）
    generateAnchor: async (assetId: string, file: File, options?: {
        generate_depth?: boolean
        generate_canny?: boolean
        generate_lineart?: boolean
    }): Promise<{
        asset_id: string
        status: string
        generated_maps: string[]
        message: string
    }> => {
        const formData = new FormData()
        formData.append('file', file)

        const params = new URLSearchParams()
        if (options?.generate_depth !== undefined) params.set('generate_depth', String(options.generate_depth))
        if (options?.generate_canny !== undefined) params.set('generate_canny', String(options.generate_canny))
        if (options?.generate_lineart !== undefined) params.set('generate_lineart', String(options.generate_lineart))

        const url = `/api/v1/scene_anchor/generate/${assetId}${params.toString() ? '?' + params.toString() : ''}`
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ''}${url}`, {
            method: 'POST',
            body: formData,
        })
        if (!response.ok) throw new Error(await response.text())
        return response.json()
    },

    // 获取锚点状态
    getStatus: (assetId: string) =>
        apiGet<{
            asset_id: string
            status: 'none' | 'pending' | 'ready' | 'failed'
            has_anchor: boolean
            has_depth: boolean
            has_canny: boolean
            has_lineart: boolean
            message?: string
        }>(`/api/v1/scene_anchor/status/${assetId}`),

    // 获取控制图 URLs (预览用)
    getUrls: (assetId: string) =>
        apiGet<{
            asset_id: string
            anchor_url?: string
            depth_url?: string
            canny_url?: string
            lineart_url?: string
        }>(`/api/v1/scene_anchor/urls/${assetId}`),

    // 删除锚点
    deleteAnchor: (assetId: string) =>
        apiDelete<{ success: boolean; message: string }>(`/api/v1/scene_anchor/anchor/${assetId}`),

    // 重新生成单个控制图
    regenerateMap: (assetId: string, mapType: 'depth' | 'canny' | 'lineart') =>
        apiPost<{
            asset_id: string
            map_type: string
            status: string
            message: string
        }>(`/api/v1/scene_anchor/regenerate/${assetId}/${mapType}`),
}

// ============ Conversations API ============

export interface Conversation {
    id: string
    project_id: string
    chapter_id?: string
    episode_number?: number  // 分集编号
    title?: string
    status: string
    message_count: number
    total_tokens_used: number
    current_context?: Record<string, any>
    created_at: string
    updated_at: string
}export interface ConversationMessage {
    id: string
    conversation_id: string
    role: 'user' | 'assistant' | 'system'
    content: string
    content_type?: string
    tokens_used: number
    entities_json?: Record<string, any>  // This is where metadata is stored
    created_at: string
}

export const conversationsApi = {
    // 创建对话
    create: (data: { project_id: string; chapter_id?: string; title?: string; episode_number?: number }) =>
        apiPost<Conversation>('/api/v1/conversations', data),    // 获取对话详情
    get: (conversationId: string) =>
        apiGet<Conversation>(`/api/v1/conversations/${conversationId}`),

    // 获取或创建分集对话（用于持久化分集聊天历史）
    getOrCreateEpisode: (projectId: string, episodeNumber: number) =>
        apiGet<Conversation>(`/api/v1/conversations/episode/${episodeNumber}?project_id=${projectId}`),

    // 获取项目的对话列表
    listByProject: (projectId: string, limit = 20, offset = 0) =>
        apiGet<Conversation[]>(`/api/v1/conversations?project_id=${projectId}&limit=${limit}&offset=${offset}`),

    // 获取对话消息
    getMessages: (conversationId: string, limit = 50, offset = 0) =>
        apiGet<ConversationMessage[]>(`/api/v1/conversations/${conversationId}/messages?limit=${limit}&offset=${offset}`),

    // 直接保存消息（不触发AI）
    saveMessage: async (conversationId: string, role: string, content: string, metadata?: Record<string, any>) => {
        // Use POST body instead of URL params to handle long content properly
        return apiPost<{ success: boolean; message_id: string }>(
            `/api/v1/conversations/${conversationId}/messages/save`,
            { content, role, metadata }
        )
    },    // 重置对话上下文
    reset: (conversationId: string) =>
        apiPost<{ success: boolean; message: string }>(`/api/v1/conversations/${conversationId}/reset`),

    // 删除对话
    delete: (conversationId: string) =>
        apiDelete<{ success: boolean; message: string }>(`/api/v1/conversations/${conversationId}`),

    // 删除单条消息
    deleteMessage: (messageId: string) =>
        apiDelete<{ success: boolean; message: string }>(`/api/v1/conversations/messages/${messageId}`),
}

// ============ Agent API ============

export const agentApi = {
    commitToStudio: (
        projectId: string,
        payload: {
            conversation_id: string
            episode_number: number
            episode_title?: string
            outline_summary?: string
            art_style?: { base_style?: string; color_tone?: string; atmosphere?: string }
            characters?: Array<Record<string, unknown>>
            scenes?: Array<Record<string, unknown>>
            panels?: Array<Record<string, unknown>>
        }
    ) =>
        apiPost<{
            chapter_id: string
            chapter_title: string
            status: 'created' | 'already_exists'
            created_assets: { characters: number; scenes: number }
            created_panels: number
            studio_url: string
            warnings: string[]
            payload_source: 'request' | 'conversation'
        }>(`/api/v1/agent/projects/${projectId}/commit-to-studio`, payload),
}