'use client'

import { useStudioStore } from '@/lib/store/studioStore'
import { useShallow } from 'zustand/react/shallow'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Slider } from '@/components/ui/slider'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import {
  Layers, Eye, EyeOff, Wand2, User, ImageIcon, RefreshCw,
  CheckCircle, AlertTriangle
} from 'lucide-react'

const LAYER_CONFIG = [
  { key: 'bg' as const, label: '背景层', icon: ImageIcon },
  { key: 'char' as const, label: '角色层', icon: User },
  { key: 'fg' as const, label: '前景层', icon: Layers },
  { key: 'text' as const, label: '文字层', icon: null },
]

export function InspectorLayers() {
  const {
    selectedPanelId,
    getSelectedLayerPack,
    getLayerPacksForPanel,
    selectLayerPack,
    selectedLayerPackIdByPanel,
    viewer,
    setLayerVisibility,
    setLayerOpacity,
    openFixModal,
  } = useStudioStore(
    useShallow(s => ({ selectedPanelId: s.selectedPanelId, getSelectedLayerPack: s.getSelectedLayerPack, getLayerPacksForPanel: s.getLayerPacksForPanel, selectLayerPack: s.selectLayerPack, selectedLayerPackIdByPanel: s.selectedLayerPackIdByPanel, viewer: s.viewer, setLayerVisibility: s.setLayerVisibility, setLayerOpacity: s.setLayerOpacity, openFixModal: s.openFixModal }))
  )

  const layerPack = getSelectedLayerPack()
  const allVersions = selectedPanelId ? getLayerPacksForPanel(selectedPanelId) : []
  const currentVersionId = selectedPanelId ? selectedLayerPackIdByPanel[selectedPanelId] : null

  if (!selectedPanelId) {
    return (
      <div className="h-full flex items-center justify-center text-ink-muted p-4">
        <div className="text-center">
          <Layers className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">请选择一个面板</p>
        </div>
      </div>
    )
  }

  if (!layerPack) {
    return (
      <div className="h-full flex items-center justify-center text-ink-muted p-4">
        <div className="text-center">
          <Layers className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">尚未渲染</p>
          <p className="text-xs mt-1">渲染后可查看图层</p>
        </div>
      </div>
    )
  }

  const qa = 'qa' in layerPack ? layerPack.qa : undefined

  return (
    <ScrollArea className="h-full">
      <div className="p-4 space-y-6">
        {/* 版本选择 */}
        {allVersions.length > 1 && (
          <div className="space-y-2">
            <Label className="text-xs text-ink-muted">版本选择</Label>
            <Select
              value={currentVersionId || ''}
              onValueChange={(value) => selectLayerPack(selectedPanelId, value)}
            >
              <SelectTrigger className="bg-canvas border-panel-border">
                <SelectValue placeholder="" />
              </SelectTrigger>
              <SelectContent>
                {allVersions.map((lp, index) => (
                  <SelectItem key={lp.id} value={lp.id}>
                    v{index + 1} - {new Date(lp.createdAt).toLocaleTimeString('zh-CN')}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {/* QA 分数 */}
        {qa && (
          <div className="p-3 rounded-lg bg-panel-hover border border-panel-border">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">质量评分</span>
              <Badge
                variant="outline"
                className={qa.score >= 0.8 ? 'text-emerald-400' : qa.score >= 0.6 ? 'text-yellow-400' : 'text-red-400'}
              >
                {Math.round(qa.score * 100)}%
              </Badge>
            </div>
            {qa.issues.length > 0 && (
              <div className="space-y-1">
                {qa.issues.map((issue, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs text-ink-muted">
                    <AlertTriangle className="w-3 h-3 mt-0.5 text-yellow-400 shrink-0" />
                    {issue}
                  </div>
                ))}
              </div>
            )}
            {qa.issues.length === 0 && (
              <div className="flex items-center gap-2 text-xs text-emerald-400">
                <CheckCircle className="w-3 h-3" />
                无明显问题
              </div>
            )}
          </div>
        )}

        {/* 图层控制 */}
        <div className="space-y-3">
          <Label className="text-xs text-ink-muted">图层控制</Label>
          {LAYER_CONFIG.map(({ key, label, icon: Icon }) => (
            <div key={key} className="p-3 rounded-lg bg-panel-hover border border-panel-border">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  {Icon && <Icon className="w-4 h-4 text-ink-muted" />}
                  <span className="text-sm">{label}</span>
                </div>
                <button
                  onClick={() => setLayerVisibility(key, !viewer.layerVisibility[key])}
                  className="p-1.5 rounded hover:bg-panel transition-colors"
                >
                  {viewer.layerVisibility[key] ? (
                    <Eye className="w-4 h-4 text-accent" />
                  ) : (
                    <EyeOff className="w-4 h-4 text-ink-dim" />
                  )}
                </button>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-ink-dim w-12">
                  {Math.round(viewer.layerOpacity[key] * 100)}%
                </span>
                <Slider
                  value={[viewer.layerOpacity[key]]}
                  onValueChange={([value]) => setLayerOpacity(key, value)}
                  min={0}
                  max={1}
                  step={0.05}
                  className="flex-1"
                  disabled={!viewer.layerVisibility[key]}
                />
              </div>
            </div>
          ))}
        </div>

        {/* 修复按钮 */}
        <div className="space-y-2">
          <Label className="text-xs text-ink-muted">修复操作</Label>
          <div className="grid grid-cols-2 gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => openFixModal(selectedPanelId, 'inpaint')}
              className="h-9 text-xs"
            >
              <Wand2 className="w-3.5 h-3.5 mr-1.5" />
              局部修复
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => openFixModal(selectedPanelId, 'redraw_char')}
              className="h-9 text-xs"
            >
              <User className="w-3.5 h-3.5 mr-1.5" />
              重绘角色
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => openFixModal(selectedPanelId, 'redraw_bg')}
              className="h-9 text-xs"
            >
              <ImageIcon className="w-3.5 h-3.5 mr-1.5" />
              重绘背景
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => openFixModal(selectedPanelId, 'reroll')}
              className="h-9 text-xs"
            >
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
              重新抽卡
            </Button>
          </div>
        </div>
      </div>
    </ScrollArea>
  )
}
