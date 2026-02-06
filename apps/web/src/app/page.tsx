"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import {
    Plus, Folder, Clock, Sparkles, BookOpen,
    MoreHorizontal, Trash2, Archive, Edit3,
    Search, Grid, List, Zap
} from "lucide-react"
import { projectsApi, type Project } from "@/lib/api"
import { formatRelativeTime, cn } from "@/lib/utils/cn"
import Link from "next/link"
import { InspirationInput } from '@/components/home/InspirationInput'
import { TemplateChips, Template } from '@/components/home/TemplateChips'
import { InspirationFeed } from '@/components/home/InspirationFeed'

export default function HomePage() {
    const router = useRouter()
    const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null)
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [showProjects, setShowProjects] = useState(false)
    const [projects, setProjects] = useState<Project[]>([])

    const handleTemplateSelect = (template: Template) => {
        setSelectedTemplate(template)
    }

    const handleSubmit = async (data: {
        prompt: string
        attachments: File[]
        multiEpisode: boolean
        template?: string
    }) => {
        setIsSubmitting(true)
        try {
            // Create new project
            const project = await projectsApi.create({
                name: '新项目',
                description: data.prompt,
                creation_method: 'agent',
            })
            // Navigate to agent workspace with the prompt as query param
            const params = new URLSearchParams({
                prompt: data.prompt,
                multi_episode: String(data.multiEpisode),
            })
            if (data.template) {
                params.set('template', data.template)
            }
            router.push(`/agent/${project.id}?${params.toString()}`)
        } catch (error) {
            console.error('Failed to create project:', error)
            setIsSubmitting(false)
        }
    }

    const handleClone = (workId: string) => {
        console.log('Clone work:', workId)
        // TODO: Implement clone functionality
    }

    return (
        <div className="flex-1 flex flex-col min-h-screen bg-[#000000] text-[#FAFAFA] font-body overflow-hidden">
            {/* Main Content (GlobalNav is provided by AppShell) */}
            <div className="flex-1 overflow-y-auto">
                <div className="min-h-screen flex flex-col">
                    {/* Hero Section */}
                    <div className="flex-1 flex flex-col items-center justify-center px-8 py-16">
                        {/* Title */}
                        <motion.div
                            initial={{ opacity: 0, y: -20 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="text-center mb-10"
                        >
                            <h1 className="font-heading font-bold text-4xl md:text-5xl tracking-tight mb-4">
                                讲述你的
                                <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#10B981] via-[#06B6D4] to-[#8B5CF6]">
                                    创意故事
                                </span>
                            </h1>
                            <p className="text-[#71717A] text-lg md:text-xl max-w-xl mx-auto">
                                用自然语言描述你的想法，AI 帮你生成完整的漫剧
                            </p>
                        </motion.div>

                        {/* Template Chips */}
                        <div className="mb-8">
                            <TemplateChips
                                selectedId={selectedTemplate?.id || null}
                                onSelect={handleTemplateSelect}
                            />
                        </div>

                        {/* Inspiration Input */}
                        <InspirationInput
                            onSubmit={handleSubmit}
                            isSubmitting={isSubmitting}
                            selectedTemplate={selectedTemplate?.label}
                        />

                        {/* Quick Actions */}
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ delay: 0.3 }}
                            className="flex items-center gap-4 mt-8"
                        >
                            <Link href="/projects">
                                <motion.button
                                    whileHover={{ scale: 1.02 }}
                                    whileTap={{ scale: 0.98 }}
                                    className="flex items-center gap-2 px-4 py-2 bg-[#18181B] hover:bg-[#27272A] border border-[#27272A] rounded-xl text-sm font-heading text-[#A1A1AA] hover:text-[#FAFAFA] transition-colors cursor-pointer"
                                >
                                    <Folder className="w-4 h-4" />
                                    我的项目
                                </motion.button>
                            </Link>
                            <button
                                onClick={() => setShowProjects(!showProjects)}
                                className="flex items-center gap-2 px-4 py-2 text-sm font-heading text-[#71717A] hover:text-[#FAFAFA] transition-colors cursor-pointer"
                            >
                                <Clock className="w-4 h-4" />
                                最近项目
                            </button>
                        </motion.div>
                    </div>

                    {/* Inspiration Feed */}
                    <div className="px-8 pb-16">
                        <InspirationFeed onClone={handleClone} />
                    </div>
                </div>
            </div>
        </div>
    )
}
