import { create } from 'zustand'
import { PanelSpec, ChapterSpec, createDefaultPanelSpec } from '@/lib/schema'
import { RenderJob, LayerPack, RenderProvider, createRenderJob } from '@/lib/schema/job'
import { ExtendedLayerPack, createExtendedLayerPack } from '@/lib/schema/layerPack'
import { FixPlan, FixStrategy, Roi, createDefaultFixPlan } from '@/lib/schema/fixPlan'
import { Clip, ClipStatus, createDefaultClip } from '@/lib/schema/clip'
import { VideoJob, createVideoJob } from '@/lib/schema/videoJob'
import { Timeline, TimelineSettings, createDefaultTimeline, calculateTotalDuration } from '@/lib/schema/timeline'
import { ExportSpec, ExportJob, createExportJob } from '@/lib/schema/exportSpec'
import { Provider } from '@/lib/schema/provider'
import { WsEvent } from '@/lib/ws/events'
import { connect, getConnection } from '@/lib/ws/client'

interface PanelListItem {
  id: string
  index: number
  title: string
  description?: string
  location?: string
  shotType?: string
  duration?: number
  status: 'Draft' | 'Queued' | 'Running' | 'Rendered' | 'NeedsFix'
  previewUrl?: string  // P0: 渲染预览图 URL
}

// Viewer 状态
interface ViewerState {
  layerVisibility: { bg: boolean; char: boolean; fg: boolean; text: boolean }
  layerOpacity: { bg: number; char: number; fg: number; text: number }
  roi: Roi | null
  isRoiSelecting: boolean
}

// FixModal 状态
interface FixModalState {
  open: boolean
  draft: FixPlan | null
}

// Storyboard Job State
interface StoryboardJobState {
  id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  progress: number
  stage: string
  message?: string
  updatedAt: string
}

// Asset Summary (from backend)
interface AssetSummary {
  id: string
  name: string
  thumbnail_url?: string
  face_embedding_status?: 'none' | 'pending' | 'ready'
  anchor_status?: 'none' | 'pending' | 'ready'
}

interface StudioStore {
  // Context
  projectId: string | null
  chapterId: string | null

  // Storyboard Job (S2)
  storyboardJob: StoryboardJobState | null

  // Panel management
  selectedPanelId: string | null
  panelList: PanelListItem[]
  panelSpecs: Record<string, PanelSpec>

  // Render Jobs
  jobs: Record<string, RenderJob>
  jobOrder: string[]
  layerPacks: Record<string, LayerPack | ExtendedLayerPack>
  panelLatestLayerPack: Record<string, string>
  needsFixPanelIds: string[]

  // LayerPack 版本管理 (Task 05)
  layerPacksByPanel: Record<string, string[]>
  selectedLayerPackIdByPanel: Record<string, string>

  // Viewer 状态 (Task 05)
  viewer: ViewerState

  // FixModal 状态 (Task 05)
  fixModal: FixModalState

  // Timeline 状态 (Task 06)
  timelineByChapter: Record<string, Timeline>
  videoJobs: Record<string, VideoJob>
  videoJobOrder: string[]
  exportJobs: Record<string, ExportJob>
  exportJobOrder: string[]
  selectedClipId: string | null

  // UI state
  isDirty: boolean

  // Script (章节剧本)
  script: string

  // Assets (S3-01)
  characters: AssetSummary[]
  scenes: AssetSummary[]
  styles: AssetSummary[]
  props: AssetSummary[]

  // Draft (S3-02)
  pendingDraftId: string | null
  showDraftModal: boolean

  // Assets Lock (S3-06)
  canRender: boolean
  pendingAssetsCount: number
  showAssetsLockPanel: boolean
  activeInspectorTab: string  // S3-08: 用于自动切换 tab

  // S4-01-02: Storyboard Settings (style + constraints)
  storyboardSettings: {
    stylePreset: string
    constraints: {
      panelsMin: number
      panelsMax: number
      totalDurationMin: number
      totalDurationMax: number
      perPanelDurationMin: number
      perPanelDurationMax: number
    }
  } | null
  setStoryboardSettings: (settings: StudioStore['storyboardSettings']) => void

  // Actions
  setContext: (projectId: string, chapterId: string) => void
  setPanelList: (list: PanelListItem[]) => void
  selectPanel: (id: string) => void
  setSelectedPanelId: (id: string | null) => void
  setDirty: (dirty: boolean) => void
  setScript: (script: string) => void
  reset: () => void

  // Data Sync
  setStudioData: (data: any) => void
  refreshChapterData: (chapterId: string) => Promise<void>  // S3-08: 统一刷新方法

  // PanelSpec actions
  setPanelSpec: (panelId: string, patch: Partial<PanelSpec>) => void
  replacePanelSpec: (panelId: string, spec: PanelSpec) => void
  loadChapterDraft: (projectId: string, chapterId: string) => void
  saveChapterDraft: () => void
  exportChapterSpec: () => string
  importChapterSpec: (json: string) => void

  // Render Job actions
  enqueueRender: (panelIds: string[], provider?: RenderProvider) => void
  applyWsEvent: (event: WsEvent) => void
  retryJob: (jobId: string) => void
  getJobsForChapter: () => RenderJob[]
  updatePanelStatus: (panelId: string, status: PanelListItem['status']) => void

  // LayerPack 版本管理 (Task 05)
  selectLayerPack: (panelId: string, layerPackId: string) => void
  getSelectedLayerPack: () => (LayerPack | ExtendedLayerPack) | null
  getLayerPacksForPanel: (panelId: string) => (LayerPack | ExtendedLayerPack)[]

  // Viewer 控制 (Task 05)
  setLayerVisibility: (layer: keyof ViewerState['layerVisibility'], visible: boolean) => void
  setLayerOpacity: (layer: keyof ViewerState['layerOpacity'], opacity: number) => void
  setRoi: (roi: Roi | null) => void
  clearRoi: () => void
  setIsRoiSelecting: (selecting: boolean) => void

  // FixModal 控制 (Task 05)
  openFixModal: (panelId: string, strategy?: FixStrategy) => void
  closeFixModal: () => void
  updateFixPlanDraft: (patch: Partial<FixPlan>) => void
  submitFixPlan: () => void

  // Helpers
  getSelectedSpec: () => PanelSpec | null
  getPanelSummary: (panelId: string) => {
    title: string
    duration: number
    weather: string
    location: string
    characterCount: number
  } | null

  // Timeline 方法 (Task 06)
  getTimelineKey: (projectId: string, chapterId: string) => string
  ensureTimeline: (projectId: string, chapterId: string) => Timeline
  addPanelAsClip: (panelId: string) => void
  removeClip: (clipId: string) => void
  reorderClip: (clipId: string, direction: 'up' | 'down') => void
  updateClip: (clipId: string, patch: Partial<Clip>) => void
  selectClip: (clipId: string | null) => void
  enqueueClipRender: (clipId: string) => void
  retryClipRender: (clipId: string) => void
  buildExportSpec: () => ExportSpec | null
  enqueueExport: () => void
  getClipsForChapter: () => Clip[]
  getSelectedClip: () => Clip | null
  updateTimelineSettings: (settings: Partial<TimelineSettings>) => void
}

const initialViewerState: ViewerState = {
  layerVisibility: { bg: true, char: true, fg: true, text: true },
  layerOpacity: { bg: 1, char: 1, fg: 1, text: 1 },
  roi: null,
  isRoiSelecting: false,
}

const initialFixModalState: FixModalState = {
  open: false,
  draft: null,
}

const initialState = {
  projectId: null as string | null,
  chapterId: null as string | null,
  selectedPanelId: null as string | null,
  panelList: [] as PanelListItem[],
  panelSpecs: {} as Record<string, PanelSpec>,
  jobs: {} as Record<string, RenderJob>,
  jobOrder: [] as string[],
  layerPacks: {} as Record<string, LayerPack | ExtendedLayerPack>,
  panelLatestLayerPack: {} as Record<string, string>,
  needsFixPanelIds: [] as string[],
  layerPacksByPanel: {} as Record<string, string[]>,
  selectedLayerPackIdByPanel: {} as Record<string, string>,
  viewer: initialViewerState,
  fixModal: initialFixModalState,
  // Timeline 状态 (Task 06)
  timelineByChapter: {} as Record<string, Timeline>,
  videoJobs: {} as Record<string, VideoJob>,
  videoJobOrder: [] as string[],
  exportJobs: {} as Record<string, ExportJob>,
  exportJobOrder: [] as string[],
  selectedClipId: null as string | null,
  isDirty: false,
  script: '',
  storyboardJob: null as StoryboardJobState | null,
  // Assets (S3-01)
  characters: [] as AssetSummary[],
  scenes: [] as AssetSummary[],
  styles: [] as AssetSummary[],
  props: [] as AssetSummary[],
  // Draft (S3-02)
  pendingDraftId: null as string | null,
  showDraftModal: false,
  // Assets Lock (S3-06)
  canRender: true,
  pendingAssetsCount: 0,
  showAssetsLockPanel: false,
  activeInspectorTab: 'story',  // S3-08: 默认 tab
  // S4-01-02: Storyboard Settings
  storyboardSettings: null as StudioStore['storyboardSettings'],
}

export const useStudioStore = create<StudioStore>((set, get) => ({
  ...initialState,

  setContext: (projectId, chapterId) => set({ projectId, chapterId }),
  setPanelList: (list) => set({ panelList: list }),
  selectPanel: (id) => set({ selectedPanelId: id }),
  setSelectedPanelId: (id) => set({ selectedPanelId: id }),
  setDirty: (dirty) => set({ isDirty: dirty }),
  setScript: (script) => set({ script }),
  reset: () => set(initialState),
  // S4-01-02: Storyboard Settings
  setStoryboardSettings: (settings) => set({ storyboardSettings: settings }),

  setStudioData: (data) => {
    // 从后端 StudioData 转换到 Store 状态
    const panelSpecs: Record<string, PanelSpec> = {}
    const panelList: PanelListItem[] = []

    // 处理 Panels
    if (data.panels_by_id) {
      Object.values(data.panels_by_id).forEach((p: any) => {
        if (p.spec_json) {
          panelSpecs[p.id] = p.spec_json
        }
      })
    }

    if (data.panels) {
      data.panels.forEach((p: any) => {
        // P0: Extract previewUrl from spec_json.render if available
        const specJson = p.spec_json || {}
        const previewUrl = specJson.render?.preview_url

        panelList.push({
          id: p.id,
          index: p.order_index,
          title: p.title || `Panel ${p.order_index + 1}`,
          description: p.summary,
          status: p.render_status,
          previewUrl: previewUrl,
          // 其他字段根据需要映射
        })
      })
    }

    // 更新 Script
    const script = data.chapter?.script_raw || ''

    // 提取 Assets (S3-01)
    const characters: AssetSummary[] = (data.assets?.characters || []).map((a: any) => ({
      id: a.id,
      name: a.name,
      thumbnail_url: a.thumbnail_url,
      face_embedding_status: a.face_embedding_status || 'none',
    }))
    const scenes: AssetSummary[] = (data.assets?.scenes || []).map((a: any) => ({
      id: a.id,
      name: a.name,
      thumbnail_url: a.thumbnail_url,
      anchor_status: a.anchor_status || 'none',
    }))
    const styles: AssetSummary[] = (data.assets?.styles || []).map((a: any) => ({
      id: a.id,
      name: a.name,
      thumbnail_url: a.thumbnail_url,
    }))

    // S5-04: Props
    const props: AssetSummary[] = (data.assets?.props || []).map((a: any) => ({
      id: a.id,
      name: a.canonical_name,
      thumbnail_url: a.ref_image_paths?.[0], // Use first ref image as thumbnail
    }))

    // P0-TL-FIX-01: 加载 Timeline 数据
    let timelineUpdate: Partial<StudioStore> = {}
    if (data.chapter?.timeline_json?.clips?.length > 0) {
      const tl = data.chapter.timeline_json
      const timelineKey = `${data.chapter.project_id}::${data.chapter.id}`
      const now = new Date().toISOString()
      const clips: Clip[] = tl.clips.map((c: any, idx: number) => ({
        id: c.id || `clip_${idx}`,
        projectId: data.chapter.project_id,
        chapterId: data.chapter.id,
        panelId: c.panelId || c.panel_id || '',
        layerPackId: c.layerPackId || null,
        type: c.type || 'motion_clip',
        startFrame: c.startFrame || null,
        endFrame: c.endFrame || null,
        motionMode: c.motionMode || 'dual_keyframe',
        cameraPlan: c.cameraPlan,
        durationSec: c.durationSec || (c.durationMs || c.duration_ms || 3000) / 1000,
        fps: c.fps || 24,
        provider: c.provider || 'mock',
        motionPrompt: c.motionPrompt || '',
        negative: c.negative || '',
        seedMode: c.seedMode || 'new',
        status: (c.status || 'Idle') as ClipStatus,
        progress: c.progress || 0,
        output: c.output || undefined,
        error: c.error,
        createdAt: c.createdAt || now,
        updatedAt: c.updatedAt || now,
      }))

      timelineUpdate = {
        timelineByChapter: {
          ...get().timelineByChapter,
          [timelineKey]: {
            projectId: data.chapter.project_id,
            chapterId: data.chapter.id,
            clips,
            settings: {
              fpsDefault: tl.settings?.fpsDefault || 24,
              aspect: tl.settings?.aspect || '9:16',
              exportPreset: tl.settings?.exportPreset || 'draft'
            },
            meta: { updatedAt: new Date().toISOString() }
          }
        },
        selectedClipId: clips[0]?.id || null  // 自动选中第一个 clip
      }
    }

    set({
      panelSpecs,
      panelList,
      script,
      characters,
      scenes,
      styles,
      props,
      ...timelineUpdate,  // P0-TL-FIX-01: 合并 timeline 状态
      // 如果有正在运行的分镜任务，也要恢复状态
      storyboardJob: data.chapter?.layout_json?.storyboard_job_id ? {
        id: data.chapter.layout_json.storyboard_job_id,
        status: data.chapter.layout_json.status === 'storyboarded' ? 'succeeded' : 'running',
        progress: 0,
        stage: 'unknown',
        updatedAt: new Date().toISOString()
      } : null
    })
  },

  // S3-08: 统一刷新章节数据（panels + assets lock + render status）
  refreshChapterData: async (chapterId: string) => {
    try {
      // 1. 刷新 studio 数据（panels）
      const { chaptersApi } = await import('@/lib/api/services')
      const studioData = await chaptersApi.getStudio(chapterId)
      get().setStudioData(studioData)

      // 2. 刷新 assets lock
      try {
        const assetsLock = await chaptersApi.getAssetsLock(chapterId)
        set({
          canRender: assetsLock.can_render,
          pendingAssetsCount: assetsLock.stats.pending_count
        })
      } catch (e) {
        console.warn('Failed to refresh assets lock:', e)
      }

      // 3. 刷新 render status
      try {
        const renderStatus = await chaptersApi.getRenderStatus(chapterId)
        // 可以根据需要更新 panelRenderStateMap
      } catch (e) {
        console.warn('Failed to refresh render status:', e)
      }
    } catch (error) {
      console.error('Failed to refresh chapter data:', error)
    }
  },

  // PanelSpec operations
  setPanelSpec: (panelId, patch) => {
    const state = get()
    const existing = state.panelSpecs[panelId]
    if (!existing) return

    const updated = {
      ...existing,
      ...patch,
      meta: {
        ...existing.meta,
        updatedAt: new Date().toISOString(),
      },
    }

    set({
      panelSpecs: {
        ...state.panelSpecs,
        [panelId]: updated,
      },
      isDirty: true,
    })
  },

  replacePanelSpec: (panelId, spec) => {
    const state = get()
    set({
      panelSpecs: {
        ...state.panelSpecs,
        [panelId]: spec,
      },
      isDirty: true,
    })
  },

  getSelectedSpec: () => {
    const state = get()
    if (!state.selectedPanelId) return null
    return state.panelSpecs[state.selectedPanelId] || null
  },

  getPanelSummary: (panelId) => {
    const state = get()
    const spec = state.panelSpecs[panelId]
    if (!spec) return null

    return {
      title: `${spec.scene.location} / ${spec.shot.shotType}`,
      duration: spec.shot.durationSec,
      weather: spec.scene.weather,
      location: spec.scene.location,
      characterCount: spec.characters.length,
    }
  },

  // ============ Render Job Actions ============

  enqueueRender: (panelIds, provider = 'mock') => {
    const state = get()
    if (!state.projectId || !state.chapterId) return

    const connection = getConnection() || connect()
    const newJobs: Record<string, RenderJob> = {}
    const newJobOrder: string[] = []

    panelIds.forEach((panelId) => {
      const job = createRenderJob(panelId, state.chapterId!, state.projectId!, provider)
      newJobs[job.id] = job
      newJobOrder.push(job.id)
      connection.startRenderJob(job)
    })

    set({
      jobs: { ...state.jobs, ...newJobs },
      jobOrder: [...state.jobOrder, ...newJobOrder],
    })
  },

  applyWsEvent: (event) => {
    const state = get()

    switch (event.type) {
      case 'job_created': {
        const { job } = event.payload
        set({
          jobs: { ...state.jobs, [job.id]: job },
          jobOrder: [...state.jobOrder, job.id],
        })
        break
      }

      case 'job_progress': {
        const { jobId, progress } = event.payload
        const job = state.jobs[jobId]
        if (job) {
          set({
            jobs: {
              ...state.jobs,
              [jobId]: { ...job, progress, status: 'Running', updatedAt: new Date().toISOString() },
            },
          })
        }
        break
      }

      case 'job_status': {
        const { jobId, status, error } = event.payload
        const job = state.jobs[jobId]
        if (job) {
          const updated: RenderJob = {
            ...job,
            status,
            updatedAt: new Date().toISOString(),
            ...(error && { error }),
          }
          set({
            jobs: { ...state.jobs, [jobId]: updated },
          })
        }
        break
      }

      case 'panel_status': {
        const { panelId, status } = event.payload
        get().updatePanelStatus(panelId, status)

        if (status === 'NeedsFix') {
          const current = get().needsFixPanelIds
          if (!current.includes(panelId)) {
            set({ needsFixPanelIds: [...current, panelId] })
          }
        } else if (status === 'Rendered') {
          const current = get().needsFixPanelIds
          set({ needsFixPanelIds: current.filter((id) => id !== panelId) })
        }
        break
      }

      case 'layerpack_ready': {
        const { panelId, layerPack } = event.payload
        const currentState = get()

        // 更新 layerPacks
        const newLayerPacks = { ...currentState.layerPacks, [layerPack.id]: layerPack }

        // 更新 layerPacksByPanel（版本列表）
        const currentVersions = currentState.layerPacksByPanel[panelId] || []
        const newVersions = [...currentVersions, layerPack.id]
        const newLayerPacksByPanel = { ...currentState.layerPacksByPanel, [panelId]: newVersions }

        // 自动选中最新版本
        const newSelectedLayerPackIdByPanel = {
          ...currentState.selectedLayerPackIdByPanel,
          [panelId]: layerPack.id
        }

        set({
          layerPacks: newLayerPacks,
          panelLatestLayerPack: { ...currentState.panelLatestLayerPack, [panelId]: layerPack.id },
          layerPacksByPanel: newLayerPacksByPanel,
          selectedLayerPackIdByPanel: newSelectedLayerPackIdByPanel,
        })
        break
      }

      case 'qa_result': {
        const { panelId, score, issues } = event.payload
        const spec = state.panelSpecs[panelId]
        if (spec) {
          const updated = {
            ...spec,
            qa: { score, issues },
            meta: { ...spec.meta, updatedAt: new Date().toISOString() },
          }
          set({
            panelSpecs: { ...state.panelSpecs, [panelId]: updated as PanelSpec },
          })
        }
        break
      }

      // ============ Video Job Events (Task 06) ============

      case 'video_job_created': {
        const { videoJob } = event.payload
        set({
          videoJobs: { ...state.videoJobs, [videoJob.id]: videoJob },
          videoJobOrder: [...state.videoJobOrder, videoJob.id],
        })
        break
      }

      case 'video_job_progress': {
        const { videoJobId, clipId, progress } = event.payload
        const videoJob = state.videoJobs[videoJobId]
        if (videoJob) {
          set({
            videoJobs: {
              ...state.videoJobs,
              [videoJobId]: { ...videoJob, progress, status: 'Running', updatedAt: new Date().toISOString() },
            },
          })
        }
        // 同时更新 clip 的 progress
        get().updateClip(clipId, { progress })
        break
      }

      case 'video_job_status': {
        const { videoJobId, status, error } = event.payload
        const videoJob = state.videoJobs[videoJobId]
        if (videoJob) {
          set({
            videoJobs: {
              ...state.videoJobs,
              [videoJobId]: { ...videoJob, status, updatedAt: new Date().toISOString(), ...(error && { error }) },
            },
          })
        }
        break
      }

      case 'clip_status': {
        const { clipId, status } = event.payload
        get().updateClip(clipId, { status })
        break
      }

      case 'clip_output_ready': {
        const { clipId, output } = event.payload
        get().updateClip(clipId, { output })
        break
      }

      // ============ Export Job Events (Task 06) ============

      case 'export_job_created': {
        const { exportJobId, chapterId } = event.payload
        const exportJob: ExportJob = {
          id: exportJobId,
          chapterId,
          status: 'Queued',
          progress: 0,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        }
        set({
          exportJobs: { ...state.exportJobs, [exportJobId]: exportJob },
          exportJobOrder: [...state.exportJobOrder, exportJobId],
        })
        break
      }

      case 'export_job_progress': {
        const { exportJobId, progress } = event.payload
        const exportJob = state.exportJobs[exportJobId]
        if (exportJob) {
          set({
            exportJobs: {
              ...state.exportJobs,
              [exportJobId]: { ...exportJob, progress, status: 'Running', updatedAt: new Date().toISOString() },
            },
          })
        }
        break
      }

      case 'export_job_status': {
        const { exportJobId, status, error } = event.payload
        const exportJob = state.exportJobs[exportJobId]
        if (exportJob) {
          set({
            exportJobs: {
              ...state.exportJobs,
              [exportJobId]: { ...exportJob, status, updatedAt: new Date().toISOString(), ...(error && { error }) },
            },
          })
        }
        break
      }

      case 'export_ready': {
        const { exportJobId, exportSpec } = event.payload
        const exportJob = state.exportJobs[exportJobId]
        if (exportJob) {
          set({
            exportJobs: {
              ...state.exportJobs,
              [exportJobId]: { ...exportJob, outputSpecUrl: JSON.stringify(exportSpec), updatedAt: new Date().toISOString() },
            },
          })
        }
        break
      }

      // ============ Storyboard Events (S2) ============

      case 'storyboard_progress': {
        const { jobId, stage, progress, message } = event.payload
        set({
          storyboardJob: {
            id: jobId,
            status: 'running',
            stage,
            progress,
            message,
            updatedAt: new Date().toISOString()
          }
        })
        break
      }

      case 'storyboard_done': {
        const { jobId } = event.payload
        const currentJob = get().storyboardJob
        if (currentJob && currentJob.id === jobId) {
          set({
            storyboardJob: {
              ...currentJob,
              status: 'succeeded',
              progress: 100,
              stage: 'done',
              message: 'Done',
              updatedAt: new Date().toISOString()
            }
          })
        }
        break
      }

      case 'storyboard_error': {
        const { jobId, message } = event.payload
        const currentJob = get().storyboardJob
        if (currentJob && currentJob.id === jobId) {
          set({
            storyboardJob: {
              ...currentJob,
              status: 'failed',
              message,
              updatedAt: new Date().toISOString()
            }
          })
        }
        break
      }

      // S3-02: Draft ready event
      case 'storyboard_draft_ready': {
        const { jobId, draftId, chapterId } = event.payload
        const currentJob = get().storyboardJob
        if (currentJob && currentJob.id === jobId) {
          set({
            storyboardJob: {
              ...currentJob,
              status: 'succeeded',
              stage: 'done',
              progress: 100,
              updatedAt: new Date().toISOString()
            },
            pendingDraftId: draftId,
            showDraftModal: true
          })
        }
        break
      }
    }
  },

  retryJob: (jobId) => {
    const state = get()
    const oldJob = state.jobs[jobId]
    if (!oldJob || oldJob.status !== 'Failed' || !oldJob.panelId) return
    get().enqueueRender([oldJob.panelId], oldJob.provider)
  },

  getJobsForChapter: () => {
    const state = get()
    return state.jobOrder
      .map((id) => state.jobs[id])
      .filter((job) => job && job.projectId === state.projectId && job.chapterId === state.chapterId)
  },

  updatePanelStatus: (panelId, status) => {
    const state = get()
    const updatedList = state.panelList.map((item) =>
      item.id === panelId ? { ...item, status } : item
    )
    const spec = state.panelSpecs[panelId]
    if (spec) {
      const renderStatus = status === 'Queued' || status === 'Running' ? 'Draft' : status
      const updatedSpec = {
        ...spec,
        render: { ...spec.render, status: renderStatus as 'Draft' | 'Rendered' | 'NeedsFix' },
        meta: { ...spec.meta, updatedAt: new Date().toISOString() },
      }
      set({
        panelList: updatedList,
        panelSpecs: { ...state.panelSpecs, [panelId]: updatedSpec },
      })
    } else {
      set({ panelList: updatedList })
    }
  },

  // ============ LayerPack 版本管理 (Task 05) ============

  selectLayerPack: (panelId, layerPackId) => {
    const state = get()
    set({
      selectedLayerPackIdByPanel: {
        ...state.selectedLayerPackIdByPanel,
        [panelId]: layerPackId,
      },
    })
  },

  getSelectedLayerPack: () => {
    const state = get()
    if (!state.selectedPanelId) return null
    const layerPackId = state.selectedLayerPackIdByPanel[state.selectedPanelId]
    if (!layerPackId) return null
    return state.layerPacks[layerPackId] || null
  },

  getLayerPacksForPanel: (panelId) => {
    const state = get()
    const ids = state.layerPacksByPanel[panelId] || []
    return ids.map((id) => state.layerPacks[id]).filter(Boolean)
  },

  // ============ Viewer 控制 (Task 05) ============

  setLayerVisibility: (layer, visible) => {
    const state = get()
    set({
      viewer: {
        ...state.viewer,
        layerVisibility: { ...state.viewer.layerVisibility, [layer]: visible },
      },
    })
  },

  setLayerOpacity: (layer, opacity) => {
    const state = get()
    set({
      viewer: {
        ...state.viewer,
        layerOpacity: { ...state.viewer.layerOpacity, [layer]: opacity },
      },
    })
  },

  setRoi: (roi) => {
    const state = get()
    set({
      viewer: { ...state.viewer, roi, isRoiSelecting: false },
    })
  },

  clearRoi: () => {
    const state = get()
    set({
      viewer: { ...state.viewer, roi: null },
    })
  },

  setIsRoiSelecting: (selecting) => {
    const state = get()
    set({
      viewer: { ...state.viewer, isRoiSelecting: selecting },
    })
  },

  // ============ FixModal 控制 (Task 05) ============

  openFixModal: (panelId, strategy = 'inpaint') => {
    const state = get()
    const layerPackId = state.selectedLayerPackIdByPanel[panelId] ||
      state.panelLatestLayerPack[panelId] || ''

    const draft = createDefaultFixPlan(panelId, layerPackId, strategy)
    // 如果有 ROI，自动填入
    if (state.viewer.roi) {
      draft.roi = state.viewer.roi
    }

    set({
      fixModal: { open: true, draft },
    })
  },

  closeFixModal: () => {
    set({
      fixModal: { open: false, draft: null },
    })
  },

  updateFixPlanDraft: (patch) => {
    const state = get()
    if (!state.fixModal.draft) return
    set({
      fixModal: {
        ...state.fixModal,
        draft: { ...state.fixModal.draft, ...patch },
      },
    })
  },

  submitFixPlan: () => {
    const state = get()
    const { draft } = state.fixModal
    if (!draft) return

    // 创建 RenderJob 并启动
    const provider = 'mock' as RenderProvider
    get().enqueueRender([draft.panelId], provider)

    // 关闭弹窗
    set({
      fixModal: { open: false, draft: null },
    })
  },

  // 丰富 PanelListItem 结构以支持更详细的列表展示
  // localStorage operations
  loadChapterDraft: (projectId, chapterId) => {
    const key = `ai-webtoon:chapterDraft:${projectId}:${chapterId}`

    try {
      const stored = localStorage.getItem(key)

      if (stored) {
        const chapterSpec: ChapterSpec = JSON.parse(stored)
        const panelSpecs: Record<string, PanelSpec> = {}
        const panelList: PanelListItem[] = []

        chapterSpec.panels.forEach((spec) => {
          panelSpecs[spec.id] = spec
          // 从 spec 中提取元数据以构建更丰富的列表项
          const title = spec.shot.description
            ? (spec.shot.description.length > 20 ? spec.shot.description.substring(0, 20) + '...' : spec.shot.description)
            : `Panel ${spec.index + 1}`

          panelList.push({
            id: spec.id,
            index: spec.index,
            title: title,
            description: spec.shot.description,
            location: spec.scene.location,
            shotType: spec.shot.shotType,
            duration: spec.shot.durationSec,
            status: spec.render.status,
          })
        })

        set({ panelSpecs, panelList, isDirty: false })
      } else {
        // 没有草稿数据时，返回空状态（不生成假数据）
        set({ panelSpecs: {}, panelList: [], isDirty: false })
      }
    } catch (error) {
      console.error('Failed to load chapter draft:', error)
    }
  },

  saveChapterDraft: () => {
    const state = get()
    if (!state.projectId || !state.chapterId) return

    const key = `ai-webtoon:chapterDraft:${state.projectId}:${state.chapterId}`

    const chapterSpec: ChapterSpec = {
      projectId: state.projectId,
      chapterId: state.chapterId,
      version: '1.0',
      panels: Object.values(state.panelSpecs).sort((a, b) => a.index - b.index),
    }

    try {
      localStorage.setItem(key, JSON.stringify(chapterSpec))
      set({ isDirty: false })
    } catch (error) {
      console.error('Failed to save chapter draft:', error)
    }
  },

  exportChapterSpec: () => {
    const state = get()
    if (!state.projectId || !state.chapterId) return ''

    const chapterSpec: ChapterSpec = {
      projectId: state.projectId,
      chapterId: state.chapterId,
      version: '1.0',
      panels: Object.values(state.panelSpecs).sort((a, b) => a.index - b.index),
    }

    return JSON.stringify(chapterSpec, null, 2)
  },

  importChapterSpec: (json) => {
    try {
      const chapterSpec: ChapterSpec = JSON.parse(json)

      if (!chapterSpec.projectId || !chapterSpec.chapterId || !Array.isArray(chapterSpec.panels)) {
        throw new Error('Invalid chapter spec format')
      }

      const panelSpecs: Record<string, PanelSpec> = {}
      const panelList: PanelListItem[] = []

      chapterSpec.panels.forEach((spec) => {
        panelSpecs[spec.id] = spec
        panelList.push({
          id: spec.id,
          index: spec.index,
          title: `Panel ${spec.index + 1}`,
          status: spec.render.status,
        })
      })

      set({
        projectId: chapterSpec.projectId,
        chapterId: chapterSpec.chapterId,
        panelSpecs,
        panelList,
        isDirty: true,
      })
    } catch (error) {
      console.error('Failed to import chapter spec:', error)
      throw error
    }
  },

  // ============ Timeline 方法 (Task 06) ============

  getTimelineKey: (projectId, chapterId) => {
    return `${projectId}:${chapterId}`
  },

  ensureTimeline: (projectId, chapterId) => {
    const state = get()
    const key = `${projectId}:${chapterId}`
    if (state.timelineByChapter[key]) {
      return state.timelineByChapter[key]
    }
    const timeline = createDefaultTimeline(projectId, chapterId)
    set({
      timelineByChapter: { ...state.timelineByChapter, [key]: timeline },
    })
    return timeline
  },

  addPanelAsClip: (panelId) => {
    const state = get()
    if (!state.projectId || !state.chapterId) return

    const key = `${state.projectId}:${state.chapterId}`
    const timeline = state.timelineByChapter[key] || createDefaultTimeline(state.projectId, state.chapterId)

    // 获取当前 panel 的 layerPackId
    const layerPackId = state.selectedLayerPackIdByPanel[panelId] ||
      state.panelLatestLayerPack[panelId] || null

    // 获取 panel 的 durationSec
    const panelSpec = state.panelSpecs[panelId]
    const durationSec = panelSpec?.shot?.durationSec || 3

    const clip = createDefaultClip(panelId, state.chapterId, state.projectId, layerPackId)
    clip.durationSec = durationSec
    clip.fps = timeline.settings.fpsDefault

    const updatedTimeline: Timeline = {
      ...timeline,
      clips: [...timeline.clips, clip],
      meta: { updatedAt: new Date().toISOString() },
    }

    set({
      timelineByChapter: { ...state.timelineByChapter, [key]: updatedTimeline },
      isDirty: true,
    })
  },

  removeClip: (clipId) => {
    const state = get()
    if (!state.projectId || !state.chapterId) return

    const key = `${state.projectId}:${state.chapterId}`
    const timeline = state.timelineByChapter[key]
    if (!timeline) return

    const updatedTimeline: Timeline = {
      ...timeline,
      clips: timeline.clips.filter((c) => c.id !== clipId),
      meta: { updatedAt: new Date().toISOString() },
    }

    set({
      timelineByChapter: { ...state.timelineByChapter, [key]: updatedTimeline },
      selectedClipId: state.selectedClipId === clipId ? null : state.selectedClipId,
      isDirty: true,
    })
  },

  reorderClip: (clipId, direction) => {
    const state = get()
    if (!state.projectId || !state.chapterId) return

    const key = `${state.projectId}:${state.chapterId}`
    const timeline = state.timelineByChapter[key]
    if (!timeline) return

    const clips = [...timeline.clips]
    const index = clips.findIndex((c) => c.id === clipId)
    if (index === -1) return

    const newIndex = direction === 'up' ? index - 1 : index + 1
    if (newIndex < 0 || newIndex >= clips.length) return

    // Swap
    [clips[index], clips[newIndex]] = [clips[newIndex], clips[index]]

    const updatedTimeline: Timeline = {
      ...timeline,
      clips,
      meta: { updatedAt: new Date().toISOString() },
    }

    set({
      timelineByChapter: { ...state.timelineByChapter, [key]: updatedTimeline },
      isDirty: true,
    })
  },

  updateClip: (clipId, patch) => {
    const state = get()
    if (!state.projectId || !state.chapterId) return

    const key = `${state.projectId}:${state.chapterId}`
    const timeline = state.timelineByChapter[key]
    if (!timeline) return

    const updatedClips = timeline.clips.map((c) =>
      c.id === clipId ? { ...c, ...patch, updatedAt: new Date().toISOString() } : c
    )

    const updatedTimeline: Timeline = {
      ...timeline,
      clips: updatedClips,
      meta: { updatedAt: new Date().toISOString() },
    }

    set({
      timelineByChapter: { ...state.timelineByChapter, [key]: updatedTimeline },
      isDirty: true,
    })
  },

  selectClip: (clipId) => {
    set({ selectedClipId: clipId })
  },

  getClipsForChapter: () => {
    const state = get()
    if (!state.projectId || !state.chapterId) return []
    const key = `${state.projectId}:${state.chapterId}`
    return state.timelineByChapter[key]?.clips || []
  },

  getSelectedClip: () => {
    const state = get()
    if (!state.selectedClipId || !state.projectId || !state.chapterId) return null
    const key = `${state.projectId}:${state.chapterId}`
    const timeline = state.timelineByChapter[key]
    return timeline?.clips.find((c) => c.id === state.selectedClipId) || null
  },

  updateTimelineSettings: (settings) => {
    const state = get()
    if (!state.projectId || !state.chapterId) return

    const key = `${state.projectId}:${state.chapterId}`
    const timeline = state.timelineByChapter[key]
    if (!timeline) return

    const updatedTimeline: Timeline = {
      ...timeline,
      settings: { ...timeline.settings, ...settings },
      meta: { updatedAt: new Date().toISOString() },
    }

    set({
      timelineByChapter: { ...state.timelineByChapter, [key]: updatedTimeline },
      isDirty: true,
    })
  },

  enqueueClipRender: (clipId) => {
    const state = get()
    if (!state.projectId || !state.chapterId) return

    const key = `${state.projectId}:${state.chapterId}`
    const timeline = state.timelineByChapter[key]
    if (!timeline) return

    const clip = timeline.clips.find((c) => c.id === clipId)
    if (!clip) return

    // 更新 clip 状态为 Queued
    get().updateClip(clipId, { status: 'Queued', progress: 0 })

    // 创建 VideoJob
    const videoJob = createVideoJob(clipId, clip.provider)

    set({
      videoJobs: { ...state.videoJobs, [videoJob.id]: videoJob },
      videoJobOrder: [...state.videoJobOrder, videoJob.id],
    })

    // 启动 mock 渲染
    const connection = getConnection() || connect()
    connection.startVideoJob(videoJob, clip)
  },

  retryClipRender: (clipId) => {
    get().enqueueClipRender(clipId)
  },

  buildExportSpec: () => {
    const state = get()
    if (!state.projectId || !state.chapterId) return null

    const key = `${state.projectId}:${state.chapterId}`
    const timeline = state.timelineByChapter[key]
    if (!timeline || timeline.clips.length === 0) return null

    const exportClips = timeline.clips.map((clip, index) => {
      const layerPack = clip.layerPackId ? state.layerPacks[clip.layerPackId] : null
      // 获取 imageUrl：尝试从 outputs.full.url 或 layers.full 获取
      let imageUrl = `https://picsum.photos/seed/${clip.panelId}/512/896`
      if (layerPack) {
        const lp = layerPack as any
        if (lp.outputs?.full?.url) {
          imageUrl = lp.outputs.full.url
        } else if (lp.layers?.full) {
          imageUrl = lp.layers.full
        }
      }

      return {
        order: index,
        clipId: clip.id,
        panelId: clip.panelId,
        layerPackId: clip.layerPackId,
        provider: clip.provider,
        durationSec: clip.durationSec,
        fps: clip.fps,
        motionPrompt: clip.motionPrompt,
        input: { imageUrl },
        output: clip.output,
      }
    })

    const totalDuration = calculateTotalDuration(timeline.clips)

    return {
      projectId: state.projectId,
      chapterId: state.chapterId,
      version: '1.0',
      timeline: {
        fps: timeline.settings.fpsDefault,
        aspect: timeline.settings.aspect,
        totalDurationSec: totalDuration,
      },
      clips: exportClips,
      generatedAt: new Date().toISOString(),
    }
  },

  enqueueExport: () => {
    const state = get()
    if (!state.projectId || !state.chapterId) return

    const exportJob = createExportJob(state.chapterId)

    set({
      exportJobs: { ...state.exportJobs, [exportJob.id]: exportJob },
      exportJobOrder: [...state.exportJobOrder, exportJob.id],
    })

    // 启动 mock 导出
    const connection = getConnection() || connect()
    const exportSpec = get().buildExportSpec()
    if (exportSpec) {
      connection.startExportJob(exportJob, exportSpec)
    }
  },
}))
