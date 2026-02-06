'use client';

interface Layer {
  id: string;
  name: string;
  type: 'bg' | 'char' | 'fg' | 'effect';
  visible: boolean;
  locked: boolean;
  imageUrl?: string;
}

interface LayerPanelProps {
  layers: Layer[];
  selectedLayerId?: string;
  onLayerSelect?: (layerId: string) => void;
  onLayerVisibilityToggle?: (layerId: string) => void;
  onLayerLockToggle?: (layerId: string) => void;
  onLayerReorder?: (fromIndex: number, toIndex: number) => void;
  onLayerDelete?: (layerId: string) => void;
}

const TYPE_COLORS = {
  bg: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  char: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  fg: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  effect: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
};

const TYPE_LABELS = {
  bg: '背景',
  char: '角色',
  fg: '前景',
  effect: '特效',
};

export function LayerPanel({
  layers,
  selectedLayerId,
  onLayerSelect,
  onLayerVisibilityToggle,
  onLayerLockToggle,
  onLayerReorder,
  onLayerDelete,
}: LayerPanelProps) {
  return (
    <div className="w-64 bg-zinc-900 border-l border-zinc-800 flex flex-col">
      {/* 头部 */}
      <div className="px-4 py-3 border-b border-zinc-800 flex items-center justify-between">
        <h3 className="text-sm font-medium text-zinc-200">图层</h3>
        <div className="flex items-center gap-1">
          <button
            className="p-1.5 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded transition-colors"
            title="添加图层"
          >
            ➕
          </button>
        </div>
      </div>

      {/* 图层列表 */}
      <div className="flex-1 overflow-y-auto">
        {layers.length === 0 ? (
          <div className="p-4 text-center text-zinc-500 text-sm">
            暂无图层
          </div>
        ) : (
          <div className="p-2 space-y-1">
            {layers.map((layer, index) => {
              const isSelected = layer.id === selectedLayerId;
              const typeStyle = TYPE_COLORS[layer.type];

              return (
                <div
                  key={layer.id}
                  onClick={() => onLayerSelect?.(layer.id)}
                  className={`flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-colors ${isSelected
                      ? 'bg-emerald-500/20 border border-emerald-500/50'
                      : 'hover:bg-zinc-800 border border-transparent'
                    }`}
                >
                  {/* 可见性切换 */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onLayerVisibilityToggle?.(layer.id);
                    }}
                    className={`text-sm ${layer.visible ? 'text-zinc-300' : 'text-zinc-600'
                      }`}
                    title={layer.visible ? '隐藏' : '显示'}
                  >
                    {layer.visible ? '👁️' : '👁️‍🗨️'}
                  </button>

                  {/* 缩略图 */}
                  <div className="w-10 h-10 rounded bg-zinc-800 flex-shrink-0 overflow-hidden">
                    {layer.imageUrl ? (
                      <img
                        src={layer.imageUrl}
                        alt={layer.name}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-xs text-zinc-600">
                        📦
                      </div>
                    )}
                  </div>

                  {/* 信息 */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-zinc-200 truncate">
                        {layer.name}
                      </span>
                      {layer.locked && (
                        <span className="text-xs text-zinc-500">🔒</span>
                      )}
                    </div>
                    <span
                      className={`inline-block px-1.5 py-0.5 rounded text-xs border ${typeStyle}`}
                    >
                      {TYPE_LABELS[layer.type]}
                    </span>
                  </div>

                  {/* 操作按钮 */}
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onLayerLockToggle?.(layer.id);
                      }}
                      className="p-1 text-zinc-400 hover:text-white rounded"
                      title={layer.locked ? '解锁' : '锁定'}
                    >
                      {layer.locked ? '🔓' : '🔒'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 底部工具栏 */}
      <div className="px-4 py-3 border-t border-zinc-800 flex items-center justify-between">
        <div className="flex items-center gap-1">
          <button
            className="p-1.5 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded transition-colors"
            title="上移图层"
          >
            ⬆️
          </button>
          <button
            className="p-1.5 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded transition-colors"
            title="下移图层"
          >
            ⬇️
          </button>
        </div>
        <button
          onClick={() => selectedLayerId && onLayerDelete?.(selectedLayerId)}
          disabled={!selectedLayerId}
          className="p-1.5 text-zinc-400 hover:text-red-400 hover:bg-zinc-800 rounded transition-colors disabled:opacity-30"
          title="删除图层"
        >
          🗑️
        </button>
      </div>
    </div>
  );
}
