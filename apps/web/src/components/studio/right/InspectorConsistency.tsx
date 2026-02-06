'use client'

import { useEffect, useState } from 'react'
import { useStudioStore } from '@/lib/store/studioStore'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { CharacterEmbeddingPanel } from '../panels/CharacterEmbeddingPanel'
import { Users, Image, CheckCircle, AlertCircle, Loader2, Link, RefreshCw } from 'lucide-react'
import { chaptersApi, identityApi } from '@/lib/api/services'
import { useToast } from '@/hooks/use-toast'

// AssetsLock 中角色/场景的状态类型
type AssetLockStatus = 'pending' | 'exact' | 'fuzzy' | 'none'

// AssetsLock 数据结构
interface AssetsLockData {
    chapter_id: string
    storyboard_version: number
    characters: Record<string, {
        asset_id: string
        name: string
        status: AssetLockStatus
        embedding_path?: string
        canonical_image_url?: string
    }>
    scenes: Record<string, {
        asset_id: string
        name: string
        status: AssetLockStatus
        anchor_path?: string
        control_maps?: Record<string, string>
    }>
    styles: Record<string, any>
    stats: {
        locked_characters: number
        locked_scenes: number
        locked_styles: number
        pending_count: number
    }
    can_render: boolean
}

// 状态徽章组件
function StatusBadge({ status }: { status: AssetLockStatus }) {
    switch (status) {
        case 'exact':
            return (
                <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30 text-[10px] px-1.5">
                    <CheckCircle className="w-2.5 h-2.5 mr-0.5" />
                    已确认
                </Badge>
            )
        case 'fuzzy':
            return (
                <Badge className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30 text-[10px] px-1.5">
                    <AlertCircle className="w-2.5 h-2.5 mr-0.5" />
                    模糊匹配
                </Badge>
            )
        case 'pending':
            return (
                <Badge className="bg-orange-500/20 text-orange-400 border-orange-500/30 text-[10px] px-1.5">
                    <Loader2 className="w-2.5 h-2.5 mr-0.5 animate-spin" />
                    待确认
                </Badge>
            )
        default:
            return (
                <Badge variant="outline" className="text-[10px] px-1.5">
                    未知
                </Badge>
            )
    }
}

// CharacterAssetCard 组件 - 展示角色资产并支持上传参考图
function CharacterAssetCard({
    character,
    onRefresh
}: {
    character: {
        asset_id: string
        name: string
        status: AssetLockStatus
        embedding_path?: string
        canonical_image_url?: string
    }
    onRefresh: () => void
}) {
    const [isUploading, setIsUploading] = useState(false)
    const [uploadError, setUploadError] = useState<string | null>(null)
    const { toast } = useToast()

    const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (!file) return

        // Validate file
        if (!file.type.startsWith('image/')) {
            setUploadError('请选择图片文件')
            return
        }
        if (file.size > 10 * 1024 * 1024) {
            setUploadError('图片大小不能超过 10MB')
            return
        }

        setIsUploading(true)
        setUploadError(null)

        try {
            // P0: 真实调用 API 提取 FaceID
            await identityApi.extractEmbedding(character.asset_id, [file])

            toast({
                title: "上传成功",
                description: `${character.name} 的参考图已更新，FaceID 提取完成`,
            })

            onRefresh()
        } catch (error) {
            console.error('Upload failed:', error)
            setUploadError(error instanceof Error ? error.message : '上传失败请重试')
            toast({
                title: "上传失败",
                description: "无法提取 FaceID，请确保图片包含清晰的人脸",
                variant: "destructive",
            })
        } finally {
            setIsUploading(false)
            if (e.target) e.target.value = ''
        }
    }

    const handleUploadClick = () => {
        const input = document.createElement('input')
        input.type = 'file'
        input.accept = 'image/*'
        input.onchange = handleFileSelect as any
        input.click()
    }

    const embeddingStatus = character.embedding_path ? 'ready' : 'missing'
    const hasRefImage = !!character.canonical_image_url

    return (
        <div className="group p-3 rounded-lg border border-white/10 bg-muted/10 hover:bg-muted/20 transition-colors cursor-pointer">
            <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2 flex-1 min-w-0">
                    {hasRefImage ? (
                        <div className="w-10 h-10 rounded-full overflow-hidden bg-muted/20 flex-shrink-0">
                            <img
                                src={character.canonical_image_url}
                                alt={character.name}
                                className="w-full h-full object-cover"
                            />
                        </div>
                    ) : (
                        <div className="w-10 h-10 rounded-full bg-muted/20 flex items-center justify-center flex-shrink-0">
                            <Users className="w-5 h-5 text-muted-foreground" />
                        </div>
                    )}
                    <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{character.name}</p>
                        <div className="flex items-center gap-1.5 mt-0.5">
                            {embeddingStatus === 'ready' ? (
                                <span className="text-[10px] text-emerald-400 flex items-center gap-0.5">
                                    <CheckCircle className="w-2.5 h-2.5" />
                                    FaceID 就绪
                                </span>
                            ) : (
                                <span className="text-[10px] text-muted-foreground flex items-center gap-0.5">
                                    <AlertCircle className="w-2.5 h-2.5" />
                                    待上传参考图
                                </span>
                            )}
                        </div>
                    </div>
                </div>
                <div className="flex flex-col items-end gap-1.5">
                    <StatusBadge status={character.status} />
                    {!isUploading && (
                        <Button
                            size="sm"
                            variant="ghost"
                            className="h-6 px-2 text-[10px] opacity-0 group-hover:opacity-100 transition-opacity"
                            onClick={handleUploadClick}
                        >
                            <Image className="w-3 h-3 mr-1" />
                            {hasRefImage ? '更新' : '上传'}
                        </Button>
                    )}
                    {isUploading && (
                        <span className="text-[10px] text-blue-400 flex items-center gap-1">
                            <Loader2 className="w-3 h-3 animate-spin" />
                            处理中
                        </span>
                    )}
                </div>
            </div>
            {uploadError && (
                <p className="text-[10px] text-red-400 mt-2">{uploadError}</p>
            )}
        </div>
    )
}

export function InspectorConsistency() {
    const { chapterId, canRender, pendingAssetsCount, activeInspectorTab } = useStudioStore()
    const [assetsLock, setAssetsLock] = useState<AssetsLockData | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    // 加载 AssetsLock 数据
    const fetchAssetsLock = async () => {
        if (!chapterId) return

        setLoading(true)
        setError(null)

        try {
            const data = await chaptersApi.getAssetsLock(chapterId)
            setAssetsLock(data as AssetsLockData)
        } catch (err) {
            console.error('Failed to load assets lock:', err)
            setError('加载资产锁定状态失败')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchAssetsLock()
    }, [chapterId])

    // 当 Tab 激活时刷新数据
    useEffect(() => {
        if (activeInspectorTab === 'consistency') {
            fetchAssetsLock()
        }
    }, [activeInspectorTab])

    // 获取角色和场景列表
    const characters = assetsLock ? Object.values(assetsLock.characters) : []
    const scenes = assetsLock ? Object.values(assetsLock.scenes) : []

    // 统计
    const pendingCharacters = characters.filter(c => c.status === 'pending').length
    const exactCharacters = characters.filter(c => c.status === 'exact').length
    const pendingScenes = scenes.filter(s => s.status === 'pending').length
    const exactScenes = scenes.filter(s => s.status === 'exact').length

    return (
        <ScrollArea className="h-full">
            <div className="p-4 space-y-5">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <h3 className="font-medium flex items-center gap-2">
                        <Link className="w-4 h-4" />
                        一致性状态
                    </h3>
                    <div className="flex items-center gap-2">
                        {canRender ? (
                            <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30">
                                <CheckCircle className="w-3 h-3 mr-1" />
                                可渲染
                            </Badge>
                        ) : (
                            <Badge className="bg-orange-500/20 text-orange-400 border-orange-500/30">
                                <AlertCircle className="w-3 h-3 mr-1" />
                                {pendingAssetsCount} 待确认
                            </Badge>
                        )}
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6"
                            onClick={fetchAssetsLock}
                            disabled={loading}
                        >
                            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
                        </Button>
                    </div>
                </div>

                <Separator />

                {/* Loading State */}
                {loading && !assetsLock ? (
                    <div className="space-y-4">
                        <Skeleton className="h-20 w-full" />
                        <Skeleton className="h-20 w-full" />
                    </div>
                ) : error ? (
                    <div className="p-4 text-center text-red-400 text-sm">
                        <AlertCircle className="w-6 h-6 mx-auto mb-2" />
                        {error}
                        <Button
                            variant="outline"
                            size="sm"
                            className="mt-2"
                            onClick={fetchAssetsLock}
                        >
                            重试
                        </Button>
                    </div>
                ) : (
                    <>
                        {/* 角色资产状态 */}
                        <div className="space-y-3">
                            <Label className="text-xs text-ink-muted flex items-center justify-between">
                                <span className="flex items-center gap-1.5">
                                    <Users className="w-3 h-3" />
                                    角色资产
                                </span>
                                <span className="text-muted-foreground">
                                    {exactCharacters}/{characters.length} 已确认
                                </span>
                            </Label>

                            {characters.length === 0 ? (
                                <div className="p-6 text-center text-ink-muted border border-dashed border-panel-border rounded-lg cursor-pointer hover:bg-muted/5 transition-colors">
                                    <Users className="w-8 h-8 mx-auto mb-2 opacity-50" />
                                    <p className="text-sm">暂无角色资产</p>
                                    <p className="text-xs mt-1">运行 AI 分镜后自动提取角色</p>
                                </div>
                            ) : (
                                <div className="space-y-2">
                                    {characters.map(char => (
                                        <CharacterAssetCard
                                            key={char.asset_id}
                                            character={char}
                                            onRefresh={fetchAssetsLock}
                                        />
                                    ))}
                                </div>
                            )}

                            {pendingCharacters > 0 && (
                                <p className="text-xs text-orange-400">
                                    ⚠ {pendingCharacters} 个角色待确认，请前往「资产锁定」Tab 完成
                                </p>
                            )}
                        </div>

                        <Separator />

                        {/* 场景资产状态 */}
                        <div className="space-y-3">
                            <Label className="text-xs text-ink-muted flex items-center justify-between">
                                <span className="flex items-center gap-1.5">
                                    <Image className="w-3 h-3" />
                                    场景资产
                                </span>
                                <span className="text-muted-foreground">
                                    {exactScenes}/{scenes.length} 已确认
                                </span>
                            </Label>

                            {scenes.length === 0 ? (
                                <div className="p-4 text-center text-ink-muted border border-dashed border-panel-border rounded-lg">
                                    <Image className="w-6 h-6 mx-auto mb-2 opacity-50" />
                                    <p className="text-sm">暂无场景资产</p>
                                </div>
                            ) : (
                                <div className="grid grid-cols-2 gap-2">
                                    {scenes.map(scene => (
                                        <div
                                            key={scene.asset_id}
                                            className="p-2 rounded border border-white/10 bg-muted/10"
                                        >
                                            <div className="flex items-center justify-between mb-1">
                                                <span className="text-xs font-medium truncate">{scene.name}</span>
                                                <StatusBadge status={scene.status} />
                                            </div>
                                            <p className="text-[10px] text-muted-foreground">
                                                {scene.anchor_path ? '锚点已生成' : '锚点未生成'}
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            )}

                            {pendingScenes > 0 && (
                                <p className="text-xs text-orange-400">
                                    ⚠ {pendingScenes} 个场景待确认
                                </p>
                            )}
                        </div>

                        {/* 底部提示 */}
                        <div className="pt-2 text-center text-xs text-muted-foreground">
                            <p>数据与「资产锁定」Tab 保持同步</p>
                            <p className="mt-1">
                                {assetsLock?.storyboard_version &&
                                    `分镜版本: v${assetsLock.storyboard_version}`}
                            </p>
                        </div>
                    </>
                )}
            </div>
        </ScrollArea>
    )
}
