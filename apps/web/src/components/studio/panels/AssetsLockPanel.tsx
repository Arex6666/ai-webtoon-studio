'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
import { chaptersApi, assetsApi } from '@/lib/api/services'
import { useStudioStore } from '@/lib/store/studioStore'
import {
    Check,
    AlertTriangle,
    AlertCircle,
    User,
    Map,
    Palette,
    Loader2,
    Link,
    HelpCircle,
    RefreshCw,
    Wand2,
    ImagePlus
} from 'lucide-react'


interface AssetLock {
    asset_id: string
    name: string
    face_embedding_path?: string
    lora_path?: string
    reference_images?: string[]
}

interface AssetsLockData {
    chapter_id: string
    storyboard_version: number
    locked_at?: string
    characters: Record<string, AssetLock>
    scenes: Record<string, AssetLock>
    styles: Record<string, AssetLock>
    stats: {
        locked_characters: number
        locked_scenes: number
        locked_styles: number
        pending_count: number
    }
    can_render: boolean
}

type MatchType = 'exact' | 'fuzzy' | 'pending'

interface AssetItem {
    id: string
    name: string
    type: 'character' | 'scene' | 'style'
    matchType: MatchType
    assetId?: string
    confidence?: number
    similar?: Array<{ id: string; name: string; confidence: number }>
}

interface AssetsLockPanelProps {
    chapterId: string
    onRenderReady?: (canRender: boolean) => void
}

export function AssetsLockPanel({ chapterId, onRenderReady }: AssetsLockPanelProps) {
    const [lockData, setLockData] = useState<AssetsLockData | null>(null)
    const [loading, setLoading] = useState(true)
    const [confirmingAsset, setConfirmingAsset] = useState<AssetItem | null>(null)
    const [refreshing, setRefreshing] = useState(false)
    const [projectAssets, setProjectAssets] = useState<Array<{ id: string; name: string; type: string; thumbnail_url?: string }>>([])
    const [generatingImage, setGeneratingImage] = useState<string | null>(null)

    const projectId = useStudioStore((s) => s.projectId)

    const loadAssetsLock = async () => {
        if (!chapterId) return
        try {
            const data = await chaptersApi.getAssetsLock(chapterId)
            setLockData(data)
            onRenderReady?.(data.can_render)
        } catch (error) {
            console.error('Failed to load assets lock:', error)
        } finally {
            setLoading(false)
        }
    }

    // 加载项目资产库
    const loadProjectAssets = async (type: 'character' | 'scene') => {
        if (!projectId) return
        try {
            const result = await assetsApi.list(projectId, type)
            setProjectAssets(result.items || [])
        } catch (error) {
            console.error('Failed to load project assets:', error)
        }
    }

    useEffect(() => {
        loadAssetsLock()
    }, [chapterId])

    // 打开绑定对话框时加载对应类型的资产
    useEffect(() => {
        if (confirmingAsset) {
            loadProjectAssets(confirmingAsset.type as 'character' | 'scene')
        }
    }, [confirmingAsset, projectId])

    const handleRefresh = async () => {
        setRefreshing(true)
        await loadAssetsLock()
        setRefreshing(false)

    }

    // 模拟解析资产列表（实际应从后端获取详细匹配信息）
    const parseAssets = (): AssetItem[] => {
        if (!lockData) return []

        const items: AssetItem[] = []

        // 角色
        Object.entries(lockData.characters).forEach(([id, char]) => {
            items.push({
                id,
                name: char.name,
                type: 'character',
                matchType: char.face_embedding_path ? 'exact' : 'fuzzy',
                assetId: char.asset_id
            })
        })

        // 场景
        Object.entries(lockData.scenes).forEach(([id, scene]) => {
            items.push({
                id,
                name: scene.name,
                type: 'scene',
                matchType: 'exact',
                assetId: scene.asset_id
            })
        })

        return items
    }

    const getMatchBadge = (matchType: MatchType) => {
        switch (matchType) {
            case 'exact':
                return (
                    <Badge variant="outline" className="text-green-500 border-green-500/30">
                        <Check className="w-3 h-3 mr-1" />
                        精确匹配
                    </Badge>
                )
            case 'fuzzy':
                return (
                    <Badge variant="outline" className="text-amber-500 border-amber-500/30">
                        <HelpCircle className="w-3 h-3 mr-1" />
                        需确认
                    </Badge>
                )
            case 'pending':
                return (
                    <Badge variant="outline" className="text-red-500 border-red-500/30">
                        <AlertCircle className="w-3 h-3 mr-1" />
                        待绑定
                    </Badge>
                )
        }
    }

    const getTypeIcon = (type: 'character' | 'scene' | 'style') => {
        switch (type) {
            case 'character':
                return <User className="w-4 h-4" />
            case 'scene':
                return <Map className="w-4 h-4" />
            case 'style':
                return <Palette className="w-4 h-4" />
        }
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center p-8">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
        )
    }

    if (!lockData) {
        return (
            <div className="p-4 text-center text-muted-foreground">
                <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">未找到资产锁定信息</p>
                <p className="text-xs mt-1">请先应用 AI 分镜</p>
            </div>
        )
    }

    const assets = parseAssets()
    const hasPending = lockData.stats.pending_count > 0
    const hasFuzzy = assets.some(a => a.matchType === 'fuzzy')

    return (
        <div className="flex flex-col h-full">
            {/* 头部状态 */}
            <div className="p-3 border-b border-white/10">
                <div className="flex items-center justify-between mb-2">
                    <h3 className="font-medium text-sm">资产锁定</h3>
                    <Button
                        size="sm"
                        variant="ghost"
                        onClick={handleRefresh}
                        disabled={refreshing}
                    >
                        <RefreshCw className={`w-3 h-3 ${refreshing ? 'animate-spin' : ''}`} />
                    </Button>
                </div>

                {/* 渲染状态 */}
                <div className={`p-2 rounded-lg border ${lockData.can_render
                    ? 'bg-green-500/10 border-green-500/30'
                    : 'bg-amber-500/10 border-amber-500/30'
                    }`}>
                    <div className="flex items-center gap-2">
                        {lockData.can_render ? (
                            <Check className="w-4 h-4 text-green-500" />
                        ) : (
                            <AlertTriangle className="w-4 h-4 text-amber-500" />
                        )}
                        <span className="text-sm">
                            {lockData.can_render
                                ? '资产已就绪，可以渲染'
                                : `${lockData.stats.pending_count} 个资产待确认`
                            }
                        </span>
                    </div>
                </div>

                {/* 统计 */}
                <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
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
            </div>

            {/* 资产列表 */}
            <ScrollArea className="flex-1">
                <div className="p-2 space-y-1">
                    {assets.length === 0 ? (
                        <p className="text-xs text-muted-foreground p-4 text-center">
                            暂无锁定资产
                        </p>
                    ) : (
                        assets.map((asset) => (
                            <div
                                key={asset.id}
                                className={`p-2 rounded-lg border transition-colors ${asset.matchType === 'pending'
                                    ? 'border-red-500/30 bg-red-500/5'
                                    : asset.matchType === 'fuzzy'
                                        ? 'border-amber-500/30 bg-amber-500/5'
                                        : 'border-white/10 bg-muted/5'
                                    }`}
                            >
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <div className="w-8 h-8 rounded-full bg-muted/30 flex items-center justify-center">
                                            {getTypeIcon(asset.type)}
                                        </div>
                                        <div>
                                            <div className="text-sm font-medium">{asset.name}</div>
                                            <div className="text-xs text-muted-foreground">
                                                {asset.type === 'character' ? '角色' : asset.type === 'scene' ? '场景' : '风格'}
                                            </div>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {getMatchBadge(asset.matchType)}
                                        {(asset.matchType === 'fuzzy' || asset.matchType === 'pending') && (
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                onClick={() => setConfirmingAsset(asset)}
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
                </div>
            </ScrollArea>

            {/* 确认弹窗 */}
            <Dialog open={!!confirmingAsset} onOpenChange={() => setConfirmingAsset(null)}>
                <DialogContent className="max-w-md">
                    <DialogHeader>
                        <DialogTitle>资产绑定</DialogTitle>
                        <DialogDescription>
                            为 "{confirmingAsset?.name}" 选择资产库中的对应项，或生成新的参考图
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-2 max-h-60 overflow-y-auto">
                        {projectAssets.length > 0 ? (
                            projectAssets.map((asset) => (
                                <div
                                    key={asset.id}
                                    className="p-3 rounded-lg border border-white/10 hover:border-primary/50 cursor-pointer transition-colors flex items-center justify-between"
                                    onClick={() => {
                                        // TODO: 实际绑定逻辑
                                        console.log(`Binding ${confirmingAsset?.id} to asset ${asset.id}`)
                                        setConfirmingAsset(null)
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
                                                {confirmingAsset?.type === 'character' ? (
                                                    <User className="w-5 h-5 opacity-30" />
                                                ) : (
                                                    <Map className="w-5 h-5 opacity-30" />
                                                )}
                                            </div>
                                        )}
                                        <span className="font-medium">{asset.name}</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <Button
                                            size="sm"
                                            variant="ghost"
                                            disabled={generatingImage === asset.id}
                                            onClick={async (e) => {
                                                e.stopPropagation()
                                                setGeneratingImage(asset.id)
                                                try {
                                                    const result = await assetsApi.generateImage(asset.id)
                                                    if (result.success) {
                                                        // 刷新资产列表
                                                        await loadProjectAssets(confirmingAsset!.type as 'character' | 'scene')
                                                    } else {
                                                        console.error('Generate failed:', result.error)
                                                    }
                                                } catch (error) {
                                                    console.error('Generate error:', error)
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
                                        <Badge variant="outline">选择</Badge>
                                    </div>
                                </div>
                            ))
                        ) : (
                            <div className="text-center py-4">
                                <p className="text-sm text-muted-foreground mb-2">
                                    资产库中暂无此类型资产
                                </p>
                            </div>
                        )}
                    </div>

                    <DialogFooter className="flex gap-2">
                        <Button variant="outline" onClick={() => setConfirmingAsset(null)}>
                            取消
                        </Button>
                        <Button
                            variant="secondary"
                            onClick={() => {
                                // TODO: 创建新资产的逻辑
                                console.log('Create new asset for:', confirmingAsset?.name)
                                setConfirmingAsset(null)
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
