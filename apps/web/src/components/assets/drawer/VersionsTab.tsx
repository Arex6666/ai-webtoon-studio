'use client'

export interface VersionsTabProps {
    assetId: string
}

export function VersionsTab({ assetId: _assetId }: VersionsTabProps) {
    return (
        <div className="py-8 text-center text-sm text-muted-foreground">
            <p>版本历史功能即将上线。</p>
            <p className="mt-1 text-xs">当前资产的所有渲染/修改会在此显示时间线。</p>
        </div>
    )
}
