'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
    DropdownMenu, DropdownMenuContent, DropdownMenuItem,
    DropdownMenuTrigger, DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ChevronDown, Plus, Search } from 'lucide-react'
import { projectsApi } from '@/lib/api/services'
import type { Project } from '@/lib/api/types'

export interface ChatProjectPickerProps {
    currentProjectId: string
    onCreateNew?: () => void
}

export function ChatProjectPicker({ currentProjectId, onCreateNew }: ChatProjectPickerProps) {
    const router = useRouter()
    const [projects, setProjects] = useState<Project[]>([])
    const [open, setOpen] = useState(false)
    const [query, setQuery] = useState('')

    useEffect(() => {
        if (!open) return
        projectsApi.list?.().then((data: any) => {
            const items = Array.isArray(data) ? data : (data?.items ?? [])
            setProjects(items)
        }).catch(() => {})
    }, [open])

    const current = projects.find(p => p.id === currentProjectId)
    const filtered = useMemo(() => {
        const q = query.trim().toLowerCase()
        if (!q) return projects
        return projects.filter(p => p.name.toLowerCase().includes(q))
    }, [projects, query])

    return (
        <DropdownMenu open={open} onOpenChange={setOpen}>
            <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="gap-2">
                    <span className="truncate max-w-[200px]">{current?.name ?? '选择项目'}</span>
                    <ChevronDown className="w-4 h-4" />
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-[280px]">
                <div className="p-2">
                    <div className="relative">
                        <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                        <Input
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder="搜索项目…"
                            className="pl-8"
                            aria-label="搜索项目"
                        />
                    </div>
                </div>
                <DropdownMenuSeparator />
                <div className="max-h-[320px] overflow-y-auto">
                    {filtered.length === 0 ? (
                        <div className="px-3 py-6 text-center text-sm text-muted-foreground">
                            {query ? '无匹配项目' : '还没有项目'}
                        </div>
                    ) : filtered.map(p => (
                        <DropdownMenuItem
                            key={p.id}
                            onSelect={() => { setOpen(false); router.push(`/chat/${p.id}`) }}
                            className={p.id === currentProjectId ? 'bg-accent' : ''}
                        >
                            <div className="flex flex-col gap-0.5 min-w-0">
                                <span className="truncate text-sm">{p.name}</span>
                                {p.description ? (
                                    <span className="truncate text-xs text-muted-foreground">{p.description}</span>
                                ) : null}
                            </div>
                        </DropdownMenuItem>
                    ))}
                </div>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={onCreateNew ?? (() => router.push('/projects?create=1'))}>
                    <Plus className="w-4 h-4 mr-2" />
                    新建项目
                </DropdownMenuItem>
            </DropdownMenuContent>
        </DropdownMenu>
    )
}
