'use client'

import { useStudioStore } from '@/lib/store/studioStore'
import { useShallow } from 'zustand/react/shallow'
import { STRATEGY_LABELS, FixStrategy } from '@/lib/schema/fixPlan'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Slider } from '@/components/ui/slider'
import { cn } from '@/lib/utils'
import { Wand2, RefreshCw, User, ImageIcon, Sparkles, AlertCircle } from 'lucide-react'

const STRATEGY_ICONS: Record<FixStrategy, React.ReactNode> = {
    inpaint: <Wand2 className="w-4 h-4" />,
    redraw_char: <User className="w-4 h-4" />,
    redraw_bg: <ImageIcon className="w-4 h-4" />,
    reroll: <RefreshCw className="w-4 h-4" />,
}

export function FixModal() {
    const {
        fixModal,
        closeFixModal,
        updateFixPlanDraft,
        submitFixPlan,
        viewer,
    } = useStudioStore(
    useShallow(s => ({ fixModal: s.fixModal, closeFixModal: s.closeFixModal, updateFixPlanDraft: s.updateFixPlanDraft, submitFixPlan: s.submitFixPlan, viewer: s.viewer }))
  )

    const { open, draft } = fixModal

    if (!draft) return null

    const handleStrategyChange = (strategy: string) => {
        updateFixPlanDraft({ strategy: strategy as FixStrategy })
    }

    const handleSubmit = () => {
        submitFixPlan()
    }

    return (
        <Dialog open={open} onOpenChange={(isOpen) => !isOpen && closeFixModal()}>
            <DialogContent className="max-w-lg bg-panel border-panel-border">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Sparkles className="w-5 h-5 text-accent" />
                        局部重绘 / 修复
                    </DialogTitle>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    {/* 策略选择 */}
                    <div className="space-y-2">
                        <Label>修复策略</Label>
                        <Tabs value={draft.strategy} onValueChange={handleStrategyChange}>
                            <TabsList className="grid grid-cols-4 bg-panel-hover">
                                {(Object.keys(STRATEGY_LABELS) as FixStrategy[]).map((strategy) => (
                                    <TabsTrigger
                                        key={strategy}
                                        value={strategy}
                                        className="text-xs gap-1.5 data-[state=active]:bg-accent"
                                    >
                                        {STRATEGY_ICONS[strategy]}
                                        {STRATEGY_LABELS[strategy].label}
                                    </TabsTrigger>
                                ))}
                            </TabsList>
                        </Tabs>
                        <p className="text-xs text-ink-muted mt-1">
                            {STRATEGY_LABELS[draft.strategy].description}
                        </p>
                    </div>

                    {/* ROI 信息 */}
                    <div className="p-3 rounded-lg bg-panel-hover border border-panel-border">
                        {draft.roi ? (
                            <div className="text-sm">
                                <div className="flex items-center gap-2 text-ink-muted mb-1">
                                    <span className="text-emerald-400">✓</span>
                                    已选择修复区域
                                </div>
                                <div className="text-xs text-ink-dim">
                                    位置: ({Math.round(draft.roi.x)}, {Math.round(draft.roi.y)}) -
                                    尺寸: {Math.round(draft.roi.w)} x {Math.round(draft.roi.h)}
                                </div>
                            </div>
                        ) : (
                            <div className="flex items-center gap-2 text-sm text-ink-muted">
                                <AlertCircle className="w-4 h-4 text-yellow-400" />
                                未选择选区，将对整图生效
                            </div>
                        )}
                    </div>

                    {/* Prompt */}
                    <div className="space-y-2">
                        <Label>修复指令 (Prompt)</Label>
                        <Textarea
                            value={draft.prompt}
                            onChange={(e) => updateFixPlanDraft({ prompt: e.target.value })}
                            placeholder=""
                            className="min-h-[80px] bg-canvas border-panel-border"
                        />
                    </div>

                    {/* Negative Prompt */}
                    <div className="space-y-2">
                        <Label>排除内容 (Negative)</Label>
                        <Textarea
                            value={draft.negative}
                            onChange={(e) => updateFixPlanDraft({ negative: e.target.value })}
                            placeholder=""
                            className="min-h-[60px] bg-canvas border-panel-border"
                        />
                    </div>

                    {/* Strength Slider */}
                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <Label>修复强度</Label>
                            <span className="text-sm text-ink-muted">{Math.round(draft.strength * 100)}%</span>
                        </div>
                        <Slider
                            value={[draft.strength]}
                            onValueChange={([value]) => updateFixPlanDraft({ strength: value })}
                            min={0.1}
                            max={1}
                            step={0.05}
                            className="w-full"
                        />
                        <p className="text-xs text-ink-dim">
                            强度越高，修改幅度越大
                        </p>
                    </div>

                    {/* Seed Mode */}
                    <div className="space-y-2">
                        <Label>随机种子</Label>
                        <div className="flex gap-2">
                            <Button
                                type="button"
                                variant={draft.seedMode === 'keep' ? 'default' : 'outline'}
                                size="sm"
                                onClick={() => updateFixPlanDraft({ seedMode: 'keep' })}
                                className={cn(
                                    "flex-1",
                                    draft.seedMode === 'keep' && "bg-accent hover:bg-accent-hover"
                                )}
                            >
                                保持原种子
                            </Button>
                            <Button
                                type="button"
                                variant={draft.seedMode === 'new' ? 'default' : 'outline'}
                                size="sm"
                                onClick={() => updateFixPlanDraft({ seedMode: 'new' })}
                                className={cn(
                                    "flex-1",
                                    draft.seedMode === 'new' && "bg-accent hover:bg-accent-hover"
                                )}
                            >
                                使用新种子
                            </Button>
                        </div>
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={closeFixModal}>
                        取消
                    </Button>
                    <Button onClick={handleSubmit} className="bg-accent hover:bg-accent-hover">
                        <Wand2 className="w-4 h-4 mr-2" />
                        执行修复
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
