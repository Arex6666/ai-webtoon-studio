'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useStudioStore } from '@/lib/store/studioStore'
import { connect, disconnect } from '@/lib/ws/client'
import { StudioTopbar } from './StudioTopbar'
import { StudioLayout } from './StudioLayout'
import { FixModal } from './modals/FixModal'
import { DraftPreviewModal } from './modals/DraftPreviewModal'
import { projectsApi, chaptersApi } from '@/lib/api/services'

interface StudioShellProps {
  projectId: string
  chapterId: string
}

// 包装组件：处理 draft 数据加载和弹窗显示
function DraftPreviewWrapper() {
  const { showDraftModal, pendingDraftId, chapterId } = useStudioStore()
  const [draft, setDraft] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  // 当有 pendingDraftId 且弹窗需要显示时，加载 draft 数据
  useEffect(() => {
    if (showDraftModal && pendingDraftId) {
      setLoading(true)
      chaptersApi.getDraft(pendingDraftId)
        .then((data) => {
          setDraft(data)
        })
        .catch((error) => {
          console.error('Failed to load draft:', error)
        })
        .finally(() => {
          setLoading(false)
        })
    }
  }, [showDraftModal, pendingDraftId])

  const handleOpenChange = (open: boolean) => {
    useStudioStore.setState({ showDraftModal: open })
    if (!open) {
      setDraft(null)
    }
  }

  const handleApplied = async () => {
    // 刷新数据
    if (chapterId) {
      await useStudioStore.getState().refreshChapterData(chapterId)
    }
    useStudioStore.setState({
      showDraftModal: false,
      pendingDraftId: null
    })
  }

  return (
    <DraftPreviewModal
      open={showDraftModal && !!draft}
      onOpenChange={handleOpenChange}
      draft={draft}
      onApplied={handleApplied}
    />
  )
}

export function StudioShell({ projectId, chapterId }: StudioShellProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [loadingContext, setLoadingContext] = useState(true)
  const [projectInfo, setProjectInfo] = useState<{ name: string } | null>(null)
  const [chapterInfo, setChapterInfo] = useState<{ title: string } | null>(null)

  const {
    setContext,
    setScript,
    setStudioData,
    loadChapterDraft,
    saveChapterDraft,
    selectPanel,
    selectedPanelId,
    panelSpecs,
    applyWsEvent,
    storyboardJob,
  } = useStudioStore()

  // Initialize context on mount
  useEffect(() => {
    setContext(projectId, chapterId)

    // Load metadata and script
    const loadMetadata = async () => {
      try {
        const [p, studioData] = await Promise.all([
          projectsApi.get(projectId),
          chaptersApi.getStudio(chapterId)
        ])
        setProjectInfo(p)
        setChapterInfo({ title: studioData.chapter.title })

        // Initialize store with full studio data
        setStudioData(studioData)

      } catch (error) {
        console.error("Failed to load project/chapter metadata", error)
      } finally {
        setLoadingContext(false)
      }
    }
    loadMetadata()

  }, [projectId, chapterId, setContext, setScript])

  // Load chapter draft on mount
  useEffect(() => {
    loadChapterDraft(projectId, chapterId)
  }, [projectId, chapterId, loadChapterDraft])

  // Connect to WS and subscribe to chapter events
  useEffect(() => {
    const connection = connect()

    const unsubscribe = connection.subscribeChapter(projectId, chapterId, (event) => {
      applyWsEvent(event)
    })

    return () => {
      unsubscribe()
      disconnect()
    }
  }, [projectId, chapterId, applyWsEvent])

  // Auto-refresh when storyboard job completes
  useEffect(() => {
    if (storyboardJob?.status === 'succeeded' && storyboardJob.stage === 'done') {
      const refreshData = async () => {
        try {
          const studioData = await chaptersApi.getStudio(chapterId)
          setStudioData(studioData)
        } catch (error) {
          console.error("Failed to refresh studio data", error)
        }
      }
      refreshData()
    }
  }, [storyboardJob?.status, storyboardJob?.stage, chapterId, setStudioData])

  // Auto-save when panelSpecs change (debounced 600ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      saveChapterDraft()
    }, 600)

    return () => clearTimeout(timer)
  }, [panelSpecs, saveChapterDraft])

  // Sync URL panelId to store on mount
  useEffect(() => {
    const panelId = searchParams.get('panelId')
    if (panelId) {
      selectPanel(panelId)
    }
  }, []) // Only run on mount

  // Sync store selectedPanelId to URL
  useEffect(() => {
    const currentPanelId = searchParams.get('panelId')
    if (selectedPanelId !== currentPanelId) {
      const params = new URLSearchParams(searchParams.toString())
      if (selectedPanelId) {
        params.set('panelId', selectedPanelId)
      } else {
        params.delete('panelId')
      }
      router.replace(`?${params.toString()}`, { scroll: false })
    }
  }, [selectedPanelId, searchParams, router])

  return (
    <div className="h-screen flex flex-col bg-canvas">
      <StudioTopbar
        projectId={projectId}
        chapterId={chapterId}
        projectName={projectInfo?.name}
        chapterTitle={chapterInfo?.title}
      />
      <StudioLayout />
      <FixModal />
      <DraftPreviewWrapper />
    </div>
  )
}
