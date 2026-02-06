'use client'

import React from 'react'
import { cn } from '@/lib/utils'

interface MarkdownContentProps {
    content: string
    className?: string
}

/**
 * 简易 Markdown 渲染组件
 * 支持：标题(#)、粗体(**)、斜体(*)、列表(- 和 数字.)、代码块(`)
 */
export function MarkdownContent({ content, className }: MarkdownContentProps) {
    const tryRenderImageLine = (line: string, index: number): React.ReactNode | null => {
        const trimmed = line.trim()

        // 1) Markdown 图片: ![alt](url)
        const mdImage = trimmed.match(/^!\[(.*?)\]\((https?:\/\/[^\s)]+)\)$/)
        if (mdImage) {
            const alt = mdImage[1] || 'image'
            const url = mdImage[2]
            return (
                <div key={`img-${index}`} className="my-2">
                    <a href={url} target="_blank" rel="noreferrer" className="block">
                        <img
                            src={url}
                            alt={alt}
                            className="max-w-full rounded-lg border border-[#27272A]"
                            loading="lazy"
                            referrerPolicy="no-referrer"
                        />
                    </a>
                </div>
            )
        }

        // 2) 纯 URL（你截图里这种）: [标题](url) 或 url
        const mdLink = trimmed.match(/^\[(.*?)\]\((https?:\/\/[^\s)]+)\)$/)
        if (mdLink) {
            const label = mdLink[1] || ''
            const url = mdLink[2]
            if (/\.(png|jpe?g|webp|gif)(\?.*)?$/i.test(url) || label.includes('场景图') || label.includes('参考图') || label.includes('图片')) {
                return (
                    <div key={`img-${index}`} className="my-2">
                        <div className="text-xs text-[#A1A1AA] mb-1">{label}</div>
                        <a href={url} target="_blank" rel="noreferrer" className="block">
                            <img
                                src={url}
                                alt={label || 'image'}
                                className="max-w-full rounded-lg border border-[#27272A]"
                                loading="lazy"
                                referrerPolicy="no-referrer"
                            />
                        </a>
                    </div>
                )
            }
        }

        const rawUrl = trimmed.match(/^(https?:\/\/\S+)$/)
        if (rawUrl) {
            const url = rawUrl[1]
            if (/\.(png|jpe?g|webp|gif)(\?.*)?$/i.test(url)) {
                return (
                    <div key={`img-${index}`} className="my-2">
                        <a href={url} target="_blank" rel="noreferrer" className="block">
                            <img
                                src={url}
                                alt="image"
                                className="max-w-full rounded-lg border border-[#27272A]"
                                loading="lazy"
                                referrerPolicy="no-referrer"
                            />
                        </a>
                    </div>
                )
            }
        }

        return null
    }

    const renderLine = (line: string, index: number): React.ReactNode => {
        // 优先尝试渲染图片
        const img = tryRenderImageLine(line, index)
        if (img) return img

        // 空行
        if (!line.trim()) {
            return <div key={index} className="h-2" />
        }

        // 标题
        if (line.startsWith('### ')) {
            return (
                <h3 key={index} className="font-heading font-bold text-[#10B981] text-base mt-4 mb-2">
                    {renderInlineStyles(line.slice(4))}
                </h3>
            )
        }
        if (line.startsWith('## ')) {
            return (
                <h2 key={index} className="font-heading font-bold text-[#06B6D4] text-lg mt-4 mb-2">
                    {renderInlineStyles(line.slice(3))}
                </h2>
            )
        }
        if (line.startsWith('# ')) {
            return (
                <h1 key={index} className="font-heading font-bold text-[#FAFAFA] text-xl mt-4 mb-3">
                    {renderInlineStyles(line.slice(2))}
                </h1>
            )
        }

        // 无序列表
        if (line.startsWith('- ') || line.startsWith('* ')) {
            return (
                <div key={index} className="flex items-start gap-2 ml-2 my-1">
                    <span className="text-[#10B981] mt-1">•</span>
                    <span>{renderInlineStyles(line.slice(2))}</span>
                </div>
            )
        }

        // 缩进无序列表
        if (line.match(/^  +[-*] /)) {
            const trimmed = line.replace(/^  +[-*] /, '')
            return (
                <div key={index} className="flex items-start gap-2 ml-6 my-1">
                    <span className="text-[#71717A] mt-1">◦</span>
                    <span className="text-[#A1A1AA]">{renderInlineStyles(trimmed)}</span>
                </div>
            )
        }

        // 有序列表
        const orderedMatch = line.match(/^(\d+)\.\s+(.*)/)
        if (orderedMatch) {
            return (
                <div key={index} className="flex items-start gap-2 ml-2 my-1">
                    <span className="text-[#10B981] font-mono text-sm w-5">{orderedMatch[1]}.</span>
                    <span>{renderInlineStyles(orderedMatch[2])}</span>
                </div>
            )
        }

        // 普通段落
        return (
            <p key={index} className="my-1.5 leading-relaxed">
                {renderInlineStyles(line)}
            </p>
        )
    }

    const renderInlineStyles = (text: string): React.ReactNode => {
        // 先处理粗体 **text**
        const parts: React.ReactNode[] = []
        let lastIndex = 0
        const boldRegex = /\*\*(.+?)\*\*/g
        let match

        while ((match = boldRegex.exec(text)) !== null) {
            // 添加前面的普通文本
            if (match.index > lastIndex) {
                parts.push(...renderItalic(text.slice(lastIndex, match.index)))
            }
            // 添加粗体文本
            parts.push(
                <strong key={`bold-${match.index}`} className="font-bold text-[#FAFAFA]">
                    {match[1]}
                </strong>
            )
            lastIndex = match.index + match[0].length
        }

        // 添加剩余文本
        if (lastIndex < text.length) {
            parts.push(...renderItalic(text.slice(lastIndex)))
        }

        return parts.length > 0 ? parts : text
    }

    const renderItalic = (text: string): React.ReactNode[] => {
        const parts: React.ReactNode[] = []
        let lastIndex = 0
        // 单个 * 表示斜体（避免与粗体冲突）
        const italicRegex = /(?<!\*)\*(?!\*)(.+?)\*(?!\*)/g
        let match

        while ((match = italicRegex.exec(text)) !== null) {
            if (match.index > lastIndex) {
                parts.push(...renderCode(text.slice(lastIndex, match.index)))
            }
            parts.push(
                <em key={`italic-${match.index}`} className="italic text-[#A1A1AA]">
                    {match[1]}
                </em>
            )
            lastIndex = match.index + match[0].length
        }

        if (lastIndex < text.length) {
            parts.push(...renderCode(text.slice(lastIndex)))
        }

        return parts.length > 0 ? parts : [text]
    }

    const renderCode = (text: string): React.ReactNode[] => {
        const parts: React.ReactNode[] = []
        let lastIndex = 0
        const codeRegex = /`(.+?)`/g
        let match

        while ((match = codeRegex.exec(text)) !== null) {
            if (match.index > lastIndex) {
                parts.push(text.slice(lastIndex, match.index))
            }
            parts.push(
                <code
                    key={`code-${match.index}`}
                    className="px-1.5 py-0.5 bg-[#27272A] rounded text-[#06B6D4] font-mono text-sm"
                >
                    {match[1]}
                </code>
            )
            lastIndex = match.index + match[0].length
        }

        if (lastIndex < text.length) {
            parts.push(text.slice(lastIndex))
        }

        return parts.length > 0 ? parts : [text]
    }

    const lines = content.split('\n')

    return (
        <div className={cn("text-[#D4D4D8] font-body", className)}>
            {lines.map((line, index) => renderLine(line, index))}
        </div>
    )
}
