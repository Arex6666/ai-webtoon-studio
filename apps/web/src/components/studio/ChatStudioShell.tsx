'use client'

import { useEffect, useState, useMemo } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useOrchestrator } from '@/hooks/useOrchestrator'
import { DirectorChat } from './chat/DirectorChat'
import { CreativeCanvas } from './canvas/CreativeCanvas'
import { Panel, Group, Separator } from "react-resizable-panels"
import { Home, Settings, Layers, Image as ImageIcon, MessageSquare, History, HelpCircle } from "lucide-react"
import Link from 'next/link'
import { Toaster } from "@/components/ui/toaster"
import { cn } from "@/lib/utils"

export function ChatStudioShell() {
    const router = useRouter()
    const params = useParams()
    const projectId = params.projectId as string

    const sessionId = useMemo(() => `sess_${projectId}_${new Date().getDate()}`, [projectId])

    const {
        messages,
        sendMessage,
        isTyping,
        currentMode,
        sessionState
    } = useOrchestrator({ projectId, sessionId })

    const [activeNavItem, setActiveNavItem] = useState("chat")

    const navItems = [
        { id: "home", icon: Home, label: "首页", href: "/" },
        { id: "chat", icon: MessageSquare, label: "对话" },
        { id: "layers", icon: Layers, label: "图层" },
        { id: "assets", icon: ImageIcon, label: "资产" },
    ]

    const bottomNavItems = [
        { id: "history", icon: History, label: "历史" },
        { id: "help", icon: HelpCircle, label: "帮助" },
        { id: "settings", icon: Settings, label: "设置" },
    ]

    return (
        <div className="h-screen w-screen bg-[#020617] flex overflow-hidden text-slate-50 font-sans">
            {/* Sidebar - OLED Dark with subtle border */}
            <div className="w-16 bg-[#0F172A] border-r border-slate-800/50 flex flex-col items-center py-4 gap-1 z-20">
                {/* Logo */}
                <Link
                    href="/"
                    className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center mb-4 shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/40 transition-shadow cursor-pointer"
                >
                    <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                </Link>

                {/* Main Nav */}
                <nav className="flex flex-col gap-1">
                    {navItems.map((item) => {
                        const isActive = item.id === activeNavItem
                        const content = (
                            <div
                                className={cn(
                                    "w-10 h-10 rounded-xl flex items-center justify-center transition-all cursor-pointer",
                                    isActive
                                        ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                                        : "text-slate-500 hover:text-slate-300 hover:bg-slate-800/50"
                                )}
                                title={item.label}
                            >
                                <item.icon className="w-5 h-5" />
                            </div>
                        )

                        if (item.href) {
                            return <Link key={item.id} href={item.href}>{content}</Link>
                        }
                        return (
                            <button key={item.id} onClick={() => setActiveNavItem(item.id)}>
                                {content}
                            </button>
                        )
                    })}
                </nav>

                <div className="flex-1" />

                {/* Bottom Nav */}
                <nav className="flex flex-col gap-1">
                    {bottomNavItems.map((item) => (
                        <button
                            key={item.id}
                            className="w-10 h-10 rounded-xl flex items-center justify-center text-slate-500 hover:text-slate-300 hover:bg-slate-800/50 transition-all cursor-pointer"
                            title={item.label}
                        >
                            <item.icon className="w-5 h-5" />
                        </button>
                    ))}
                </nav>
            </div>

            {/* Main Content with Resizable Panels */}
            <Group orientation="horizontal" className="flex-1">
                {/* Chat Interface */}
                <Panel defaultSize={32} minSize={25} maxSize={45} className="z-10">
                    <DirectorChat
                        messages={messages}
                        onSendMessage={sendMessage}
                        isTyping={isTyping}
                        currentMode={currentMode}
                    />
                </Panel>

                <Separator className="w-px bg-slate-800/50 hover:bg-emerald-500/50 transition-colors cursor-col-resize" />

                {/* Creative Canvas */}
                <Panel defaultSize={68} className="relative">
                    <CreativeCanvas
                        storyboard={sessionState?.current_storyboard}
                        onPanelSelect={(id) => console.log('Selected panel:', id)}
                    />
                </Panel>
            </Group>

            <Toaster />
        </div>
    )
}
