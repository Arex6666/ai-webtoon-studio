'use client'

import { useState, useEffect, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { sceneAnchorApi } from '@/lib/api/services'
import { useToast } from '@/hooks/use-toast'
import {
    Upload,
    Map,
    CheckCircle,
    AlertCircle,
    Loader2,
    Trash2,
    RefreshCw,
    Eye,
    Layers,
    Box,
    Pencil
} from 'lucide-react'

interface SceneAnchorPanelProps {
    assetId: string
    assetName: string
    onStatusChange?: (status: 'none' | 'pending' | 'ready' | 'failed') => void
}

interface AnchorStatus {
    asset_id: string
    status: 'none' | 'pending' | 'ready' | 'failed'
    has_anchor: boolean
    has_depth: boolean
    has_canny: boolean
    has_lineart: boolean
    message?: string
}

interface AnchorUrls {
    anchor_url?: string
    depth_url?: string
    canny_url?: string
    lineart_url?: string
}

export function SceneAnchorPanel({
    assetId,
    assetName,
    onStatusChange
}: SceneAnchorPanelProps) {
    const [status, setStatus] = useState<AnchorStatus | null>(null)
    const [urls, setUrls] = useState<AnchorUrls | null>(null)
    const [loading, setLoading] = useState(false)
    const [uploading, setUploading] = useState(false)
    const [previewType, setPreviewType] = useState<'anchor' | 'depth' | 'canny' | 'lineart' | null>(null)
    const inputRef = useRef<HTMLInputElement>(null)
    const { toast } = useToast()

    // 加载状态和 URLs
    useEffect(() => {
        loadData()
    }, [assetId])

    const loadData = async () => {
        setLoading(true)
        try {
            const [statusResult, urlsResult] = await Promise.all([
                sceneAnchorApi.getStatus(assetId),
                sceneAnchorApi.getUrls(assetId).catch(() => null)
            ])
            setStatus(statusResult)
            setUrls(urlsResult)
            onStatusChange?.(statusResult.status)
        } catch (error) {
            console.error('Failed to load anchor data:', error)
        } finally {
            setLoading(false)
        }
    }

    const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (!file) return

        setUploading(true)
        try {
            const result = await sceneAnchorApi.generateAnchor(assetId, file, {
                generate_depth: true,
                generate_canny: true,
                generate_lineart: true
            })

            toast({
                title: '控制图生成成功',
                description: `已生成: ${result.generated_maps.join(', ')}`
            })

            // 刷新数据
            await loadData()
        } catch (error) {
            console.error('Failed to generate anchor:', error)
            toast({
                title: '生成失败',
                description: error instanceof Error ? error.message : '请重试',
                variant: 'destructive'
            })
        } finally {
            setUploading(false)
            // 清空 input
            if (inputRef.current) inputRef.current.value = ''
        }
    }

    const handleRegenerate = async (mapType: 'depth' | 'canny' | 'lineart') => {
        try {
            await sceneAnchorApi.regenerateMap(assetId, mapType)
            toast({
                title: '重新生成中',
                description: `${mapType} 控制图正在重新生成`
            })
            await loadData()
        } catch (error) {
            toast({
                title: '重新生成失败',
                variant: 'destructive'
            })
        }
    }

    const handleDelete = async () => {
        if (!confirm('确定要删除此场景的所有控制图吗？')) return

        try {
            await sceneAnchorApi.deleteAnchor(assetId)
            setStatus({ ...status!, status: 'none', has_anchor: false, has_depth: false, has_canny: false, has_lineart: false })
            setUrls(null)
            onStatusChange?.('none')
            toast({
                title: '已删除',
                description: '场景控制图已删除'
            })
        } catch (error) {
            toast({
                title: '删除失败',
                variant: 'destructive'
            })
        }
    }

    const getStatusBadge = () => {
        if (!status) return null
        switch (status.status) {
            case 'ready':
                return (
                    <Badge variant="outline" className="text-emerald-500 border-emerald-500/30">
                        <CheckCircle className="w-3 h-3 mr-1" />
                        已就绪
                    </Badge>
                )
            case 'pending':
                return (
                    <Badge variant="outline" className="text-yellow-500 border-yellow-500/30">
                        <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                        处理中
                    </Badge>
                )
            case 'failed':
                return (
                    <Badge variant="outline" className="text-red-500 border-red-500/30">
                        <AlertCircle className="w-3 h-3 mr-1" />
                        失败
                    </Badge>
                )
            default:
                return (
                    <Badge variant="outline" className="text-muted-foreground">
                        未配置
                    </Badge>
                )
        }
    }

    const controlMaps = [
        { key: 'depth', label: 'Depth', icon: Box, color: 'text-blue-400', has: status?.has_depth, url: urls?.depth_url },
        { key: 'canny', label: 'Canny', icon: Layers, color: 'text-green-400', has: status?.has_canny, url: urls?.canny_url },
        { key: 'lineart', label: 'Lineart', icon: Pencil, color: 'text-purple-400', has: status?.has_lineart, url: urls?.lineart_url },
    ] as const

    if (loading) {
        return (
            <div className="p-4 flex items-center justify-center">
                <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
            </div>
        )
    }

    return (
        <div className="p-4 space-y-4 border border-white/10 rounded-lg bg-panel/30">
            {/* 标题行 */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Map className="w-4 h-4 text-teal-400" />
                    <span className="font-medium text-sm">{assetName}</span>
                </div>
                {getStatusBadge()}
            </div>

            {/* 锚点图预览 */}
            {urls?.anchor_url && (
                <div className="relative rounded-lg overflow-hidden border border-white/10">
                    <img
                        src={urls.anchor_url}
                        alt="Anchor"
                        className="w-full h-32 object-cover"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
                    <div className="absolute bottom-2 left-2 text-xs text-white/80">
                        原始锚点图
                    </div>
                </div>
            )}

            {/* 控制图状态 */}
            {status?.status === 'ready' && (
                <div className="grid grid-cols-3 gap-2">
                    {controlMaps.map((map) => (
                        <div
                            key={map.key}
                            className={`relative group rounded-lg border border-white/10 p-2 text-center ${map.has ? 'bg-muted/20' : 'bg-muted/5 opacity-50'
                                }`}
                        >
                            <map.icon className={`w-5 h-5 mx-auto mb-1 ${map.color}`} />
                            <div className="text-xs font-medium">{map.label}</div>
                            {map.has && (
                                <div className="absolute top-1 right-1">
                                    <CheckCircle className="w-3 h-3 text-emerald-400" />
                                </div>
                            )}
                            {/* 悬停操作 */}
                            {map.has && map.url && (
                                <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-1">
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="h-6 w-6 p-0"
                                        onClick={() => setPreviewType(map.key)}
                                    >
                                        <Eye className="w-3 h-3" />
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="h-6 w-6 p-0"
                                        onClick={() => handleRegenerate(map.key)}
                                    >
                                        <RefreshCw className="w-3 h-3" />
                                    </Button>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}

            {/* 预览弹窗 (简化版) */}
            {previewType && (
                <div
                    className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center"
                    onClick={() => setPreviewType(null)}
                >
                    <img
                        src={urls?.[`${previewType}_url`]}
                        alt={previewType}
                        className="max-w-[80%] max-h-[80%] object-contain rounded-lg"
                        onClick={(e) => e.stopPropagation()}
                    />
                </div>
            )}

            {/* 上传区域 */}
            {status?.status !== 'ready' && (
                <div
                    className="border-2 border-dashed border-white/10 rounded-lg p-4 text-center cursor-pointer hover:border-teal-500/50 transition-colors"
                    onClick={() => inputRef.current?.click()}
                >
                    {uploading ? (
                        <>
                            <Loader2 className="w-6 h-6 mx-auto mb-2 animate-spin text-teal-400" />
                            <p className="text-sm text-muted-foreground">生成控制图中...</p>
                        </>
                    ) : (
                        <>
                            <Upload className="w-6 h-6 mx-auto mb-2 text-muted-foreground" />
                            <p className="text-sm text-muted-foreground">
                                点击上传空镜锚点图
                            </p>
                            <p className="text-xs text-muted-foreground/70 mt-1">
                                系统将自动生成 Depth / Canny / Lineart
                            </p>
                        </>
                    )}
                    <input
                        ref={inputRef}
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={handleFileSelect}
                        disabled={uploading}
                    />
                </div>
            )}

            {/* 已就绪时的操作 */}
            {status?.status === 'ready' && (
                <div className="flex gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        className="flex-1"
                        onClick={() => inputRef.current?.click()}
                    >
                        <RefreshCw className="w-3 h-3 mr-1" />
                        重新上传
                        <input
                            ref={inputRef}
                            type="file"
                            accept="image/*"
                            className="hidden"
                            onChange={handleFileSelect}
                            disabled={uploading}
                        />
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        className="text-red-500 hover:text-red-400"
                        onClick={handleDelete}
                    >
                        <Trash2 className="w-3 h-3" />
                    </Button>
                </div>
            )}
        </div>
    )
}
