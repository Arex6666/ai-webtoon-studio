'use client';

import React, { useRef, useState, useCallback, useEffect } from 'react';
import { Bubble, TailDirection } from '@/lib/schema/bubble';

interface BubbleRendererProps {
    bubble: Bubble;
    isSelected?: boolean;
    isEditing?: boolean;
    scale?: number;
    onClick?: () => void;
    onDoubleClick?: () => void;
    onTextChange?: (text: string) => void;
    onDragEnd?: (x: number, y: number) => void;
    onResize?: (width: number, height: number) => void;
}

/**
 * 气泡渲染器 - 渲染单个气泡
 */
export function BubbleRenderer({
    bubble,
    isSelected = false,
    isEditing = false,
    scale = 1,
    onClick,
    onDoubleClick,
    onTextChange,
    onDragEnd,
    onResize,
}: BubbleRendererProps) {
    const textRef = useRef<HTMLDivElement>(null);
    const [isDragging, setIsDragging] = useState(false);
    const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

    // 气泡样式
    const bubbleStyle: React.CSSProperties = {
        position: 'absolute',
        left: `${bubble.x}%`,
        top: `${bubble.y}%`,
        transform: `translate(-50%, -50%) rotate(${bubble.rotation}deg)`,
        width: bubble.width * scale,
        minHeight: bubble.height * scale,
        padding: '12px 16px',
        backgroundColor: bubble.backgroundColor,
        border: `${bubble.borderWidth}px solid ${bubble.borderColor}`,
        borderRadius: bubble.borderRadius,
        cursor: isEditing ? 'text' : 'move',
        zIndex: bubble.zIndex,
        boxShadow: bubble.shadow ? '4px 4px 8px rgba(0,0,0,0.3)' : 'none',
        filter: bubble.glow ? 'drop-shadow(0 0 8px rgba(255,255,255,0.8))' : 'none',
        outline: isSelected ? '2px solid #6366f1' : 'none',
        outlineOffset: '2px',
    };

    // 文字样式
    const textStyle: React.CSSProperties = {
        fontSize: bubble.fontSize * scale,
        fontFamily: bubble.fontFamily,
        fontWeight: bubble.fontWeight,
        textAlign: bubble.textAlign,
        color: bubble.textColor,
        lineHeight: 1.4,
        wordBreak: 'break-word',
        whiteSpace: 'pre-wrap',
    };

    // 处理文本编辑
    const handleBlur = () => {
        if (textRef.current && onTextChange) {
            onTextChange(textRef.current.innerText);
        }
    };

    // 拖拽处理
    const handleMouseDown = (e: React.MouseEvent) => {
        if (isEditing) return;
        e.preventDefault();
        setIsDragging(true);
        setDragStart({ x: e.clientX, y: e.clientY });
    };

    useEffect(() => {
        if (!isDragging) return;

        const handleMouseMove = (e: MouseEvent) => {
            // 拖拽逻辑由父组件处理
        };

        const handleMouseUp = (e: MouseEvent) => {
            setIsDragging(false);
            if (onDragEnd) {
                // 计算新位置
                const deltaX = (e.clientX - dragStart.x) / scale;
                const deltaY = (e.clientY - dragStart.y) / scale;
                // 这里需要转换为百分比，由父组件计算
            }
        };

        window.addEventListener('mousemove', handleMouseMove);
        window.addEventListener('mouseup', handleMouseUp);

        return () => {
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);
        };
    }, [isDragging, dragStart, scale, onDragEnd]);

    return (
        <div
            style={bubbleStyle}
            onClick={onClick}
            onDoubleClick={onDoubleClick}
            onMouseDown={handleMouseDown}
            className="bubble-container"
        >
            {/* 尾巴 */}
            {bubble.tailDirection !== 'none' && (
                <BubbleTail
                    direction={bubble.tailDirection}
                    size={bubble.tailSize}
                    color={bubble.backgroundColor}
                    borderColor={bubble.borderColor}
                    borderWidth={bubble.borderWidth}
                />
            )}

            {/* 文字内容 */}
            <div
                ref={textRef}
                style={textStyle}
                contentEditable={isEditing}
                suppressContentEditableWarning
                onBlur={handleBlur}
            >
                {bubble.text || '点击输入文字'}
            </div>

            {/* 调整大小把手 */}
            {isSelected && !isEditing && (
                <div className="resize-handles">
                    <div className="resize-handle resize-se" />
                </div>
            )}

            <style jsx>{`
        .bubble-container {
          user-select: ${isEditing ? 'text' : 'none'};
        }
        .resize-handles {
          position: absolute;
          inset: 0;
          pointer-events: none;
        }
        .resize-handle {
          position: absolute;
          width: 10px;
          height: 10px;
          background: #6366f1;
          border: 2px solid white;
          border-radius: 2px;
          pointer-events: auto;
          cursor: se-resize;
        }
        .resize-se {
          right: -5px;
          bottom: -5px;
        }
      `}</style>
        </div>
    );
}

// 气泡尾巴组件
interface BubbleTailProps {
    direction: TailDirection;
    size: number;
    color: string;
    borderColor: string;
    borderWidth: number;
}

function BubbleTail({ direction, size, color, borderColor, borderWidth }: BubbleTailProps) {
    const tailPositions: Record<TailDirection, React.CSSProperties> = {
        'none': {},
        'top-left': { top: -size, left: '20%' },
        'top': { top: -size, left: '50%', transform: 'translateX(-50%)' },
        'top-right': { top: -size, right: '20%' },
        'left': { left: -size, top: '50%', transform: 'translateY(-50%) rotate(90deg)' },
        'right': { right: -size, top: '50%', transform: 'translateY(-50%) rotate(-90deg)' },
        'bottom-left': { bottom: -size, left: '20%', transform: 'rotate(180deg)' },
        'bottom': { bottom: -size, left: '50%', transform: 'translateX(-50%) rotate(180deg)' },
        'bottom-right': { bottom: -size, right: '20%', transform: 'rotate(180deg)' },
    };

    if (direction === 'none') return null;

    return (
        <div
            style={{
                position: 'absolute',
                width: 0,
                height: 0,
                borderLeft: `${size}px solid transparent`,
                borderRight: `${size}px solid transparent`,
                borderBottom: `${size}px solid ${color}`,
                ...tailPositions[direction],
            }}
        />
    );
}

export default BubbleRenderer;
