'use client';

import React, { useState, useCallback } from 'react';
import { Layer, LayerStack, LayerType, LAYER_NAMES, LAYER_COLORS } from '@/lib/schema/layers';
import { Eye, EyeOff, Layers, Download, RefreshCw } from 'lucide-react';

interface LayerViewerProps {
    stack: LayerStack;
    onLayerToggle?: (type: LayerType, visible: boolean) => void;
    onLayerOpacityChange?: (type: LayerType, opacity: number) => void;
    onRefresh?: () => void;
    className?: string;
}

/**
 * 图层查看器 - 显示分层图像并支持切换
 */
export function LayerViewer({
    stack,
    onLayerToggle,
    onLayerOpacityChange,
    onRefresh,
    className = '',
}: LayerViewerProps) {
    const [selectedLayer, setSelectedLayer] = useState<LayerType | null>(null);

    const visibleLayers = stack.layers.filter(l => l.visible && l.url);

    return (
        <div className={`layer-viewer ${className}`}>
            {/* 预览区域 */}
            <div className="layer-preview relative bg-gray-900 rounded-lg overflow-hidden aspect-[9/16]">
                {/* 棋盘格背景 */}
                <div
                    className="absolute inset-0"
                    style={{
                        backgroundImage: 'linear-gradient(45deg, #333 25%, transparent 25%), linear-gradient(-45deg, #333 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #333 75%), linear-gradient(-45deg, transparent 75%, #333 75%)',
                        backgroundSize: '20px 20px',
                        backgroundPosition: '0 0, 0 10px, 10px -10px, -10px 0px',
                    }}
                />

                {/* 渲染图层 */}
                {visibleLayers.map((layer, index) => (
                    <img
                        key={layer.type}
                        src={layer.url!}
                        alt={LAYER_NAMES[layer.type]}
                        className="absolute inset-0 w-full h-full object-contain"
                        style={{
                            opacity: layer.opacity,
                            mixBlendMode: layer.blendMode,
                            zIndex: index,
                        }}
                    />
                ))}

                {/* 空状态 */}
                {visibleLayers.length === 0 && (
                    <div className="absolute inset-0 flex items-center justify-center text-gray-500">
                        <Layers className="w-12 h-12" />
                    </div>
                )}
            </div>

            {/* 图层列表 */}
            <div className="layer-list mt-4 space-y-2">
                <div className="flex items-center justify-between mb-2">
                    <h4 className="text-sm font-medium text-gray-300">图层 ({stack.layers.length})</h4>
                    {onRefresh && (
                        <button
                            onClick={onRefresh}
                            className="p-1 hover:bg-gray-700 rounded"
                            title="刷新图层"
                        >
                            <RefreshCw className="w-4 h-4" />
                        </button>
                    )}
                </div>

                {stack.layers.map((layer) => (
                    <LayerItem
                        key={layer.type}
                        layer={layer}
                        isSelected={selectedLayer === layer.type}
                        onClick={() => setSelectedLayer(layer.type)}
                        onToggle={(visible) => onLayerToggle?.(layer.type, visible)}
                        onOpacityChange={(opacity) => onLayerOpacityChange?.(layer.type, opacity)}
                    />
                ))}
            </div>

            <style jsx>{`
        .layer-viewer {
          background: var(--color-bg-secondary, #0f172a);
          border-radius: 8px;
          padding: 16px;
        }
      `}</style>
        </div>
    );
}

interface LayerItemProps {
    layer: Layer;
    isSelected: boolean;
    onClick: () => void;
    onToggle: (visible: boolean) => void;
    onOpacityChange: (opacity: number) => void;
}

function LayerItem({ layer, isSelected, onClick, onToggle, onOpacityChange }: LayerItemProps) {
    return (
        <div
            className={`
        layer-item flex items-center gap-3 p-2 rounded-lg cursor-pointer
        transition-colors
        ${isSelected ? 'bg-emerald-500/20 border border-emerald-500/50' : 'bg-gray-800/50 border border-transparent hover:bg-gray-700/50'}
      `}
            onClick={onClick}
        >
            {/* 可见性切换 */}
            <button
                onClick={(e) => {
                    e.stopPropagation();
                    onToggle(!layer.visible);
                }}
                className="p-1 hover:bg-gray-600 rounded"
            >
                {layer.visible ? (
                    <Eye className="w-4 h-4 text-gray-300" />
                ) : (
                    <EyeOff className="w-4 h-4 text-gray-500" />
                )}
            </button>

            {/* 颜色标识 */}
            <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: LAYER_COLORS[layer.type] }}
            />

            {/* 图层名称 */}
            <span className={`flex-1 text-sm ${layer.visible ? 'text-gray-200' : 'text-gray-500'}`}>
                {LAYER_NAMES[layer.type]}
            </span>

            {/* 缩略图 */}
            {layer.url && (
                <div className="w-8 h-8 rounded overflow-hidden bg-gray-700">
                    <img
                        src={layer.url}
                        alt=""
                        className="w-full h-full object-cover"
                    />
                </div>
            )}

            {/* 透明度滑块 */}
            <input
                type="range"
                min="0"
                max="100"
                value={layer.opacity * 100}
                onChange={(e) => onOpacityChange(parseInt(e.target.value) / 100)}
                onClick={(e) => e.stopPropagation()}
                className="w-16 h-1 accent-emerald-500"
                title={`透明度: ${Math.round(layer.opacity * 100)}%`}
            />
        </div>
    );
}

export default LayerViewer;
