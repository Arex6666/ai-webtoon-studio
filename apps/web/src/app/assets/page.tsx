'use client'

import { useEffect, useState, useMemo } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
    Plus, Search, Users, MapPin, Package,
    MoreHorizontal, Pencil, Trash2, RefreshCw,
    Loader2, Image as ImageIcon, Sparkles
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { assetsApi, projectsApi, type Asset, type Project } from '@/lib/api'
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { AssetEditDrawer } from '@/components/assets/AssetEditDrawer'
import { AssetSourceBadge } from '@/components/assets/AssetSourceBadge'

// 资产类型配置
const ASSET_TYPES = {
    character: {
        label: '人物',
        icon: Users,
        gradient: 'from-emerald-500 to-teal-600',
        description: '角色设定',
    },
    scene: {
        label: '场景',
        icon: MapPin,
        gradient: 'from-blue-500 to-cyan-600',
        description: '背景/环境',
    },
    prop: {
        label: '物品',
        icon: Package,
        gradient: 'from-amber-500 to-orange-600',
        description: '道具/陈设',
    },
} as const

type AssetType = keyof typeof ASSET_TYPES

// 资产卡片组件
function AssetCard({
    asset,
    onEdit,
    onDelete,
    onRegenerate
}: {
    asset: Asset
    onEdit: () => void
    onDelete: () => void
    onRegenerate: () => void
}) {
    const typeConfig = ASSET_TYPES[asset.type as AssetType] || ASSET_TYPES.prop
    const TypeIcon = typeConfig.icon

    return (
        <Card className={cn(
            "group relative overflow-hidden cursor-pointer transition-all duration-300",
            "bg-slate-900/40",
            "border border-slate-800/60 backdrop-blur-sm",
            "hover:border-emerald-500/30 hover:bg-slate-800/60",
            "hover:-translate-y-1"
        )}>
            {/* Thumbnail */}
            <div className="aspect-square relative overflow-hidden bg-slate-900/50">
                {asset.thumbnail_url ? (
                    <img
                        src={asset.thumbnail_url}
                        alt={asset.name}
                        className="w-full h-full object-cover"
                    />
                ) : (
                    <div className="w-full h-full flex items-center justify-center">
                        <div className={cn(
                            "w-16 h-16 rounded-2xl flex items-center justify-center",
                            `bg-gradient-to-br ${typeConfig.gradient}/20`
                        )}>
                            <TypeIcon className={cn("w-8 h-8", `text-${typeConfig.gradient.split('-')[1]}-400`)} />
                        </div>
                    </div>
                )}

                {/* Type badge */}
                <div className="absolute top-2 left-2">
                    <Badge className={cn(
                        "text-[10px] px-2 py-0.5 rounded-md border-0",
                        `bg-gradient-to-r ${typeConfig.gradient} text-white shadow-lg`
                    )}>
                        <TypeIcon className="w-3 h-3 mr-1" />
                        {typeConfig.label}
                    </Badge>
                </div>

                {/* Actions on hover */}
                <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button
                                size="icon"
                                variant="ghost"
                                className="h-7 w-7 bg-black/50 backdrop-blur-sm hover:bg-black/70"
                            >
                                <MoreHorizontal className="w-4 h-4" />
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="bg-zinc-900 border-zinc-800">
                            <DropdownMenuItem onClick={onEdit} className="gap-2">
                                <Pencil className="w-4 h-4" />
                                编辑
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={onRegenerate} className="gap-2">
                                <RefreshCw className="w-4 h-4" />
                                重新生成
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={onDelete} className="gap-2 text-red-400 focus:text-red-400">
                                <Trash2 className="w-4 h-4" />
                                删除
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                </div>
            </div>

            {/* Content */}
            <CardContent className="p-3 space-y-1.5">
                <div className="flex items-center gap-1.5 min-w-0">
                    <h3 className="font-medium text-sm text-foreground/90 line-clamp-1 flex-1 min-w-0">
                        {asset.name}
                    </h3>
                    <AssetSourceBadge
                        createdVia={(asset as any).data_json?.created_via}
                        sourceConversationId={(asset as any).data_json?.source_conversation_id}
                        size="sm"
                    />
                </div>
                {asset.description && (
                    <p className="text-xs text-muted-foreground line-clamp-2">
                        {asset.description}
                    </p>
                )}
                {/* Tags */}
                {asset.tags && asset.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 pt-1">
                        {asset.tags.slice(0, 3).map((tag, i) => (
                            <span
                                key={i}
                                className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-muted-foreground"
                            >
                                {tag}
                            </span>
                        ))}
                        {asset.tags.length > 3 && (
                            <span className="text-[10px] text-muted-foreground">
                                +{asset.tags.length - 3}
                            </span>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

// 创建资产弹窗
function CreateAssetModal({
    open,
    onOpenChange,
    projects,
    onCreated,
}: {
    open: boolean
    onOpenChange: (open: boolean) => void
    projects: Project[]
    onCreated: () => void
}) {
    const [loading, setLoading] = useState(false)
    const [form, setForm] = useState({
        project_id: '',
        name: '',
        type: 'character' as AssetType,
        description: '',
    })

    const handleCreate = async () => {
        if (!form.project_id || !form.name) return

        setLoading(true)
        try {
            await assetsApi.create({
                project_id: form.project_id,
                name: form.name,
                type: form.type,
                description: form.description || undefined,
            })
            onCreated()
            onOpenChange(false)
            setForm({ project_id: '', name: '', type: 'character', description: '' })
        } catch (error) {
            console.error('Failed to create asset:', error)
        } finally {
            setLoading(false)
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="bg-zinc-900 border-zinc-800">
                <DialogHeader>
                    <DialogTitle>创建新资产</DialogTitle>
                    <DialogDescription>
                        为项目添加人物、场景或物品资产
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    {/* Project select */}
                    <div className="space-y-2">
                        <Label>所属项目</Label>
                        <Select
                            value={form.project_id}
                            onValueChange={(v) => setForm({ ...form, project_id: v })}
                        >
                            <SelectTrigger className="bg-zinc-800 border-zinc-700">
                                <SelectValue placeholder="选择项目" />
                            </SelectTrigger>
                            <SelectContent className="bg-zinc-900 border-zinc-800">
                                {projects.map((p) => (
                                    <SelectItem key={p.id} value={p.id}>
                                        {p.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Type select */}
                    <div className="space-y-2">
                        <Label>资产类型</Label>
                        <div className="grid grid-cols-3 gap-2">
                            {(Object.keys(ASSET_TYPES) as AssetType[]).map((type) => {
                                const config = ASSET_TYPES[type]
                                const Icon = config.icon
                                return (
                                    <button
                                        key={type}
                                        onClick={() => setForm({ ...form, type })}
                                        className={cn(
                                            "flex flex-col items-center gap-2 p-3 rounded-lg border transition-all",
                                            form.type === type
                                                ? `bg-gradient-to-br ${config.gradient}/20 border-${config.gradient.split('-')[1]}-500/50`
                                                : "bg-zinc-800/50 border-zinc-700 hover:border-zinc-600"
                                        )}
                                    >
                                        <Icon className="w-5 h-5" />
                                        <span className="text-xs font-medium">{config.label}</span>
                                    </button>
                                )
                            })}
                        </div>
                    </div>

                    {/* Name */}
                    <div className="space-y-2">
                        <Label>名称</Label>
                        <Input
                            value={form.name}
                            onChange={(e) => setForm({ ...form, name: e.target.value })}
                            placeholder="输入资产名称"
                            className="bg-zinc-800 border-zinc-700"
                        />
                    </div>

                    {/* Description */}
                    <div className="space-y-2">
                        <Label>描述（可选）</Label>
                        <Textarea
                            value={form.description}
                            onChange={(e) => setForm({ ...form, description: e.target.value })}
                            placeholder="简要描述资产特征..."
                            className="bg-zinc-800 border-zinc-700 resize-none"
                            rows={3}
                        />
                    </div>
                </div>

                <DialogFooter>
                    <Button
                        variant="outline"
                        onClick={() => onOpenChange(false)}
                        className="border-zinc-700"
                    >
                        取消
                    </Button>
                    <Button
                        onClick={handleCreate}
                        disabled={loading || !form.project_id || !form.name}
                        className="bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500"
                    >
                        {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                        创建
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

// 空状态组件
function EmptyState({ type }: { type: AssetType }) {
    const config = ASSET_TYPES[type]
    const Icon = config.icon

    return (
        <div className="flex flex-col items-center justify-center py-16 text-center">
            {/* Decorative orbs */}
            <div className="relative">
                <div className="absolute -top-10 -right-10 w-32 h-32 bg-emerald-500/5 rounded-full blur-3xl" />
                <div className="absolute -bottom-5 -left-10 w-24 h-24 bg-teal-500/5 rounded-full blur-2xl" />

                {/* Icon */}
                <div className={cn(
                    "relative w-20 h-20 rounded-2xl flex items-center justify-center",
                    `bg-gradient-to-br ${config.gradient}/20 border border-${config.gradient.split('-')[1]}-500/10`
                )}>
                    <Icon className="w-9 h-9 text-slate-500" />
                </div>
            </div>

            <h3 className="mt-6 text-lg font-semibold text-foreground/90">
                暂无{config.label}资产
            </h3>
            <p className="mt-2 text-sm text-muted-foreground max-w-sm">
                点击右上角「新建资产」按钮，添加你的第一个{config.label}资产。
            </p>
        </div>
    )
}

// 主页面
export default function AssetsPage() {
    const [assets, setAssets] = useState<Asset[]>([])
    const [projects, setProjects] = useState<Project[]>([])
    const [loading, setLoading] = useState(true)
    const [activeTab, setActiveTab] = useState<AssetType>('character')
    const [searchQuery, setSearchQuery] = useState('')
    const [selectedProject, setSelectedProject] = useState<string>('all')
    const [showCreateModal, setShowCreateModal] = useState(false)
    const [editingAssetId, setEditingAssetId] = useState<string | null>(null)

    // 加载项目列表和资产
    const loadData = async () => {
        setLoading(true)
        try {
            // 先加载项目列表
            const projectsRes = await projectsApi.list()
            const projectList = projectsRes.items || []
            setProjects(projectList)

            // 如果有项目，加载所有项目的资产
            if (projectList.length > 0) {
                const allAssets: Asset[] = []
                for (const project of projectList) {
                    try {
                        const assetsRes = await assetsApi.list(project.id)
                        if (assetsRes.items) {
                            allAssets.push(...assetsRes.items)
                        }
                    } catch (e) {
                        console.warn(`Failed to load assets for project ${project.id}`, e)
                    }
                }
                setAssets(allAssets)
            }
        } catch (error) {
            console.error('Failed to load data:', error)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        loadData()
    }, [])

    // 过滤资产
    const filteredAssets = useMemo(() => {
        return assets.filter((asset) => {
            // 类型过滤
            if (asset.type !== activeTab) return false

            // 项目过滤
            if (selectedProject !== 'all' && asset.project_id !== selectedProject) return false

            // 搜索过滤
            if (searchQuery) {
                const query = searchQuery.toLowerCase()
                const matchName = asset.name.toLowerCase().includes(query)
                const matchDesc = asset.description?.toLowerCase().includes(query)
                const matchTags = asset.tags?.some(t => t.toLowerCase().includes(query))
                if (!matchName && !matchDesc && !matchTags) return false
            }

            return true
        })
    }, [assets, activeTab, selectedProject, searchQuery])

    // 删除资产
    const handleDelete = async (assetId: string) => {
        if (!confirm('确定要删除这个资产吗？')) return
        try {
            await assetsApi.delete(assetId)
            setAssets(assets.filter(a => a.id !== assetId))
        } catch (error) {
            console.error('Failed to delete asset:', error)
        }
    }

    // 重新生成参考图（角色/场景统一走 generate-image）
    const handleRegenerate = async (assetId: string) => {
        try {
            // 后端会根据 asset.type 自动生成角色定妆照或场景空镜图
            await assetsApi.generateImage(assetId)
            loadData()
        } catch (error) {
            console.error('Failed to regenerate:', error)
        }
    }

    return (
        <div className="min-h-screen bg-canvas p-6">
            <div className="max-w-7xl mx-auto space-y-6">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-foreground">资产库</h1>
                        <p className="text-sm text-muted-foreground mt-1">
                            管理项目中的人物、场景和物品资产
                        </p>
                    </div>
                    <Button
                        onClick={() => setShowCreateModal(true)}
                        className="bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500 gap-2"
                    >
                        <Plus className="w-4 h-4" />
                        新建资产
                    </Button>
                </div>

                {/* Tabs and filters */}
                <div className="flex items-center justify-between gap-4 flex-wrap">
                    <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as AssetType)}>
                        <TabsList className="bg-zinc-900/50 border border-white/5">
                            {(Object.keys(ASSET_TYPES) as AssetType[]).map((type) => {
                                const config = ASSET_TYPES[type]
                                const Icon = config.icon
                                const count = assets.filter(a => a.type === type).length
                                return (
                                    <TabsTrigger
                                        key={type}
                                        value={type}
                                        className={cn(
                                            "gap-2 data-[state=active]:bg-gradient-to-r",
                                            `data-[state=active]:${config.gradient}`,
                                            "data-[state=active]:text-white"
                                        )}
                                    >
                                        <Icon className="w-4 h-4" />
                                        {config.label}
                                        <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-xs">
                                            {count}
                                        </Badge>
                                    </TabsTrigger>
                                )
                            })}
                        </TabsList>
                    </Tabs>

                    <div className="flex items-center gap-3">
                        {/* Project filter */}
                        <Select value={selectedProject} onValueChange={setSelectedProject}>
                            <SelectTrigger className="w-[180px] bg-zinc-900/50 border-white/5">
                                <SelectValue placeholder="所有项目" />
                            </SelectTrigger>
                            <SelectContent className="bg-zinc-900 border-zinc-800">
                                <SelectItem value="all">所有项目</SelectItem>
                                {projects.map((p) => (
                                    <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>

                        {/* Search */}
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                            <Input
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                placeholder="搜索资产..."
                                className="w-[200px] pl-9 bg-zinc-900/50 border-white/5"
                            />
                        </div>
                    </div>
                </div>

                {/* Assets grid */}
                {loading ? (
                    <div className="flex items-center justify-center py-20">
                        <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
                    </div>
                ) : filteredAssets.length === 0 ? (
                    <EmptyState type={activeTab} />
                ) : (
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                        {filteredAssets.map((asset) => (
                            <AssetCard
                                key={asset.id}
                                asset={asset}
                                onEdit={() => setEditingAssetId(asset.id)}
                                onDelete={() => handleDelete(asset.id)}
                                onRegenerate={() => handleRegenerate(asset.id)}
                            />
                        ))}
                    </div>
                )}
            </div>

            {/* Create modal */}
            <CreateAssetModal
                open={showCreateModal}
                onOpenChange={setShowCreateModal}
                projects={projects}
                onCreated={loadData}
            />

            <AssetEditDrawer
                assetId={editingAssetId}
                onClose={() => setEditingAssetId(null)}
                onSaved={() => { loadData() }}
            />
        </div>
    )
}
