'use client';

import { useState, useCallback, useRef } from 'react';
import { api } from '@/lib/api';

type AnchorStatus = 'pending' | 'generating' | 'ready' | 'failed';

interface SceneCardProps {
  id: string;
  name: string;
  anchorUrl?: string;
  anchorStatus: AnchorStatus;
  timeOfDay?: 'day' | 'night' | 'dawn' | 'dusk';
  weather?: 'clear' | 'rain' | 'snow' | 'cloudy';
  hasDepth?: boolean;
  hasCanny?: boolean;
  hasLineart?: boolean;
  onStatusChange?: (status: AnchorStatus) => void;
  onSelect?: () => void;
  isSelected?: boolean;
}

const STATUS_CONFIG = {
  pending: {
    color: 'bg-yellow-500',
    text: '无锚点',
    icon: '⚠️',
    textColor: 'text-yellow-400',
  },
  generating: {
    color: 'bg-blue-500 animate-pulse',
    text: '生成中...',
    icon: '⏳',
    textColor: 'text-blue-400',
  },
  ready: {
    color: 'bg-emerald-500',
    text: '结构锁定',
    icon: '🔒',
    textColor: 'text-emerald-400',
  },
  failed: {
    color: 'bg-red-500',
    text: '生成失败',
    icon: '❌',
    textColor: 'text-red-400',
  },
};

const TIME_OPTIONS = [
  { value: 'day', label: '☀️ 白天' },
  { value: 'night', label: '🌙 夜晚' },
  { value: 'dawn', label: '🌅 黎明' },
  { value: 'dusk', label: '🌇 黄昏' },
];

const WEATHER_OPTIONS = [
  { value: 'clear', label: '☀️ 晴天' },
  { value: 'rain', label: '🌧️ 雨天' },
  { value: 'snow', label: '❄️ 雪天' },
  { value: 'cloudy', label: '☁️ 阴天' },
];

export function SceneCard({
  id,
  name,
  anchorUrl,
  anchorStatus,
  timeOfDay = 'day',
  weather = 'clear',
  hasDepth,
  hasCanny,
  hasLineart,
  onStatusChange,
  onSelect,
  isSelected,
}: SceneCardProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [status, setStatus] = useState<AnchorStatus>(anchorStatus);
  const [showControls, setShowControls] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const statusConfig = STATUS_CONFIG[status];

  const handleUpload = useCallback(async (file: File | null) => {
    if (!file) return;

    setIsUploading(true);
    setStatus('generating');
    onStatusChange?.('generating');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(
        `${api.baseUrl}/api/v1/scene-anchor/${id}/generate-anchor`,
        {
          method: 'POST',
          body: formData,
        }
      );

      const data = await response.json();

      if (response.ok && data.status === 'ready') {
        setStatus('ready');
        onStatusChange?.('ready');
      } else {
        setStatus('failed');
        onStatusChange?.('failed');
      }
    } catch (err) {
      console.error('Upload failed:', err);
      setStatus('failed');
      onStatusChange?.('failed');
    } finally {
      setIsUploading(false);
    }
  }, [id, onStatusChange]);

  return (
    <div
      className={`relative group rounded-xl border-2 transition-all duration-200 cursor-pointer overflow-hidden ${
        isSelected
          ? 'border-cyan-500 bg-cyan-500/10'
          : 'border-zinc-700 bg-zinc-800/50 hover:border-zinc-600'
      }`}
      onClick={onSelect}
    >
      {/* 状态指示灯 */}
      <div className="absolute top-2 right-2 z-10">
        <div className={`w-3 h-3 rounded-full ${statusConfig.color}`} title={statusConfig.text} />
      </div>

      {/* 缩略图区域 */}
      <div className="aspect-video relative bg-zinc-900">
        {anchorUrl ? (
          <img
            src={anchorUrl}
            alt={name}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-4xl text-zinc-600">
            🏞️
          </div>
        )}

        {/* 控制图预览按钮 */}
        {status === 'ready' && (
          <div className="absolute bottom-2 left-2 flex gap-1">
            {hasDepth && (
              <span className="px-2 py-0.5 bg-black/60 text-xs text-zinc-300 rounded" title="深度图">
                D
              </span>
            )}
            {hasCanny && (
              <span className="px-2 py-0.5 bg-black/60 text-xs text-zinc-300 rounded" title="边缘图">
                C
              </span>
            )}
            {hasLineart && (
              <span className="px-2 py-0.5 bg-black/60 text-xs text-zinc-300 rounded" title="线稿图">
                L
              </span>
            )}
          </div>
        )}

        {/* 上传叠加层 */}
        {(!anchorUrl || status === 'pending') && (
          <div
            className="absolute inset-0 bg-black/60 flex flex-col items-center justify-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity"
            onClick={(e) => {
              e.stopPropagation();
              fileInputRef.current?.click();
            }}
          >
            <span className="text-3xl">📷</span>
            <span className="text-sm text-zinc-300">上传空镜</span>
            <span className="text-xs text-zinc-500">系统自动生成控制图</span>
          </div>
        )}

        {/* 加载指示 */}
        {isUploading && (
          <div className="absolute inset-0 bg-black/80 flex items-center justify-center">
            <div className="text-center">
              <span className="text-2xl animate-spin block mb-2">⏳</span>
              <span className="text-sm text-zinc-300">生成控制图...</span>
            </div>
          </div>
        )}
      </div>

      {/* 信息区域 */}
      <div className="p-3">
        <h4 className="font-medium text-zinc-100 truncate">{name}</h4>
        
        {/* 状态和属性标签 */}
        <div className="flex items-center gap-2 mt-2 flex-wrap">
          <span className={`text-xs ${statusConfig.textColor}`}>
            {statusConfig.icon} {statusConfig.text}
          </span>
          <span className="text-xs text-zinc-500">
            {TIME_OPTIONS.find(t => t.value === timeOfDay)?.label}
          </span>
          <span className="text-xs text-zinc-500">
            {WEATHER_OPTIONS.find(w => w.value === weather)?.label}
          </span>
        </div>

        {/* 操作按钮 */}
        <div className="flex items-center gap-2 mt-3">
          {status === 'pending' || status === 'failed' ? (
            <button
              onClick={(e) => {
                e.stopPropagation();
                fileInputRef.current?.click();
              }}
              className="flex-1 px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white text-xs rounded-lg transition-colors"
            >
              上传空镜
            </button>
          ) : (
            <>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowControls(!showControls);
                }}
                className="flex-1 px-3 py-1.5 bg-zinc-700 hover:bg-zinc-600 text-zinc-300 text-xs rounded-lg transition-colors"
              >
                查看控制图
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  fileInputRef.current?.click();
                }}
                className="px-3 py-1.5 bg-zinc-700 hover:bg-zinc-600 text-zinc-300 text-xs rounded-lg transition-colors"
              >
                更新
              </button>
            </>
          )}
        </div>
      </div>

      {/* 控制图预览弹出层 */}
      {showControls && status === 'ready' && (
        <div className="absolute inset-0 bg-zinc-900/95 p-3 z-20">
          <div className="flex justify-between items-center mb-3">
            <h5 className="text-sm font-medium text-zinc-200">控制图预览</h5>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowControls(false);
              }}
              className="text-zinc-400 hover:text-white"
            >
              ✕
            </button>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <div className="aspect-video bg-zinc-800 rounded flex items-center justify-center text-xs text-zinc-500">
              Depth
            </div>
            <div className="aspect-video bg-zinc-800 rounded flex items-center justify-center text-xs text-zinc-500">
              Canny
            </div>
            <div className="aspect-video bg-zinc-800 rounded flex items-center justify-center text-xs text-zinc-500">
              Lineart
            </div>
          </div>
        </div>
      )}

      {/* 隐藏的文件输入 */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => handleUpload(e.target.files?.[0] || null)}
      />
    </div>
  );
}
