'use client';

import React, { useState, useCallback } from 'react';
import { BubbleRenderer } from './BubbleRenderer';
import { Bubble, PanelTypeset, BubbleStyle, BUBBLE_PRESETS, BUBBLE_STYLE_NAMES } from '@/lib/schema/bubble';
import { Plus, Trash2, Copy, Type, MessageSquare } from 'lucide-react';
import { v4 as uuidv4 } from 'uuid';

interface BubbleEditorProps {
    panelId: string;
    imageUrl: string;
    initialBubbles?: Bubble[];
    onSave?: (bubbles: Bubble[]) => void;
    className?: string;
}

/**
 * 气泡编辑器 - 在面板上添加和编辑气泡
 */
export function BubbleEditor({
    panelId,
    imageUrl,
    initialBubbles = [],
    onSave,
    className = '',
}: BubbleEditorProps) {
    const [bubbles, setBubbles] = useState<Bubble[]>(initialBubbles);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [currentStyle, setCurrentStyle] = useState<BubbleStyle>('speech');

    const selectedBubble = bubbles.find(b => b.id === selectedId);

    // 添加新气泡
    const handleAddBubble = useCallback(() => {
        const preset = BUBBLE_PRESETS[currentStyle];
        const newBubble: Bubble = {
            id: uuidv4(),
            text: '',
            style: currentStyle,
            x: 50,
            y: 50,
            width: 200,
            height: 80,
            fontSize: 24,
            fontFamily: 'Noto Sans SC',
            fontWeight: 'normal',
            textAlign: 'center',
            textColor: '#000000',
            backgroundColor: '#ffffff',
            borderColor: '#000000',
            borderWidth: 2,
            borderRadius: 20,
            tailDirection: 'bottom',
            tailSize: 15,
            shadow: false,
            glow: false,
            rotation: 0,
            zIndex: bubbles.length + 1,
            ...preset,
        };

        setBubbles(prev => [...prev, newBubble]);
        setSelectedId(newBubble.id);
        setEditingId(newBubble.id);
    }, [currentStyle, bubbles.length]);

    // 删除气泡
    const handleDeleteBubble = useCallback(() => {
        if (!selectedId) return;
        setBubbles(prev => prev.filter(b => b.id !== selectedId));
        setSelectedId(null);
        setEditingId(null);
    }, [selectedId]);

    // 复制气泡
    const handleDuplicateBubble = useCallback(() => {
        if (!selectedBubble) return;
        const newBubble: Bubble = {
            ...selectedBubble,
            id: uuidv4(),
            x: selectedBubble.x + 5,
            y: selectedBubble.y + 5,
            zIndex: bubbles.length + 1,
        };
        setBubbles(prev => [...prev, newBubble]);
        setSelectedId(newBubble.id);
    }, [selectedBubble, bubbles.length]);

    // 更新气泡文本
    const handleTextChange = useCallback((id: string, text: string) => {
        setBubbles(prev => prev.map(b =>
            b.id === id ? { ...b, text } : b
        ));
    }, []);

    // 更新气泡属性
    const handleBubbleUpdate = useCallback((id: string, updates: Partial<Bubble>) => {
        setBubbles(prev => prev.map(b =>
            b.id === id ? { ...b, ...updates } : b
        ));
    }, []);

    // 保存
    const handleSave = () => {
        onSave?.(bubbles);
    };

    return (
        <div className={`bubble-editor ${className}`}>
            <div className="flex h-full">
                {/* 画布区域 */}
                <div className="flex-1 relative bg-gray-900 overflow-hidden">
                    {/* 背景图 */}
                    <img
                        src={imageUrl}
                        alt="Panel"
                        className="w-full h-full object-contain"
                        onClick={() => {
                            setSelectedId(null);
                            setEditingId(null);
                        }}
                    />

                    {/* 渲染所有气泡 */}
                    {bubbles.map(bubble => (
                        <BubbleRenderer
                            key={bubble.id}
                            bubble={bubble}
                            isSelected={bubble.id === selectedId}
                            isEditing={bubble.id === editingId}
                            onClick={() => {
                                setSelectedId(bubble.id);
                                setEditingId(null);
                            }}
                            onDoubleClick={() => {
                                setSelectedId(bubble.id);
                                setEditingId(bubble.id);
                            }}
                            onTextChange={(text) => handleTextChange(bubble.id, text)}
                        />
                    ))}
                </div>

                {/* 右侧工具栏 */}
                <div className="w-64 bg-gray-800 border-l border-gray-700 p-4 overflow-y-auto">
                    {/* 气泡类型选择 */}
                    <div className="mb-4">
                        <label className="text-xs text-gray-400 mb-2 block">气泡类型</label>
                        <div className="grid grid-cols-2 gap-2">
                            {(Object.keys(BUBBLE_STYLE_NAMES) as BubbleStyle[]).map(style => (
                                <button
                                    key={style}
                                    onClick={() => setCurrentStyle(style)}
                                    className={`px-3 py-2 text-sm rounded-lg transition-colors ${currentStyle === style
                                        ? 'bg-emerald-600 text-white'
                                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                                        }`}
                                >
                                    {BUBBLE_STYLE_NAMES[style]}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* 操作按钮 */}
                    <div className="flex gap-2 mb-4">
                        <button
                            onClick={handleAddBubble}
                            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-lg"
                        >
                            <Plus className="w-4 h-4" />
                            <span>添加</span>
                        </button>
                        <button
                            onClick={handleDeleteBubble}
                            disabled={!selectedId}
                            className="px-3 py-2 bg-red-600 hover:bg-red-700 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg"
                        >
                            <Trash2 className="w-4 h-4" />
                        </button>
                        <button
                            onClick={handleDuplicateBubble}
                            disabled={!selectedId}
                            className="px-3 py-2 bg-gray-600 hover:bg-gray-500 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg"
                        >
                            <Copy className="w-4 h-4" />
                        </button>
                    </div>

                    {/* 选中气泡属性 */}
                    {selectedBubble && (
                        <div className="space-y-4">
                            <h4 className="text-sm font-medium text-gray-300 border-b border-gray-700 pb-2">
                                属性
                            </h4>

                            {/* 字体大小 */}
                            <div>
                                <label className="text-xs text-gray-400 mb-1 block">字体大小</label>
                                <input
                                    type="range"
                                    min="12"
                                    max="72"
                                    value={selectedBubble.fontSize}
                                    onChange={(e) => handleBubbleUpdate(selectedBubble.id, {
                                        fontSize: parseInt(e.target.value)
                                    })}
                                    className="w-full accent-emerald-500"
                                />
                                <span className="text-xs text-gray-500">{selectedBubble.fontSize}px</span>
                            </div>

                            {/* 文字颜色 */}
                            <div>
                                <label className="text-xs text-gray-400 mb-1 block">文字颜色</label>
                                <input
                                    type="color"
                                    value={selectedBubble.textColor}
                                    onChange={(e) => handleBubbleUpdate(selectedBubble.id, {
                                        textColor: e.target.value
                                    })}
                                    className="w-full h-8 rounded"
                                />
                            </div>

                            {/* 背景颜色 */}
                            <div>
                                <label className="text-xs text-gray-400 mb-1 block">背景颜色</label>
                                <input
                                    type="color"
                                    value={selectedBubble.backgroundColor}
                                    onChange={(e) => handleBubbleUpdate(selectedBubble.id, {
                                        backgroundColor: e.target.value
                                    })}
                                    className="w-full h-8 rounded"
                                />
                            </div>

                            {/* 边框圆角 */}
                            <div>
                                <label className="text-xs text-gray-400 mb-1 block">圆角</label>
                                <input
                                    type="range"
                                    min="0"
                                    max="50"
                                    value={selectedBubble.borderRadius}
                                    onChange={(e) => handleBubbleUpdate(selectedBubble.id, {
                                        borderRadius: parseInt(e.target.value)
                                    })}
                                    className="w-full accent-emerald-500"
                                />
                            </div>

                            {/* 阴影 */}
                            <div className="flex items-center gap-2">
                                <input
                                    type="checkbox"
                                    checked={selectedBubble.shadow}
                                    onChange={(e) => handleBubbleUpdate(selectedBubble.id, {
                                        shadow: e.target.checked
                                    })}
                                    className="accent-emerald-500"
                                />
                                <label className="text-sm text-gray-300">阴影</label>
                            </div>
                        </div>
                    )}

                    {/* 保存按钮 */}
                    <button
                        onClick={handleSave}
                        className="w-full mt-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg"
                    >
                        保存排版
                    </button>

                    {/* 气泡列表 */}
                    <div className="mt-4">
                        <h4 className="text-xs text-gray-400 mb-2">气泡列表 ({bubbles.length})</h4>
                        <div className="space-y-1">
                            {bubbles.map((bubble, index) => (
                                <div
                                    key={bubble.id}
                                    onClick={() => setSelectedId(bubble.id)}
                                    className={`flex items-center gap-2 px-2 py-1 rounded cursor-pointer ${bubble.id === selectedId
                                        ? 'bg-emerald-600/30 border border-emerald-500/50'
                                        : 'bg-gray-700/50 hover:bg-gray-700'
                                        }`}
                                >
                                    <MessageSquare className="w-3 h-3 text-gray-400" />
                                    <span className="text-sm truncate flex-1">
                                        {bubble.text || `气泡 ${index + 1}`}
                                    </span>
                                    <span className="text-xs text-gray-500">
                                        {BUBBLE_STYLE_NAMES[bubble.style]}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            <style jsx>{`
        .bubble-editor {
          height: 100%;
          min-height: 600px;
        }
      `}</style>
        </div>
    );
}

export default BubbleEditor;
