'use client'

import { useState, useRef, useCallback } from 'react'
import { useStudioStore } from '@/lib/store/studioStore'
import { useShallow } from 'zustand/react/shallow'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Crosshair, X, Image as ImageIcon } from 'lucide-react'

export function CanvasStage() {
  const {
    selectedPanelId,
    getSelectedLayerPack,
    viewer,
    setRoi,
    clearRoi,
    setIsRoiSelecting,
  } = useStudioStore(
    useShallow(s => ({ selectedPanelId: s.selectedPanelId, getSelectedLayerPack: s.getSelectedLayerPack, viewer: s.viewer, setRoi: s.setRoi, clearRoi: s.clearRoi, setIsRoiSelecting: s.setIsRoiSelecting }))
  )

  const layerPack = getSelectedLayerPack()
  const containerRef = useRef<HTMLDivElement>(null)
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null)
  const [currentRoi, setCurrentRoi] = useState<{ x: number; y: number; w: number; h: number } | null>(null)

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (!viewer.isRoiSelecting) return

    const rect = containerRef.current?.getBoundingClientRect()
    if (!rect) return

    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    setDragStart({ x, y })
    setCurrentRoi({ x, y, w: 0, h: 0 })
  }, [viewer.isRoiSelecting])

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragStart || !viewer.isRoiSelecting) return

    const rect = containerRef.current?.getBoundingClientRect()
    if (!rect) return

    const currentX = e.clientX - rect.left
    const currentY = e.clientY - rect.top

    setCurrentRoi({
      x: Math.min(dragStart.x, currentX),
      y: Math.min(dragStart.y, currentY),
      w: Math.abs(currentX - dragStart.x),
      h: Math.abs(currentY - dragStart.y),
    })
  }, [dragStart, viewer.isRoiSelecting])

  const handleMouseUp = useCallback(() => {
    if (!viewer.isRoiSelecting || !currentRoi) return

    if (currentRoi.w > 10 && currentRoi.h > 10) {
      setRoi(currentRoi)
    }
    setDragStart(null)
    setCurrentRoi(null)
    setIsRoiSelecting(false)
  }, [viewer.isRoiSelecting, currentRoi, setRoi, setIsRoiSelecting])

  const hasOutputs = layerPack && 'outputs' in layerPack && layerPack.outputs

  // 如果没有选中面板
  if (!selectedPanelId) {
    return (
      <div className="h-full flex items-center justify-center bg-canvas-dark">
        <div className="text-center text-ink-muted">
          <ImageIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>请选择一个面板</p>
        </div>
      </div>
    )
  }

  // 如果没有 LayerPack
  if (!layerPack || !hasOutputs) {
    return (
      <div className="h-full flex items-center justify-center bg-canvas-dark">
        <div className="text-center text-ink-muted">
          <ImageIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>尚未渲染</p>
          <p className="text-xs mt-1">点击"渲染当前"生成图片</p>
        </div>
      </div>
    )
  }

  const outputs = layerPack.outputs as {
    full: { url: string }
    bg?: { url: string }
    char?: { url: string }
    fg?: { url: string }
    text?: { url: string }
  }

  return (
    <div className="h-full flex flex-col bg-canvas-dark">
      {/* 工具栏 */}
      <div className="flex items-center justify-between px-3 py-2 bg-panel/50 border-b border-panel-border">
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant={viewer.isRoiSelecting ? 'default' : 'outline'}
            onClick={() => setIsRoiSelecting(!viewer.isRoiSelecting)}
            className="h-7 text-xs"
          >
            <Crosshair className="w-3.5 h-3.5 mr-1.5" />
            选区工具
          </Button>
          {viewer.roi && (
            <Button
              size="sm"
              variant="outline"
              onClick={clearRoi}
              className="h-7 text-xs"
            >
              <X className="w-3.5 h-3.5 mr-1.5" />
              清除选区
            </Button>
          )}
        </div>
        {viewer.roi && (
          <div className="text-xs text-ink-muted">
            选区: ({Math.round(viewer.roi.x)}, {Math.round(viewer.roi.y)}) -
            {Math.round(viewer.roi.w)} x {Math.round(viewer.roi.h)}
          </div>
        )}
      </div>

      {/* 图层叠加显示区 */}
      <div
        ref={containerRef}
        className={cn(
          "flex-1 relative overflow-hidden",
          viewer.isRoiSelecting && "cursor-crosshair"
        )}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="relative">
            {/* 背景层 */}
            {outputs.bg && viewer.layerVisibility.bg && (
              <img
                src={outputs.bg.url}
                alt="Background"
                className="max-w-full max-h-full"
                style={{ opacity: viewer.layerOpacity.bg }}
                draggable={false}
              />
            )}

            {/* 角色层 */}
            {outputs.char && viewer.layerVisibility.char && (
              <img
                src={outputs.char.url}
                alt="Character"
                className="absolute inset-0 max-w-full max-h-full"
                style={{ opacity: viewer.layerOpacity.char }}
                draggable={false}
              />
            )}

            {/* 前景层 */}
            {outputs.fg && viewer.layerVisibility.fg && (
              <img
                src={outputs.fg.url}
                alt="Foreground"
                className="absolute inset-0 max-w-full max-h-full"
                style={{ opacity: viewer.layerOpacity.fg }}
                draggable={false}
              />
            )}

            {/* 如果没有分层，显示完整图 */}
            {!outputs.bg && !outputs.char && !outputs.fg && outputs.full && (
              <img
                src={outputs.full.url}
                alt="Full"
                className="max-w-full max-h-full"
                draggable={false}
              />
            )}

            {/* ROI 选区显示 */}
            {(viewer.roi || currentRoi) && (
              <div
                className="absolute border-2 border-accent bg-accent/20 pointer-events-none"
                style={{
                  left: (currentRoi || viewer.roi)!.x,
                  top: (currentRoi || viewer.roi)!.y,
                  width: (currentRoi || viewer.roi)!.w,
                  height: (currentRoi || viewer.roi)!.h,
                }}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
