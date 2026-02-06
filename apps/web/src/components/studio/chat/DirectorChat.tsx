import { useState, useRef, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Send, Sparkles, Bot, User, Image as ImageIcon, Paperclip, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

export type MessageRole = "user" | "assistant" | "system"
export type AgentMode = "scriptwriter" | "director" | "art_director" | "producer" | "qa"

export interface Message {
    id: string
    role: MessageRole
    content: string
    mode?: AgentMode
    timestamp: number
    attachments?: string[]
}

interface DirectorChatProps {
    messages: Message[]
    onSendMessage: (content: string) => void
    isTyping?: boolean
    currentMode?: AgentMode
}

const ModeIndicator = ({ mode }: { mode: AgentMode }) => {
    const modes = {
        scriptwriter: { label: "编剧", color: "text-blue-400", bg: "bg-blue-500/10", border: "border-blue-500/30" },
        director: { label: "导演", color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/30" },
        art_director: { label: "美术", color: "text-pink-400", bg: "bg-pink-500/10", border: "border-pink-500/30" },
        producer: { label: "制片", color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/30" },
        qa: { label: "质检", color: "text-cyan-400", bg: "bg-cyan-500/10", border: "border-cyan-500/30" },
    }

    const config = modes[mode] || modes.director

    return (
        <div className={cn(
            "flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors cursor-default",
            config.color, config.bg, config.border
        )}>
            <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
            {config.label}模式
        </div>
    )
}

export function DirectorChat({ messages, onSendMessage, isTyping, currentMode = "director" }: DirectorChatProps) {
    const [input, setInput] = useState("")
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
        setInput("")
    }

    return (
        <div className="flex flex-col h-full bg-[#020617] font-sans">
            {/* Header - Glassmorphism */}
            <div className="flex items-center justify-between p-4 border-b border-slate-800/50 bg-slate-900/80 backdrop-blur-md sticky top-0 z-10">
                <div className="flex items-center gap-3">
                    <div className="relative">
                        <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
                            <Bot className="w-6 h-6 text-white" />
                        </div>
                        <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-emerald-400 rounded-full border-2 border-[#020617]" />
                    </div>
                    <div>
                        <h3 className="font-mono font-semibold text-slate-50 text-base tracking-tight">Director Agent</h3>
                        <div className="flex items-center gap-2 mt-0.5">
                            <ModeIndicator mode={currentMode} />
                        </div>
                    </div>
                </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-5" ref={scrollRef}>
                {messages.length === 0 && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="flex flex-col items-center justify-center h-full text-center p-8"
                    >
                        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-500/20 to-cyan-500/20 border border-emerald-500/30 flex items-center justify-center mb-5">
                            <Sparkles className="w-8 h-8 text-emerald-400" />
                        </div>
                        <h4 className="font-mono font-medium text-lg text-slate-100 mb-2">开始创作您的漫剧</h4>
                        <p className="text-sm text-slate-400 max-w-xs leading-relaxed">
                            您可以直接告诉我您的创意，或者从剧本开始。我是您的 AI 导演，将协助您完成全流程创作。
                        </p>
                        <div className="mt-6 flex flex-wrap gap-2 justify-center">
                            {["帮我创建一个4格漫画", "修改第2格的构图", "添加一个新角色"].map((suggestion) => (
                                <button
                                    key={suggestion}
                                    onClick={() => { setInput(suggestion); inputRef.current?.focus() }}
                                    className="px-3 py-1.5 rounded-lg bg-slate-800/50 border border-slate-700/50 text-xs text-slate-300 hover:bg-slate-700/50 hover:border-slate-600 transition-all cursor-pointer"
                                >
                                    {suggestion}
                                </button>
                            ))}
                        </div>
                    </motion.div>
                )}

                <AnimatePresence initial={false}>
                    {messages.map((msg) => (
                        <motion.div
                            key={msg.id}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                            transition={{ duration: 0.2 }}
                            className={cn("flex gap-3 max-w-[92%]", msg.role === "user" ? "ml-auto flex-row-reverse" : "")}
                        >
                            <div className={cn(
                                "w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-1",
                                msg.role === "assistant"
                                    ? "bg-slate-800 border border-slate-700"
                                    : "bg-emerald-500"
                            )}>
                                {msg.role === "assistant" ? <Bot className="w-4 h-4 text-slate-400" /> : <User className="w-4 h-4 text-white" />}
                            </div>

                            <div className="flex flex-col gap-1 min-w-0">
                                <div className={cn(
                                    "px-4 py-3 rounded-2xl text-sm leading-relaxed",
                                    msg.role === "assistant"
                                        ? "bg-slate-800/80 border border-slate-700/50 text-slate-200 rounded-tl-md"
                                        : "bg-emerald-500/20 border border-emerald-500/30 text-slate-100 rounded-tr-md"
                                )}>
                                    <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                                </div>
                                <span className="text-[10px] text-slate-500 px-1 font-mono">
                                    {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </span>
                            </div>
                        </motion.div>
                    ))}
                </AnimatePresence>

                {isTyping && (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-3">
                        <div className="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center flex-shrink-0 mt-1">
                            <Bot className="w-4 h-4 text-slate-400" />
                        </div>
                        <div className="px-4 py-3 rounded-2xl bg-slate-800/80 border border-slate-700/50 rounded-tl-md flex items-center gap-1.5">
                            <span className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
                            <span className="w-2 h-2 bg-cyan-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
                            <span className="w-2 h-2 bg-emerald-400 rounded-full animate-bounce" />
                        </div>
                    </motion.div>
                )}
            </div>

            {/* Input Area */}
            <div className="p-4 border-t border-slate-800/50 bg-slate-900/50 backdrop-blur-sm">
                <div className="flex items-center gap-2 mb-2">
                    <button className="p-2 text-slate-500 hover:text-slate-300 hover:bg-slate-800 rounded-lg transition-colors cursor-pointer">
                        <ImageIcon className="w-4 h-4" />
                    </button>
                    <button className="p-2 text-slate-500 hover:text-slate-300 hover:bg-slate-800 rounded-lg transition-colors cursor-pointer">
                        <Paperclip className="w-4 h-4" />
                    </button>
                </div>
                <div className="relative">
                    <textarea
                        ref={inputRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === "Enter" && !e.shiftKey) {
                                e.preventDefault()
                                handleSend()
                            }
                        }}
                        placeholder="输入您的指令..."
                        className="w-full bg-slate-900 border border-slate-700/50 rounded-xl p-4 pr-14 min-h-[60px] max-h-[180px] resize-none focus:outline-none focus:border-emerald-500/50 focus:ring-2 focus:ring-emerald-500/20 transition-all text-sm text-slate-200 placeholder:text-slate-500 font-sans"
                    />
                    <button
                        onClick={handleSend}
                        disabled={!input.trim() || isTyping}
                        className="absolute right-3 bottom-3 p-2.5 bg-emerald-500 hover:bg-emerald-400 text-white rounded-lg disabled:opacity-40 disabled:cursor-not-allowed transition-all cursor-pointer shadow-lg shadow-emerald-500/20"
                    >
                        {isTyping ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    </button>
                </div>
                <p className="text-[10px] text-slate-600 text-center mt-2 font-mono">
                    Director Agent 可能生成不准确的信息
                </p>
            </div>
        </div>
    )
}
