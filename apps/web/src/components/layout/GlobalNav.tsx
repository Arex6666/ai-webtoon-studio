'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import {
    Sparkles, Folder, Palette, Zap, Settings,
    ChevronLeft, ChevronRight, Hammer
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface NavItem {
    id: string
    label: string
    icon: React.ElementType
    href: string
    badge?: number
}

const navItems: NavItem[] = [
    { id: 'inspiration', label: '灵感广场', icon: Sparkles, href: '/' },
    { id: 'my-projects', label: '我的项目', icon: Folder, href: '/projects' },
    { id: 'production-project', label: '生产项目', icon: Hammer, href: '/production' },
    { id: 'assets', label: '资产库', icon: Palette, href: '/assets' },
    { id: 'queue', label: '生产队列', icon: Zap, href: '/queue' },
    { id: 'settings', label: '设置', icon: Settings, href: '/settings' },
]

export function GlobalNav() {
    const pathname = usePathname()
    const [collapsed, setCollapsed] = useState(false)

    const isActive = (href: string) => {
        if (href === '/') return pathname === '/'
        return pathname.startsWith(href)
    }

    return (
        <motion.nav
            initial={false}
            animate={{ width: collapsed ? 72 : 240 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="h-screen bg-[#0C0C0C] border-r border-[#27272A] flex flex-col z-30 relative"
        >
            {/* Logo */}
            <div className="h-16 flex items-center px-4 border-b border-[#27272A]">
                <Link href="/" className="flex items-center gap-3 group">
                    <motion.div
                        whileHover={{ scale: 1.05 }}
                        className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#10B981] to-[#06B6D4] flex items-center justify-center glow-emerald"
                    >
                        <Zap className="w-5 h-5 text-white" />
                    </motion.div>
                    <AnimatePresence>
                        {!collapsed && (
                            <motion.span
                                initial={{ opacity: 0, x: -10 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -10 }}
                                transition={{ duration: 0.15 }}
                                className="font-heading font-bold text-[#FAFAFA] text-sm whitespace-nowrap"
                            >
                                AI Webtoon
                            </motion.span>
                        )}
                    </AnimatePresence>
                </Link>
            </div>

            {/* Nav Items */}
            <div className="flex-1 py-4 px-3 space-y-1">
                {navItems.map((item) => {
                    const active = isActive(item.href)
                    return (
                        <Link key={item.id} href={item.href}>
                            <motion.div
                                whileHover={{ x: 4 }}
                                transition={{ duration: 0.15 }}
                                className={cn(
                                    "flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-200 cursor-pointer group",
                                    active
                                        ? "bg-[#10B981]/15 text-[#10B981]"
                                        : "text-[#71717A] hover:text-[#FAFAFA] hover:bg-[#18181B]"
                                )}
                            >
                                <item.icon className={cn(
                                    "w-5 h-5 flex-shrink-0 transition-colors duration-200",
                                    active ? "text-[#10B981]" : "text-[#52525B] group-hover:text-[#FAFAFA]"
                                )} />
                                <AnimatePresence>
                                    {!collapsed && (
                                        <motion.span
                                            initial={{ opacity: 0 }}
                                            animate={{ opacity: 1 }}
                                            exit={{ opacity: 0 }}
                                            transition={{ duration: 0.15 }}
                                            className="font-body text-sm font-medium whitespace-nowrap"
                                        >
                                            {item.label}
                                        </motion.span>
                                    )}
                                </AnimatePresence>
                                {item.badge && !collapsed && (
                                    <span className="ml-auto px-2 py-0.5 text-xs font-heading bg-[#F59E0B]/20 text-[#F59E0B] rounded-full">
                                        {item.badge}
                                    </span>
                                )}
                            </motion.div>
                        </Link>
                    )
                })}
            </div>

            {/* Collapse Toggle */}
            <div className="p-3 border-t border-[#27272A]">
                <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setCollapsed(!collapsed)}
                    className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-[#71717A] hover:text-[#FAFAFA] hover:bg-[#18181B] transition-all duration-200 cursor-pointer"
                >
                    {collapsed ? (
                        <ChevronRight className="w-4 h-4" />
                    ) : (
                        <>
                            <ChevronLeft className="w-4 h-4" />
                            <span className="text-xs font-body">收起</span>
                        </>
                    )}
                </motion.button>
            </div>
        </motion.nav>
    )
}
