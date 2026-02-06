'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Stage, Layer, Image as KonvaImage, Group, Rect, Text, Transformer } from 'react-konva';
import Konva from 'konva';
import { type BubbleCandidate } from '@/lib/api';

interface BubbleEditorProps {
  panelId: string;
  imageUrl?: string;
  bubbles: BubbleCandidate[];
  onBubbleUpdate: (bubbleId: string, updates: Partial<BubbleCandidate>) => void;
  onBubbleSelect?: (bubbleId: string | null) => void;
  selectedBubbleId?: string | null;
  width?: number;
  height?: number;
}

// 气泡样式配置
const BUBBLE_STYLES: Record<string, {
  fill: string;
  stroke: string;
  strokeWidth: number;
  cornerRadius: number;
  fontStyle: string;
  opacity: number;
}> = {
  normal: {
    fill: '#ffffff',
    stroke: '#0f172a',
    strokeWidth: 3,
    cornerRadius: 20,
    fontStyle: 'normal',
    opacity: 0.95,
  },
  shout: {
    fill: '#ffeb3b',
    stroke: '#ff5722',
    strokeWidth: 4,
    cornerRadius: 8,
    fontStyle: 'bold',
    opacity: 1,
  },
  whisper: {
    fill: '#f5f5f5',
    stroke: '#9e9e9e',
    strokeWidth: 2,
    cornerRadius: 16,
    fontStyle: 'italic',
    opacity: 0.85,
  },
  thought: {
    fill: '#e3f2fd',
    stroke: '#90caf9',
    strokeWidth: 2,
    cornerRadius: 30,
    fontStyle: 'normal',
    opacity: 0.9,
  },
  narration: {
    fill: '#263238',
    stroke: '#455a64',
    strokeWidth: 2,
    cornerRadius: 4,
    fontStyle: 'normal',
    opacity: 0.95,
  },
};

// 单个气泡组件
function BubbleShape({
  bubble,
  isSelected,
  canvasWidth,
  canvasHeight,
  onSelect,
  onDragEnd,
  onTransformEnd,
}: {
  bubble: BubbleCandidate;
  isSelected: boolean;
  canvasWidth: number;
  canvasHeight: number;
  onSelect: () => void;
  onDragEnd: (x: number, y: number) => void;
  onTransformEnd: (width: number, scaleX: number, scaleY: number) => void;
}) {
  const groupRef = useRef<Konva.Group>(null);
  const transformerRef = useRef<Konva.Transformer>(null);

  const style = BUBBLE_STYLES[bubble.style] || BUBBLE_STYLES.normal;

  // 计算实际像素位置
  const x = (bubble.x ?? 0.5) * canvasWidth;
  const y = (bubble.y ?? 0.3) * canvasHeight;
  const width = (bubble.width ?? 0.4) * canvasWidth;

  // 计算文字换行
  const padding = 16;
  const fontSize = bubble.font_size || 24;
  const lineHeight = fontSize * 1.4;

  // 简单的文字换行计算
  const maxCharsPerLine = Math.floor((width - padding * 2) / fontSize);
  const lines = [];
  let remaining = bubble.text;
  while (remaining.length > 0) {
    if (remaining.length <= maxCharsPerLine) {
      lines.push(remaining);
      break;
    }
    lines.push(remaining.slice(0, maxCharsPerLine));
    remaining = remaining.slice(maxCharsPerLine);
  }

  const textHeight = lines.length * lineHeight + padding * 2;
  const bubbleHeight = Math.max(60, textHeight);

  // 连接 Transformer
  useEffect(() => {
    if (isSelected && groupRef.current && transformerRef.current) {
      transformerRef.current.nodes([groupRef.current]);
      transformerRef.current.getLayer()?.batchDraw();
    }
  }, [isSelected]);

  const isNarration = bubble.style === 'narration';
  const textColor = isNarration ? '#ffffff' : '#0f172a';

  return (
    <>
      <Group
        ref={groupRef}
        x={x}
        y={y}
        draggable
        onClick={onSelect}
        onTap={onSelect}
        onDragEnd={(e) => {
          const newX = e.target.x() / canvasWidth;
          const newY = e.target.y() / canvasHeight;
          onDragEnd(newX, newY);
        }}
        onTransformEnd={() => {
          const node = groupRef.current;
          if (node) {
            const scaleX = node.scaleX();
            const scaleY = node.scaleY();
            const newWidth = (width * scaleX) / canvasWidth;

            // 重置 scale，保持位置
            node.scaleX(1);
            node.scaleY(1);

            onTransformEnd(newWidth, scaleX, scaleY);
          }
        }}
      >
        {/* 气泡背景 */}
        <Rect
          width={width}
          height={bubbleHeight}
          fill={style.fill}
          stroke={isSelected ? '#7c3aed' : style.stroke}
          strokeWidth={isSelected ? 4 : style.strokeWidth}
          cornerRadius={style.cornerRadius}
          opacity={style.opacity}
          shadowColor="#000"
          shadowBlur={isSelected ? 12 : 6}
          shadowOpacity={0.2}
          shadowOffsetY={3}
        />

        {/* 气泡尾巴（仅对话气泡） */}
        {(bubble.style === 'normal' || bubble.style === 'shout') && (
          <Rect
            x={width * 0.3}
            y={bubbleHeight - 5}
            width={20}
            height={20}
            fill={style.fill}
            rotation={45}
            stroke={style.stroke}
            strokeWidth={style.strokeWidth}
            cornerRadius={2}
          />
        )}

        {/* 气泡文字 */}
        <Text
          x={padding}
          y={padding}
          width={width - padding * 2}
          height={bubbleHeight - padding * 2}
          text={bubble.text}
          fontSize={fontSize}
          fontFamily="'Noto Sans SC', 'Microsoft YaHei', sans-serif"
          fontStyle={style.fontStyle}
          fill={textColor}
          align="center"
          verticalAlign="middle"
          wrap="word"
          lineHeight={1.4}
        />
      </Group>

      {/* 变换控制器 */}
      {isSelected && (
        <Transformer
          ref={transformerRef}
          rotateEnabled={false}
          enabledAnchors={['middle-left', 'middle-right', 'top-center', 'bottom-center']}
          boundBoxFunc={(oldBox, newBox) => {
            // 限制最小尺寸
            if (newBox.width < 80 || newBox.height < 40) {
              return oldBox;
            }
            return newBox;
          }}
          anchorFill="#7c3aed"
          anchorStroke="#5b21b6"
          anchorSize={12}
          borderStroke="#7c3aed"
          borderStrokeWidth={2}
        />
      )}
    </>
  );
}

export function BubbleEditor({
  panelId,
  imageUrl,
  bubbles,
  onBubbleUpdate,
  onBubbleSelect,
  selectedBubbleId,
  width = 400,
  height = 711,
}: BubbleEditorProps) {
  const stageRef = useRef<Konva.Stage>(null);
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [stageSize, setStageSize] = useState({ width, height });
  const containerRef = useRef<HTMLDivElement>(null);

  // 加载背景图
  useEffect(() => {
    if (imageUrl) {
      const img = new window.Image();
      img.crossOrigin = 'anonymous';
      img.src = imageUrl;
      img.onload = () => {
        setImage(img);
        // 根据图片比例调整 stage 尺寸
        const aspectRatio = img.width / img.height;
        if (containerRef.current) {
          const containerWidth = containerRef.current.clientWidth;
          const containerHeight = containerRef.current.clientHeight;
          const containerRatio = containerWidth / containerHeight;

          if (aspectRatio > containerRatio) {
            setStageSize({
              width: containerWidth,
              height: containerWidth / aspectRatio,
            });
          } else {
            setStageSize({
              width: containerHeight * aspectRatio,
              height: containerHeight,
            });
          }
        }
      };
    }
  }, [imageUrl]);

  // 响应式调整
  useEffect(() => {
    const handleResize = () => {
      if (containerRef.current && image) {
        const aspectRatio = image.width / image.height;
        const containerWidth = containerRef.current.clientWidth;
        const containerHeight = containerRef.current.clientHeight;
        const containerRatio = containerWidth / containerHeight;

        if (aspectRatio > containerRatio) {
          setStageSize({
            width: containerWidth,
            height: containerWidth / aspectRatio,
          });
        } else {
          setStageSize({
            width: containerHeight * aspectRatio,
            height: containerHeight,
          });
        }
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [image]);

  // 点击空白区域取消选中
  const handleStageClick = useCallback((e: Konva.KonvaEventObject<MouseEvent>) => {
    if (e.target === e.target.getStage()) {
      onBubbleSelect?.(null);
    }
  }, [onBubbleSelect]);

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full flex items-center justify-center bg-canvas-dark"
    >
      <div className="relative shadow-2xl rounded-2xl overflow-hidden">
        <Stage
          ref={stageRef}
          width={stageSize.width}
          height={stageSize.height}
          onClick={handleStageClick}
          onTap={handleStageClick}
        >
          {/* 背景图层 */}
          <Layer>
            {image && (
              <KonvaImage
                image={image}
                width={stageSize.width}
                height={stageSize.height}
              />
            )}
            {!image && (
              <Rect
                width={stageSize.width}
                height={stageSize.height}
                fill="#0f172a"
              />
            )}
          </Layer>

          {/* 气泡图层 */}
          <Layer>
            {bubbles.map((bubble) => (
              <BubbleShape
                key={bubble.id}
                bubble={bubble}
                isSelected={selectedBubbleId === bubble.id}
                canvasWidth={stageSize.width}
                canvasHeight={stageSize.height}
                onSelect={() => onBubbleSelect?.(bubble.id)}
                onDragEnd={(x, y) => {
                  onBubbleUpdate(bubble.id, { x, y });
                }}
                onTransformEnd={(newWidth) => {
                  onBubbleUpdate(bubble.id, { width: newWidth });
                }}
              />
            ))}
          </Layer>
        </Stage>

        {/* 编辑提示 */}
        {bubbles.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="bg-panel/80 backdrop-blur px-6 py-4 rounded-xl text-center">
              <p className="text-ink-muted text-sm">
                在右侧面板添加气泡后
              </p>
              <p className="text-ink-muted text-sm">
                可在此拖拽调整位置
              </p>
            </div>
          </div>
        )}

        {/* 选中提示 */}
        {selectedBubbleId && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 
            bg-accent/90 backdrop-blur px-4 py-2 rounded-full text-xs text-white">
            拖拽移动 · 拖拽边缘调整大小
          </div>
        )}
      </div>
    </div>
  );
}

export default BubbleEditor;
