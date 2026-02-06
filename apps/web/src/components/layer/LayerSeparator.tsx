'use client';

import React, { useState, useCallback, useRef } from 'react';
import { Scissors, RotateCcw, Loader2, Target } from 'lucide-react';

interface LayerSeparatorProps {
    imageUrl: string;
    panelId: string;
    onSeparate: (points: [number, number][]) => Promise<void>;
    onResult?: (result: { maskUrl: string; charUrl: string; bgUrl: string }) => void;
    className?: string;
}

/**
 * 图层分离器 - 交互式选择分离点
 */
export function LayerSeparator({
    imageUrl,
    panelId,
    onSeparate,
    onResult,
    className = '',
}: LayerSeparatorProps) {
    const [points, setPoints] = useState<[number, number][]>([]);
    const [isProcessing, setIsProcessing] = useState(false);
    const imageRef = useRef<HTMLImageElement>(null);

    // 点击添加分离点
    const handleImageClick = useCallback((e: React.MouseEvent<HTMLImageElement>) => {
        if (isProcessing) return;

        const img = imageRef.current;
        if (!img) return;

        const rect = img.getBoundingClientRect();
        const scaleX = img.naturalWidth / rect.width;
        const scaleY = img.naturalHeight / rect.height;

        const x = Math.round((e.clientX - rect.left) * scaleX);
        const y = Math.round((e.clientY - rect.top) * scaleY);

        setPoints(prev => [...prev, [x, y]]);
    }, [isProcessing]);

    // 清除所有点
    const handleClear = () => {
        setPoints([]);
    };

    // 执行分离
    const handleSeparate = async () => {
        if (points.length === 0) {
            // 默认使用图片中心
            const centerX = 540;
            const centerY = 960;
            setPoints([[centerX, centerY]]);
            await executeSeparation([[centerX, centerY]]);
        } else {
            await executeSeparation(points);
        }
    };

    const executeSeparation = async (pointsToUse: [number, number][]) => {
        setIsProcessing(true);
        try {
            await onSeparate(pointsToUse);
        } finally {
            setIsProcessing(false);
        }
    };

    return (
        <div className={`layer-separator ${className}`}>
            {/* 图片预览 */}
            <div className="relative rounded-lg overflow-hidden bg-gray-900">
                <img
                    ref={imageRef}
                    src={imageUrl}
                    alt="Source"
                    className="w-full cursor-crosshair"
                    onClick={handleImageClick}
                />

                {/* 渲染分离点 */}
                {points.map((point, index) => {
                    const img = imageRef.current;
                    if (!img) return null;

                    const rect = img.getBoundingClientRect();
                    const scaleX = rect.width / img.naturalWidth;
                    const scaleY = rect.height / img.naturalHeight;

                    return (
                        <div
                            key={index}
                            className="absolute w-6 h-6 -translate-x-1/2 -translate-y-1/2 pointer-events-none"
                            style={{
                                left: point[0] * scaleX,
                                top: point[1] * scaleY,
                            }}
                        >
                            <Target className="w-6 h-6 text-red-500 drop-shadow-lg" />
                            <span className="absolute -top-4 left-1/2 -translate-x-1/2 text-xs bg-red-500 px-1 rounded">
                                {index + 1}
                            </span>
                        </div>
                    );
                })}

                {/* 处理中遮罩 */}
                {isProcessing && (
                    <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                        <div className="text-center">
                            <Loader2 className="w-8 h-8 animate-spin text-emerald-400 mx-auto mb-2" />
                            <span className="text-sm text-gray-300">分离中...</span>
                        </div>
                    </div>
                )}
            </div>

            {/* 操作按钮 */}
            <div className="flex items-center gap-3 mt-4">
                <button
                    onClick={handleSeparate}
                    disabled={isProcessing}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-600 rounded-lg transition-colors"
                >
                    {isProcessing ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                        <Scissors className="w-4 h-4" />
                    )}
                    <span>{points.length > 0 ? `分离 (${points.length} 点)` : '自动分离'}</span>
                </button>

                <button
                    onClick={handleClear}
                    disabled={isProcessing || points.length === 0}
                    className="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-500 rounded-lg transition-colors"
                >
                    <RotateCcw className="w-4 h-4" />
                </button>
            </div>

            {/* 使用说明 */}
            <p className="text-xs text-gray-500 mt-3">
                点击图片选择要保留的角色区域，或直接点击"自动分离"使用默认中心点。
            </p>

            <style jsx>{`
        .layer-separator {
          background: var(--color-bg-secondary, #0f172a);
          border-radius: 8px;
          padding: 16px;
        }
      `}</style>
        </div>
    );
}

export default LayerSeparator;
