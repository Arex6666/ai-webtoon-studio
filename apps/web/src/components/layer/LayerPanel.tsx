'use client';

import React, { useState, useEffect } from 'react';
import { LayerViewer } from './LayerViewer';
import { LayerSeparator } from './LayerSeparator';
import { LayerStack, Layer, LayerType, LAYER_NAMES } from '@/lib/schema/layers';
import { Layers, Split, Download, ChevronDown, ChevronUp } from 'lucide-react';

interface LayerPanelProps {
    panelId: string;
    layerpackId?: string;
    sourceImageUrl?: string;
    initialLayers?: Partial<Record<LayerType, string>>;
    onLayersUpdated?: (layers: Layer[]) => void;
    className?: string;
}

/**
 * 图层面板 - 完整的分层输出管理
 */
export function LayerPanel({
    panelId,
    layerpackId,
    sourceImageUrl,
    initialLayers,
    onLayersUpdated,
    className = '',
}: LayerPanelProps) {
    const [mode, setMode] = useState<'view' | 'separate'>('view');
    const [isExpanded, setIsExpanded] = useState(true);
    const [stack, setStack] = useState<LayerStack>(() => ({
        panelId,
        layerpackId: layerpackId || null,
        layers: buildLayersFromInitial(initialLayers),
        width: 1080,
        height: 1920,
    }));

    // 构建初始图层
    function buildLayersFromInitial(layers?: Partial<Record<LayerType, string>>): Layer[] {
        const allTypes: LayerType[] = ['full', 'char', 'bg', 'mask', 'depth', 'pose', 'lineart'];
        return allTypes.map(type => ({
            type,
            url: layers?.[type] || null,
            visible: type === 'full' || (layers?.[type] ? true : false),
            opacity: 1,
            blendMode: 'normal' as const,
        }));
    }

    // 更新图层可见性
    const handleLayerToggle = (type: LayerType, visible: boolean) => {
        setStack(prev => ({
            ...prev,
            layers: prev.layers.map(l =>
                l.type === type ? { ...l, visible } : l
            ),
        }));
    };

    // 更新图层透明度
    const handleOpacityChange = (type: LayerType, opacity: number) => {
        setStack(prev => ({
            ...prev,
            layers: prev.layers.map(l =>
                l.type === type ? { ...l, opacity } : l
            ),
        }));
    };

    // 执行分离
    const handleSeparate = async (points: [number, number][]) => {
        try {
            const response = await fetch('/api/v1/generate/layer-separation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    panel_id: panelId,
                    source_image_url: sourceImageUrl,
                    point_coords: points,
                }),
            });

            if (!response.ok) throw new Error('Separation failed');

            const result = await response.json();

            // 模拟轮询结果（实际应该使用 WebSocket）
            setTimeout(() => {
                // 假设分离成功，更新图层
                setStack(prev => ({
                    ...prev,
                    layers: prev.layers.map(l => {
                        if (l.type === 'mask') return { ...l, url: result.outputs?.maskUrl || l.url };
                        if (l.type === 'char') return { ...l, url: result.outputs?.charUrl || l.url, visible: true };
                        if (l.type === 'bg') return { ...l, url: result.outputs?.bgUrl || l.url, visible: true };
                        return l;
                    }),
                }));
                setMode('view');
            }, 3000);

        } catch (error) {
            console.error('Layer separation failed:', error);
        }
    };

    // 下载图层
    const handleDownloadLayer = (layer: Layer) => {
        if (!layer.url) return;
        const link = document.createElement('a');
        link.href = layer.url;
        link.download = `${panelId}_${layer.type}.png`;
        link.click();
    };

    // 下载所有图层
    const handleDownloadAll = () => {
        stack.layers.filter(l => l.url).forEach(handleDownloadLayer);
    };

    return (
        <div className={`layer-panel ${className}`}>
            {/* 标题栏 */}
            <div
                className="flex items-center justify-between p-3 bg-gray-800/50 rounded-t-lg cursor-pointer"
                onClick={() => setIsExpanded(!isExpanded)}
            >
                <div className="flex items-center gap-2">
                    <Layers className="w-4 h-4 text-emerald-400" />
                    <span className="font-medium">图层</span>
                    <span className="text-xs text-gray-500">
                        ({stack.layers.filter(l => l.url).length}/{stack.layers.length})
                    </span>
                </div>
                {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </div>

            {isExpanded && (
                <div className="p-4 border-t border-gray-700/50">
                    {/* 模式切换 */}
                    <div className="flex gap-2 mb-4">
                        <button
                            onClick={() => setMode('view')}
                            className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg transition-colors ${mode === 'view'
                                ? 'bg-emerald-600 text-white'
                                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                                }`}
                        >
                            <Layers className="w-4 h-4" />
                            <span>查看</span>
                        </button>
                        <button
                            onClick={() => setMode('separate')}
                            disabled={!sourceImageUrl}
                            className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg transition-colors ${mode === 'separate'
                                ? 'bg-emerald-600 text-white'
                                : 'bg-gray-700 text-gray-300 hover:bg-gray-600 disabled:opacity-50'
                                }`}
                        >
                            <Split className="w-4 h-4" />
                            <span>分离</span>
                        </button>
                    </div>

                    {/* 内容区域 */}
                    {mode === 'view' ? (
                        <LayerViewer
                            stack={stack}
                            onLayerToggle={handleLayerToggle}
                            onLayerOpacityChange={handleOpacityChange}
                        />
                    ) : sourceImageUrl && (
                        <LayerSeparator
                            imageUrl={sourceImageUrl}
                            panelId={panelId}
                            onSeparate={handleSeparate}
                        />
                    )}

                    {/* 下载按钮 */}
                    {mode === 'view' && stack.layers.some(l => l.url) && (
                        <button
                            onClick={handleDownloadAll}
                            className="w-full flex items-center justify-center gap-2 mt-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
                        >
                            <Download className="w-4 h-4" />
                            <span>下载所有图层</span>
                        </button>
                    )}
                </div>
            )}

            <style jsx>{`
        .layer-panel {
          background: var(--color-bg-secondary, #0f172a);
          border-radius: 8px;
          border: 1px solid rgba(255,255,255,0.1);
        }
      `}</style>
        </div>
    );
}

export default LayerPanel;
