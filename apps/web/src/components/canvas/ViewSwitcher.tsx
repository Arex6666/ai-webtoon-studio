'use client';

import { useState } from 'react';

export type ViewMode = 'storyboard' | 'stage';

interface ViewSwitcherProps {
  mode: ViewMode;
  onModeChange: (mode: ViewMode) => void;
  panelCount?: number;
  selectedPanelIndex?: number;
}

export function ViewSwitcher({
  mode,
  onModeChange,
  panelCount = 0,
  selectedPanelIndex,
}: ViewSwitcherProps) {
  return (
    <div className="flex items-center justify-between px-4 py-2 bg-zinc-900 border-b border-zinc-800">
      {/* 视图切换 Tab */}
      <div className="flex items-center gap-1 p-1 bg-zinc-800 rounded-lg">
        <button
          onClick={() => onModeChange('storyboard')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${mode === 'storyboard'
              ? 'bg-emerald-600 text-white shadow-lg'
              : 'text-zinc-400 hover:text-white hover:bg-zinc-700'
            }`}
        >
          <span className="mr-2">📋</span>
          故事板
        </button>
        <button
          onClick={() => onModeChange('stage')}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${mode === 'stage'
              ? 'bg-emerald-600 text-white shadow-lg'
              : 'text-zinc-400 hover:text-white hover:bg-zinc-700'
            }`}
        >
          <span className="mr-2">🎭</span>
          舞台
        </button>
      </div>

      {/* 面板信息 */}
      <div className="flex items-center gap-4 text-sm text-zinc-400">
        {panelCount > 0 && (
          <span>
            共 <span className="text-white font-medium">{panelCount}</span> 个分镜
          </span>
        )}
        {selectedPanelIndex !== undefined && mode === 'stage' && (
          <span>
            正在编辑: <span className="text-emerald-400 font-medium">#{selectedPanelIndex + 1}</span>
          </span>
        )}
      </div>

      {/* 工具栏 */}
      <div className="flex items-center gap-2">
        <button
          className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors"
          title="撤销"
        >
          ↩️
        </button>
        <button
          className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors"
          title="重做"
        >
          ↪️
        </button>
        <div className="w-px h-6 bg-zinc-700 mx-2" />
        <button
          className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors"
          title="缩放"
        >
          🔍
        </button>
        <button
          className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors"
          title="全屏"
        >
          ⛶
        </button>
      </div>
    </div>
  );
}
