'use client'

import { Button } from '@/components/ui/button'
import { TemplateModal } from '../modals/TemplateModal'
import { BatchModal } from '../modals/BatchModal'
import { ExportModal } from '../modals/ExportModal'
import { Layers, GitBranch, Play, BarChart3, Package } from 'lucide-react'
import { useState } from 'react'

export function ChapterActions() {
    const [templateModalOpen, setTemplateModalOpen] = useState(false)
    const [batchModalOpen, setBatchModalOpen] = useState(false)
    const [exportModalOpen, setExportModalOpen] = useState(false)

    return (
        <>
            <div className="flex items-center gap-2">
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setTemplateModalOpen(true)}
                >
                    <Layers className="w-3.5 h-3.5 mr-1.5" />
                    模板
                </Button>

                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => { }}
                    disabled
                >
                    <GitBranch className="w-3.5 h-3.5 mr-1.5" />
                    版本
                </Button>

                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setBatchModalOpen(true)}
                >
                    <Play className="w-3.5 h-3.5 mr-1.5" />
                    批量生成
                </Button>

                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setExportModalOpen(true)}
                >
                    <Package className="w-3.5 h-3.5 mr-1.5" />
                    导出章节
                </Button>
            </div>

            <TemplateModal open={templateModalOpen} onOpenChange={setTemplateModalOpen} />
            <BatchModal open={batchModalOpen} onOpenChange={setBatchModalOpen} />
            <ExportModal open={exportModalOpen} onOpenChange={setExportModalOpen} />
        </>
    )
}
