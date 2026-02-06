'use client'

import { useStudioStore } from '@/lib/store/studioStore'
import { canGenerateClip, type Clip } from '@/lib/schema/clip'
import { type KeyframeRef, createKeyframeFromLayerPack } from '@/lib/schema/keyframe'
import { TRANSITION_LABELS, type TransitionType } from '@/lib/schema/transition'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import {
  Film, Play, Image, ArrowRight, Check, AlertCircle, RefreshCw
} from 'lucide-react'

const PROVIDER_OPTIONS = [
  { value: 'mock', label: 'Mock (测试)' },
  { value: 'comfyui_svd', label: 'ComfyUI SVD' },
  { value: 'kling', label: 'Keling' },
  { value: 'tongyi', label: '通义' },
  { value: 'doubao', label: '豆包' },
]

const FPS_OPTIONS = [6, 8, 12, 24]

export function InspectorTimeline() {
  const {
    selectedClipId,
    getSelectedClip,
    updateClip,
    panelList,
    panelSpecs,
    layerPacks,
    selectedLayerPackIdByPanel,
    panelLatestLayerPack,
  } = useStudioStore()

  const clip = getSelectedClip()

  if (!selectedClipId || !clip) {
    return (
      <div className="h-full flex items-center justify-center text-ink-muted p-4">
        <div className="text-center">
          <Film className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">请在时间轴选中一个 Clip</p>
        </div>
      </div>
    )
  }

  const { canGenerate, reason } = canGenerateClip(clip)

  // 从 panel 列表创建关键帧选项
  const panelOptions = panelList.map(p => {
    const spec = panelSpecs[p.id]
    const layerPackId = selectedLayerPackIdByPanel[p.id] || panelLatestLayerPack[p.id]
    const layerPack = layerPackId ? layerPacks[layerPackId] : null
    const hasLayerPack = !!layerPack

    // 获取 URL：尝试从 outputs.full.url 或 layers.full 获取
    let url: string | undefined
    if (layerPack) {
      const lp = layerPack as any
      if (lp.outputs?.full?.url) {
        url = lp.outputs.full.url
      } else if (lp.layers?.full) {
        url = lp.layers.full
      }
    }

    return {
      panelId: p.id,
      label: `Panel #${p.index + 1} - ${spec?.scene?.location || 'Unknown'}`,
      layerPackId,
      url,
      hasLayerPack: hasLayerPack && !!url,
    }
  }).filter(p => p.hasLayerPack)

  const handleSetStartFrame = (panelId: string) => {
    const option = panelOptions.find(p => p.panelId === panelId)
    if (!option || !option.layerPackId || !option.url) return

    const keyframe = createKeyframeFromLayerPack(
      panelId,
      option.layerPackId,
      option.url,
      800,
      600
    )
    updateClip(clip.id, { startFrame: keyframe })
  }

  const handleSetEndFrame = (panelId: string) => {
    const option = panelOptions.find(p => p.panelId === panelId)
    if (!option || !option.layerPackId || !option.url) return

    const keyframe = createKeyframeFromLayerPack(
      panelId,
      option.layerPackId,
      option.url,
      800,
      600
    )
    updateClip(clip.id, { endFrame: keyframe })
  }

  const handleSwapFrames = () => {
    updateClip(clip.id, {
      startFrame: clip.endFrame,
      endFrame: clip.startFrame,
    })
  }

  return (
    <ScrollArea className="h-full">
      <div className="p-4 space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h3 className="font-medium flex items-center gap-2">
            <Film className="w-4 h-4" />
            Clip 编辑器
          </h3>
          <Badge variant="outline" className="text-xs">
            {clip.status}
          </Badge>
        </div>

        <Separator />

        {/* Motion Mode */}
        <div className="space-y-2">
          <Label className="text-xs text-ink-muted">运动模式</Label>
          <Select
            value={clip.motionMode}
            onValueChange={(v) => updateClip(clip.id, { motionMode: v as 'single_keyframe' | 'dual_keyframe' })}
          >
            <SelectTrigger className="bg-canvas border-panel-border">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="dual_keyframe">双关键帧 (首尾帧)</SelectItem>
              <SelectItem value="single_keyframe">单关键帧</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Start Frame */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="text-xs text-ink-muted flex items-center gap-1.5">
              <span>起始帧</span>
              {clip.startFrame ? (
                <Check className="w-3 h-3 text-emerald-400" />
              ) : (
                <AlertCircle className="w-3 h-3 text-yellow-400" />
              )}
            </Label>
          </div>
          <Select
            value={clip.startFrame?.type === 'layerpack' ? clip.startFrame.panelId : ''}
            onValueChange={handleSetStartFrame}
          >
            <SelectTrigger className="bg-canvas border-panel-border">
              <SelectValue placeholder="" />
            </SelectTrigger>
            <SelectContent>
              {panelOptions.map(opt => (
                <SelectItem key={opt.panelId} value={opt.panelId}>
                  <div className="flex items-center gap-2">
                    <Image className="w-3 h-3" />
                    {opt.label}
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {clip.startFrame && (
            <div className="text-xs text-ink-dim truncate">
              {clip.startFrame.url}
            </div>
          )}
        </div>

        {/* End Frame (only for dual_keyframe) */}
        {clip.motionMode === 'dual_keyframe' && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs text-ink-muted flex items-center gap-1.5">
                <span>结束帧</span>
                {clip.endFrame ? (
                  <Check className="w-3 h-3 text-emerald-400" />
                ) : (
                  <AlertCircle className="w-3 h-3 text-yellow-400" />
                )}
              </Label>
              <Button
                size="sm"
                variant="ghost"
                onClick={handleSwapFrames}
                className="h-6 text-xs"
                disabled={!clip.startFrame && !clip.endFrame}
              >
                <RefreshCw className="w-3 h-3 mr-1" />
                交换
              </Button>
            </div>
            <Select
              value={clip.endFrame?.type === 'layerpack' ? clip.endFrame.panelId : ''}
              onValueChange={handleSetEndFrame}
            >
              <SelectTrigger className="bg-canvas border-panel-border">
                <SelectValue placeholder="" />
              </SelectTrigger>
              <SelectContent>
                {panelOptions.map(opt => (
                  <SelectItem key={opt.panelId} value={opt.panelId}>
                    <div className="flex items-center gap-2">
                      <Image className="w-3 h-3" />
                      {opt.label}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {clip.endFrame && (
              <div className="text-xs text-ink-dim truncate">
                {clip.endFrame.url}
              </div>
            )}
          </div>
        )}

        <Separator />

        {/* Motion Prompt */}
        <div className="space-y-2">
          <Label className="text-xs text-ink-muted">运镜描述</Label>
          <Textarea
            value={clip.motionPrompt}
            onChange={(e) => updateClip(clip.id, { motionPrompt: e.target.value })}
            placeholder=""
            className="min-h-[60px] bg-canvas border-panel-border text-sm"
          />
        </div>

        {/* Duration & FPS */}
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <Label className="text-xs text-ink-muted">时长 (秒)</Label>
            <Input
              type="number"
              value={clip.durationSec}
              onChange={(e) => updateClip(clip.id, { durationSec: parseFloat(e.target.value) || 3 })}
              min={0.5}
              max={10}
              step={0.5}
              className="bg-canvas border-panel-border"
            />
          </div>
          <div className="space-y-2">
            <Label className="text-xs text-ink-muted">FPS</Label>
            <Select
              value={String(clip.fps)}
              onValueChange={(v) => updateClip(clip.id, { fps: parseInt(v) })}
            >
              <SelectTrigger className="bg-canvas border-panel-border">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {FPS_OPTIONS.map(fps => (
                  <SelectItem key={fps} value={String(fps)}>{fps} fps</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Provider */}
        <div className="space-y-2">
          <Label className="text-xs text-ink-muted">生成器</Label>
          <Select
            value={clip.provider}
            onValueChange={(v) => updateClip(clip.id, { provider: v as any })}
          >
            <SelectTrigger className="bg-canvas border-panel-border">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PROVIDER_OPTIONS.map(opt => (
                <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <Separator />

        {/* Generate Status */}
        {!canGenerate && (
          <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/30">
            <div className="flex items-center gap-2 text-sm text-yellow-400">
              <AlertCircle className="w-4 h-4" />
              {reason}
            </div>
          </div>
        )}

        {canGenerate && (
          <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
            <div className="flex items-center gap-2 text-sm text-emerald-400">
              <Check className="w-4 h-4" />
              准备就绪，可以生成视频
            </div>
          </div>
        )}
      </div>
    </ScrollArea>
  )
}
