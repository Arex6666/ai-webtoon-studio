'use client'

import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { AlertTriangle } from 'lucide-react'

export interface CommitWarningsDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    warnings: string[]
}

export function CommitWarningsDialog({ open, onOpenChange, warnings }: CommitWarningsDialogProps) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-lg">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <AlertTriangle className="w-5 h-5 text-amber-400" />
                        提交时的警告
                    </DialogTitle>
                </DialogHeader>
                <ScrollArea className="max-h-[300px] pr-4">
                    <ul className="space-y-2 text-sm">
                        {warnings.map((w, i) => (
                            <li key={i} className="text-zinc-400 pl-4 border-l border-amber-500/30">
                                {w}
                            </li>
                        ))}
                    </ul>
                </ScrollArea>
                <p className="text-xs text-zinc-500 mt-2">
                    Chapter 已创建，但部分数据未能完全传输。你可以在 Studio 里手动补全。
                </p>
            </DialogContent>
        </Dialog>
    )
}
