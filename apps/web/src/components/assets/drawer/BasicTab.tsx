'use client'

import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { assetsApi } from '@/lib/api/services'
import type { Asset } from '@/lib/api/types'

export interface BasicTabProps {
    asset: Asset
    draft: Partial<Asset>
    onChange: (draft: Partial<Asset>) => void
}

export function BasicTab({ asset, draft, onChange }: BasicTabProps) {
    const current = { ...asset, ...draft } as Asset & Record<string, unknown>

    const update = (patch: Partial<Asset>) => onChange({ ...draft, ...patch })

    const handleRegenerate = async () => {
        await assetsApi.regenerateReference(asset.id)
    }

    return (
        <div className="space-y-4">
            <div>
                <Label>名称</Label>
                <Input
                    value={(current.name as string) ?? ''}
                    onChange={(e) => update({ name: e.target.value } as Partial<Asset>)}
                />
            </div>
            <div>
                <Label>描述</Label>
                <Textarea
                    rows={4}
                    value={(current.description as string) ?? ''}
                    onChange={(e) => update({ description: e.target.value } as Partial<Asset>)}
                />
            </div>
            <div>
                <Label>Tags（逗号分隔）</Label>
                <Input
                    value={Array.isArray(current.tags) ? current.tags.join(',') : ''}
                    onChange={(e) => update({
                        tags: e.target.value.split(',').map(t => t.trim()).filter(Boolean),
                    } as Partial<Asset>)}
                />
            </div>
            <div>
                <Label>封面</Label>
                <div className="mt-2 flex items-center gap-3">
                    {asset.thumbnail_url ? (
                        <img src={asset.thumbnail_url} alt="" className="w-24 h-24 object-cover rounded" />
                    ) : <div className="w-24 h-24 rounded bg-muted/30" />}
                    <Button variant="outline" onClick={handleRegenerate}>重新生成参考图</Button>
                </div>
            </div>
        </div>
    )
}
