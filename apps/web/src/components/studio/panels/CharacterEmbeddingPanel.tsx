'use client'

import { useState, useEffect, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { identityApi } from '@/lib/api/services'
import { useToast } from '@/hooks/use-toast'
import {
    Upload,
    User,
    CheckCircle,
    AlertCircle,
    Loader2,
    Trash2,
    Image as ImageIcon,
    RefreshCw
} from 'lucide-react'

interface CharacterEmbeddingPanelProps {
    assetId: string
    assetName: string
    onStatusChange?: (status: 'none' | 'pending' | 'ready' | 'failed') => void
}

interface EmbeddingStatus {
    asset_id: string
    status: 'none' | 'pending' | 'ready' | 'failed'
    embedding_path?: string
    source_image_count: number
    message?: string
}

export function CharacterEmbeddingPanel({
    assetId,
    assetName,
    onStatusChange
}: CharacterEmbeddingPanelProps) {
    const [status, setStatus] = useState<EmbeddingStatus | null>(null)
    const [loading, setLoading] = useState(false)
    const [uploading, setUploading] = useState(false)
    const [selectedFiles, setSelectedFiles] = useState<File[]>([])
    const inputRef = useRef<HTMLInputElement>(null)
    const { toast } = useToast()

    // 加载状态
    useEffect(() => {
        loadStatus()
    }, [assetId])

    const loadStatus = async () => {
        setLoading(true)
        try {
            const result = await identityApi.getStatus(assetId)
            setStatus(result)
            onStatusChange?.(result.status)
        } catch (error) {
            console.error('Failed to load embedding status:', error)
        } finally {
            setLoading(false)
        }
    }

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = Array.from(e.target.files || [])
        if (files.length > 0) {
            setSelectedFiles(prev => [...prev, ...files])
        }
    }

    const handleRemoveFile = (index: number) => {
        setSelectedFiles(prev => prev.filter((_, i) => i !== index))
    }

    const handleUpload = async () => {
        if (selectedFiles.length === 0) {
            toast({
                title: '请选择图片',
                description: '请上传 1-5 张角色定妆照',
                variant: 'destructive'
            })
            return
        }

        setUploading(true)
        try {
            const result = await identityApi.extractEmbedding(assetId, selectedFiles)
            setStatus(result as EmbeddingStatus)
            onStatusChange?.(result.status as EmbeddingStatus['status'])
            setSelectedFiles([])
            toast({
                title: 'FaceID 提取成功',
                description: `已从 ${result.source_image_count} 张图片提取身份特征`
            })
        } catch (error) {
            console.error('Failed to extract embedding:', error)
            toast({
                title: '提取失败',
                description: error instanceof Error ? error.message : '请重试',
                variant: 'destructive'
            })
        } finally {
            setUploading(false)
        }
    }

    const handleDelete = async () => {
        if (!confirm('确定要删除此角色的 FaceID Embedding 吗？')) return

        try {
            await identityApi.deleteEmbedding(assetId)
            setStatus({ ...status!, status: 'none', embedding_path: undefined })
            onStatusChange?.('none')
            toast({
                title: '已删除',
                description: 'FaceID Embedding 已删除'
            })
        } catch (error) {
            console.error('Failed to delete embedding:', error)
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
                    <User className="w-4 h-4 text-emerald-400" />
                    <span className="font-medium text-sm">{assetName}</span>
                </div>
                {getStatusBadge()}
            </div>

            {/* 状态信息 */}
            {status?.status === 'ready' && (
                <div className="text-xs text-muted-foreground space-y-1">
                    <div className="flex items-center gap-2">
                        <CheckCircle className="w-3 h-3 text-emerald-500" />
                        <span>512 维 FaceID 向量已就绪</span>
                    </div>
                    <div>来源图片: {status.source_image_count} 张</div>
                </div>
            )}

            {/* 上传区域 */}
            {status?.status !== 'ready' && (
                <div className="space-y-3">
                    <div
                        className="border-2 border-dashed border-white/10 rounded-lg p-4 text-center cursor-pointer hover:border-emerald-500/50 transition-colors"
                        onClick={() => inputRef.current?.click()}
                    >
                        <Upload className="w-6 h-6 mx-auto mb-2 text-muted-foreground" />
                        <p className="text-sm text-muted-foreground">
                            点击上传定妆照 (1-5 张)
                        </p>
                        <p className="text-xs text-muted-foreground/70 mt-1">
                            建议: 正面照 + 侧面照 + 不同表情
                        </p>
                        <input
                            ref={inputRef}
                            type="file"
                            accept="image/*"
                            multiple
                            className="hidden"
                            onChange={handleFileSelect}
                        />
                    </div>

                    {/* 已选择的文件 */}
                    {selectedFiles.length > 0 && (
                        <div className="space-y-1">
                            {selectedFiles.map((file, i) => (
                                <div key={i} className="flex items-center justify-between text-xs bg-muted/10 rounded px-2 py-1">
                                    <span className="truncate flex-1">{file.name}</span>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="h-5 w-5 p-0"
                                        onClick={() => handleRemoveFile(i)}
                                    >
                                        <Trash2 className="w-3 h-3" />
                                    </Button>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* 上传按钮 */}
                    <Button
                        className="w-full"
                        size="sm"
                        disabled={selectedFiles.length === 0 || uploading}
                        onClick={handleUpload}
                    >
                        {uploading ? (
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        ) : (
                            <Upload className="w-4 h-4 mr-2" />
                        )}
                        {uploading ? '提取中...' : `提取 FaceID (${selectedFiles.length} 张)`}
                    </Button>
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
                        重新提取
                        <input
                            ref={inputRef}
                            type="file"
                            accept="image/*"
                            multiple
                            className="hidden"
                            onChange={handleFileSelect}
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
