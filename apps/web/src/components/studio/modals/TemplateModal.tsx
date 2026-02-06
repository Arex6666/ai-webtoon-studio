'use client'

import { MOCK_TEMPLATES, type Template, type ApplyScope } from '@/lib/schema/template'
import { MOCK_STYLE_PROFILES } from '@/lib/schema/styleProfile'
import { MOCK_IDENTITY_ASSETS } from '@/lib/schema/assets.identity'
import { MOCK_SCENE_ASSETS } from '@/lib/schema/assets.scene'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Label } from '@/components/ui/label'
import { Layers, Users, Image, Palette, Check, Settings } from 'lucide-react'
import { useState } from 'react'

interface TemplateModalProps {
    open: boolean
    onOpenChange: (open: boolean) => void
}

export function TemplateModal({ open, onOpenChange }: TemplateModalProps) {
    const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(MOCK_TEMPLATES[0])
    const [applyScope, setApplyScope] = useState<ApplyScope>('chapter_defaults')

    const handleApply = () => {
        if (!selectedTemplate) return
        console.log('Applying template:', selectedTemplate.id, 'with scope:', applyScope)
        // TODO: 调用 store.applyTemplateToChapter
        onOpenChange(false)
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-4xl h-[600px] flex flex-col">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Layers className="w-5 h-5" />
                        生产模板
                    </DialogTitle>
                </DialogHeader>

                <div className="flex-1 flex gap-4 overflow-hidden">
                    {/* 左侧：模板列表 */}
                    <div className="w-64 border-r pr-4">
                        <ScrollArea className="h-full">
                            <div className="space-y-2">
                                {MOCK_TEMPLATES.map(template => (
                                    <div
                                        key={template.id}
                                        onClick={() => setSelectedTemplate(template)}
                                        className={`p-3 rounded-lg border cursor-pointer transition-colors ${selectedTemplate?.id === template.id
                                                ? 'border-accent bg-accent/10'
                                                : 'border-panel-border hover:border-accent/50'
                                            }`}
                                    >
                                        <div className="font-medium text-sm">{template.name}</div>
                                        <div className="text-xs text-ink-muted mt-1 line-clamp-2">
                                            {template.description}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </ScrollArea>
                    </div>

                    {/* 右侧：模板详情 */}
                    <div className="flex-1 overflow-auto">
                        {selectedTemplate ? (
                            <div className="space-y-4">
                                <div>
                                    <h3 className="font-semibold text-lg">{selectedTemplate.name}</h3>
                                    <p className="text-sm text-ink-muted">{selectedTemplate.description}</p>
                                </div>

                                <Separator />

                                {/* 风格 */}
                                <div className="space-y-2">
                                    <Label className="text-xs text-ink-muted flex items-center gap-1">
                                        <Palette className="w-3 h-3" /> 风格
                                    </Label>
                                    <Badge variant="secondary">
                                        {MOCK_STYLE_PROFILES.find(s => s.id === selectedTemplate.styleProfileId)?.name || '未设置'}
                                    </Badge>
                                </div>

                                {/* 角色资产 */}
                                <div className="space-y-2">
                                    <Label className="text-xs text-ink-muted flex items-center gap-1">
                                        <Users className="w-3 h-3" /> 角色资产
                                    </Label>
                                    <div className="flex flex-wrap gap-1">
                                        {selectedTemplate.identityAssetIds.length > 0 ? (
                                            selectedTemplate.identityAssetIds.map(id => {
                                                const asset = MOCK_IDENTITY_ASSETS.find(a => a.id === id)
                                                return (
                                                    <Badge key={id} variant="outline">
                                                        {asset?.name || id}
                                                    </Badge>
                                                )
                                            })
                                        ) : (
                                            <span className="text-xs text-ink-dim">无</span>
                                        )}
                                    </div>
                                </div>

                                {/* 场景资产 */}
                                <div className="space-y-2">
                                    <Label className="text-xs text-ink-muted flex items-center gap-1">
                                        <Image className="w-3 h-3" /> 场景资产
                                    </Label>
                                    <div className="flex flex-wrap gap-1">
                                        {selectedTemplate.sceneAssetIds.length > 0 ? (
                                            selectedTemplate.sceneAssetIds.map(id => {
                                                const asset = MOCK_SCENE_ASSETS.find(a => a.id === id)
                                                return (
                                                    <Badge key={id} variant="outline">
                                                        {asset?.name || id}
                                                    </Badge>
                                                )
                                            })
                                        ) : (
                                            <span className="text-xs text-ink-dim">无</span>
                                        )}
                                    </div>
                                </div>

                                {/* QA/重试 */}
                                <div className="space-y-2">
                                    <Label className="text-xs text-ink-muted flex items-center gap-1">
                                        <Settings className="w-3 h-3" /> QA 配置
                                    </Label>
                                    <div className="text-sm">
                                        阈值 {Math.round(selectedTemplate.qaConfig.threshold * 100)}% |
                                        最多重试 {selectedTemplate.retryPolicy.maxAttempts} 次 |
                                        预算 {selectedTemplate.retryPolicy.budget.maxCost}
                                    </div>
                                </div>

                                <Separator />

                                {/* 应用范围 */}
                                <div className="space-y-3">
                                    <Label className="text-xs text-ink-muted">应用范围</Label>
                                    <RadioGroup value={applyScope} onValueChange={(v) => setApplyScope(v as ApplyScope)}>
                                        <div className="flex items-center space-x-2">
                                            <RadioGroupItem value="chapter_defaults" id="scope-chapter" />
                                            <Label htmlFor="scope-chapter">章节默认设置</Label>
                                        </div>
                                        <div className="flex items-center space-x-2">
                                            <RadioGroupItem value="all_panels" id="scope-panels" />
                                            <Label htmlFor="scope-panels">所有面板</Label>
                                        </div>
                                        <div className="flex items-center space-x-2">
                                            <RadioGroupItem value="all_clips" id="scope-clips" />
                                            <Label htmlFor="scope-clips">所有 Clips</Label>
                                        </div>
                                        <div className="flex items-center space-x-2">
                                            <RadioGroupItem value="selected_only" id="scope-selected" />
                                            <Label htmlFor="scope-selected">仅选中项</Label>
                                        </div>
                                    </RadioGroup>
                                </div>
                            </div>
                        ) : (
                            <div className="h-full flex items-center justify-center text-ink-muted">
                                请选择一个模板
                            </div>
                        )}
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        取消
                    </Button>
                    <Button onClick={handleApply} disabled={!selectedTemplate}>
                        <Check className="w-4 h-4 mr-1.5" />
                        应用模板
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
