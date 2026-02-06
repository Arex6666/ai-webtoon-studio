'use client'

import { useState, useEffect } from 'react'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { useStudioStore } from '@/lib/store/studioStore'
import { chaptersApi } from '@/lib/api/services'
import {
    Check,
    X,
    Film,
    User,
    Map,
    ChevronRight,
    Loader2,
    AlertCircle,
    AlertTriangle,
    CheckCircle2,
    Wrench,
    RefreshCw
} from 'lucide-react'

interface DraftPanel {
    index: number
    title: string
    description: string
    shot_type?: string
    characters: string[]
    location?: string
}

interface DraftCharacter {
    name: string
    description?: string
    appearances: number
    matched_asset_id?: string
}

interface DraftScene {
    name: string
    description?: string
    appearances: number
    matched_asset_id?: string
}

interface DraftPreview {
    id: string
    chapter_id: string
    job_id?: string
    status: string
    version: number
    panels: DraftPanel[]
    characters: DraftCharacter[]
    scenes: DraftScene[]
    generated_panels_count: number
    generated_characters_count: number
    generated_scenes_count: number
    created_at: string
}

interface QAResult {
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
    }>
}

interface DraftPreviewModalProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    draft: DraftPreview | null
    onApplied?: () => void
    currentStoryboardVersion?: number  // S3-04: 用于乐观锁
}

export function DraftPreviewModal({
    open,
    onOpenChange,
    draft,
    onApplied,
    currentStoryboardVersion
}: DraftPreviewModalProps) {
    const [selectedPanels, setSelectedPanels] = useState<Set<number>>(new Set())
    const [selectAll, setSelectAll] = useState(true)
    const [isApplying, setIsApplying] = useState(false)
    const [isDiscarding, setIsDiscarding] = useState(false)
    const [isFixing, setIsFixing] = useState(false)
    const [qaResult, setQaResult] = useState<QAResult | null>(null)
    const [loadingQA, setLoadingQA] = useState(false)
    const [conflictError, setConflictError] = useState<string | null>(null)
    const { setStudioData, chapterId } = useStudioStore()

    // 加载 QA 评分
    useEffect(() => {
        if (open && draft) {
            loadQAResult()
        }
    }, [open, draft?.id])

    const loadQAResult = async () => {
        if (!draft) return
        setLoadingQA(true)
        try {
            const result = await chaptersApi.getDraftQA(draft.id)
            setQaResult(result)
        } catch (error) {
            console.error('Failed to load QA result:', error)
        } finally {
            setLoadingQA(false)
        }
    }

    if (!draft) return null

    const togglePanel = (index: number) => {
        const newSelected = new Set(selectedPanels)
        if (newSelected.has(index)) {
            newSelected.delete(index)
        } else {
            newSelected.add(index)
        }
        setSelectedPanels(newSelected)
        setSelectAll(newSelected.size === draft.panels.length)
    }

    const toggleSelectAll = () => {
        if (selectAll) {
            setSelectedPanels(new Set())
        } else {
            setSelectedPanels(new Set(draft.panels.map(p => p.index)))
        }
        setSelectAll(!selectAll)
    }

    const handleApply = async () => {
        if (!draft || !chapterId) return

        setIsApplying(true)
        setConflictError(null)

        try {
            const panelIndices = selectAll ? undefined : Array.from(selectedPanels)
            const result = await chaptersApi.applyDraft(draft.id, {
                panel_indices: panelIndices,
                expected_storyboard_version: currentStoryboardVersion
            })

            // 如果是幂等返回
            if (result.already_applied) {
                console.log('Draft already applied, version:', result.new_version)
            }

            // S3-08: 使用统一刷新方法
            await useStudioStore.getState().refreshChapterData(chapterId)

            // S3-08: 检查 pending 资产并提示
            const { pendingAssetsCount } = useStudioStore.getState()
            if (pendingAssetsCount > 0) {
                // 自动切换到资产锁定 tab
                useStudioStore.setState({
                    activeInspectorTab: 'assets-lock'
                })
                // 非阻塞提示（用 console 或 toast，取决于是否有 toast hook）
                console.info(`检测到 ${pendingAssetsCount} 项资产待确认。已为你打开【资产锁定】，确认后即可一键渲染。`)
            }

            onOpenChange(false)
            onApplied?.()
        } catch (error: any) {
            // S3-04: 处理 409 冲突
            if (error?.response?.status === 409) {
                setConflictError(error?.response?.data?.detail || '版本冲突，请刷新页面后重试')
            } else {
                console.error('Failed to apply draft:', error)
            }
        } finally {
            setIsApplying(false)
        }
    }

    const handleDiscard = async () => {
        if (!draft) return

        setIsDiscarding(true)
        try {
            await chaptersApi.discardDraft(draft.id)
            onOpenChange(false)
        } catch (error) {
            console.error('Failed to discard draft:', error)
        } finally {
            setIsDiscarding(false)
        }
    }

    const handleFix = async () => {
        if (!draft) return

        setIsFixing(true)
        try {
            await chaptersApi.fixDraft(draft.id)
            // 重新加载 QA 结果
            await loadQAResult()
        } catch (error) {
            console.error('Failed to fix draft:', error)
        } finally {
            setIsFixing(false)
        }
    }

    // QA 分数颜色
    const getScoreColor = (score: number) => {
        if (score >= 80) return 'text-green-500'
        if (score >= 60) return 'text-amber-500'
        return 'text-red-500'
    }

    const getScoreBg = (score: number) => {
        if (score >= 80) return 'bg-green-500/10 border-green-500/20'
        if (score >= 60) return 'bg-amber-500/10 border-amber-500/20'
        return 'bg-red-500/10 border-red-500/20'
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-4xl max-h-[85vh] flex flex-col">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Film className="w-5 h-5 text-primary" />
                        AI 分镜预览
                    </DialogTitle>
                    <DialogDescription>
                        AI 已生成 {draft.generated_panels_count} 个分镜。请审阅后选择应用。
                    </DialogDescription>
                </DialogHeader>

                {/* S3-04: 版本冲突警告 */}
                {conflictError && (
                    <div className="mb-2 p-3 rounded-lg bg-red-500/10 border border-red-500/30 flex items-center justify-between">
                        <div className="flex items-center gap-2 text-red-500">
                            <AlertTriangle className="h-4 w-4" />
                            <span className="text-sm">{conflictError}</span>
                        </div>
                        <Button
                            size="sm"
                            variant="outline"
                            onClick={() => window.location.reload()}
                        >
                            <RefreshCw className="w-3 h-3 mr-1" />
                            刷新页面
                        </Button>
                    </div>
                )}

                {/* S3-05: QA 评分卡片 */}
                {qaResult && (
                    <div className={`p-3 rounded-lg border ${getScoreBg(qaResult.score)} mb-2`}>
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className={`text-2xl font-bold ${getScoreColor(qaResult.score)}`}>
                                    {qaResult.score.toFixed(0)}
                                </div>
                                <div className="text-sm">
                                    <div className="flex items-center gap-2">
                                        {qaResult.passed ? (
                                            <Badge variant="outline" className="text-green-500 border-green-500/30">
                                                <CheckCircle2 className="w-3 h-3 mr-1" />
                                                通过
                                            </Badge>
                                        ) : (
                                            <Badge variant="outline" className="text-red-500 border-red-500/30">
                                                <AlertCircle className="w-3 h-3 mr-1" />
                                                需改进
                                            </Badge>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                                        {qaResult.error_count > 0 && (
                                            <span className="text-red-500">{qaResult.error_count} 错误</span>
                                        )}
                                        {qaResult.warning_count > 0 && (
                                            <span className="text-amber-500">{qaResult.warning_count} 警告</span>
                                        )}
                                        {qaResult.fixable_count > 0 && (
                                            <span className="text-blue-500">{qaResult.fixable_count} 可修复</span>
                                        )}
                                    </div>
                                </div>
                            </div>
                            {qaResult.fixable_count > 0 && (
                                <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={handleFix}
                                    disabled={isFixing}
                                >
                                    {isFixing ? (
                                        <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                                    ) : (
                                        <Wrench className="w-3 h-3 mr-1" />
                                    )}
                                    一键修复
                                </Button>
                            )}
                        </div>

                        {/* 问题列表（折叠显示前3条） */}
                        {qaResult.issues.length > 0 && (
                            <div className="mt-2 pt-2 border-t border-white/10">
                                <div className="space-y-1">
                                    {qaResult.issues.slice(0, 3).map((issue, i) => (
                                        <div key={i} className="flex items-start gap-2 text-xs">
                                            {issue.severity === 'error' && (
                                                <AlertCircle className="w-3 h-3 text-red-500 mt-0.5" />
                                            )}
                                            {issue.severity === 'warning' && (
                                                <AlertTriangle className="w-3 h-3 text-amber-500 mt-0.5" />
                                            )}
                                            {issue.severity === 'info' && (
                                                <AlertCircle className="w-3 h-3 text-blue-500 mt-0.5" />
                                            )}
                                            <span className="text-muted-foreground">
                                                Panel {issue.panel_index + 1}: {issue.message}
                                            </span>
                                        </div>
                                    ))}
                                    {qaResult.issues.length > 3 && (
                                        <div className="text-xs text-muted-foreground">
                                            还有 {qaResult.issues.length - 3} 个问题...
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {loadingQA && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        正在检查质量...
                    </div>
                )}

                <div className="flex-1 min-h-0 grid grid-cols-3 gap-4">
                    {/* 左侧：Panels 列表 */}
                    <div className="col-span-2 flex flex-col min-h-0">
                        <div className="flex items-center justify-between mb-2">
                            <h3 className="text-sm font-medium flex items-center gap-2">
                                <Film className="w-4 h-4" />
                                分镜列表
                            </h3>
                            <div className="flex items-center gap-2">
                                <Checkbox
                                    id="select-all"
                                    checked={selectAll}
                                    onCheckedChange={toggleSelectAll}
                                />
                                <label htmlFor="select-all" className="text-xs text-muted-foreground cursor-pointer">
                                    全选
                                </label>
                            </div>
                        </div>

                        <ScrollArea className="flex-1 border border-white/10 rounded-lg">
                            <div className="p-2 space-y-2">
                                {draft.panels.map((panel) => (
                                    <div
                                        key={panel.index}
                                        className={`p-3 rounded-lg border transition-colors cursor-pointer ${selectedPanels.has(panel.index) || selectAll
                                            ? 'border-primary/50 bg-primary/5'
                                            : 'border-white/10 bg-muted/10 hover:bg-muted/20'
                                            }`}
                                        onClick={() => !selectAll && togglePanel(panel.index)}
                                    >
                                        <div className="flex items-start gap-3">
                                            {!selectAll && (
                                                <Checkbox
                                                    checked={selectedPanels.has(panel.index)}
                                                    onCheckedChange={() => togglePanel(panel.index)}
                                                    className="mt-1"
                                                />
                                            )}
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2 mb-1">
                                                    <span className="font-medium text-sm">{panel.title}</span>
                                                    {panel.shot_type && (
                                                        <Badge variant="outline" className="text-xs">
                                                            {panel.shot_type}
                                                        </Badge>
                                                    )}
                                                </div>
                                                <p className="text-xs text-muted-foreground line-clamp-2">
                                                    {panel.description}
                                                </p>
                                                <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                                                    {panel.characters.length > 0 && (
                                                        <span className="flex items-center gap-1">
                                                            <User className="w-3 h-3" />
                                                            {panel.characters.join(', ')}
                                                        </span>
                                                    )}
                                                    {panel.location && (
                                                        <span className="flex items-center gap-1">
                                                            <Map className="w-3 h-3" />
                                                            {panel.location}
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                            <ChevronRight className="w-4 h-4 text-muted-foreground/50" />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </ScrollArea>
                    </div>

                    {/* 右侧：角色/场景 */}
                    <div className="flex flex-col gap-4">
                        {/* 角色 */}
                        <div className="flex-1 flex flex-col min-h-0">
                            <h3 className="text-sm font-medium flex items-center gap-2 mb-2">
                                <User className="w-4 h-4" />
                                识别的角色 ({draft.characters.length})
                            </h3>
                            <ScrollArea className="flex-1 border border-white/10 rounded-lg">
                                <div className="p-2 space-y-1">
                                    {draft.characters.length === 0 ? (
                                        <p className="text-xs text-muted-foreground p-2">暂无角色</p>
                                    ) : (
                                        draft.characters.map((char, i) => (
                                            <div
                                                key={i}
                                                className="flex items-center justify-between p-2 rounded hover:bg-muted/10"
                                            >
                                                <div className="flex items-center gap-2">
                                                    <div className="w-6 h-6 rounded-full bg-muted/30 flex items-center justify-center text-xs">
                                                        {char.name[0]}
                                                    </div>
                                                    <span className="text-sm">{char.name}</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs text-muted-foreground">
                                                        {char.appearances}次
                                                    </span>
                                                    {char.matched_asset_id ? (
                                                        <Check className="w-3 h-3 text-green-500" />
                                                    ) : (
                                                        <AlertCircle className="w-3 h-3 text-amber-500" />
                                                    )}
                                                </div>
                                            </div>
                                        ))
                                    )}
                                </div>
                            </ScrollArea>
                        </div>

                        {/* 场景 */}
                        <div className="flex-1 flex flex-col min-h-0">
                            <h3 className="text-sm font-medium flex items-center gap-2 mb-2">
                                <Map className="w-4 h-4" />
                                识别的场景 ({draft.scenes.length})
                            </h3>
                            <ScrollArea className="flex-1 border border-white/10 rounded-lg">
                                <div className="p-2 space-y-1">
                                    {draft.scenes.length === 0 ? (
                                        <p className="text-xs text-muted-foreground p-2">暂无场景</p>
                                    ) : (
                                        draft.scenes.map((scene, i) => (
                                            <div
                                                key={i}
                                                className="flex items-center justify-between p-2 rounded hover:bg-muted/10"
                                            >
                                                <div className="flex items-center gap-2">
                                                    <Map className="w-4 h-4 text-muted-foreground" />
                                                    <span className="text-sm">{scene.name}</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <span className="text-xs text-muted-foreground">
                                                        {scene.appearances}次
                                                    </span>
                                                    {scene.matched_asset_id ? (
                                                        <Check className="w-3 h-3 text-green-500" />
                                                    ) : (
                                                        <AlertCircle className="w-3 h-3 text-amber-500" />
                                                    )}
                                                </div>
                                            </div>
                                        ))
                                    )}
                                </div>
                            </ScrollArea>
                        </div>
                    </div>
                </div>

                <DialogFooter className="flex items-center justify-between gap-2 pt-4 border-t border-white/10">
                    <Button
                        variant="ghost"
                        onClick={handleDiscard}
                        disabled={isApplying || isDiscarding}
                        className="text-destructive hover:text-destructive"
                    >
                        {isDiscarding ? (
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        ) : (
                            <X className="w-4 h-4 mr-2" />
                        )}
                        丢弃
                    </Button>

                    <div className="flex items-center gap-2">
                        <Button variant="outline" onClick={() => onOpenChange(false)}>
                            稍后决定
                        </Button>
                        <Button
                            onClick={handleApply}
                            disabled={isApplying || isDiscarding || (!selectAll && selectedPanels.size === 0)}
                        >
                            {isApplying ? (
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            ) : (
                                <Check className="w-4 h-4 mr-2" />
                            )}
                            应用 {selectAll ? '全部' : `${selectedPanels.size} 个`} 分镜
                        </Button>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
