'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Plus, Loader2, RefreshCw, ArrowRight, Bot, HardHat, Folder, Search, LayoutGrid, List, Film, Sparkles, Trash2, X } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { projectsApi, type Project } from '@/lib/api'

// Enhanced Project Card with Delete Functionality
function ProjectCard({
  project,
  onDelete
}: {
  project: Project
  onDelete: (id: string) => void
}) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

  const isAgentProject = project.creation_method === 'agent'
  const href = isAgentProject ? `/agent/${project.id}` : `/projects/${project.id}`

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-'
    try {
      return new Date(dateStr).toLocaleDateString('zh-CN')
    } catch {
      return dateStr
    }
  }

  const handleDelete = async (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDeleting(true)
    try {
      await projectsApi.delete(project.id)
      onDelete(project.id)
    } catch (err) {
      console.error('Failed to delete project:', err)
      alert('删除项目失败，请重试')
    } finally {
      setIsDeleting(false)
      setShowDeleteConfirm(false)
    }
  }

  return (
    <div className="relative group">
      <Link href={href} className="block">
        <Card
          className={cn(
            'relative h-full cursor-pointer overflow-hidden transition-all duration-300',
            'bg-gradient-to-br from-zinc-900/80 to-zinc-950/90',
            'border border-zinc-800/50 backdrop-blur-sm',
            'hover:-translate-y-1 hover:shadow-xl hover:shadow-emerald-500/10',
            'hover:border-zinc-700'
          )}
        >
          {/* Gradient accent line at top */}
          <div className={cn(
            'absolute top-0 left-0 right-0 h-0.5 opacity-60 group-hover:opacity-100 transition-opacity',
            isAgentProject
              ? 'bg-gradient-to-r from-emerald-500 via-emerald-400 to-cyan-400'
              : 'bg-gradient-to-r from-blue-500 via-blue-400 to-violet-400'
          )} />

          <CardHeader className="pb-3">
            <div className="flex items-center justify-between gap-2">
              <div className={cn(
                'p-2.5 rounded-xl',
                isAgentProject
                  ? 'bg-emerald-500/10 text-emerald-400'
                  : 'bg-blue-500/10 text-blue-400'
              )}>
                <Film className="h-5 w-5" />
              </div>
              <Badge
                variant="outline"
                className={cn(
                  'text-xs px-2 py-0.5 rounded-md border',
                  isAgentProject
                    ? 'border-emerald-500/30 bg-emerald-500/5 text-emerald-400'
                    : 'border-blue-500/30 bg-blue-500/5 text-blue-400'
                )}
              >
                {isAgentProject ? (
                  <Bot className="mr-1.5 h-3 w-3" />
                ) : (
                  <HardHat className="mr-1.5 h-3 w-3" />
                )}
                {isAgentProject ? 'Agent' : '工作台'}
              </Badge>
            </div>
            <CardTitle className="pt-4 line-clamp-1 text-base font-semibold text-zinc-100 group-hover:text-white transition-colors">
              {project.name || '未命名项目'}
            </CardTitle>
            {project.description && (
              <CardDescription className="mt-1 line-clamp-2 text-xs text-zinc-500">
                {project.description}
              </CardDescription>
            )}
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between text-xs text-zinc-500 group-hover:text-zinc-400 transition-colors">
              <span className="flex items-center gap-1">
                <span className="text-zinc-400 font-medium">{project.chapter_count ?? 0}</span> 章节
              </span>
              <span>更新于 {formatDate(project.updated_at)}</span>
            </div>
          </CardContent>
        </Card>
      </Link>

      {/* Delete Button - visible on hover */}
      <button
        onClick={(e) => {
          e.preventDefault()
          e.stopPropagation()
          setShowDeleteConfirm(true)
        }}
        className={cn(
          'absolute top-2 right-2 p-1.5 rounded-lg z-10',
          'opacity-0 group-hover:opacity-100 transition-opacity',
          'bg-zinc-800/80 hover:bg-red-500/20 border border-zinc-700 hover:border-red-500/50',
          'text-zinc-400 hover:text-red-400'
        )}
        title="删除项目"
      >
        <Trash2 className="h-4 w-4" />
      </button>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
          onClick={() => setShowDeleteConfirm(false)}
        >
          <div
            className="bg-zinc-900 border border-zinc-700 rounded-xl p-6 max-w-sm mx-4 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-full bg-red-500/10">
                <Trash2 className="h-5 w-5 text-red-400" />
              </div>
              <h3 className="text-lg font-semibold text-white">删除项目</h3>
            </div>
            <p className="text-zinc-400 text-sm mb-6">
              确定要删除项目 "<span className="text-white font-medium">{project.name || '未命名项目'}</span>" 吗？此操作不可撤销，项目下的所有章节和数据将被永久删除。
            </p>
            <div className="flex gap-3 justify-end">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowDeleteConfirm(false)}
                className="text-zinc-400 hover:text-white"
              >
                取消
              </Button>
              <Button
                size="sm"
                onClick={handleDelete}
                disabled={isDeleting}
                className="bg-red-600 hover:bg-red-700 text-white"
              >
                {isDeleting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    删除中...
                  </>
                ) : (
                  '确认删除'
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [filter, setFilter] = useState<'all' | 'agent' | 'workbench'>('all')

  const fetchProjects = async () => {
    try {
      setLoading(true)
      setError(null)
      const { items } = await projectsApi.list()
      setProjects(items)
    } catch (err) {
      console.error('Error fetching projects:', err)
      setError(err instanceof Error ? err.message : 'Failed to load projects')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchProjects()
  }, [])

  // Filter projects by search query and mode
  const filteredProjects = useMemo(() => {
    let result = projects

    // Filter by mode
    if (filter !== 'all') {
      result = result.filter(p => p.creation_method === filter)
    }

    // Filter by search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      result = result.filter(p =>
        p.name?.toLowerCase().includes(query) ||
        p.description?.toLowerCase().includes(query)
      )
    }

    return result
  }, [projects, searchQuery, filter])

  // Count projects by mode
  const agentCount = projects.filter(p => p.creation_method === 'agent').length
  const workbenchCount = projects.filter(p => p.creation_method === 'workbench').length

  return (
    <div className="min-h-screen bg-black">
      {/* Subtle gradient background */}
      <div className="fixed inset-0 bg-gradient-to-br from-emerald-950/20 via-black to-cyan-950/10 pointer-events-none" />

      <div className="relative mx-auto flex w-full max-w-7xl flex-col gap-8 py-10 px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <header className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="h-10 w-1 rounded-full bg-gradient-to-b from-emerald-400 to-cyan-400" />
            <h1 className="font-heading text-3xl font-bold tracking-tight text-white">
              我的项目
            </h1>
            <Badge variant="secondary" className="text-xs bg-zinc-800 text-zinc-400 border-transparent">
              {projects.length}
            </Badge>
          </div>
          <p className="text-sm text-zinc-500 pl-6 ml-1">
            管理你的所有漫剧项目，包括 Agent 模式和工作台模式。
          </p>
        </header>

        {/* Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* Mode Filter */}
          <div className="flex rounded-lg border border-zinc-800 p-0.5 bg-zinc-900/50">
            <Button
              variant="ghost"
              size="sm"
              className={cn(
                'rounded-md px-3 text-xs',
                filter === 'all' ? 'bg-zinc-800 text-white' : 'text-zinc-500 hover:text-white'
              )}
              onClick={() => setFilter('all')}
            >
              全部 <span className="ml-1 text-zinc-500">{projects.length}</span>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className={cn(
                'rounded-md px-3 text-xs',
                filter === 'agent' ? 'bg-zinc-800 text-emerald-400' : 'text-zinc-500 hover:text-white'
              )}
              onClick={() => setFilter('agent')}
            >
              <Bot className="mr-1 h-3 w-3" />
              Agent <span className="ml-1 text-zinc-500">{agentCount}</span>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className={cn(
                'rounded-md px-3 text-xs',
                filter === 'workbench' ? 'bg-zinc-800 text-blue-400' : 'text-zinc-500 hover:text-white'
              )}
              onClick={() => setFilter('workbench')}
            >
              <HardHat className="mr-1 h-3 w-3" />
              工作台 <span className="ml-1 text-zinc-500">{workbenchCount}</span>
            </Button>
          </div>

          {/* Right side tools */}
          <div className="flex items-center gap-2">
            {/* Search Input */}
            <div className="relative w-56">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
              <Input
                placeholder="搜索项目..."
                className="pl-9 bg-zinc-900/50 border-zinc-800 focus:border-emerald-600 focus:ring-emerald-500/20 text-sm"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            {/* View Mode Toggle */}
            <div className="flex rounded-lg border border-zinc-800 p-0.5 bg-zinc-900/50">
              <Button
                variant="ghost"
                size="icon"
                className={cn(
                  'h-8 w-8 rounded-md',
                  viewMode === 'grid' ? 'bg-zinc-800 text-white' : 'text-zinc-500 hover:text-white'
                )}
                onClick={() => setViewMode('grid')}
              >
                <LayoutGrid className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className={cn(
                  'h-8 w-8 rounded-md',
                  viewMode === 'list' ? 'bg-zinc-800 text-white' : 'text-zinc-500 hover:text-white'
                )}
                onClick={() => setViewMode('list')}
              >
                <List className="h-4 w-4" />
              </Button>
            </div>
            {/* Refresh Button */}
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-zinc-500 hover:text-white"
              onClick={fetchProjects}
              disabled={loading}
            >
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
            </Button>
            {/* New Project Button */}
            <Link href="/">
              <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white">
                <Plus className="mr-1 h-4 w-4" />
                新建项目
              </Button>
            </Link>
          </div>
        </div>

        {/* Project Grid/List */}
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-emerald-500" />
            <span className="text-sm text-zinc-500">加载项目中...</span>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-20 gap-4 rounded-xl bg-zinc-900/50 border border-zinc-800">
            <div className="p-4 rounded-full bg-red-500/10">
              <span className="text-2xl">⚠️</span>
            </div>
            <p className="text-red-400 text-sm">{error}</p>
            <Button variant="outline" size="sm" onClick={fetchProjects}>
              <RefreshCw className="h-4 w-4 mr-2" />
              重试
            </Button>
          </div>
        ) : filteredProjects.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 gap-4 rounded-xl bg-zinc-900/30 border border-dashed border-zinc-800">
            <div className="p-4 rounded-full bg-zinc-800/50">
              <Folder className="h-8 w-8 text-zinc-600" />
            </div>
            <div className="text-center">
              <p className="text-zinc-400 mb-1">
                {searchQuery ? '没有找到匹配的项目' : filter !== 'all' ? `没有${filter === 'agent' ? 'Agent' : '工作台'}模式的项目` : '还没有项目'}
              </p>
              <p className="text-xs text-zinc-600">
                {searchQuery ? '尝试其他搜索词' : '在灵感广场创建 Agent 项目，或在生产项目中创建工作台项目'}
              </p>
            </div>
          </div>
        ) : (
          <div className={cn(
            'grid gap-4',
            viewMode === 'grid'
              ? 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4'
              : 'grid-cols-1'
          )}>
            {filteredProjects.map((p) => (
              <ProjectCard
                key={p.id}
                project={p}
                onDelete={(id) => setProjects(prev => prev.filter(proj => proj.id !== id))}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
