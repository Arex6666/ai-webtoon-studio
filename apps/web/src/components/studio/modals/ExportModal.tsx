'use client'

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Package, Check, AlertTriangle, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useToast } from '@/hooks/use-toast'
import { useParams } from 'next/navigation'

interface ExportModalProps {
    open: boolean
    onOpenChange: (open: boolean) => void
}

export function ExportModal({ open, onOpenChange }: ExportModalProps) {
    const params = useParams()
    const chapterId = params.chapterId as string
    const { toast } = useToast()

    const [isStarted, setIsStarted] = useState(false)

    // TODO: move to API hook
    const createExport = async () => {
        const response = await fetch(`/api/v1/exports`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chapter_id: chapterId,
                type: 'bundle',
                settings_json: {}
            })
        })
        if (!response.ok) throw new Error('Export failed')
        return response.json()
    }

    const mutation = useMutation({
        mutationFn: createExport,
        onSuccess: () => {
            setIsStarted(true)
            toast({
                title: '导出任务已开始',
                description: '请在任务控制台查看进度',
            })
            // Don't close immediately so user can see feedback
            setTimeout(() => onOpenChange(false), 1500)
        },
        onError: (error) => {
            toast({
                title: '启动失败',
                description: error.message,
                variant: 'destructive',
            })
        }
    })

    const handleExport = () => {
        mutation.mutate()
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-md">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Package className="w-5 h-5" />
                        发布章节 Bundle
                    </DialogTitle>
                    <DialogDescription>
                        将当前章节的所有资源打包为一个标准化的 ZIP 归档。
                        <br />
                        包含：高清大图、分层文件、排版信息、字体和复现元数据。
                    </DialogDescription>
                </DialogHeader>

                <div className="py-4">
                    <div className="bg-panel-hover p-4 rounded-lg text-sm space-y-2">
                        <div className="flex items-center gap-2 text-ink-muted">
                            <Check className="w-4 h-4 text-emerald-400" />
                            <span>自动检查资源完整性</span>
                        </div>
                        <div className="flex items-center gap-2 text-ink-muted">
                            <Check className="w-4 h-4 text-emerald-400" />
                            <span>生成 assets.json 版本锁定</span>
                        </div>
                        <div className="flex items-center gap-2 text-ink-muted">
                            <Check className="w-4 h-4 text-emerald-400" />
                            <span>包含完整生成历史 (Provenance)</span>
                        </div>
                        <div className="flex items-center gap-2 text-ink-muted">
                            <AlertTriangle className="w-4 h-4 text-yellow-400" />
                            <span>如果存在未通过 QA 的面板，将会包含警告</span>
                        </div>
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        取消
                    </Button>
                    <Button onClick={handleExport} disabled={mutation.isPending || isStarted}>
                        {mutation.isPending ? (
                            <>
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                启动中...
                            </>
                        ) : isStarted ? (
                            <>
                                <Check className="w-4 h-4 mr-2" />
                                已开始
                            </>
                        ) : (
                            <>
                                <Package className="w-4 h-4 mr-2" />
                                开始打包
                            </>
                        )}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
