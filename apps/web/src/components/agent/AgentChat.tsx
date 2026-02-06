'use client'

import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
    Bot, User, Send, Sparkles, FileText, Image as ImageIcon,
    Layers, Eye, Check, RotateCcw, ExternalLink, Loader2, AtSign, Trash2, ArrowRight
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { MarkdownContent } from '@/components/ui/MarkdownContent'

export type CardType = 'outline' | 'script' | 'storyboard' | 'asset'
export type MessageRole = 'user' | 'assistant' | 'system'

export interface ActionCard {
    id: string
    type: CardType
    title: string
    description: string
    target?: string
    previewUrl?: string
    actions: {
        id: string
        label: string
        icon: React.ElementType
        variant: 'primary' | 'secondary' | 'ghost'
    }[]
}

export interface AgentMessage {
    id: string
    role: MessageRole
    content: string
    timestamp: number
    card?: ActionCard
}

interface AgentChatProps {
    messages: AgentMessage[]
    onSendMessage: (content: string) => void
    onCardAction: (cardId: string, actionId: string) => void
    onDeleteMessage?: (messageId: string) => void
    isTyping?: boolean
    // 新增：显示「进入分集」按钮
    showEpisodesButton?: boolean
    onGoToEpisodes?: () => void
}

const cardTypeConfig = {
    outline: { icon: FileText, color: 'text-[#10B981]', bg: 'bg-[#10B981]/10', border: 'border-[#10B981]/30', label: '大纲' },
    script: { icon: FileText, color: 'text-[#3B82F6]', bg: 'bg-[#3B82F6]/10', border: 'border-[#3B82F6]/30', label: '剧本' },
    storyboard: { icon: Layers, color: 'text-[#8B5CF6]', bg: 'bg-[#8B5CF6]/10', border: 'border-[#8B5CF6]/30', label: '分镜' },
    asset: { icon: ImageIcon, color: 'text-[#F59E0B]', bg: 'bg-[#F59E0B]/10', border: 'border-[#F59E0B]/30', label: '资产' },
}

function ActionCardComponent({ card, onAction }: { card: ActionCard; onAction: (actionId: string) => void }) {
    const config = cardTypeConfig[card.type]

    return (
        <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.2 }}
            className={cn(
                "mt-3 p-4 rounded-xl border backdrop-blur-sm",
                config.bg, config.border
            )}
        >
            {/* Header */}
            <div className="flex items-start gap-3 mb-3">
                <motion.div
                    whileHover={{ scale: 1.05 }}
                    className={cn("w-10 h-10 rounded-lg flex items-center justify-center border", config.bg, config.border)}
                >
                    <config.icon className={cn("w-5 h-5", config.color)} />
                </motion.div>
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                        <span className={cn("px-2 py-0.5 rounded text-xs font-heading font-medium", config.bg, config.color)}>
                            {config.label}
                        </span>
                        {card.target && (
                            <span className="px-2 py-0.5 rounded bg-[#27272A] text-[#71717A] text-xs font-heading">
                                {card.target}
                            </span>
                        )}
                    </div>
                    <h4 className="font-heading font-semibold text-[#FAFAFA] mt-1">{card.title}</h4>
                    <p className="text-sm text-[#71717A] font-body mt-0.5">{card.description}</p>
                </div>
            </div>

            {/* Preview */}
            {card.previewUrl && (
                <motion.div
                    whileHover={{ scale: 1.01 }}
                    className="mb-3 rounded-lg overflow-hidden border border-[#3F3F46]"
                >
                    <img src={card.previewUrl} alt="Preview" className="w-full h-32 object-cover" />
                </motion.div>
            )}

            {/* Actions */}
            <div className="flex flex-wrap gap-2">
                {card.actions.map((action) => (
                    <motion.button
                        key={action.id}
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => onAction(action.id)}
                        className={cn(
                            "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-heading font-medium transition-all duration-200 cursor-pointer",
                            action.variant === 'primary' && "bg-[#10B981] hover:bg-[#059669] text-white glow-emerald",
                            action.variant === 'secondary' && "bg-[#27272A] hover:bg-[#3F3F46] text-[#FAFAFA] border border-[#3F3F46]",
                            action.variant === 'ghost' && "text-[#71717A] hover:text-[#FAFAFA] hover:bg-[#27272A]"
                        )}
                    >
                        <action.icon className="w-3.5 h-3.5" />
                        {action.label}
                    </motion.button>
                ))}
            </div>
        </motion.div>
    )
}

export function AgentChat({ messages, onSendMessage, onCardAction, onDeleteMessage, isTyping, showEpisodesButton, onGoToEpisodes }: AgentChatProps) {
    const [input, setInput] = useState('')
    const [showMentions, setShowMentions] = useState(false)
    const scrollRef = useRef<HTMLDivElement>(null)
    const inputRef = useRef<HTMLTextAreaElement>(null)

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight
        }
    }, [messages, isTyping])

    const handleSend = () => {
        if (!input.trim() || isTyping) return
        onSendMessage(input)
        setInput('')
    }

    const insertMention = (mention: string) => {
        setInput(prev => prev + mention + ' ')
        setShowMentions(false)
        inputRef.current?.focus()
    }

    const mentions = ['@第1格', '@第2格', '@第3格', '@林知夏', '@雨夜旧书店', '@红色围巾']

    return (
        <div className="flex flex-col h-full bg-[#000000]">
            {/* Header */}
            <div className="h-14 flex items-center justify-between px-4 border-b border-[#27272A] bg-[#0C0C0C]/80 backdrop-blur-sm">
                <div className="flex items-center gap-3">
                    <motion.div
                        whileHover={{ scale: 1.05 }}
                        className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#10B981] to-[#06B6D4] flex items-center justify-center glow-emerald"
                    >
                        <Bot className="w-5 h-5 text-white" />
                    </motion.div>
                    <div>
                        <h3 className="font-heading text-sm font-semibold text-[#FAFAFA]">导演 Agent</h3>
                        <span className="text-xs text-[#10B981] font-body">在线</span>
                    </div>
                </div>

                {/* 进入分集按钮 */}
                {showEpisodesButton && onGoToEpisodes && (
                    <motion.button
                        initial={{ opacity: 0, x: 10 }}
                        animate={{ opacity: 1, x: 0 }}
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={onGoToEpisodes}
                        className={cn(
                            "flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-heading font-medium",
                            "bg-gradient-to-r from-[#10B981] to-[#06B6D4] text-white",
                            "hover:from-[#059669] hover:to-[#0891B2]",
                            "transition-all duration-200 cursor-pointer glow-emerald"
                        )}
                    >
                        <Layers className="w-4 h-4" />
                        进入分集
                        <ArrowRight className="w-4 h-4" />
                    </motion.button>
                )}
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4" ref={scrollRef}>
                {messages.length === 0 && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="flex flex-col items-center justify-center h-full text-center p-8"
                    >
                        <motion.div
                            animate={{ rotate: [0, 5, -5, 0] }}
                            transition={{ duration: 2, repeat: Infinity }}
                        >
                            <Sparkles className="w-12 h-12 text-[#10B981] mb-4" />
                        </motion.div>
                        <h4 className="font-heading font-semibold text-[#FAFAFA] text-lg mb-2">开始策划</h4>
                        <p className="text-sm text-[#71717A] font-body max-w-xs leading-relaxed">
                            告诉我您的创意想法，我来帮您规划剧本、分镜和资产
                        </p>
                    </motion.div>
                )}

                <AnimatePresence initial={false}>
                    {messages.map((msg, idx) => (
                        <motion.div
                            key={msg.id}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, x: msg.role === 'user' ? 20 : -20, height: 0 }}
                            transition={{ delay: idx * 0.05 }}
                            className={cn("flex gap-3 group relative", msg.role === 'user' ? "flex-row-reverse" : "")}
                        >
                            <motion.div
                                whileHover={{ scale: 1.05 }}
                                className={cn(
                                    "w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0",
                                    msg.role === 'user' ? "bg-[#10B981]" : "bg-[#18181B] border border-[#3F3F46]"
                                )}
                            >
                                {msg.role === 'user' ? <User className="w-4 h-4 text-white" /> : <Bot className="w-4 h-4 text-[#71717A]" />}
                            </motion.div>

                            <div className={cn("max-w-[80%]", msg.role === 'user' && "text-right")}>
                                <div className={cn(
                                    "px-4 py-3 rounded-2xl text-sm font-body leading-relaxed",
                                    msg.role === 'user'
                                        ? "bg-[#10B981]/20 border border-[#10B981]/30 text-[#FAFAFA] rounded-tr-md"
                                        : "bg-[#18181B] border border-[#27272A] text-[#FAFAFA] rounded-tl-md"
                                )}>
                                    {msg.role === 'user' ? (
                                        <p className="whitespace-pre-wrap">{msg.content}</p>
                                    ) : (
                                        <MarkdownContent content={msg.content} />
                                    )}
                                </div>

                                {msg.card && (
                                    <ActionCardComponent
                                        card={msg.card}
                                        onAction={(actionId) => onCardAction(msg.card!.id, actionId)}
                                    />
                                )}
                            </div>

                            {/* Delete button - shown on hover */}
                            {onDeleteMessage && (
                                <motion.button
                                    initial={{ opacity: 0, scale: 0.8 }}
                                    whileHover={{ scale: 1.1 }}
                                    whileTap={{ scale: 0.9 }}
                                    onClick={() => onDeleteMessage(msg.id)}
                                    className={cn(
                                        "absolute top-0 opacity-0 group-hover:opacity-100 transition-opacity duration-200",
                                        "p-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 hover:text-red-300",
                                        msg.role === 'user' ? "left-0" : "right-0"
                                    )}
                                    title="删除此消息"
                                >
                                    <Trash2 className="w-3.5 h-3.5" />
                                </motion.button>
                            )}
                        </motion.div>
                    ))}
                </AnimatePresence>

                {isTyping && (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-3">
                        <div className="w-8 h-8 rounded-lg bg-[#18181B] border border-[#3F3F46] flex items-center justify-center">
                            <Bot className="w-4 h-4 text-[#71717A]" />
                        </div>
                        <div className="px-4 py-3 rounded-2xl bg-[#18181B] border border-[#27272A] rounded-tl-md">
                            <div className="flex gap-1.5">
                                <motion.span animate={{ scale: [1, 1.2, 1] }} transition={{ repeat: Infinity, duration: 0.6, delay: 0 }} className="w-2 h-2 bg-[#10B981] rounded-full" />
                                <motion.span animate={{ scale: [1, 1.2, 1] }} transition={{ repeat: Infinity, duration: 0.6, delay: 0.15 }} className="w-2 h-2 bg-[#06B6D4] rounded-full" />
                                <motion.span animate={{ scale: [1, 1.2, 1] }} transition={{ repeat: Infinity, duration: 0.6, delay: 0.3 }} className="w-2 h-2 bg-[#10B981] rounded-full" />
                            </div>
                        </div>
                    </motion.div>
                )}
            </div>

            {/* Input Area */}
            <div className="p-4 border-t border-[#27272A] bg-[#0C0C0C]/50">
                {/* Mention Suggestions */}
                <AnimatePresence>
                    {showMentions && (
                        <motion.div
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: 10 }}
                            className="mb-3 flex flex-wrap gap-2"
                        >
                            {mentions.map((mention) => (
                                <motion.button
                                    key={mention}
                                    whileHover={{ scale: 1.02 }}
                                    whileTap={{ scale: 0.98 }}
                                    onClick={() => insertMention(mention)}
                                    className="px-2.5 py-1 bg-[#18181B] hover:bg-[#27272A] border border-[#3F3F46] rounded-lg text-xs text-[#FAFAFA] font-heading transition-colors duration-200 cursor-pointer"
                                >
                                    {mention}
                                </motion.button>
                            ))}
                        </motion.div>
                    )}
                </AnimatePresence>

                <div className="relative">
                    <textarea
                        ref={inputRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault()
                                handleSend()
                            }
                            if (e.key === '@' || (e.key === '2' && e.shiftKey)) {
                                setShowMentions(true)
                            }
                        }}
                        placeholder="输入指令，使用 @ 引用对象..."
                        className="input pr-24 min-h-[52px] max-h-[150px] resize-none"
                    />
                    <div className="absolute right-2 bottom-2 flex items-center gap-1">
                        <motion.button
                            whileHover={{ scale: 1.1 }}
                            whileTap={{ scale: 0.9 }}
                            onClick={() => setShowMentions(!showMentions)}
                            className="p-2 text-[#71717A] hover:text-[#10B981] hover:bg-[#18181B] rounded-lg transition-colors duration-200 cursor-pointer"
                        >
                            <AtSign className="w-4 h-4" />
                        </motion.button>
                        <motion.button
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                            onClick={handleSend}
                            disabled={!input.trim() || isTyping}
                            className="p-2 bg-[#10B981] hover:bg-[#059669] text-white rounded-lg disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200 cursor-pointer glow-emerald"
                        >
                            {isTyping ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                        </motion.button>
                    </div>
                </div>
            </div>
        </div>
    )
}
