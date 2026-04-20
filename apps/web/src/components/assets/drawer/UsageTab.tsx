'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { assetsApi } from '@/lib/api/services'
import { Loader2 } from 'lucide-react'

export interface UsageTabProps {
    assetId: string
}

type Usage = Awaited<ReturnType<typeof assetsApi.getUsage>>

export function UsageTab({ assetId }: UsageTabProps) {
    const [data, setData] = useState<Usage | null>(null)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        let alive = true
        setData(null)
        setError(null)
        assetsApi.getUsage(assetId)
            .then((d) => { if (alive) setData(d) })
            .catch((e) => { if (alive) setError(e instanceof Error ? e.message : String(e)) })
        return () => { alive = false }
    }, [assetId])

    if (error) return <p className="text-sm text-red-400">加载失败：{error}</p>
    if (!data) return <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="w-4 h-4 animate-spin" /> 加载引用…
    </div>
    if (data.total_count === 0) return <p className="text-sm text-muted-foreground">此资产尚未被任何分镜引用。</p>

    return (
        <div className="space-y-2">
            <p className="text-xs text-muted-foreground">共 {data.total_count} 处引用</p>
            {data.references.map((ref) => (
                <Link
                    key={ref.panel_id}
                    href={`/projects/_/chapters/${ref.chapter_id}/studio?panel=${ref.panel_id}`}
                    className="flex items-center gap-3 p-2 rounded hover:bg-white/5"
                >
                    {ref.panel_preview_url ? (
                        <img src={ref.panel_preview_url} alt="" className="w-12 h-12 rounded object-cover" />
                    ) : <div className="w-12 h-12 rounded bg-muted/30" />}
                    <div className="flex-1 min-w-0">
                        <p className="truncate text-sm">{ref.chapter_title ?? ref.chapter_id}</p>
                        <p className="text-xs text-muted-foreground">Panel #{ref.panel_order}</p>
                    </div>
                </Link>
            ))}
        </div>
    )
}
