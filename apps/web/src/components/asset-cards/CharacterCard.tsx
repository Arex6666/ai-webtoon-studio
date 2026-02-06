'use client';

import { useState, useCallback, useRef } from 'react';
import { api } from '@/lib/api';

type EmbeddingStatus = 'pending' | 'extracting' | 'ready' | 'failed';

interface CharacterCardProps {
  id: string;
  name: string;
  thumbnailUrl?: string;
  embeddingStatus: EmbeddingStatus;
  referenceCount: number;
  onStatusChange?: (status: EmbeddingStatus) => void;
  onSelect?: () => void;
  isSelected?: boolean;
}

const STATUS_CONFIG = {
  pending: {
    color: 'bg-yellow-500',
    text: '缺少参考图',
    icon: '⚠️',
    textColor: 'text-yellow-400',
  },
  extracting: {
    color: 'bg-blue-500 animate-pulse',
    text: '提取中...',
    icon: '⏳',
    textColor: 'text-blue-400',
  },
  ready: {
    color: 'bg-emerald-500',
    text: '一致性锁定',
    icon: '✅',
    textColor: 'text-emerald-400',
  },
  failed: {
    color: 'bg-red-500',
    text: '提取失败',
    icon: '❌',
    textColor: 'text-red-400',
  },
};

export function CharacterCard({
  id,
  name,
  thumbnailUrl,
  embeddingStatus,
  referenceCount,
  onStatusChange,
  onSelect,
  isSelected,
}: CharacterCardProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [status, setStatus] = useState<EmbeddingStatus>(embeddingStatus);
  const [showUpload, setShowUpload] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const statusConfig = STATUS_CONFIG[status];

  const handleUpload = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    setIsUploading(true);
    setStatus('extracting');
    onStatusChange?.('extracting');

    const formData = new FormData();
    Array.from(files).forEach((file) => {
      formData.append('files', file);
    });

    try {
      const response = await fetch(
        `${api.baseUrl}/api/v1/identity/${id}/extract-embedding`,
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
      setShowUpload(false);
    }
  }, [id, onStatusChange]);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      handleUpload(e.dataTransfer.files);
    },
    [handleUpload]
  );

  return (
    <div
      className={`relative group rounded-xl border-2 transition-all duration-200 cursor-pointer overflow-hidden ${isSelected
          ? 'border-emerald-500 bg-emerald-500/10'
          : 'border-zinc-700 bg-zinc-800/50 hover:border-zinc-600'
        }`}
      onClick={onSelect}
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
    >
      {/* 状态指示灯 */}
      <div className="absolute top-2 right-2 z-10">
        <div className={`w-3 h-3 rounded-full ${statusConfig.color}`} title={statusConfig.text} />
      </div>

      {/* 缩略图区域 */}
      <div className="aspect-[3/4] relative bg-zinc-900">
        {thumbnailUrl ? (
          <img
            src={thumbnailUrl}
            alt={name}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-4xl text-zinc-600">
            👤
          </div>
        )}

        {/* 上传叠加层 */}
        {(showUpload || !thumbnailUrl) && (
          <div
            className="absolute inset-0 bg-black/60 flex flex-col items-center justify-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity"
            onClick={(e) => {
              e.stopPropagation();
              fileInputRef.current?.click();
            }}
          >
            <span className="text-3xl">📷</span>
            <span className="text-sm text-zinc-300">上传定妆照</span>
            <span className="text-xs text-zinc-500">建议: 正面+侧面+多表情</span>
          </div>
        )}

        {/* 加载指示 */}
        {isUploading && (
          <div className="absolute inset-0 bg-black/80 flex items-center justify-center">
            <div className="text-center">
              <span className="text-2xl animate-spin block mb-2">⏳</span>
              <span className="text-sm text-zinc-300">提取 Embedding...</span>
            </div>
          </div>
        )}
      </div>

      {/* 信息区域 */}
      <div className="p-3">
        <h4 className="font-medium text-zinc-100 truncate">{name}</h4>

        {/* 状态标签 */}
        <div className="flex items-center gap-2 mt-2">
          <span className={`text-xs ${statusConfig.textColor}`}>
            {statusConfig.icon} {statusConfig.text}
          </span>
          {referenceCount > 0 && (
            <span className="text-xs text-zinc-500">
              {referenceCount} 张参考
            </span>
          )}
        </div>

        {/* 操作按钮 */}
        <div className="flex items-center gap-2 mt-3">
          {status === 'pending' || status === 'failed' ? (
            <button
              onClick={(e) => {
                e.stopPropagation();
                fileInputRef.current?.click();
              }}
              className="flex-1 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs rounded-lg transition-colors"
            >
              上传参考图
            </button>
          ) : (
            <button
              onClick={(e) => {
                e.stopPropagation();
                fileInputRef.current?.click();
              }}
              className="flex-1 px-3 py-1.5 bg-zinc-700 hover:bg-zinc-600 text-zinc-300 text-xs rounded-lg transition-colors"
            >
              更新参考
            </button>
          )}
        </div>
      </div>

      {/* 隐藏的文件输入 */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={(e) => handleUpload(e.target.files)}
      />
    </div>
  );
}
