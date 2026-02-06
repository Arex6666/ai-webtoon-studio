'use client'

import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Package, FileText, AlertTriangle, CheckCircle, XCircle, Image as ImageIcon } from 'lucide-react'
import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { cn } from '@/lib/utils'

interface BundlePreviewModalProps {
    exportId: string | null
    open: boolean
    onOpenChange: (open: boolean) => void
}

interface BundleManifest {
    spec_version: string
    bundle_id: string
    chapter: {
        chapter_title: string
        panel_count: number
    }
    panels: Array<{
        index: string
        panel_id: string
        online_preview_url?: string // Our new field
        preview_image: string // Relative path fallback
        qa_score: number | null
        needs_fix: boolean
        duration_sec: number | null
    }>
    qa_summary: {
        total_panels: number
        passed_panels: number
        failed_panels: number
        needs_fix_count: number
        avg_score: number | null
    } | null
    provenance: {
        generated_at: string
    }
}

export function BundlePreviewModal({ exportId, open, onOpenChange }: BundlePreviewModalProps) {
    const [selectedPanelIndex, setSelectedPanelIndex] = useState<string | null>(null)

    const { data: manifest, isLoading, error } = useQuery<BundleManifest>({
        queryKey: ['export-manifest', exportId],
        queryFn: async () => {
            if (!exportId) return null
            const res = await fetch(`/api/v1/exports/${exportId}/manifest`)
            if (!res.ok) throw new Error('Failed to fetch manifest')
            return res.json()
        },
        enabled: !!exportId && open
    })

    // Auto-select first panel on load
    useMemo(() => {
        if (manifest?.panels?.length && !selectedPanelIndex) {
            setSelectedPanelIndex(manifest.panels[0].index)
        }
    }, [manifest, selectedPanelIndex])

    const activePanel = useMemo(() =>
        manifest?.panels.find(p => p.index === selectedPanelIndex),
        [manifest, selectedPanelIndex]
    )

    if (!exportId) return null

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-5xl h-[85vh] flex flex-col p-0 gap-0 overflow-hidden">
                <DialogHeader className="px-6 py-4 border-b shrink-0 bg-panel-header">
                    <DialogTitle className="flex items-center gap-2">
                        <Package className="w-5 h-5 text-purple-400" />
                        Bundle Preview
                        {manifest && (
                            <span className="text-sm font-normal text-ink-muted ml-2">
                                {manifest.chapter.chapter_title} (v1)
                            </span>
                        )}
                        {isLoading && <span className="text-sm font-normal text-ink-muted ml-2">Loading...</span>}
                    </DialogTitle>
                </DialogHeader>

                <div className="flex flex-1 min-h-0">
                    {/* Left Sidebar: Panel List */}
                    <div className="w-64 border-r bg-panel-bg flex flex-col">
                        <div className="p-3 border-b text-xs font-medium text-ink-muted flex justify-between">
                            <span>PANELS ({manifest?.panels.length || 0})</span>
                            {manifest?.qa_summary && (
                                <span className={manifest.qa_summary.needs_fix_count > 0 ? "text-yellow-400" : "text-emerald-400"}>
                                    QA: {Math.round((manifest.qa_summary.avg_score || 0) * 100)}%
                                </span>
                            )}
                        </div>
                        <ScrollArea className="flex-1">
                            <div className="flex flex-col p-2 gap-1">
                                {manifest?.panels.map((panel) => (
                                    <button
                                        key={panel.index}
                                        onClick={() => setSelectedPanelIndex(panel.index)}
                                        className={cn(
                                            "flex items-center gap-3 p-2 rounded text-sm text-left transition-colors",
                                            selectedPanelIndex === panel.index
                                                ? "bg-purple-500/20 text-purple-100 ring-1 ring-purple-500/50"
                                                : "hover:bg-panel-hover text-ink-base"
                                        )}
                                    >
                                        <span className="font-mono text-ink-muted w-8 text-xs">{panel.index}</span>
                                        <div className="flex-1 truncate">
                                            {/* Status Dot */}
                                            <div className="flex items-center gap-2">
                                                {panel.needs_fix ? (
                                                    <AlertTriangle className="w-3 h-3 text-yellow-500" />
                                                ) : panel.qa_score !== null && panel.qa_score < 0.6 ? (
                                                    <XCircle className="w-3 h-3 text-red-500" />
                                                ) : (
                                                    <CheckCircle className="w-3 h-3 text-emerald-500/50" />
                                                )}
                                                <span className="text-xs">
                                                    {panel.qa_score !== null ? `Score: ${panel.qa_score.toFixed(2)}` : 'No QA'}
                                                </span>
                                            </div>
                                        </div>
                                    </button>
                                ))}
                            </div>
                        </ScrollArea>
                    </div>

                    {/* Right Content: Preview & Details */}
                    <div className="flex-1 bg-zinc-950/50 flex flex-col min-w-0">
                        {activePanel ? (
                            <div className="flex flex-col h-full">
                                {/* Image Preview Area */}
                                <div className="flex-1 flex items-center justify-center p-8 bg-zinc-900/50 relative overflow-hidden">
                                    {activePanel.online_preview_url ? (
                                        <img
                                            src={activePanel.online_preview_url}
                                            alt={`Panel ${activePanel.index}`}
                                            className="max-w-full max-h-full object-contain shadow-2xl rounded-sm"
                                        />
                                    ) : (
                                        <div className="flex flex-col items-center gap-3 text-ink-muted">
                                            <ImageIcon className="w-12 h-12 opacity-20" />
                                            <p>No preview image available</p>
                                            <code className="text-xs opacity-50">{activePanel.preview_image}</code>
                                        </div>
                                    )}
                                </div>

                                {/* Bottom Metadata Panel */}
                                <div className="h-48 border-t bg-panel-bg p-6 shrink-0 overflow-y-auto">
                                    <h3 className="text-sm font-medium mb-3 flex items-center gap-2">
                                        <FileText className="w-4 h-4 text-purple-400" />
                                        Panel {activePanel.index} Metadata
                                    </h3>
                                    <div className="grid grid-cols-3 gap-6 text-sm">
                                        <div className="space-y-1">
                                            <div className="text-xs text-ink-muted">Files</div>
                                            <div className="font-mono text-xs">{activePanel.preview_image}</div>
                                            <div className="font-mono text-xs text-ink-muted">UUID: {activePanel.panel_id.slice(0, 8)}...</div>
                                        </div>
                                        <div className="space-y-1">
                                            <div className="text-xs text-ink-muted">Quality Assurance</div>
                                            <div className="flex items-center gap-2">
                                                <Badge variant={activePanel.needs_fix ? "destructive" : "secondary"} className="h-5 text-[10px]">
                                                    {activePanel.needs_fix ? "Needs Fix" : "Pass"}
                                                </Badge>
                                                <span className="font-mono text-xs">Score: {activePanel.qa_score ?? '-'}</span>
                                            </div>
                                        </div>
                                        <div className="space-y-1">
                                            <div className="text-xs text-ink-muted">Duration</div>
                                            <div className="font-mono text-xs">{activePanel.duration_sec ?? '-'} sec</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="flex items-center justify-center h-full text-ink-muted">
                                Select a panel to view details
                            </div>
                        )}
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    )
}
