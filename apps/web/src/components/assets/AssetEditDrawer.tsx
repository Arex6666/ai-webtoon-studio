'use client'

import { useEffect, useState } from 'react'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { assetsApi } from '@/lib/api/services'
import type { Asset } from '@/lib/api/types'

import { BasicTab } from './drawer/BasicTab'
import { TraitsTab } from './drawer/TraitsTab'
import { UsageTab } from './drawer/UsageTab'
import { VersionsTab } from './drawer/VersionsTab'

export interface AssetEditDrawerProps {
    assetId: string | null
    onClose: () => void
    onSaved?: (asset: Asset) => void
}

export function AssetEditDrawer({ assetId, onClose, onSaved }: AssetEditDrawerProps) {
    const [asset, setAsset] = useState<Asset | null>(null)
    const [draft, setDraft] = useState<Partial<Asset>>({})
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [tab, setTab] = useState<'basic' | 'traits' | 'versions' | 'usage'>('basic')

    useEffect(() => {
        if (!assetId) {
            setAsset(null)
            setDraft({})
            return
        }
        let alive = true
        assetsApi.get(assetId).then((a) => { if (alive) { setAsset(a); setDraft({}) } })
        return () => { alive = false }
    }, [assetId])

    const dirty = Object.keys(draft).length > 0

    const handleSave = async () => {
        if (!asset || !dirty) return
        setSaving(true)
        setError(null)
        try {
            const updated = await assetsApi.update(asset.id, draft)
            onSaved?.(updated)
            setAsset(updated)
            setDraft({})
        } catch (e) {
            setError(e instanceof Error ? e.message : String(e))
        } finally {
            setSaving(false)
        }
    }

    const handleClose = () => {
        if (dirty && !confirm('有未保存的改动，确定关闭？')) return
        onClose()
    }

    return (
        <Sheet open={!!assetId} onOpenChange={(o) => { if (!o) handleClose() }}>
            <SheetContent side="right" className="w-[560px] sm:max-w-[560px] flex flex-col p-0">
                <SheetHeader className="px-6 py-4 border-b border-white/10">
                    <div className="flex items-center gap-3">
                        {asset?.thumbnail_url ? (
                            <img src={asset.thumbnail_url} alt={asset.name}
                                className="w-10 h-10 rounded object-cover" />
                        ) : <div className="w-10 h-10 rounded bg-muted/40" />}
                        <div className="flex-1">
                            <SheetTitle className="truncate">{asset?.name ?? '…'}</SheetTitle>
                            {asset?.type && (
                                <Badge variant="outline" className="mt-1">{asset.type}</Badge>
                            )}
                        </div>
                    </div>
                </SheetHeader>

                <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)}
                    className="flex-1 flex flex-col overflow-hidden">
                    <TabsList className="mx-6 mt-4 justify-start">
                        <TabsTrigger value="basic">Basic</TabsTrigger>
                        <TabsTrigger value="traits">Traits</TabsTrigger>
                        <TabsTrigger value="versions">Versions</TabsTrigger>
                        <TabsTrigger value="usage">Usage</TabsTrigger>
                    </TabsList>
                    <div className="flex-1 overflow-y-auto px-6 py-4">
                        <TabsContent value="basic" className="mt-0">
                            {asset && <BasicTab asset={asset} draft={draft} onChange={setDraft} />}
                        </TabsContent>
                        <TabsContent value="traits" className="mt-0">
                            {asset && <TraitsTab asset={asset} draft={draft} onChange={setDraft} />}
                        </TabsContent>
                        <TabsContent value="versions" className="mt-0">
                            {asset && <VersionsTab assetId={asset.id} />}
                        </TabsContent>
                        <TabsContent value="usage" className="mt-0">
                            {asset && <UsageTab assetId={asset.id} />}
                        </TabsContent>
                    </div>
                </Tabs>

                <div className="border-t border-white/10 px-6 py-3 flex items-center justify-between">
                    <div className="text-xs text-muted-foreground">
                        {dirty ? `${Object.keys(draft).length} 项改动，未保存` : error ? (
                            <span className="text-red-400">{error}</span>
                        ) : '无改动'}
                    </div>
                    <div className="flex gap-2">
                        <Button variant="outline" onClick={handleClose} disabled={saving}>取消</Button>
                        <Button onClick={handleSave} disabled={!dirty || saving}>
                            {saving ? '保存中…' : '保存'}
                        </Button>
                    </div>
                </div>
            </SheetContent>
        </Sheet>
    )
}
