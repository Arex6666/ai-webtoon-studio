'use client';

import React, { useState, useEffect } from 'react';
import { Template, MOCK_TEMPLATES } from '@/lib/schema/template';
import { Palette, Check, Sparkles, Loader2 } from 'lucide-react';

interface TemplateSelectorProps {
    chapterId: string;
    currentTemplateId?: string;
    onSelect?: (template: Template) => void;
    onApply?: (templateId: string) => Promise<void>;
    className?: string;
}

/**
 * 模板选择器 - 选择并应用模板
 */
export function TemplateSelector({
    chapterId,
    currentTemplateId,
    onSelect,
    onApply,
    className = '',
}: TemplateSelectorProps) {
    const [templates, setTemplates] = useState<Template[]>(MOCK_TEMPLATES);
    const [selectedId, setSelectedId] = useState<string | null>(currentTemplateId || null);
    const [isLoading, setIsLoading] = useState(false);
    const [isApplying, setIsApplying] = useState(false);

    // 加载模板列表
    useEffect(() => {
        fetchTemplates();
    }, []);

    const fetchTemplates = async () => {
        setIsLoading(true);
        try {
            const response = await fetch('/api/v1/templates');
            if (response.ok) {
                const data = await response.json();
                if (data.length > 0) {
                    setTemplates(data);
                }
            }
        } catch (error) {
            console.error('Failed to fetch templates:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleSelect = (template: Template) => {
        setSelectedId(template.id);
        onSelect?.(template);
    };

    const handleApply = async () => {
        if (!selectedId) return;

        setIsApplying(true);
        try {
            if (onApply) {
                await onApply(selectedId);
            } else {
                // 默认 API 调用
                const response = await fetch(`/api/v1/chapters/${chapterId}/apply-template`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        template_id: selectedId,
                        apply_to_panels: true,
                    }),
                });

                if (!response.ok) {
                    throw new Error('Failed to apply template');
                }

                const result = await response.json();
                console.log('Template applied:', result);
            }
        } catch (error) {
            console.error('Failed to apply template:', error);
        } finally {
            setIsApplying(false);
        }
    };

    return (
        <div className={`template-selector ${className}`}>
            {/* 标题 */}
            <div className="flex items-center gap-2 mb-4">
                <Palette className="w-5 h-5 text-emerald-400" />
                <h3 className="font-medium">模板库</h3>
            </div>

            {/* 加载状态 */}
            {isLoading && (
                <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
                </div>
            )}

            {/* 模板网格 */}
            <div className="grid grid-cols-2 gap-3 mb-4">
                {templates.map((template) => (
                    <div
                        key={template.id}
                        onClick={() => handleSelect(template)}
                        className={`
              template-card relative p-3 rounded-lg cursor-pointer transition-all
              ${selectedId === template.id
                                ? 'bg-emerald-600/20 border-2 border-emerald-500'
                                : 'bg-gray-800/50 border border-gray-700 hover:border-gray-600'}
            `}
                    >
                        {/* 选中标记 */}
                        {selectedId === template.id && (
                            <div className="absolute top-2 right-2">
                                <Check className="w-4 h-4 text-emerald-400" />
                            </div>
                        )}

                        {/* 预览图 */}
                        <div className="aspect-video bg-gray-700 rounded mb-2 overflow-hidden">
                            {template.styleProfileId ? (
                                <div className="w-full h-full flex items-center justify-center text-2xl">
                                    {template.name.includes('雨') ? '🌧️' :
                                        template.name.includes('赛博') ? '🌃' :
                                            '🎨'}
                                </div>
                            ) : (
                                <div className="w-full h-full flex items-center justify-center">
                                    <Sparkles className="w-6 h-6 text-gray-500" />
                                </div>
                            )}
                        </div>

                        {/* 模板信息 */}
                        <h4 className="font-medium text-sm truncate">{template.name}</h4>
                        <p className="text-xs text-gray-500 truncate mt-1">
                            {template.description || '无描述'}
                        </p>

                        {/* 资产数量 */}
                        <div className="flex gap-2 mt-2 text-xs text-gray-500">
                            {template.identityAssetIds.length > 0 && (
                                <span>👤 {template.identityAssetIds.length}</span>
                            )}
                            {template.sceneAssetIds.length > 0 && (
                                <span>🏞️ {template.sceneAssetIds.length}</span>
                            )}
                        </div>
                    </div>
                ))}
            </div>

            {/* 应用按钮 */}
            <button
                onClick={handleApply}
                disabled={!selectedId || isApplying}
                className="w-full flex items-center justify-center gap-2 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg transition-colors"
            >
                {isApplying ? (
                    <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>应用中...</span>
                    </>
                ) : (
                    <>
                        <Sparkles className="w-4 h-4" />
                        <span>应用模板</span>
                    </>
                )}
            </button>

            {/* 提示 */}
            <p className="text-xs text-gray-500 mt-2 text-center">
                应用模板将更新章节的风格、角色和场景设置
            </p>

            <style jsx>{`
        .template-selector {
          background: var(--color-bg-secondary, #0f172a);
          border-radius: 8px;
          padding: 16px;
        }
      `}</style>
        </div>
    );
}

export default TemplateSelector;
