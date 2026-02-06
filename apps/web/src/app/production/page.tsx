'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import {
  Plus, Loader2, RefreshCw, ArrowRight, Bot, HardHat, Book, Zap, Folder,
  Search, LayoutGrid, List, Sparkles, Film
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { projectsApi, chaptersApi, type Project } from '@/lib/api'
import { Badge } from '@/components/ui/badge'

// Project Card with enhanced visuals
function ProjectCard({ project }: { project: Project }) {
  const isAgentProject = project.creation_method === 'agent';
  const href = isAgentProject ? `/agent/${project.id}` : `/projects/${project.id}`;

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-';
    try {
      return new Date(dateStr).toLocaleDateString('zh-CN');
    } catch {
      return dateStr;
    }
  };

  return (
    <Link href={href} className="block group">
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
  )
}

// Action Card with enhanced visuals
function ActionCard({
  icon: Icon,
  title,
  description,
  onClick,
  gradient = 'from-emerald-500/20 to-cyan-500/10',
  iconColor = 'text-emerald-400'
}: {
  icon: any;
  title: string;
  description: string;
  onClick?: () => void;
  gradient?: string;
  iconColor?: string;
}) {
  return (
    <Card
      onClick={onClick}
      className={cn(
        'group relative cursor-pointer overflow-hidden transition-all duration-300',
        'bg-gradient-to-br from-zinc-900/80 to-zinc-950/90',
        'border border-zinc-800/50 backdrop-blur-sm',
        'hover:-translate-y-1 hover:shadow-xl hover:shadow-emerald-500/10',
        'hover:border-zinc-700'
      )}
    >
      {/* Gradient background overlay on hover */}
      <div className={cn(
        'absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500',
        `bg-gradient-to-br ${gradient}`
      )} />

      <CardHeader className="relative flex flex-row items-center gap-4 space-y-0">
        <div className={cn(
          'p-3 rounded-xl transition-all duration-300',
          'bg-zinc-800/50 group-hover:bg-zinc-800',
          iconColor
        )}>
          <Icon className="h-6 w-6" />
        </div>
        <div className="flex-1">
          <CardTitle className="text-base font-semibold text-zinc-100 group-hover:text-white transition-colors">
            {title}
          </CardTitle>
          <CardDescription className="mt-1 text-xs text-zinc-500 group-hover:text-zinc-400 transition-colors">
            {description}
          </CardDescription>
        </div>
        <ArrowRight className="h-4 w-4 text-zinc-600 opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300" />
      </CardHeader>
    </Card>
  )
}

export default function ProductionHubPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isCreateOpen, setCreateOpen] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const router = useRouter()

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

  // Filter projects: only show workbench projects, then apply search query
  const filteredProjects = useMemo(() => {
    // Only show workbench mode projects in production page
    const workbenchProjects = projects.filter(p => p.creation_method === 'workbench');

    if (!searchQuery.trim()) return workbenchProjects;
    const query = searchQuery.toLowerCase();
    return workbenchProjects.filter(p =>
      p.name?.toLowerCase().includes(query) ||
      p.description?.toLowerCase().includes(query)
    );
  }, [projects, searchQuery])

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) return;
    setIsCreating(true);
    try {
      const newProject = await projectsApi.create({
        name: newProjectName,
        creation_method: 'workbench',
      });
      setCreateOpen(false);
      setNewProjectName('');
      const newChapter = await chaptersApi.create({
        project_id: newProject.id,
        title: '第一章',
      });
      router.push(`/projects/${newProject.id}/chapters/${newChapter.id}/studio`);
    } catch (error) {
      console.error('Failed to create workbench project:', error);
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <div className="min-h-screen bg-black">
      {/* Subtle gradient background */}
      <div className="fixed inset-0 bg-gradient-to-br from-emerald-950/20 via-black to-cyan-950/10 pointer-events-none" />

      <div className="relative mx-auto flex w-full max-w-7xl flex-col gap-10 py-10 px-4 sm:px-6 lg:px-8">
        {/* Header with enhanced styling */}
        <header className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="h-10 w-1 rounded-full bg-gradient-to-b from-emerald-400 to-cyan-400" />
            <h1 className="font-heading text-3xl font-bold tracking-tight text-white">
              欢迎回来，创作者
            </h1>
            <Sparkles className="h-5 w-5 text-amber-400 animate-pulse" />
          </div>
          <p className="text-sm text-zinc-500 pl-6 ml-1">
            继续你的漫剧创作之旅，或开始一个新项目。
          </p>
        </header>

        <main className="space-y-12">
          {/* Quick Actions Section */}
          <section>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <ActionCard
                icon={Plus}
                title="新建项目"
                description="从零开始创建你的漫剧"
                onClick={() => setCreateOpen(true)}
                gradient="from-emerald-500/20 to-cyan-500/10"
                iconColor="text-emerald-400"
              />
              <ActionCard
                icon={Book}
                title="快速教程"
                description="5分钟学会使用工作台"
                gradient="from-blue-500/20 to-violet-500/10"
                iconColor="text-blue-400"
              />
              <ActionCard
                icon={Zap}
                title="模板库"
                description="浏览预设模板快速开始"
                gradient="from-amber-500/20 to-orange-500/10"
                iconColor="text-amber-400"
              />
            </div>
          </section>

          {/* Projects Section */}
          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold text-zinc-100 flex items-center gap-2">
                <span>我的项目</span>
                {!loading && (
                  <Badge variant="secondary" className="text-xs bg-zinc-800 text-zinc-400 border-transparent">
                    {filteredProjects.length}
                  </Badge>
                )}
              </h2>
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
                    {searchQuery ? '没有找到匹配的项目' : '还没有项目'}
                  </p>
                  <p className="text-xs text-zinc-600">
                    {searchQuery ? '尝试其他搜索词' : '点击"新建项目"开始创作'}
                  </p>
                </div>
                {!searchQuery && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCreateOpen(true)}
                    className="mt-2"
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    新建项目
                  </Button>
                )}
              </div>
            ) : (
              <div className={cn(
                'grid gap-4',
                viewMode === 'grid'
                  ? 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4'
                  : 'grid-cols-1'
              )}>
                {filteredProjects.map((p) => <ProjectCard key={p.id} project={p} />)}
              </div>
            )}
          </section>
        </main>

        {/* Create Project Dialog */}
        <Dialog open={isCreateOpen} onOpenChange={setCreateOpen}>
          <DialogContent className="bg-zinc-950 border-zinc-800 sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-zinc-100">
                <Plus className="h-5 w-5 text-emerald-400" />
                新建工作台项目
              </DialogTitle>
            </DialogHeader>
            <div className="py-4">
              <Input
                placeholder="输入项目名称..."
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                className="bg-zinc-900 border-zinc-800 focus:border-emerald-600 focus:ring-emerald-500/20"
                onKeyDown={(e) => e.key === 'Enter' && handleCreateProject()}
              />
            </div>
            <DialogFooter className="gap-2">
              <Button
                variant="ghost"
                onClick={() => setCreateOpen(false)}
                className="text-zinc-400 hover:text-white"
              >
                取消
              </Button>
              <Button
                onClick={handleCreateProject}
                disabled={isCreating || !newProjectName.trim()}
                className="bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                {isCreating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                创建项目
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  )
}
