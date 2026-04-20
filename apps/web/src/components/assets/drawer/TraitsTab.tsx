'use client'

import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import type { Asset } from '@/lib/api/types'

export interface TraitsTabProps {
    asset: Asset
    draft: Partial<Asset>
    onChange: (draft: Partial<Asset>) => void
}

export function TraitsTab({ asset, draft, onChange }: TraitsTabProps) {
    const dataJson: Record<string, unknown> = {
        ...((asset as any).data_json ?? {}),
        ...((draft as any).data_json ?? {}),
    }
    const update = (patch: Record<string, unknown>) => {
        onChange({ ...draft, data_json: { ...dataJson, ...patch } } as Partial<Asset>)
    }

    if (asset.type === 'character') {
        return (
            <div className="space-y-4">
                <div>
                    <Label>外貌特征（逗号分隔）</Label>
                    <Input
                        value={(dataJson.appearance_traits as string[] | undefined)?.join(',') ?? ''}
                        onChange={(e) => update({
                            appearance_traits: e.target.value.split(',').map(s => s.trim()).filter(Boolean),
                        })}
                    />
                </div>
                <div>
                    <Label>服饰备注</Label>
                    <Textarea
                        rows={2}
                        value={(dataJson.wardrobe_notes as string) ?? ''}
                        onChange={(e) => update({ wardrobe_notes: e.target.value })}
                    />
                </div>
                <div>
                    <Label>性格特征（逗号分隔）</Label>
                    <Input
                        value={(dataJson.personality_traits as string[] | undefined)?.join(',') ?? ''}
                        onChange={(e) => update({
                            personality_traits: e.target.value.split(',').map(s => s.trim()).filter(Boolean),
                        })}
                    />
                </div>
            </div>
        )
    }

    if (asset.type === 'scene') {
        return (
            <div className="space-y-4">
                <div>
                    <Label>时间</Label>
                    <Input
                        value={(dataJson.time_of_day as string) ?? ''}
                        onChange={(e) => update({ time_of_day: e.target.value })}
                    />
                </div>
                <div>
                    <Label>天气</Label>
                    <Input
                        value={(dataJson.weather as string) ?? ''}
                        onChange={(e) => update({ weather: e.target.value })}
                    />
                </div>
                <div>
                    <Label>氛围</Label>
                    <Input
                        value={(dataJson.mood as string) ?? ''}
                        onChange={(e) => update({ mood: e.target.value })}
                    />
                </div>
            </div>
        )
    }

    return (
        <p className="text-sm text-muted-foreground">
            此类型资产暂无 Traits 字段。
        </p>
    )
}
