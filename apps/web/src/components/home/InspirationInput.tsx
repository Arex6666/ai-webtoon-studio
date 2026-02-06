'use client'

import { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
    Send, Sparkles, Paperclip, Users, Map, AtSign,
    X, FileText, Image as ImageIcon, ToggleLeft, ToggleRight, Loader2
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface InspirationInputProps {
    onSubmit: (data: {
        prompt: string
        attachments: File[]
        multiEpisode: boolean
        template?: string
    }) => void
    isSubmitting?: boolean
    selectedTemplate?: string
}

export function InspirationInput({ onSubmit, isSubmitting, selectedTemplate }: InspirationInputProps) {
    const [prompt, setPrompt] = useState('')
    const [attachments, setAttachments] = useState<File[]>([])
    const [multiEpisode, setMultiEpisode] = useState(false)
    const [showMentions, setShowMentions] = useState(false)
    const fileInputRef = useRef<HTMLInputElement>(null)
    const textareaRef = useRef<HTMLTextAreaElement>(null)

    const mentions = ['@林知夏', '@雨夜旧书店', '@红色围巾', '@韩漫风格']

    const handleSubmit = () => {
        if (!prompt.trim() || isSubmitting) return
        onSubmit({
            prompt,
            attachments,
            multiEpisode,
            template: selectedTemplate
        })
    }

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = Array.from(e.target.files || [])
        setAttachments(prev => [...prev, ...files])
    }

    const removeAttachment = (index: number) => {
        setAttachments(prev => prev.filter((_, i) => i !== index))
    }

    const insertMention = (mention: string) => {
        setPrompt(prev => prev + mention + ' ')
        setShowMentions(false)
        textareaRef.current?.focus()
    }

    const getFileIcon = (file: File) => {
        if (file.type.startsWith('image/')) return ImageIcon
        return FileText
    }

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="w-full max-w-2xl mx-auto"
        >
            <div className="relative bg-gradient-to-br from-[#18181B] to-[#0C0C0C] rounded-2xl border border-[#27272A] shadow-2xl overflow-hidden">
                {/* Glow effect */}
                <div className="absolute inset-0 bg-gradient-to-br from-[#10B981]/5 via-transparent to-[#06B6D4]/5 pointer-events-none" />

                {/* Main input */}
                <div className="relative p-5">
                    <textarea
                        ref={textareaRef}
                        value={prompt}
                        onChange={(e) => setPrompt(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault()
                                handleSubmit()
                            }
                            if (e.key === '@' || (e.key === '2' && e.shiftKey)) {
                                setShowMentions(true)
                            }
                        }}
                        placeholder="描述你的创意，或上传剧本..."
                        className="w-full min-h-[120px] bg-transparent text-[#FAFAFA] font-body text-lg leading-relaxed resize-none focus:outline-none placeholder:text-[#52525B]"
                    />

                    {/* Attachments */}
                    <AnimatePresence>
                        {attachments.length > 0 && (
                            <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-[#27272A]"
                            >
                                {attachments.map((file, idx) => {
                                    const Icon = getFileIcon(file)
                                    return (
                                        <motion.div
                                            key={idx}
                                            initial={{ scale: 0.8, opacity: 0 }}
                                            animate={{ scale: 1, opacity: 1 }}
                                            exit={{ scale: 0.8, opacity: 0 }}
                                            className="flex items-center gap-2 px-3 py-1.5 bg-[#27272A] rounded-lg group"
                                        >
                                            <Icon className="w-4 h-4 text-[#71717A]" />
                                            <span className="text-sm text-[#FAFAFA] font-body max-w-[100px] truncate">{file.name}</span>
                                            <button
                                                onClick={() => removeAttachment(idx)}
                                                className="p-0.5 rounded hover:bg-[#3F3F46] text-[#71717A] hover:text-[#FAFAFA] transition-colors cursor-pointer opacity-0 group-hover:opacity-100"
                                            >
                                                <X className="w-3.5 h-3.5" />
                                            </button>
                                        </motion.div>
                                    )
                                })}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>

                {/* Mentions dropdown */}
                <AnimatePresence>
                    {showMentions && (
                        <motion.div
                            initial={{ opacity: 0, y: -10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                            className="absolute left-5 right-5 top-[calc(100%-80px)] bg-[#1A1A1A] border border-[#3F3F46] rounded-xl shadow-xl z-10 p-2"
                        >
                            <div className="text-xs text-[#71717A] font-heading px-2 py-1 mb-1">引用资产</div>
                            <div className="flex flex-wrap gap-1">
                                {mentions.map((mention) => (
                                    <motion.button
                                        key={mention}
                                        whileHover={{ scale: 1.02 }}
                                        whileTap={{ scale: 0.98 }}
                                        onClick={() => insertMention(mention)}
                                        className="px-2.5 py-1.5 bg-[#27272A] hover:bg-[#3F3F46] rounded-lg text-sm font-body text-[#FAFAFA] transition-colors cursor-pointer"
                                    >
                                        {mention}
                                    </motion.button>
                                ))}
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Toolbar */}
                <div className="flex items-center justify-between px-5 py-3 border-t border-[#27272A] bg-[#000000]/30">
                    {/* Left actions */}
                    <div className="flex items-center gap-2">
                        <input
                            ref={fileInputRef}
                            type="file"
                            multiple
                            accept="image/*,.txt,.md,.doc,.docx,.pdf"
                            onChange={handleFileChange}
                            className="hidden"
                        />
                        <motion.button
                            whileHover={{ scale: 1.1 }}
                            whileTap={{ scale: 0.9 }}
                            onClick={() => fileInputRef.current?.click()}
                            className="p-2.5 rounded-xl text-[#71717A] hover:text-[#FAFAFA] hover:bg-[#27272A] transition-colors cursor-pointer"
                            title="上传附件"
                        >
                            <Paperclip className="w-5 h-5" />
                        </motion.button>
                        <motion.button
                            whileHover={{ scale: 1.1 }}
                            whileTap={{ scale: 0.9 }}
                            onClick={() => setShowMentions(!showMentions)}
                            className="p-2.5 rounded-xl text-[#71717A] hover:text-[#FAFAFA] hover:bg-[#27272A] transition-colors cursor-pointer"
                            title="引用资产"
                        >
                            <AtSign className="w-5 h-5" />
                        </motion.button>

                        <div className="w-px h-6 bg-[#27272A] mx-1" />

                        {/* Multi-episode toggle */}
                        <motion.button
                            whileHover={{ scale: 1.02 }}
                            whileTap={{ scale: 0.98 }}
                            onClick={() => setMultiEpisode(!multiEpisode)}
                            className={cn(
                                "flex items-center gap-2 px-3 py-1.5 rounded-xl text-sm font-heading transition-colors cursor-pointer",
                                multiEpisode
                                    ? "bg-[#10B981]/20 text-[#10B981]"
                                    : "bg-[#27272A] text-[#71717A] hover:text-[#FAFAFA]"
                            )}
                        >
                            {multiEpisode ? <ToggleRight className="w-4 h-4" /> : <ToggleLeft className="w-4 h-4" />}
                            多剧集
                        </motion.button>
                    </div>

                    {/* Submit button */}
                    <motion.button
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={handleSubmit}
                        disabled={!prompt.trim() || isSubmitting}
                        className={cn(
                            "flex items-center gap-2 px-6 py-2.5 rounded-xl font-heading font-semibold transition-all cursor-pointer",
                            prompt.trim() && !isSubmitting
                                ? "bg-gradient-to-r from-[#10B981] to-[#06B6D4] text-white glow-emerald"
                                : "bg-[#27272A] text-[#52525B] cursor-not-allowed"
                        )}
                    >
                        {isSubmitting ? (
                            <>
                                <Loader2 className="w-5 h-5 animate-spin" />
                                创建中...
                            </>
                        ) : (
                            <>
                                <Sparkles className="w-5 h-5" />
                                开始创作
                            </>
                        )}
                    </motion.button>
                </div>
            </div>

            {/* Selected template indicator */}
            {selectedTemplate && (
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mt-3 flex items-center justify-center gap-2 text-sm text-[#71717A] font-body"
                >
                    <span>已选择模板:</span>
                    <span className="px-2 py-0.5 bg-[#27272A] rounded text-[#FAFAFA] font-heading">{selectedTemplate}</span>
                </motion.div>
            )}
        </motion.div>
    )
}
