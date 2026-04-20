'use client'

import { useState, useEffect } from 'react'
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { assetsApi } from '@/lib/api/services'
import {
    User,
    Map,
    Wand2,
    Loader2,
    X,
    Plus,
    RefreshCw,
    ImagePlus,
    Sparkles
} from 'lucide-react'

interface Asset {
    id: string
    name: string
    type: string
    description?: string
    thumbnail_url?: string
    data_json: {
        reference_images?: string[]
        appearance_traits?: string[]
        face_embedding?: string
        anchor_image?: string
        gender?: string
        age_range?: string
        [key: string]: any
    }
}

interface AssetDetailModalProps {
    assetId: string | null
    assetType?: 'character' | 'scene'
    onClose: () => void
    onAssetUpdated?: () => void
}

export function AssetDetailModal({
    assetId,
    assetType = 'character',
    onClose,
    onAssetUpdated,
}: AssetDetailModalProps) {
    const [asset, setAsset] = useState<Asset | null>(null)
    const [loading, setLoading] = useState(true)
    const [generating, setGenerating] = useState(false)
    const [saving, setSaving] = useState(false)

    // Editable fields
    const [name, setName] = useState('')
    const [description, setDescription] = useState('')
    const [traits, setTraits] = useState<string[]>([])
    const [newTrait, setNewTrait] = useState('')

    // Load asset details
    useEffect(() => {
        if (!assetId) {
            setAsset(null)
            setLoading(false)
            return
        }

        const loadAsset = async () => {
            setLoading(true)
            try {
                const data = await assetsApi.get(assetId)
                setAsset(data)
                setName(data.name)
                setDescription(data.description || '')
                setTraits((data.data_json?.appearance_traits as string[]) || [])
            } catch (error) {
                console.error('Failed to load asset:', error)
            } finally {
                setLoading(false)
            }
        }

        loadAsset()
    }, [assetId])

    // Generate new portrait/background using Doubao
    const handleGenerate = async () => {
        if (!assetId) return

        setGenerating(true)
        try {
            const result = await assetsApi.generateImage(assetId)
            if (result.success) {
                // Reload asset to get new image
                const data = await assetsApi.get(assetId)
                setAsset(data)
                onAssetUpdated?.()
            } else {
                console.error('Generation failed:', result.error)
                alert('生成失败: ' + result.error)
            }
        } catch (error) {
            console.error('Generate error:', error)
            alert('生成出错: ' + (error instanceof Error ? error.message : '未知错误'))
        } finally {
            setGenerating(false)
        }
    }

    // Handle manual upload
    const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (!file || !assetId) return

        setLoading(true)
        try {
            const result = await assetsApi.uploadImage(assetId, file)
            if (result.success) {
                const data = await assetsApi.get(assetId)
                setAsset(data)
                onAssetUpdated?.()
            } else {
                alert(`上传失败: ${result.error}`)
            }
        } catch (error) {
            console.error('Upload error:', error)
            alert('上传请求失败')
        } finally {
            setLoading(false)
        }
    }

    // Generate description using LLM
    const handleGenerateDescription = async () => {
        if (!assetId) return

        // Show loading
        const prevDesc = description
        setDescription('AI 正在思考描述...')

        try {
            const result = await assetsApi.generateDescription(assetId)
            if (result.success && result.description) {
                setDescription(result.description)
            } else {
                setDescription(prevDesc)
                alert(`生成描述失败: ${result.error}`)
            }
        } catch (error) {
            setDescription(prevDesc)
            console.error('Desc gen error:', error)
            alert('生成描述请求失败')
        }
    }

    // Save asset changes
    const handleSave = async () => {
        if (!assetId) return

        setSaving(true)
        try {
            await assetsApi.update(assetId, {
                name,
                description,
                data_json: {
                    ...asset?.data_json,
                    appearance_traits: traits,
                },
            })
            onAssetUpdated?.()
            onClose()
        } catch (error) {
            console.error('Save error:', error)
            alert('保存失败')
        } finally {
            setSaving(false)
        }
    }

    // Add trait
    const handleAddTrait = () => {
        if (newTrait.trim() && !traits.includes(newTrait.trim())) {
            setTraits([...traits, newTrait.trim()])
            setNewTrait('')
        }
    }

    // Remove trait
    const handleRemoveTrait = (trait: string) => {
        setTraits(traits.filter((t) => t !== trait))
    }

    // Get main image
    const mainImage = asset?.thumbnail_url ||
        asset?.data_json?.reference_images?.[0] ||
        asset?.data_json?.anchor_image

    // Get reference images (excluding main)
    const referenceImages = asset?.data_json?.reference_images?.filter(
        (img) => img !== mainImage
    ) || []

    const isCharacter = assetType === 'character' || asset?.type === 'character'

    return (
        <Dialog open={!!assetId} onOpenChange={() => onClose()}>
            <DialogContent className="max-w-3xl h-[600px] p-0 gap-0 bg-zinc-900 border-white/10">
                <DialogHeader className="p-4 pb-0">
                    <DialogTitle className="flex items-center gap-2">
                        {isCharacter ? (
                            <User className="w-5 h-5 text-primary" />
                        ) : (
                            <Map className="w-5 h-5 text-primary" />
                        )}
                        {loading ? '加载中...' : '资产详情'}
                    </DialogTitle>
                </DialogHeader>

                {loading ? (
                    <div className="flex-1 flex items-center justify-center">
                        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                    </div>
                ) : !asset ? (
                    <div className="flex-1 flex items-center justify-center">
                        <p className="text-muted-foreground">资产未找到</p>
                    </div>
                ) : (
                    <div className="flex flex-1 overflow-hidden">
                        {/* Left: Main Image */}
                        <div className="w-1/2 p-4 flex flex-col">
                            <div className="flex-1 relative rounded-lg overflow-hidden bg-zinc-800 border border-white/5">
                                {mainImage ? (
                                    <img
                                        src={mainImage}
                                        alt={asset.name}
                                        className="w-full h-full object-contain"
                                    />
                                ) : (
                                    <div className="w-full h-full flex flex-col items-center justify-center text-muted-foreground">
                                        {isCharacter ? (
                                            <User className="w-16 h-16 opacity-20" />
                                        ) : (
                                            <Map className="w-16 h-16 opacity-20" />
                                        )}
                                        <p className="mt-4 text-sm">暂无参考图</p>
                                        <div className="flex gap-2 mt-4">
                                            <Button
                                                size="sm"
                                                className="gap-2"
                                                onClick={handleGenerate}
                                                disabled={generating}
                                            >
                                                {generating ? (
                                                    <Loader2 className="w-4 h-4 animate-spin" />
                                                ) : (
                                                    <Sparkles className="w-4 h-4" />
                                                )}
                                                AI 生成
                                            </Button>
                                            <div className="relative">
                                                <input
                                                    type="file"
                                                    id="upload-asset-empty"
                                                    className="hidden"
                                                    accept="image/*"
                                                    onChange={handleUpload}
                                                />
                                                <Button
                                                    size="sm"
                                                    variant="secondary"
                                                    className="gap-2"
                                                    disabled={loading}
                                                    onClick={() => document.getElementById('upload-asset-empty')?.click()}
                                                >
                                                    <ImagePlus className="w-4 h-4" />
                                                    上传
                                                </Button>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* Generate overlay button */}
                                {mainImage && (
                                    <div className="absolute bottom-3 right-3 flex gap-2">
                                        <div className="relative">
                                            <input
                                                type="file"
                                                id="upload-asset-overlay"
                                                className="hidden"
                                                accept="image/*"
                                                onChange={handleUpload}
                                            />
                                            <Button
                                                size="sm"
                                                variant="secondary"
                                                className="gap-2 bg-black/50 backdrop-blur hover:bg-black/70"
                                                onClick={() => document.getElementById('upload-asset-overlay')?.click()}
                                            >
                                                <ImagePlus className="w-4 h-4" />
                                            </Button>
                                        </div>
                                        <Button
                                            size="sm"
                                            variant="secondary"
                                            className="gap-2 bg-black/50 backdrop-blur hover:bg-black/70"
                                            onClick={handleGenerate}
                                            disabled={generating}
                                        >
                                            {generating ? (
                                                <Loader2 className="w-4 h-4 animate-spin" />
                                            ) : (
                                                <RefreshCw className="w-4 h-4" />
                                            )}
                                            重新生成
                                        </Button>
                                    </div>
                                )}
                            </div>

                            {/* Reference images */}
                            {referenceImages.length > 0 && (
                                <div className="mt-3">
                                    <p className="text-xs text-muted-foreground mb-2">参考图</p>
                                    <div className="flex gap-2 overflow-x-auto">
                                        {referenceImages.map((img, idx) => (
                                            <img
                                                key={idx}
                                                src={img}
                                                alt={`参考图 ${idx + 1}`}
                                                className="w-16 h-16 rounded object-cover border border-white/10 cursor-pointer hover:border-primary transition-colors"
                                            />
                                        ))}
                                        <div className="w-16 h-16 rounded border border-dashed border-white/20 flex items-center justify-center cursor-pointer hover:border-white/40 transition-colors">
                                            <Plus className="w-5 h-5 text-muted-foreground" />
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Right: Details */}
                        <ScrollArea className="w-1/2 border-l border-white/5">
                            <div className="p-4 space-y-4">
                                {/* Name */}
                                <div>
                                    <label className="text-xs text-muted-foreground mb-1 block">
                                        名称
                                    </label>
                                    <Input
                                        value={name}
                                        onChange={(e) => setName(e.target.value)}
                                        className="bg-zinc-800 border-white/10"
                                    />
                                </div>

                                {/* Description */}
                                <div>
                                    <div className="flex items-center justify-between mb-1">
                                        <label className="text-xs text-muted-foreground block">
                                            描述
                                        </label>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="h-5 px-2 text-[10px] text-emerald-500 hover:text-emerald-400 hover:bg-emerald-500/10"
                                            onClick={handleGenerateDescription}
                                        >
                                            <Sparkles className="w-3 h-3 mr-1" />
                                            AI 完善描述
                                        </Button>
                                    </div>
                                    <Textarea
                                        value={description}
                                        onChange={(e) => setDescription(e.target.value)}
                                        placeholder={isCharacter ? '角色背景、性格特点...' : '场景描述、氛围...'}
                                        className="bg-zinc-800 border-white/10 min-h-[80px]"
                                    />
                                </div>

                                {/* Appearance Traits */}
                                <div>
                                    <label className="text-xs text-muted-foreground mb-1 block">
                                        {isCharacter ? '外貌特征' : '场景特征'}
                                    </label>
                                    <div className="flex flex-wrap gap-2 mb-2">
                                        {traits.map((trait) => (
                                            <Badge
                                                key={trait}
                                                variant="secondary"
                                                className="gap-1 cursor-pointer hover:bg-destructive/20"
                                                onClick={() => handleRemoveTrait(trait)}
                                            >
                                                {trait}
                                                <X className="w-3 h-3" />
                                            </Badge>
                                        ))}
                                    </div>
                                    <div className="flex gap-2">
                                        <Input
                                            value={newTrait}
                                            onChange={(e) => setNewTrait(e.target.value)}
                                            placeholder="添加特征..."
                                            className="bg-zinc-800 border-white/10 flex-1"
                                            onKeyDown={(e) => {
                                                if (e.key === 'Enter') {
                                                    e.preventDefault()
                                                    handleAddTrait()
                                                }
                                            }}
                                        />
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={handleAddTrait}
                                            className="border-white/10"
                                        >
                                            <Plus className="w-4 h-4" />
                                        </Button>
                                    </div>
                                </div>

                                {/* FaceID Status (for characters) */}
                                {isCharacter && (
                                    <div>
                                        <label className="text-xs text-muted-foreground mb-1 block">
                                            FaceID 状态
                                        </label>
                                        <div className="flex items-center gap-2">
                                            {asset.data_json?.face_embedding ? (
                                                <Badge variant="default" className="bg-green-600">
                                                    已提取
                                                </Badge>
                                            ) : (
                                                <Badge variant="outline" className="text-muted-foreground">
                                                    未提取
                                                </Badge>
                                            )}
                                            <span className="text-xs text-muted-foreground">
                                                {asset.data_json?.face_embedding
                                                    ? '可用于人物一致性控制'
                                                    : '生成定妆照后自动提取'}
                                            </span>
                                        </div>
                                    </div>
                                )}

                                {/* Actions */}
                                <div className="flex gap-2 pt-4">
                                    <Button
                                        variant="outline"
                                        className="flex-1 border-white/10"
                                        onClick={onClose}
                                    >
                                        取消
                                    </Button>
                                    <Button
                                        className="flex-1"
                                        onClick={handleSave}
                                        disabled={saving}
                                    >
                                        {saving ? (
                                            <Loader2 className="w-4 h-4 animate-spin mr-2" />
                                        ) : null}
                                        保存
                                    </Button>
                                </div>
                            </div>
                        </ScrollArea>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    )
}
