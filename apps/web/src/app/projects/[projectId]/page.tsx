"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import {
  Folder, Plus, Clock, FileText, MoreHorizontal,
  Edit3, Trash2, ArrowLeft, Loader2
} from "lucide-react"
import { chaptersApi, projectsApi, type Chapter, type Project } from "@/lib/api"
import { formatRelativeTime } from "@/lib/utils/cn"
import { Button } from "@/components/ui/button"

export default function ProjectDetailPage({ params }: { params: { projectId: string } }) {
  const [project, setProject] = useState<Project | null>(null)
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)

  useEffect(() => {
    loadData()
  }, [params.projectId])

  async function loadData() {
    try {
      setLoading(true)
      const [projectData, chaptersData] = await Promise.all([
        projectsApi.get(params.projectId),
        chaptersApi.list(params.projectId)
      ])
      setProject(projectData)
      setChapters(chaptersData.items)
    } catch (error) {
      console.error("Failed to load project data:", error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-full bg-canvas p-6 flex flex-col">
      {/* 顶部导航与操作栏 */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <Link href="/projects">
            <Button variant="ghost" size="icon" className="rounded-full hover:bg-panel">
              <ArrowLeft className="w-5 h-5 text-ink-muted" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-2 text-sm text-ink-muted mb-1">
              <span>Projects</span>
              <span>/</span>
              <span className="text-ink">{project?.name || "Loading..."}</span>
            </div>
            <h1 className="font-display font-bold text-2xl">{project?.name}</h1>
          </div>
        </div>

        <Button
          onClick={() => setShowCreateModal(true)}
          className="bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500 text-white shadow-lg shadow-emerald-500/20"
        >
          <Plus className="w-4 h-4 mr-2" />
          新建章节
        </Button>
      </div>

      {/* 内容区域 */}
      <div className="flex-1">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-accent" />
          </div>
        ) : chapters.length === 0 ? (
          <EmptyState onCreate={() => setShowCreateModal(true)} />
        ) : (
          <div className="space-y-4">
            {/* Section header */}
            <div className="flex items-center justify-between px-1">
              <div className="flex items-center gap-3">
                <div className="w-1 h-5 rounded-full bg-gradient-to-b from-emerald-400 to-emerald-600" />
                <span className="text-sm font-semibold text-slate-300">章节列表</span>
              </div>
              <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-slate-800/80 text-slate-400 border border-slate-700/50">
                {chapters.length} 个章节
              </span>
            </div>
            {/* Chapter cards */}
            <div className="space-y-3">
              {chapters.map((chapter, index) => (
                <ChapterListItem key={chapter.id} projectId={params.projectId} chapter={chapter} index={index} />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 创建章节模态框 */}
      <AnimatePresence>
        {showCreateModal && (
          <CreateChapterModal
            projectId={params.projectId}
            onClose={() => setShowCreateModal(false)}
            onSuccess={(newChapter) => {
              setChapters([newChapter, ...chapters])
              setShowCreateModal(false)
            }}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      className="flex flex-col items-center justify-center py-24 rounded-2xl 
        bg-slate-900/50
        border border-slate-800/60
        relative overflow-hidden"
    >
      {/* Subtle gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-transparent to-slate-900/50" />

      {/* Icon */}
      <div className="relative mb-6 z-10">
        <div className="w-16 h-16 rounded-xl bg-slate-800/80 border border-slate-700/50 flex items-center justify-center">
          <Folder className="w-7 h-7 text-slate-500" />
        </div>
      </div>

      {/* Text content */}
      <h3 className="font-display font-semibold text-lg mb-2 text-slate-200 relative z-10">还没有章节</h3>
      <p className="text-slate-500 mb-8 text-sm max-w-sm text-center leading-relaxed relative z-10">
        创建一个新章节开始编写剧本和制作分镜。<br />
        每个章节可以包含多个场景和分镜。
      </p>

      {/* Action button */}
      <Button
        onClick={onCreate}
        className="relative z-10 bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500 text-white px-6 py-2.5 rounded-lg font-medium shadow-lg shadow-emerald-500/20"
      >
        <Plus className="w-4 h-4 mr-2" />
        创建第一章
      </Button>
    </motion.div>
  )
}

function ChapterListItem({ projectId, chapter, index }: { projectId: string; chapter: Readonly<Chapter>; index: number }) {
  // Status configuration with refined dark mode colors
  const statusConfig = {
    draft: { label: 'Draft', bg: 'bg-slate-700/80', textColor: 'text-slate-300', icon: FileText },
    production: { label: '制作中', bg: 'bg-amber-500/20', textColor: 'text-amber-400', icon: Clock },
    completed: { label: '已完成', bg: 'bg-emerald-500/20', textColor: 'text-emerald-400', icon: Folder },
  }
  const status = statusConfig.draft // Default to draft

  return (
    <Link href={`/projects/${projectId}/chapters/${chapter.id}/studio`}>
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: index * 0.05 }}
        whileHover={{ x: 4 }}
        className="group relative flex items-center gap-4 p-4 rounded-xl cursor-pointer
          bg-slate-900/60 
          border border-slate-800/60 
          hover:bg-slate-800/60 hover:border-slate-700/60
          transition-all duration-200"
      >
        {/* Chapter icon */}
        <div className="flex-shrink-0">
          <div className="w-11 h-11 rounded-lg bg-slate-800/80 border border-slate-700/50 flex items-center justify-center group-hover:border-emerald-500/30 transition-colors">
            <FileText className="w-5 h-5 text-slate-500 group-hover:text-emerald-400 transition-colors" />
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0 space-y-0.5">
          <h4 className="font-medium text-slate-200 group-hover:text-white transition-colors truncate">
            {chapter.title}
          </h4>
          <p className="text-xs text-slate-500 truncate max-w-md">
            {chapter.description || "无描述"}
          </p>
        </div>

        {/* Status badge */}
        <div className="flex-shrink-0">
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium ${status.bg} ${status.textColor} border border-slate-700/50`}>
            <status.icon className="w-3 h-3" />
            {status.label}
          </span>
        </div>

        {/* Panel count */}
        <div className="flex-shrink-0 text-center min-w-[70px]">
          <span className="text-sm text-slate-500">
            <span className="text-slate-400 font-medium">-</span> Panels
          </span>
        </div>

        {/* Timestamp */}
        <div className="flex-shrink-0 text-right min-w-[80px]">
          <span className="text-xs text-slate-600 group-hover:text-slate-500 transition-colors">
            {formatRelativeTime(chapter.updated_at)}
          </span>
        </div>

        {/* Hover arrow indicator */}
        <div className="flex-shrink-0 w-5 opacity-0 group-hover:opacity-100 transition-opacity">
          <ArrowLeft className="w-4 h-4 text-emerald-400 rotate-180" />
        </div>
      </motion.div>
    </Link>
  )
}

function CreateChapterModal({
  projectId,
  onClose,
  onSuccess
}: {
  projectId: string
  onClose: () => void
  onSuccess: (chapter: Chapter) => void
}) {
  const [title, setTitle] = useState("")
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!title.trim()) return

    try {
      setLoading(true)
      const newChapter = await chaptersApi.create({
        project_id: projectId,
        title: title,
        description: ""
      })
      onSuccess(newChapter)
    } catch (error) {
      console.error("Failed to create chapter:", error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md bg-panel rounded-2xl border border-panel-border shadow-2xl overflow-hidden"
      >
        <div className="p-6 border-b border-panel-border">
          <h2 className="text-lg font-bold">新建章节</h2>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-ink-muted mb-2">章节标题</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="例如：第一章 相遇"
              className="w-full px-4 py-2 bg-canvas rounded-lg border border-panel-border focus:border-accent outline-none transition-colors"
              autoFocus
            />
          </div>

          <div className="flex gap-3 pt-4">
            <Button type="button" variant="ghost" onClick={onClose} className="flex-1">
              取消
            </Button>
            <Button type="submit" disabled={!title.trim() || loading} className="flex-1 bg-accent hover:bg-accent-hover text-white">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : "创建"}
            </Button>
          </div>
        </form>
      </motion.div>
    </div>
  )
}
