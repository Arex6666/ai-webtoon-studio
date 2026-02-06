'use client'

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useStudioStore } from "@/lib/store/studioStore"
import { assetsApi } from "@/lib/api/services"
import { useToast } from "@/hooks/use-toast"
import { Loader2, Upload } from "lucide-react"

const assetSchema = z.object({
    name: z.string().min(1, "名称不能为空"),
    description: z.string().optional(),
    type: z.enum(['character', 'scene', 'prop', 'style']),
    image: z.any().optional(),
})

type AssetFormValues = z.infer<typeof assetSchema>

interface CreateAssetModalProps {
    open: boolean
    onOpenChange: (open: boolean) => void
}

export function CreateAssetModal({ open, onOpenChange }: CreateAssetModalProps) {
    const { projectId, chapterId, setStudioData } = useStudioStore()
    const { toast } = useToast()
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [previewUrl, setPreviewUrl] = useState<string | null>(null)

    const form = useForm<AssetFormValues>({
        resolver: zodResolver(assetSchema),
        defaultValues: {
            name: '',
            description: '',
            type: 'character',
        }
    })

    // Watch type to change tabs
    const type = form.watch('type')

    const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (file) {
            form.setValue('image', file)
            const url = URL.createObjectURL(file)
            setPreviewUrl(url)
        }
    }

    const onSubmit = async (data: AssetFormValues) => {
        if (!projectId) return

        setIsSubmitting(true)
        try {
            // 1. Create asset record
            const asset = await assetsApi.create({
                project_id: projectId,
                name: data.name,
                description: data.description,
                type: data.type,
            })

            // 2. Upload image if selected
            if (data.image && data.image instanceof File) {
                if (data.type === 'character') {
                    const { identityApi } = await import('@/lib/api/services')
                    await identityApi.extractEmbedding(asset.id, [data.image])
                } else if (data.type === 'scene') {
                    const { sceneAnchorApi } = await import('@/lib/api/services')
                    await sceneAnchorApi.generateAnchor(asset.id, data.image)
                }
            }

            toast({
                title: "创建成功",
                description: `${data.name} 已添加到资产库`,
            })

            // Refresh studio
            if (chapterId) {
                const { chaptersApi } = await import('@/lib/api/services')
                const studioData = await chaptersApi.getStudio(chapterId)
                setStudioData(studioData)
            }

            onOpenChange(false)
            form.reset()
            setPreviewUrl(null)
        } catch (error) {
            console.error(error)
            toast({
                title: "创建失败",
                description: error instanceof Error ? error.message : "未知错误",
                variant: "destructive"
            })
        } finally {
            setIsSubmitting(false)
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-[425px] bg-zinc-950 border-white/10 text-zinc-100">
                <DialogHeader>
                    <DialogTitle>创建新资产</DialogTitle>
                </DialogHeader>

                <Tabs value={type} onValueChange={(v) => form.setValue('type', v as any)} className="w-full">
                    <TabsList className="w-full grid grid-cols-4 bg-zinc-900">
                        <TabsTrigger value="character">角色</TabsTrigger>
                        <TabsTrigger value="scene">场景</TabsTrigger>
                        <TabsTrigger value="prop">物品</TabsTrigger>
                        <TabsTrigger value="style">风格</TabsTrigger>
                    </TabsList>
                </Tabs>

                <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 mt-4">
                    <div className="space-y-2">
                        <Label>名称</Label>
                        <Input {...form.register('name')} placeholder="例如：主角小明, 教室背景" className="bg-zinc-900 border-white/10" />
                        {form.formState.errors.name && <p className="text-xs text-red-400">{form.formState.errors.name.message}</p>}
                    </div>

                    <div className="space-y-2">
                        <Label>描述 (可选)</Label>
                        <Textarea {...form.register('description')} placeholder="简要描述资产特征..." className="bg-zinc-900 border-white/10" />
                    </div>

                    <div className="space-y-2">
                        <Label>参考图 (可选)</Label>
                        <div className="flex items-center gap-4">
                            <div className="relative w-20 h-20 rounded-md border border-white/10 bg-zinc-900 flex items-center justify-center overflow-hidden shrink-0">
                                {previewUrl ? (
                                    <img src={previewUrl} alt="Preview" className="w-full h-full object-cover" />
                                ) : (
                                    <Upload className="w-6 h-6 text-zinc-700" />
                                )}
                                <Input
                                    type="file"
                                    accept="image/*"
                                    className="absolute inset-0 opacity-0 cursor-pointer"
                                    onChange={handleImageSelect}
                                />
                            </div>
                            <div className="text-xs text-zinc-500">
                                <p>点击左侧上传图片。</p>
                                <p>角色：将自动提取 FaceID</p>
                                <p>场景：将自动生成控制图</p>
                            </div>
                        </div>
                    </div>

                    <div className="flex justify-end gap-2 pt-2">
                        <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>取消</Button>
                        <Button type="submit" disabled={isSubmitting} className="bg-white text-black hover:bg-zinc-200">
                            {isSubmitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                            创建
                        </Button>
                    </div>
                </form>
            </DialogContent>
        </Dialog>
    )
}
