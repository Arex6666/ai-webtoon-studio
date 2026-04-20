import { useState, useCallback, useEffect, useRef } from 'react'
import { useStudioStore } from '@/lib/store/studioStore'
import { useShallow } from 'zustand/react/shallow'
import { useToast } from '@/hooks/use-toast'
import { chaptersApi } from '@/lib/api/services'
import { useJobTracker } from '@/hooks/useJobTracker'
import { RenderProvider } from '@/lib/schema/job'

export function useStoryboardGeneration() {
    const {
        chapterId,
        script,
        selectPanel,
    } = useStudioStore(
    useShallow(s => ({ chapterId: s.chapterId, script: s.script, selectPanel: s.selectPanel }))
  )
    const { toast } = useToast()
    const [isGenerating, setIsGenerating] = useState(false)
    const [currentJobId, setCurrentJobId] = useState<string | null>(null)
    const hasHandledRef = useRef<string | null>(null)

    const jobState = useJobTracker(currentJobId)

    // React to job completion/failure via useJobTracker
    useEffect(() => {
        if (!currentJobId || !jobState.isComplete) return
        // Prevent double-handling
        if (hasHandledRef.current === currentJobId) return
        hasHandledRef.current = currentJobId

        if (jobState.status === 'succeeded') {
            // Refresh studio data
            if (chapterId) {
                chaptersApi.getStudio(chapterId).then(studioData => {
                    useStudioStore.getState().setStudioData(studioData)

                    const pendingDraftId = (studioData.chapter?.layout_json as any)?.pending_draft_id

                    if (pendingDraftId) {
                        useStudioStore.setState({
                            pendingDraftId: pendingDraftId,
                            showDraftModal: true
                        })
                        toast({
                            title: "分镜草稿已生成",
                            description: "请在弹窗中预览并确认应用",
                        })
                    } else {
                        const panels = studioData.panels || []
                        if (panels.length > 0) {
                            selectPanel(panels[0].id)
                        }
                        toast({
                            title: "分镜生成完成",
                            description: `成功生成 ${panels.length} 个分镜`,
                        })
                    }
                }).catch(() => {
                    toast({
                        title: "数据刷新失败",
                        description: "分镜已生成但刷新失败，请手动刷新",
                        variant: "destructive",
                    })
                })
            }
            setIsGenerating(false)
        } else if (jobState.status === 'failed') {
            toast({
                title: "分镜失败",
                description: jobState.error || "生成过程出错，请重试",
                variant: "destructive",
            })
            setIsGenerating(false)
        }
    }, [currentJobId, jobState.isComplete, jobState.status, jobState.error, chapterId, selectPanel, toast])

    const generateStoryboard = useCallback(async (provider: RenderProvider = 'deepseek') => {
        if (!chapterId) return
        if (!script.trim()) {
            toast({
                title: "请先输入剧本",
                description: "在左侧剧本区域粘贴或输入剧本内容",
                variant: "destructive",
            })
            return
        }

        setIsGenerating(true)
        hasHandledRef.current = null
        toast({
            title: "AI 分镜中...",
            description: "正在解析剧本并生成分镜，请稍候",
        })

        try {
            const jobId = await useStudioStore.getState().createJob('storyboard', chapterId, provider, {
                script: script,
            })
            setCurrentJobId(jobId)
        } catch (error) {
            setIsGenerating(false)
            toast({
                title: "分镜失败",
                description: error instanceof Error ? error.message : "请求失败，请重试",
                variant: "destructive",
            })
            setCurrentJobId(null)
        }
    }, [chapterId, script, toast])

    return {
        isGenerating,
        currentJobId,
        generateStoryboard
    }
}
