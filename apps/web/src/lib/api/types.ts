/**
 * API 类型定义
 * 与后端 API 响应结构对应的 TypeScript 类型
 */

// ============ 项目与章节 ============

export interface Project {
    id: string
    name: string
    description?: string
    cover_image?: string
    is_archived: boolean
    creation_method: 'agent' | 'workbench'
    chapter_count: number
    created_at: string
    updated_at: string
}

export interface Chapter {
    id: string
    project_id: string
    title: string
    description?: string
    order_index: number
    script_raw?: string
    layout_json: ChapterLayout
    export_status: string
    exported_url?: string
    panel_count: number
    created_at: string
    updated_at: string
}

export interface ChapterLayout {
    chapter_id: string
    title: string
    reading_flow: "vertical" | "horizontal" | "zigzag"
    panels: PanelSlot[]
    export_config: ExportConfig
}

export interface PanelSlot {
    panel_id: string
    weight: "highlight" | "normal" | "transition"
    height_ratio: number
    order: number
}

export interface ExportConfig {
    strip_width: number
    panel_gap: number
    background_color: string
}

// ============ 分镜面板 ============

export type PanelStatus = "Draft" | "Queued" | "Running" | "NeedsFix" | "Rendered" | "TypesetDone" | "Exported"

export interface Panel {
    id: string
    chapter_id: string
    order_index: number
    spec_json: PanelSpec
    render_status: string
    active_layer_pack_id?: string
    typeset_status: string
    typeset_image_url?: string
    preview_url?: string
    qa_score: number
    created_at: string
    updated_at: string
}

export interface PanelSpec {
    panel_id: string
    scene: SceneDescription
    characters: CharacterPlacement[]
    action_description: string
    bubbles: BubbleCandidate[]
    camera: CameraSettings
    look: LookSettings
    act: ActSettings
    prompt_override?: string
    negative_prompt: string
    status: string
}

export interface SceneDescription {
    scene_id?: string
    time_of_day: string
    weather: string
    location_description: string
}

export interface CharacterPlacement {
    character_id: string
    position: string
    scale: number
    pose_preset?: string
    emotion?: string
}

export interface BubbleCandidate {
    id: string
    text: string
    speaker_id?: string
    style: string
    position_hint: string
    font_size: number
    is_vertical: boolean
    x?: number
    y?: number
    width?: number
}

export interface CameraSettings {
    shot_type: string
    angle: string
    focal_length: number
    depth_of_field: number
}

export interface LookSettings {
    style_preset: string
    line_intensity: number
    color_saturation: number
}

export interface ActSettings {
    emotion_intensity: number
    action_intensity: number
}

// ============ 资产 ============

export interface Asset {
    id: string
    project_id: string
    name: string
    type: string
    description?: string
    thumbnail_url?: string
    data_json: Record<string, unknown>
    status: string
    tags?: string[]
    created_at: string
    updated_at: string
}

export interface AssetCreate {
    project_id: string
    name: string
    type: string
    description?: string
    data_json?: Record<string, unknown>
}

// ============ 渲染与任务 ============

export interface JobStatus {
    job_id: string
    status: string
    progress: number
    current_step?: string
    result?: unknown
    error?: string
}

export interface LayerPackMeta {
    pack_id: string
    panel_id: string
    layers: LayerFile[]
    canvas_width: number
    canvas_height: number
    qa_score: QAScore
}

export interface LayerFile {
    type: string
    filename: string
    storage_path: string
    width: number
    height: number
}

export interface QAScore {
    overall: number
    issues: unknown[]
}

// ============ 排版 ============

export interface BubbleSuggestion {
    bubble_id: string
    suggested_x: number
    suggested_y: number
    suggested_width: number
    confidence: number
}

export interface BubbleUpdate {
    panel_id: string
    bubble_id: string
    x?: number
    y?: number
    width?: number
    text?: string
    style?: string
}

// ============ 合成与导出 ============

export interface ComposeRequest {
    chapter_id: string
    output_format?: string
    strip_width?: number
    panel_gap?: number
    background_color?: string
    include_typeset?: boolean
}

export interface ChapterPreview {
    chapter_id: string
    title: string
    export_status: string
    reading_flow: string
    panels: PreviewPanel[]
}

export interface PreviewPanel {
    panel_id: string
    order: number
    thumbnail_url?: string
    typeset_url?: string
    weight: string
    height_ratio: number
    render_status: string
    typeset_status: string
}

// ============ Studio 聚合数据 ============

export interface StudioData {
    chapter: Chapter
    layout: ChapterLayout
    panels: PanelSummary[]
    panels_by_id: Record<string, Panel>
    characters: CharacterSummary[]
    scenes: SceneSummary[]
    styles: Asset[]
    bubble_styles: Asset[]
    active_jobs: JobSummary[]
    warnings: StudioWarning[]
    stats: StudioStats
}

export interface PanelSummary {
    id: string
    order_index: number
    title?: string
    summary?: string
    preview_url?: string
    render_status: string
    typeset_status: string
    qa_score: number
    warning_count: number
    error_count: number
    render_tier: string
    dialogue_preview?: string
    character_ids: string[]
    scene_id?: string
    // 结构化字段 (从 spec_json 提取)
    shot_type?: string
    camera_move?: string
    camera_angle?: string
    duration_sec?: number
    location?: string
    time_of_day?: string
    mood?: string
    emotion?: string
    action_description?: string
}

export interface CharacterSummary {
    id: string
    name: string
    thumbnail_url?: string
    face_embedding_status: "none" | "pending" | "ready"
    reference_count: number
}

export interface SceneSummary {
    id: string
    name: string
    thumbnail_url?: string
    anchor_status: "none" | "pending" | "ready"
    control_maps_ready: boolean
}

export interface JobSummary {
    id: string
    panel_id?: string
    job_type: string
    status: string
    progress: number
    current_step?: string
}

export interface StudioWarning {
    type: string
    severity: "info" | "warning" | "error"
    message: string
    panel_id?: string
    asset_id?: string
    auto_fixable: boolean
}

export interface StudioStats {
    total_panels: number
    rendered_panels: number
    failed_panels: number
    pending_jobs: number
    avg_qa_score: number
}

export interface ScriptSubmitResponse {
    success: boolean
    chapter_id: string
    panels_created: number
    characters_detected: string[]
    scenes_detected: string[]
    warnings: StudioWarning[]
}

// ============ 通用响应类型 ============

export interface ListResponse<T> {
    items: T[]
    total: number
}

export interface MessageResponse {
    message: string
}

// ============ WebSocket 事件 ============

export type WsEvent =
    | { type: "job_progress"; jobId: string; panelId: string; progress: number }
    | { type: "job_status"; jobId: string; panelId: string; status: "Queued" | "Running" | "Succeeded" | "Failed"; error?: string }
    | { type: "panel_status"; panelId: string; status: PanelStatus }
    | { type: "qa_result"; panelId: string; score: number; issues: string[] }
    | { type: "export_status"; exportId: string; status: "Running" | "Succeeded" | "Failed"; error?: string }
    | { type: "video_job_progress"; jobId: string; clipId: string; progress: number }
    | { type: "video_job_status"; jobId: string; clipId: string; status: string; error?: string }
    | { type: "clip_output_ready"; clipId: string; output: ClipOutput }
    | { type: "batch_progress"; batchId: string; done: number; total: number }
    | { type: "analytics_updated"; chapterId: string }
    | { type: "release_ready"; chapterId: string; bundleUrl: string }

// ============ Job 系统（统一任务模型）============

export type JobType = "image_job" | "anchor_job" | "video_job" | "export_job"
export type JobStatusType = "queued" | "running" | "succeeded" | "failed" | "needs_fix" | "canceled"

export interface Job {
    id: string
    type: JobType
    project_id: string
    chapter_id: string
    panel_id?: string
    clip_id?: string
    provider: string
    attempt: number
    max_attempts: number
    progress: number
    eta?: number
    started_at?: string
    finished_at?: string
    cost: { estimated: number; used: number }
    inputs: Record<string, unknown>
    outputs?: Record<string, unknown>
    qa?: { score: number; issues: string[] }
    error?: { code: string; message: string; detail?: unknown }
    created_at: string
    updated_at: string
}

export interface JobCreateRequest {
    type: JobType
    panel_id?: string
    clip_id?: string
    provider?: string
    inputs?: Record<string, unknown>
}

// ============ Timeline / Clips ============

export interface ClipOutput {
    video_url?: string
    preview_url?: string
    frames?: string[]
}

export interface Clip {
    id: string
    chapter_id: string
    panel_id: string
    order_index: number
    duration_sec: number
    fps: number
    provider: string
    motion_prompt: string
    status: string
    progress: number
    output?: ClipOutput
    created_at: string
    updated_at: string
}

export interface Timeline {
    chapter_id: string
    clips: Clip[]
    settings: {
        fps_default: number
        aspect: string
        export_preset: string
    }
    updated_at: string
}

// ============ Bindings ============

export interface ChapterBindings {
    chapter_id: string
    identity_asset_ids: string[]
    scene_asset_ids: string[]
    style_profile_id?: string
    anchor_ids: string[]
    qa_config?: {
        threshold: number
        max_issues: number
    }
    retry_policy?: {
        max_attempts: number
        provider_chain: string[]
        budget: { max_cost: number; cost_used: number }
    }
}

// ============ Analytics ============

export interface ChapterAnalytics {
    chapter_id: string
    by_provider: ProviderStats[]
    by_character: CharacterStats[]
    chapter_summary: {
        total_cost: number
        avg_score: number
        total_clips: number
        succeeded: number
        needs_fix: number
        failed: number
        total_retries: number
    }
    computed_at: string
}

export interface ProviderStats {
    provider: string
    cost_used: number
    avg_score: number
    success_rate: number
    retry_rate: number
    job_count: number
}

export interface CharacterStats {
    asset_id: string
    asset_name: string
    cost_used: number
    avg_score: number
    success_rate: number
    usage_count: number
}

// ============ Release Bundle ============

export interface ReleaseBundle {
    id: string
    project_id: string
    chapter_id: string
    release_version: string
    bundle_url: string
    export_spec_url?: string
    qa_report_url?: string
    analytics: ChapterAnalytics
    generated_at: string
    notes?: string
}

