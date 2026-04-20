import { RenderJob, LayerPack } from '../schema/job'
import { ExtendedLayerPack } from '../schema/layerPack'
import { VideoJob } from '../schema/videoJob'
import { Clip, ClipOutput } from '../schema/clip'
import { ExportSpec } from '../schema/exportSpec'

// ============ WS Event Types ============

export type WsEventType =
    | 'job_created'
    | 'job_progress'
    | 'job_status'
    | 'panel_status'
    | 'layerpack_ready'
    | 'qa_result'
    // Video Job Events (Task 06)
    | 'video_job_created'
    | 'video_job_progress'
    | 'video_job_status'
    | 'clip_status'
    | 'clip_output_ready'
    // Export Job Events (Task 06)
    | 'export_job_created'
    | 'export_job_progress'
    | 'export_job_status'
    | 'export_ready'
    // Export events from backend workers
    | 'export_progress'
    | 'export_status'
    // Storyboard Events (Task S2)
    | 'storyboard_progress'
    | 'storyboard_done'
    | 'storyboard_error'
    // Draft Events (Task S3-02)
    | 'storyboard_draft_ready'
    // Unified Job Events (Task 09)
    | 'job_result'

export interface WsEventBase {
    type: WsEventType
    ts: string
}

export interface JobCreatedEvent extends WsEventBase {
    type: 'job_created'
    payload: {
        job: RenderJob
    }
}

export interface JobProgressEvent extends WsEventBase {
    type: 'job_progress'
    payload: {
        jobId: string
        progress: number
        message?: string
        agent?: string
    }
}

export interface JobStatusEvent extends WsEventBase {
    type: 'job_status'
    payload: {
        jobId: string
        status: 'Queued' | 'Running' | 'Succeeded' | 'Failed'
        error?: string
    }
}

export interface PanelStatusEvent extends WsEventBase {
    type: 'panel_status'
    payload: {
        panelId: string
        status: 'Draft' | 'Queued' | 'Running' | 'Rendered' | 'NeedsFix'
    }
}

export interface LayerpackReadyEvent extends WsEventBase {
    type: 'layerpack_ready'
    payload: {
        panelId: string
        layerPack: LayerPack | ExtendedLayerPack
    }
}

export interface QaResultEvent extends WsEventBase {
    type: 'qa_result'
    payload: {
        panelId: string
        jobId: string
        score: number
        issues: string[]
    }
}

// ============ Video Job Events (Task 06) — @deprecated: use unified job_progress/job_status/job_result ============

/** @deprecated Use unified job events instead */
export interface VideoJobCreatedEvent extends WsEventBase {
    type: 'video_job_created'
    payload: {
        videoJob: VideoJob
        clipId: string
    }
}

export interface VideoJobProgressEvent extends WsEventBase {
    type: 'video_job_progress'
    payload: {
        videoJobId: string
        clipId: string
        progress: number
    }
}

export interface VideoJobStatusEvent extends WsEventBase {
    type: 'video_job_status'
    payload: {
        videoJobId: string
        clipId: string
        status: 'Queued' | 'Running' | 'Succeeded' | 'Failed'
        error?: string
    }
}

export interface ClipStatusEvent extends WsEventBase {
    type: 'clip_status'
    payload: {
        clipId: string
        status: 'Idle' | 'Queued' | 'Running' | 'Succeeded' | 'Failed'
    }
}

export interface ClipOutputReadyEvent extends WsEventBase {
    type: 'clip_output_ready'
    payload: {
        clipId: string
        output: ClipOutput
    }
}

// ============ Export Job Events (Task 06) — @deprecated: use unified job_progress/job_status/job_result ============

/** @deprecated Use unified job events instead */
export interface ExportJobCreatedEvent extends WsEventBase {
    type: 'export_job_created'
    payload: {
        exportJobId: string
        chapterId: string
    }
}

export interface ExportJobProgressEvent extends WsEventBase {
    type: 'export_job_progress'
    payload: {
        exportJobId: string
        progress: number
    }
}

export interface ExportJobStatusEvent extends WsEventBase {
    type: 'export_job_status'
    payload: {
        exportJobId: string
        status: 'Queued' | 'Running' | 'Succeeded' | 'Failed'
        error?: string
    }
}

export interface ExportReadyEvent extends WsEventBase {
    type: 'export_ready'
    payload: {
        exportJobId: string
        exportSpec: ExportSpec
    }
}

export interface StoryboardProgressEvent extends WsEventBase {
    type: 'storyboard_progress'
    payload: {
        jobId: string
        stage: 'validating' | 'analyzing' | 'planning' | 'generating' | 'writing_db' | 'done'
        progress: number
        message?: string
        panelIndex?: number
        totalPanels?: number
    }
}

export interface StoryboardDoneEvent extends WsEventBase {
    type: 'storyboard_done'
    payload: {
        jobId: string
        chapterId: string
        panelsCount: number
        firstPanelId: string
    }
}

export interface StoryboardErrorEvent extends WsEventBase {
    type: 'storyboard_error'
    payload: {
        jobId: string
        chapterId: string
        errorCode: string
        message: string
    }
}

// S3-02: Draft Ready Event
export interface StoryboardDraftReadyEvent extends WsEventBase {
    type: 'storyboard_draft_ready'
    payload: {
        jobId: string
        chapterId: string
        draftId: string
        panelsCount: number
        charactersCount: number
        scenesCount: number
    }
}

// ============ Unified Job Events (Task 09) ============

/** @deprecated Use JobProgressEvent instead — unified events share the same shape */
export interface UnifiedJobProgressEvent extends WsEventBase {
  type: 'job_progress'
  payload: {
    jobId: string
    progress: number
    message?: string
  }
}

/** @deprecated Use JobStatusEvent instead — unified events share the same shape */
export interface UnifiedJobStatusEvent extends WsEventBase {
  type: 'job_status'
  payload: {
    jobId: string
    status: 'queued' | 'running' | 'succeeded' | 'failed' | 'canceled'
    type?: string
    error?: string
  }
}

export interface UnifiedJobResultEvent extends WsEventBase {
  type: 'job_result'
  payload: {
    jobId: string
    type: string
    result: Record<string, unknown>
  }
}

export type WsEvent =
    | JobCreatedEvent
    | JobProgressEvent
    | JobStatusEvent
    | PanelStatusEvent
    | LayerpackReadyEvent
    | QaResultEvent
    | VideoJobCreatedEvent
    | VideoJobProgressEvent
    | VideoJobStatusEvent
    | ClipStatusEvent
    | ClipOutputReadyEvent
    | ExportJobCreatedEvent
    | ExportJobProgressEvent
    | ExportJobStatusEvent
    | ExportReadyEvent
    | StoryboardProgressEvent
    | StoryboardDoneEvent
    | StoryboardErrorEvent
    | StoryboardDraftReadyEvent
    | UnifiedJobResultEvent

// ============ Helper Functions ============

export function createWsEvent<T extends WsEventType>(
    type: T,
    payload: Extract<WsEvent, { type: T }>['payload']
): Extract<WsEvent, { type: T }> {
    return {
        type,
        payload,
        ts: new Date().toISOString(),
    } as Extract<WsEvent, { type: T }>
}
