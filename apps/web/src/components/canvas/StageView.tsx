'use client';

import { useState, useCallback, useRef } from 'react';

interface Layer {
  id: string;
  name: string;
  type: 'bg' | 'char' | 'fg' | 'effect';
  visible: boolean;
  locked: boolean;
  imageUrl?: string;
  x: number;
  y: number;
  scale: number;
  rotation: number;
}

interface StageViewProps {
  panelId?: string;
  layers: Layer[];
  selectedLayerId?: string;
  onLayerSelect?: (layerId: string) => void;
  onLayerUpdate?: (layerId: string, updates: Partial<Layer>) => void;
  canvasWidth?: number;
  canvasHeight?: number;
}

export function StageView({
  panelId,
  layers,
  selectedLayerId,
  onLayerSelect,
  onLayerUpdate,
  canvasWidth = 768,
  canvasHeight = 1024,
}: StageViewProps) {
  const [zoom, setZoom] = useState(0.6);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const canvasRef = useRef<HTMLDivElement>(null);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent, layerId: string) => {
      const layer = layers.find((l) => l.id === layerId);
      if (layer?.locked) return;

      e.stopPropagation();
      onLayerSelect?.(layerId);
      setIsDragging(true);
      setDragStart({ x: e.clientX, y: e.clientY });
    },
    [layers, onLayerSelect]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDragging || !selectedLayerId) return;

      const layer = layers.find((l) => l.id === selectedLayerId);
      if (!layer || layer.locked) return;

      const dx = (e.clientX - dragStart.x) / zoom;
      const dy = (e.clientY - dragStart.y) / zoom;

      onLayerUpdate?.(selectedLayerId, {
        x: layer.x + dx,
        y: layer.y + dy,
      });

      setDragStart({ x: e.clientX, y: e.clientY });
    },
    [isDragging, selectedLayerId, layers, dragStart, zoom, onLayerUpdate]
  );

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    if (e.ctrlKey) {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.1 : 0.1;
      setZoom((z) => Math.max(0.1, Math.min(2, z + delta)));
    }
  }, []);

  if (!panelId) {
    return (
      <div className="flex-1 flex items-center justify-center bg-zinc-950">
        <div className="text-center text-zinc-500">
          <div className="text-6xl mb-4">🎭</div>
          <p className="text-lg">选择一个分镜进行编辑</p>
          <p className="text-sm mt-2">在故事板视图中双击分镜卡片</p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="flex-1 overflow-hidden bg-zinc-950 relative"
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onWheel={handleWheel}
    >
      {/* 缩放控制 */}
      <div className="absolute top-4 left-4 z-20 flex items-center gap-2 bg-zinc-800/80 backdrop-blur px-3 py-2 rounded-lg">
        <button
          onClick={() => setZoom((z) => Math.max(0.1, z - 0.1))}
          className="text-zinc-400 hover:text-white"
        >
          ➖
        </button>
        <span className="text-sm text-zinc-300 w-16 text-center">
          {Math.round(zoom * 100)}%
        </span>
        <button
          onClick={() => setZoom((z) => Math.min(2, z + 0.1))}
          className="text-zinc-400 hover:text-white"
        >
          ➕
        </button>
        <button
          onClick={() => setZoom(0.6)}
          className="text-xs text-zinc-500 hover:text-white ml-2"
        >
          重置
        </button>
      </div>

      {/* 画布容器 */}
      <div className="absolute inset-0 flex items-center justify-center p-8">
        <div
          ref={canvasRef}
          className="relative bg-zinc-900 shadow-2xl border border-zinc-700"
          style={{
            width: canvasWidth * zoom,
            height: canvasHeight * zoom,
          }}
        >
          {/* 图层渲染 */}
          {layers
            .filter((l) => l.visible)
            .sort((a, b) => {
              const order = { bg: 0, char: 1, fg: 2, effect: 3 };
              return order[a.type] - order[b.type];
            })
            .map((layer) => {
              const isSelected = layer.id === selectedLayerId;

              return (
                <div
                  key={layer.id}
                  className={`absolute cursor-move transition-shadow ${isSelected ? 'ring-2 ring-violet-500' : ''
                    } ${layer.locked ? 'cursor-not-allowed opacity-80' : ''}`}
                  style={{
                    left: layer.x * zoom,
                    top: layer.y * zoom,
                    transform: `scale(${layer.scale}) rotate(${layer.rotation}deg)`,
                    transformOrigin: 'top left',
                  }}
                  onMouseDown={(e) => handleMouseDown(e, layer.id)}
                >
                  {layer.imageUrl ? (
                    <img
                      src={layer.imageUrl}
                      alt={layer.name}
                      className="max-w-none"
                      style={{
                        width: 'auto',
                        height: 'auto',
                        maxWidth: canvasWidth * zoom * 0.8,
                        maxHeight: canvasHeight * zoom * 0.8,
                      }}
                      draggable={false}
                    />
                  ) : (
                    <div
                      className="bg-zinc-800/50 border-2 border-dashed border-zinc-600 flex items-center justify-center"
                      style={{
                        width: 200 * zoom,
                        height: 200 * zoom,
                      }}
                    >
                      <span className="text-zinc-500 text-sm">{layer.name}</span>
                    </div>
                  )}

                  {/* 选中时显示调整手柄 */}
                  {isSelected && !layer.locked && (
                    <>
                      <div className="absolute -top-1 -left-1 w-3 h-3 bg-blue-500 rounded-full cursor-nw-resize" />
                      <div className="absolute -top-1 -right-1 w-3 h-3 bg-blue-500 rounded-full cursor-ne-resize" />
                      <div className="absolute -bottom-1 -left-1 w-3 h-3 bg-blue-500 rounded-full cursor-sw-resize" />
                      <div className="absolute -bottom-1 -right-1 w-3 h-3 bg-blue-500 rounded-full cursor-se-resize" />
                    </>
                  )}
                </div>
              );
            })}

          {/* 空状态 */}
          {layers.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center text-zinc-600">
              <div className="text-center">
                <span className="text-4xl block mb-2">📦</span>
                <p>暂无图层</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 图层类型指示 */}
      <div className="absolute bottom-4 left-4 z-20 flex items-center gap-3 bg-zinc-800/80 backdrop-blur px-4 py-2 rounded-lg text-xs">
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-blue-500/50" /> BG
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-emerald-500/50" /> Char
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-amber-500/50" /> FG
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-purple-500/50" /> Effect
        </span>
      </div>
    </div>
  );
}
