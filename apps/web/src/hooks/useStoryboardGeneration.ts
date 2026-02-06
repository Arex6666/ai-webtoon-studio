import { useState, useCallback } from 'react'
import { useStudioStore } from '@/lib/store/studioStore'
import { useToast } from '@/hooks/use-toast'
import { chaptersApi, renderApi } from '@/lib/api/services'
import { RenderProvider } from '@/lib/schema/job'

export function useStoryboardGeneration() {
    const {
        chapterId,
        script,
        setPanelList,
        selectPanel,
    } = useStudioStore()
    const { toast } = useToast()
    const [isGenerating, setIsGenerating] = useState(false)

    const generateStoryboard = useCallback(async (provider: RenderProvider = 'mock') => {
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
        toast({
            title: "AI 分镜中...",
            description: "正在解析剧本并生成分镜，请稍候",
        })

        try {
            // 调用 API 创建分镜任务
            const result = await chaptersApi.createStoryboard(chapterId, provider)

            // 轮询 job 状态
            const pollJobStatus = async (): Promise<void> => {
                try {
                    const job = await renderApi.getJobStatus(result.job_id)

                    if (job.status === 'succeeded') {
                        // 刷新 studio 数据
                        const studioData = await chaptersApi.getStudio(chapterId)
                        useStudioStore.getState().setStudioData(studioData)

                        // S3-02: 检查是否有待审核的 draft
                        const pendingDraftId = studioData.chapter?.layout_json?.pending_draft_id

                        if (pendingDraftId) {
                            // 有 draft，打开预览弹窗让用户审核
                            useStudioStore.setState({
                                pendingDraftId: pendingDraftId,
                                showDraftModal: true
                            })

                            setIsGenerating(false)
                            toast({
                                title: "分镜草稿已生成",
                                description: `请在弹窗中预览并确认应用`,
                            })
                        } else {
                            // 旧逻辑：直接更新 panelList（如果没有 draft 流程）
                            const panels = studioData.panels || []
                            if (panels.length > 0) {
                                selectPanel(panels[0].id)
                            }

                            setIsGenerating(false)
                            toast({
                                title: "分镜生成完成",
                                description: `成功生成 ${panels.length} 个分镜`,
                            })
                        }
                    } else if (job.status === 'failed') {
                        setIsGenerating(false)
                        toast({
                            title: "分镜失败",
                            description: job.error || "生成过程出错，请重试",
                            variant: "destructive",
                        })
                    } else {
                        // 继续轮询
                        setTimeout(pollJobStatus, 1000)
                    }
                } catch (error) {
                    console.error("Poll failed", error)
                    // Stop polling on network error? Or retry? 
                    // For now retry a few times or stop. Let's stop to be safe.
                    setIsGenerating(false)
                    toast({
                        title: "状态查询失败",
                        description: "无法获取任务状态",
                        variant: "destructive"
                    })
                }
            }

            // 开始轮询
            setTimeout(pollJobStatus, 500)

        } catch (error) {
            setIsGenerating(false)
            toast({
                title: "分镜失败",
                description: error instanceof Error ? error.message : "请求失败，请重试",
                variant: "destructive",
            })
        }
    }, [chapterId, script, toast, selectPanel])

    return {
        isGenerating,
        generateStoryboard
    }
}
