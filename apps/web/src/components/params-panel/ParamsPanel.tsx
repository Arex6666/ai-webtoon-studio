'use client';

import { useState } from 'react';

type TabType = 'look' | 'act' | 'camera';

interface ParamsPanelProps {
  onParamsChange?: (params: Record<string, any>) => void;
}

// 预设配置
const PRESETS = {
  look: [
    { id: 'korean', name: '韩漫清爽', icon: '🇰🇷', values: { lineart: 70, color: 80, screentone: 20, texture: 30 } },
    { id: 'manga', name: '日漫线稿', icon: '🇯🇵', values: { lineart: 90, color: 40, screentone: 60, texture: 50 } },
    { id: 'comic', name: '美漫厚涂', icon: '🇺🇸', values: { lineart: 40, color: 90, screentone: 10, texture: 80 } },
    { id: 'manhwa', name: '漫画唯美', icon: '💕', values: { lineart: 60, color: 70, screentone: 30, texture: 40 } },
  ],
  act: [
    { id: 'subtle', name: '轻微表情', icon: '😐', values: { emotion: 30, action: 30, exaggeration: 10 } },
    { id: 'normal', name: '正常表演', icon: '🙂', values: { emotion: 50, action: 50, exaggeration: 30 } },
    { id: 'dramatic', name: '强烈崩溃', icon: '😱', values: { emotion: 90, action: 70, exaggeration: 60 } },
    { id: 'jojo', name: '夸张怒吼', icon: '💥', values: { emotion: 100, action: 90, exaggeration: 100 } },
  ],
  camera: [
    { id: 'low_pressure', name: '压迫低角度', icon: '📐', values: { distance: 40, angle: 80, movement: 20 } },
    { id: 'intimate', name: '暧昧近景', icon: '💋', values: { distance: 20, angle: 50, movement: 10 } },
    { id: 'tense_zoom', name: '紧张推近', icon: '🎯', values: { distance: 30, angle: 50, movement: 60 } },
    { id: 'epic_wide', name: '史诗远景', icon: '🏔️', values: { distance: 90, angle: 30, movement: 30 } },
  ],
};

// 参数定义
const PARAMS_CONFIG = {
  look: [
    { id: 'lineart', name: '线条硬朗度', desc: '越高线条越清晰' },
    { id: 'color', name: '上色密度', desc: '越高颜色越饱和' },
    { id: 'screentone', name: '网点强度', desc: '越高网点效果越明显' },
    { id: 'texture', name: '质感', desc: '0=干净 100=油润' },
  ],
  act: [
    { id: 'emotion', name: '情绪强度', desc: '表情的夸张程度' },
    { id: 'action', name: '动作幅度', desc: '肢体动作的夸张程度' },
    { id: 'exaggeration', name: '透视夸张', desc: 'JoJo 程度' },
  ],
  camera: [
    { id: 'distance', name: '景别', desc: '0=特写 100=远景' },
    { id: 'angle', name: '视角', desc: '0=俯视 50=平视 100=仰视' },
    { id: 'movement', name: '镜头运动', desc: '推拉摇移的强度' },
  ],
};

export function ParamsPanel({ onParamsChange }: ParamsPanelProps) {
  const [activeTab, setActiveTab] = useState<TabType>('look');
  const [values, setValues] = useState<Record<string, number>>({
    lineart: 70,
    color: 70,
    screentone: 30,
    texture: 40,
    emotion: 50,
    action: 50,
    exaggeration: 30,
    distance: 50,
    angle: 50,
    movement: 30,
  });

  const handleValueChange = (id: string, value: number) => {
    const newValues = { ...values, [id]: value };
    setValues(newValues);
    onParamsChange?.(newValues);
  };

  const applyPreset = (preset: { id: string; name: string; icon: string; values: Record<string, number> }) => {
    const newValues = { ...values, ...preset.values };
    setValues(newValues);
    onParamsChange?.(newValues);
  };

  const currentParams = PARAMS_CONFIG[activeTab];
  const currentPresets = PRESETS[activeTab];

  return (
    <div className="w-80 bg-zinc-900 border-l border-zinc-800 flex flex-col">
      {/* Tab 切换 */}
      <div className="flex border-b border-zinc-800">
        {(['look', 'act', 'camera'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 py-3 text-sm font-medium transition-colors ${activeTab === tab
                ? 'text-emerald-400 border-b-2 border-emerald-400'
                : 'text-zinc-400 hover:text-white'
              }`}
          >
            {tab === 'look' && '🎨 Look'}
            {tab === 'act' && '🎭 Act'}
            {tab === 'camera' && '📷 Camera'}
          </button>
        ))}
      </div>

      {/* 预设区域 */}
      <div className="p-4 border-b border-zinc-800">
        <h4 className="text-xs text-zinc-500 uppercase mb-3">快捷预设</h4>
        <div className="grid grid-cols-2 gap-2">
          {currentPresets.map((preset) => (
            <button
              key={preset.id}
              onClick={() => applyPreset(preset)}
              className="flex items-center gap-2 p-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg transition-colors text-left"
            >
              <span className="text-lg">{preset.icon}</span>
              <span className="text-xs text-zinc-300">{preset.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 参数滑条区域 */}
      <div className="flex-1 overflow-y-auto p-4">
        <h4 className="text-xs text-zinc-500 uppercase mb-4">详细参数</h4>
        <div className="space-y-6">
          {currentParams.map((param) => (
            <div key={param.id}>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm text-zinc-200">{param.name}</label>
                <span className="text-sm text-zinc-400 font-mono">
                  {values[param.id]}
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={values[param.id]}
                onChange={(e) => handleValueChange(param.id, parseInt(e.target.value))}
                className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-emerald-500"
              />
              <p className="text-xs text-zinc-500 mt-1">{param.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* 应用按钮 */}
      <div className="p-4 border-t border-zinc-800">
        <button className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-medium transition-colors">
          应用参数
        </button>
      </div>
    </div>
  );
}
