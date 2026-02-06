'use client';

import { useState, useCallback } from 'react';

interface PanelData {
  id: string;
  order: number;
  thumbnailUrl?: string;
  action_description: string;
  dialogue?: string;
  shot_type: string;
  emotion: string;
  status: 'draft' | 'rendering' | 'ready' | 'needs_fix';
  duration?: number;
}

interface StoryboardViewProps {
  panels: PanelData[];
  selectedPanelId?: string;
  onPanelSelect?: (panelId: string) => void;
  onPanelReorder?: (panelId: string, newOrder: number) => void;
  onEditInStage?: (panelId: string) => void;
}

const STATUS_STYLES = {
  draft: { bg: 'bg-zinc-500', text: '草稿' },
  rendering: { bg: 'bg-blue-500 animate-pulse', text: '渲染中' },
  ready: { bg: 'bg-emerald-500', text: '完成' },
  needs_fix: { bg: 'bg-amber-500', text: '需修复' },
};

const SHOT_ICONS: Record<string, string> = {
  extreme_close: '🔍',
  close: '👤',
  medium: '🧍',
  full: '🚶',
  wide: '🏞️',
  extreme_wide: '🌄',
};

const EMOTION_ICONS: Record<string, string> = {
  neutral: '😐',
  happy: '😊',
  sad: '😢',
  angry: '😠',
  surprised: '😲',
  fear: '😨',
};

export function StoryboardView({
  panels,
  selectedPanelId,
  onPanelSelect,
  onPanelReorder,
  onEditInStage,
}: StoryboardViewProps) {
  const [draggedPanel, setDraggedPanel] = useState<string | null>(null);

  const handleDragStart = useCallback((e: React.DragEvent, panelId: string) => {
    setDraggedPanel(panelId);
    e.dataTransfer.effectAllowed = 'move';
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent, targetOrder: number) => {
      e.preventDefault();
      if (draggedPanel) {
        onPanelReorder?.(draggedPanel, targetOrder);
      }
      setDraggedPanel(null);
    },
    [draggedPanel, onPanelReorder]
  );

  if (panels.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center bg-zinc-950">
        <div className="text-center text-zinc-500">
          <div className="text-6xl mb-4">📋</div>
          <p className="text-lg">暂无分镜</p>
          <p className="text-sm mt-2">使用左侧剧本编辑器自动生成分镜</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto bg-zinc-950 p-6">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        {panels.map((panel) => {
          const statusStyle = STATUS_STYLES[panel.status];
          const isSelected = panel.id === selectedPanelId;
          const isDragging = panel.id === draggedPanel;

          return (
            <div
              key={panel.id}
              draggable
              onDragStart={(e) => handleDragStart(e, panel.id)}
              onDragOver={handleDragOver}
              onDrop={(e) => handleDrop(e, panel.order)}
              onClick={() => onPanelSelect?.(panel.id)}
              onDoubleClick={() => onEditInStage?.(panel.id)}
              className={`relative group rounded-xl border-2 transition-all duration-200 cursor-pointer overflow-hidden ${isSelected
                  ? 'border-emerald-500 ring-2 ring-emerald-500/30'
                  : 'border-zinc-700 hover:border-zinc-600'
                } ${isDragging ? 'opacity-50 scale-95' : ''}`}
            >
              {/* 序号标签 */}
              <div className="absolute top-2 left-2 z-10 px-2 py-0.5 bg-black/70 rounded text-xs text-white font-mono">
                #{panel.order + 1}
              </div>

              {/* 状态指示 */}
              <div className="absolute top-2 right-2 z-10">
                <div
                  className={`w-2.5 h-2.5 rounded-full ${statusStyle.bg}`}
                  title={statusStyle.text}
                />
              </div>

              {/* 缩略图 */}
              <div className="aspect-[9/16] bg-zinc-900">
                {panel.thumbnailUrl ? (
                  <img
                    src={panel.thumbnailUrl}
                    alt={`Panel ${panel.order + 1}`}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-zinc-700">
                    <div className="text-center">
                      <span className="text-4xl block mb-2">🎬</span>
                      <span className="text-xs">{statusStyle.text}</span>
                    </div>
                  </div>
                )}

                {/* Hover 操作层 */}
                <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onEditInStage?.(panel.id);
                    }}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm rounded-lg"
                  >
                    编辑图层
                  </button>
                </div>
              </div>

              {/* 信息区域 */}
              <div className="p-3 bg-zinc-800/50">
                {/* 属性标签 */}
                <div className="flex items-center gap-2 mb-2">
                  <span
                    className="px-2 py-0.5 bg-zinc-700 rounded text-xs text-zinc-300"
                    title={panel.shot_type}
                  >
                    {SHOT_ICONS[panel.shot_type] || '📷'} {panel.shot_type}
                  </span>
                  <span
                    className="px-2 py-0.5 bg-zinc-700 rounded text-xs text-zinc-300"
                    title={panel.emotion}
                  >
                    {EMOTION_ICONS[panel.emotion] || '😐'}
                  </span>
                  {panel.duration && (
                    <span className="text-xs text-zinc-500 ml-auto">
                      {panel.duration}s
                    </span>
                  )}
                </div>

                {/* 动作描述 */}
                <p className="text-xs text-zinc-400 line-clamp-2">
                  {panel.action_description}
                </p>

                {/* 对话 */}
                {panel.dialogue && (
                  <p className="text-xs text-emerald-300 italic mt-1 line-clamp-1">
                    "{panel.dialogue}"
                  </p>
                )}
              </div>
            </div>
          );
        })}

        {/* 添加新分镜按钮 */}
        <div
          className="aspect-[9/16] rounded-xl border-2 border-dashed border-zinc-700 hover:border-emerald-500 transition-colors flex items-center justify-center cursor-pointer bg-zinc-800/30"
          onClick={() => { }}
        >
          <div className="text-center text-zinc-500">
            <span className="text-3xl block mb-2">➕</span>
            <span className="text-sm">添加分镜</span>
          </div>
        </div>
      </div>
    </div>
  );
}
