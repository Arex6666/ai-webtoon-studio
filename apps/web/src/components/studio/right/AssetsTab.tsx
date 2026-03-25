'use client'

import { useState, useEffect } from 'react'
import { useStudioStore } from '@/lib/store/studioStore'
import { useShallow } from 'zustand/react/shallow'
import { chaptersApi, assetsApi, sceneAnchorApi } from '@/lib/api/services'
import { useToast } from '@/hooks/use-toast'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
import {
    User,
    Map,
    Palette,
    Check,
    AlertTriangle,
    AlertCircle,
    Loader2,
    RefreshCw,
    Link,
    HelpCircle,
    Wand2,
    ImagePlus,
    Box,
    Layers,
    Pencil,
    CheckCircle,
    XCircle,
} from 'lucide-react'

// ─── types ───────────────────────────────────────────────────────────────────

type MatchType = 'exact' | 'fuzzy' | 'pending'

interface CharacterBinding {
    id: string
    name: string
    assetId?: string
    matchType: MatchType
    faceEmbeddingStatus?: 'none' | 'pending' | 'ready'
    thumbnailUrl?: string
}

interface SceneBinding {
    id: string
    name: string
    assetId?: string
    anchorStatus: 'none' | 'pending' | 'ready' | 'failed'
    hasDepth: boolean
    hasCanny: boolean
    hasLineart: boolean
}

interface ReadinessIssue {
    kind: 'error' | 'warning'
    message: string
}

// ─── sub-components ──────────────────────────────────────────────────────────

function MatchBadge({ matchType }: { matchType: MatchType }) {
    if (matchType === 'exact') {
        return (
            <Badge variant="outline" className="text-green-500 border-green-500/30 shrink-0">
                <Check className="w-3 h-3 mr-1" />
                精确匹配
            </Badge>
        )
    }
    if (matchType === 'fuzzy') {
        return (
            <Badge variant="outline" className="text-amber-500 border-amber-500/30 shrink-0">
                <HelpCircle className="w-3 h-3 mr-1" />
                需确认
            </Badge>
        )
    }
    return (
        <Badge variant="outline" className="text-red-500 border-red-500/30 shrink-0">
            <AlertCircle className="w-3 h-3 mr-1" />
            待绑定
        </Badge>
    )
}

function AnchorStatusBadge({ status }: { status: SceneBinding['anchorStatus'] }) {
    if (status === 'ready') {
        return (
            <Badge variant="outline" className="text-emerald-500 border-emerald-500/30 shrink-0">
                <CheckCircle className="w-3 h-3 mr-1" />
                已就绪
            </Badge>
        )
    }
    if (status === 'pending') {
        return (
            <Badge variant="outline" className="text-yellow-500 border-yellow-500/30 shrink-0">
                <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                处理中
            </Badge>
        )
    }
    if (status === 'failed') {
        return (
            <Badge variant="outline" className="text-red-500 border-red-500/30 shrink-0">
                <XCircle className="w-3 h-3 mr-1" />
                失败
            </Badge>
        )
    }
    return (
        <Badge variant="outline" className="text-muted-foreground shrink-0">
            未配置
        </Badge>
    )
}

function ControlMapBadge({
    label,
    icon: Icon,
    color,
    present,
}: {
    label: string
    icon: React.ElementType
    color: string
    present: boolean
}) {
    return (
        <span
            className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs border ${
                present
                    ? `${color} border-current/30 bg-current/5`
                    : 'text-muted-foreground border-white/10 opacity-50'
            }`}
        >
            <Icon className="w-3 h-3" />
            {label}
        </span>
    )
}

// ─── main component ───────────────────────────────────────────────────────────

export function AssetsTab() {
    const { chapterId, projectId, characters: storeCharacters, scenes: storeScenes } =
        useStudioStore(
            useShallow((s) => ({
                chapterId: s.chapterId,
                projectId: s.projectId,
                characters: s.characters,
                scenes: s.scenes,
            }))
        )

    const { toast } = useToast()

    // ── assets-lock data ──
    const [lockData, setLockData] = useState<{
        can_render: boolean
        stats: { locked_characters: number; locked_scenes: number; locked_styles: number; pending_count: number }
        characters: Record<string, { asset_id: string; name: string; face_embedding_path?: string }>
        scenes: Record<string, { asset_id: string; name: string }>
    } | null>(null)
    const [lockLoading, setLockLoading] = useState(true)
    const [lockRefreshing, setLockRefreshing] = useState(false)

    // ── anchor status per scene ──
    const [anchorStatuses, setAnchorStatuses] = useState<
        Record<string, { status: 'none' | 'pending' | 'ready' | 'failed'; has_depth: boolean; has_canny: boolean; has_lineart: boolean }>
    >({})
    const [regeneratingScene, setRegeneratingScene] = useState<string | null>(null)

    // ── bind dialog ──
    const [bindingTarget, setBindingTarget] = useState<{ id: string; name: string; type: 'character' | 'scene' } | null>(null)
    const [projectAssets, setProjectAssets] = useState<Array<{ id: string; name: string; thumbnail_url?: string }>>([])
    const [generatingImage, setGeneratingImage] = useState<string | null>(null)

    // ── load assets lock ──
    const loadLock = async () => {
        if (!chapterId) return
        try {
            const data = await chaptersApi.getAssetsLock(chapterId)
            setLockData(data as any)
        } catch (err) {
            console.error('Failed to load assets lock:', err)
        } finally {
            setLockLoading(false)
        }
    }

    // ── load anchor status for each scene ──
    const loadAnchorStatuses = async () => {
        const ids = storeScenes.map((s) => s.id)
        if (ids.length === 0) return
        const results = await Promise.allSettled(ids.map((id) => sceneAnchorApi.getStatus(id)))
        const next: typeof anchorStatuses = {}
        results.forEach((r, i) => {
            if (r.status === 'fulfilled') {
                const { status, has_depth, has_canny, has_lineart } = r.value
                next[ids[i]] = { status, has_depth, has_canny, has_lineart }
            }
        })
        setAnchorStatuses(next)
    }

    useEffect(() => {
        setLockLoading(true)
        loadLock()
    }, [chapterId])

    useEffect(() => {
        loadAnchorStatuses()
    }, [storeScenes])

    // ── open bind dialog ──
    useEffect(() => {
        if (!bindingTarget || !projectId) return
        assetsApi.list(projectId, bindingTarget.type).then((r) => setProjectAssets((r as any).items || []))
    }, [bindingTarget, projectId])

    const handleRefresh = async () => {
        setLockRefreshing(true)
        await loadLock()
        await loadAnchorStatuses()
        setLockRefreshing(false)
    }

    // ── regenerate ALL control maps for one scene ──
    const handleRegenerateControlMaps = async (sceneId: string) => {
        setRegeneratingScene(sceneId)
        try {
            await Promise.all([
                sceneAnchorApi.regenerateMap(sceneId, 'depth'),
                sceneAnchorApi.regenerateMap(sceneId, 'canny'),
                sceneAnchorApi.regenerateMap(sceneId, 'lineart'),
            ])
            toast({ title: '控制图重新生成中', description: 'Depth / Canny / Lineart 已提交重新生成' })
            await loadAnchorStatuses()
        } catch (err) {
            toast({ title: '重新生成失败', variant: 'destructive' })
        } finally {
            setRegeneratingScene(null)
        }
    }

    // ── derive character / scene binding lists ──
    const characterBindings: CharacterBinding[] = storeCharacters.map((c) => {
        const locked = lockData?.characters[c.id]
        return {
            id: c.id,
            name: c.name,
            assetId: locked?.asset_id,
            matchType: locked?.face_embedding_path ? 'exact' : locked ? 'fuzzy' : 'pending',
            faceEmbeddingStatus: c.face_embedding_status,
            thumbnailUrl: c.thumbnail_url,
        }
    })

    const sceneBindings: SceneBinding[] = storeScenes.map((s) => {
        const anchor = anchorStatuses[s.id]
        return {
            id: s.id,
            name: s.name,
            assetId: lockData?.scenes[s.id]?.asset_id,
            anchorStatus: anchor?.status ?? 'none',
            hasDepth: anchor?.has_depth ?? false,
            hasCanny: anchor?.has_canny ?? false,
            hasLineart: anchor?.has_lineart ?? false,
        }
    })

    // ── render readiness issues ──
    const readinessIssues: ReadinessIssue[] = []

    characterBindings
        .filter((c) => c.matchType !== 'exact')
        .forEach((c) => {
            readinessIssues.push({
                kind: c.matchType === 'pending' ? 'error' : 'warning',
                message:
                    c.matchType === 'pending'
                        ? `角色 "${c.name}" 未绑定资产`
                        : `角色 "${c.name}" 需手动确认绑定`,
            })
        })

    characterBindings
        .filter((c) => c.faceEmbeddingStatus && c.faceEmbeddingStatus !== 'ready')
        .forEach((c) => {
            readinessIssues.push({
                kind: c.faceEmbeddingStatus === 'pending' ? 'warning' : 'error',
                message:
                    c.faceEmbeddingStatus === 'pending'
                        ? `角色 "${c.name}" 人脸嵌入生成中`
                        : `角色 "${c.name}" 缺少人脸嵌入（FaceID）`,
            })
        })

    sceneBindings
        .filter((s) => s.anchorStatus !== 'ready')
        .forEach((s) => {
            readinessIssues.push({
                kind: s.anchorStatus === 'none' ? 'error' : 'warning',
                message:
                    s.anchorStatus === 'none'
                        ? `场景 "${s.name}" 缺少锚点控制图`
                        : s.anchorStatus === 'failed'
                        ? `场景 "${s.name}" 控制图生成失败`
                        : `场景 "${s.name}" 控制图处理中`,
            })
        })

    const canRender = lockData?.can_render ?? false

    // ─── empty state ───
    if (!chapterId) {
        return (
            <div className="h-full flex items-center justify-center text-muted-foreground p-4">
                <div className="text-center">
                    <User className="w-8 h-8 mx-auto mb-2 opacity-40" />
                    <p className="text-sm">请先打开一个章节</p>
                </div>
            </div>
        )
    }

    if (lockLoading) {
        return (
            <div className="h-full flex items-center justify-center p-8">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
        )
    }

    // ─── render ───
    return (
        <div className="flex flex-col h-full">
            {/* ── toolbar ── */}
            <div className="flex items-center justify-between px-3 py-2 border-b border-white/10 shrink-0">
                <h3 className="text-sm font-medium">资产绑定</h3>
                <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 w-6 p-0"
                    onClick={handleRefresh}
                    disabled={lockRefreshing}
                >
                    <RefreshCw className={`w-3 h-3 ${lockRefreshing ? 'animate-spin' : ''}`} />
                </Button>
            </div>

            <ScrollArea className="flex-1">
                <div className="p-3 space-y-5">

                    {/* ══ Section 1: Character Bindings ══ */}
                    <section className="space-y-2">
                        <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-medium uppercase tracking-wide">
                            <User className="w-3 h-3" />
                            角色绑定
                            <Badge variant="secondary" className="ml-auto text-xs px-1.5 py-0">
                                {characterBindings.length}
                            </Badge>
                        </div>

                        {characterBindings.length === 0 ? (
                            <div className="py-4 text-center text-muted-foreground border border-dashed border-white/10 rounded-lg">
                                <User className="w-6 h-6 mx-auto mb-1 opacity-40" />
                                <p className="text-xs">暂无角色资产</p>
                            </div>
                        ) : (
                            characterBindings.map((char) => (
                                <div
                                    key={char.id}
                                    className={`p-2.5 rounded-lg border transition-colors ${
                                        char.matchType === 'pending'
                                            ? 'border-red-500/30 bg-red-500/5'
                                            : char.matchType === 'fuzzy'
                                            ? 'border-amber-500/30 bg-amber-500/5'
                                            : 'border-white/10 bg-muted/5'
                                    }`}
                                >
                                    <div className="flex items-center gap-2">
                                        {/* avatar */}
                                        <div className="w-8 h-8 rounded-full bg-muted/30 overflow-hidden shrink-0 flex items-center justify-center">
                                            {char.thumbnailUrl ? (
                                                <img
                                                    src={char.thumbnailUrl}
                                                    alt={char.name}
                                                    className="w-full h-full object-cover"
                                                />
                                            ) : (
                                                <User className="w-4 h-4 opacity-30" />
                                            )}
                                        </div>

                                        {/* name + embedding status */}
                                        <div className="flex-1 min-w-0">
                                            <div className="text-sm font-medium truncate">{char.name}</div>
                                            {char.faceEmbeddingStatus && char.faceEmbeddingStatus !== 'ready' && (
                                                <div className="text-xs text-amber-500 flex items-center gap-0.5 mt-0.5">
                                                    {char.faceEmbeddingStatus === 'pending' ? (
                                                        <Loader2 className="w-2.5 h-2.5 animate-spin" />
                                                    ) : (
                                                        <AlertCircle className="w-2.5 h-2.5" />
                                                    )}
                                                    FaceID {char.faceEmbeddingStatus === 'pending' ? '生成中' : '缺失'}
                                                </div>
                                            )}
                                        </div>

                                        {/* binding badge + action */}
                                        <div className="flex items-center gap-1.5 shrink-0">
                                            <MatchBadge matchType={char.matchType} />
                                            {char.matchType !== 'exact' && (
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    className="h-6 px-2 text-xs"
                                                    onClick={() =>
                                                        setBindingTarget({
                                                            id: char.id,
                                                            name: char.name,
                                                            type: 'character',
                                                        })
                                                    }
                                                >
                                                    <Link className="w-3 h-3 mr-1" />
                                                    绑定
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            ))
                        )}
                    </section>

                    <Separator className="bg-white/5" />

                    {/* ══ Section 2: Scene Bindings ══ */}
                    <section className="space-y-2">
                        <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-medium uppercase tracking-wide">
                            <Map className="w-3 h-3" />
                            场景绑定
                            <Badge variant="secondary" className="ml-auto text-xs px-1.5 py-0">
                                {sceneBindings.length}
                            </Badge>
                        </div>

                        {sceneBindings.length === 0 ? (
                            <div className="py-4 text-center text-muted-foreground border border-dashed border-white/10 rounded-lg">
                                <Map className="w-6 h-6 mx-auto mb-1 opacity-40" />
                                <p className="text-xs">暂无场景资产</p>
                                <p className="text-xs mt-0.5 opacity-70">运行 AI 分镜后自动提取场景</p>
                            </div>
                        ) : (
                            sceneBindings.map((scene) => (
                                <div
                                    key={scene.id}
                                    className={`p-2.5 rounded-lg border transition-colors ${
                                        scene.anchorStatus === 'none' || scene.anchorStatus === 'failed'
                                            ? 'border-red-500/30 bg-red-500/5'
                                            : scene.anchorStatus === 'pending'
                                            ? 'border-amber-500/30 bg-amber-500/5'
                                            : 'border-white/10 bg-muted/5'
                                    }`}
                                >
                                    {/* header row */}
                                    <div className="flex items-center gap-2 mb-2">
                                        <div className="w-8 h-8 rounded-full bg-muted/30 flex items-center justify-center shrink-0">
                                            <Map className="w-4 h-4 opacity-40" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="text-sm font-medium truncate">{scene.name}</div>
                                        </div>
                                        <AnchorStatusBadge status={scene.anchorStatus} />
                                    </div>

                                    {/* control map badges */}
                                    <div className="flex items-center gap-1.5 flex-wrap">
                                        <ControlMapBadge
                                            label="Depth"
                                            icon={Box}
                                            color="text-blue-400"
                                            present={scene.hasDepth}
                                        />
                                        <ControlMapBadge
                                            label="Canny"
                                            icon={Layers}
                                            color="text-green-400"
                                            present={scene.hasCanny}
                                        />
                                        <ControlMapBadge
                                            label="Lineart"
                                            icon={Pencil}
                                            color="text-purple-400"
                                            present={scene.hasLineart}
                                        />

                                        <Button
                                            size="sm"
                                            variant="ghost"
                                            className="h-5 px-1.5 text-xs ml-auto"
                                            disabled={regeneratingScene === scene.id}
                                            onClick={() => handleRegenerateControlMaps(scene.id)}
                                        >
                                            {regeneratingScene === scene.id ? (
                                                <Loader2 className="w-3 h-3 animate-spin" />
                                            ) : (
                                                <RefreshCw className="w-3 h-3" />
                                            )}
                                            <span className="ml-1">重新生成控制图</span>
                                        </Button>
                                    </div>
                                </div>
                            ))
                        )}
                    </section>

                    <Separator className="bg-white/5" />

                    {/* ══ Section 3: Render Readiness ══ */}
                    <section className="space-y-2">
                        <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-medium uppercase tracking-wide">
                            <Palette className="w-3 h-3" />
                            渲染就绪状态
                        </div>

                        {/* overall banner */}
                        <div
                            className={`flex items-center gap-2 p-2.5 rounded-lg border ${
                                canRender
                                    ? 'bg-green-500/10 border-green-500/30 text-green-400'
                                    : 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                            }`}
                        >
                            {canRender ? (
                                <CheckCircle className="w-4 h-4 shrink-0" />
                            ) : (
                                <AlertTriangle className="w-4 h-4 shrink-0" />
                            )}
                            <span className="text-sm">
                                {canRender
                                    ? '所有资产已就绪，可以渲染'
                                    : `${readinessIssues.filter((i) => i.kind === 'error').length} 个阻断项 · ${readinessIssues.filter((i) => i.kind === 'warning').length} 个警告`}
                            </span>
                        </div>

                        {/* stats row */}
                        {lockData && (
                            <div className="flex items-center gap-3 text-xs text-muted-foreground px-0.5">
                                <span className="flex items-center gap-1">
                                    <User className="w-3 h-3" />
                                    {lockData.stats.locked_characters} 角色
                                </span>
                                <span className="flex items-center gap-1">
                                    <Map className="w-3 h-3" />
                                    {lockData.stats.locked_scenes} 场景
                                </span>
                                <span className="flex items-center gap-1">
                                    <Palette className="w-3 h-3" />
                                    {lockData.stats.locked_styles} 风格
                                </span>
                            </div>
                        )}

                        {/* issue list */}
                        {readinessIssues.length > 0 && (
                            <div className="space-y-1">
                                {readinessIssues.map((issue, i) => (
                                    <div
                                        key={i}
                                        className={`flex items-start gap-2 px-2.5 py-1.5 rounded text-xs border ${
                                            issue.kind === 'error'
                                                ? 'border-red-500/30 bg-red-500/5 text-red-400'
                                                : 'border-amber-500/30 bg-amber-500/5 text-amber-400'
                                        }`}
                                    >
                                        {issue.kind === 'error' ? (
                                            <XCircle className="w-3 h-3 mt-0.5 shrink-0" />
                                        ) : (
                                            <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
                                        )}
                                        {issue.message}
                                    </div>
                                ))}
                            </div>
                        )}

                        {readinessIssues.length === 0 && (
                            <p className="text-xs text-muted-foreground text-center py-1">
                                没有阻断项
                            </p>
                        )}
                    </section>
                </div>
            </ScrollArea>

            {/* ── bind asset dialog ── */}
            <Dialog open={!!bindingTarget} onOpenChange={() => setBindingTarget(null)}>
                <DialogContent className="max-w-md">
                    <DialogHeader>
                        <DialogTitle>资产绑定</DialogTitle>
                        <DialogDescription>
                            为 "{bindingTarget?.name}" 选择资产库中的对应项，或生成新的参考图
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-2 max-h-60 overflow-y-auto">
                        {projectAssets.length > 0 ? (
                            projectAssets.map((asset) => (
                                <div
                                    key={asset.id}
                                    className="flex items-center justify-between p-3 rounded-lg border border-white/10 hover:border-primary/50 cursor-pointer transition-colors"
                                    onClick={() => {
                                        // TODO: call bind API once backend endpoint is available
                                        console.log(`Bind ${bindingTarget?.id} → asset ${asset.id}`)
                                        setBindingTarget(null)
                                    }}
                                >
                                    <div className="flex items-center gap-3">
                                        {asset.thumbnail_url ? (
                                            <img
                                                src={asset.thumbnail_url}
                                                alt={asset.name}
                                                className="w-10 h-10 rounded object-cover"
                                            />
                                        ) : (
                                            <div className="w-10 h-10 rounded bg-muted/30 flex items-center justify-center">
                                                {bindingTarget?.type === 'character' ? (
                                                    <User className="w-5 h-5 opacity-30" />
                                                ) : (
                                                    <Map className="w-5 h-5 opacity-30" />
                                                )}
                                            </div>
                                        )}
                                        <span className="font-medium text-sm">{asset.name}</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <Button
                                            size="sm"
                                            variant="ghost"
                                            className="h-6 w-6 p-0"
                                            disabled={generatingImage === asset.id}
                                            onClick={async (e) => {
                                                e.stopPropagation()
                                                setGeneratingImage(asset.id)
                                                try {
                                                    const result = await assetsApi.generateImage(asset.id)
                                                    if ((result as any).success) {
                                                        if (projectId && bindingTarget) {
                                                            const r = await assetsApi.list(projectId, bindingTarget.type)
                                                            setProjectAssets((r as any).items || [])
                                                        }
                                                    }
                                                } catch (err) {
                                                    console.error('Generate error:', err)
                                                } finally {
                                                    setGeneratingImage(null)
                                                }
                                            }}
                                        >
                                            {generatingImage === asset.id ? (
                                                <Loader2 className="w-3 h-3 animate-spin" />
                                            ) : (
                                                <ImagePlus className="w-3 h-3" />
                                            )}
                                        </Button>
                                        <Badge variant="outline" className="text-xs">选择</Badge>
                                    </div>
                                </div>
                            ))
                        ) : (
                            <div className="text-center py-4 text-muted-foreground">
                                <p className="text-sm">资产库中暂无此类型资产</p>
                            </div>
                        )}
                    </div>

                    <DialogFooter className="flex gap-2">
                        <Button variant="outline" onClick={() => setBindingTarget(null)}>
                            取消
                        </Button>
                        <Button
                            variant="secondary"
                            onClick={() => {
                                // TODO: wire up asset creation flow
                                console.log('Create new asset for:', bindingTarget?.name)
                                setBindingTarget(null)
                            }}
                        >
                            <Wand2 className="w-4 h-4 mr-1" />
                            创建新资产
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
