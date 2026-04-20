'use client'

import { useStudioStore } from '@/lib/store/studioStore'
import type { RenderTier } from '@/lib/schema/job'

const TIER_INFO: Record<RenderTier, { label: string; desc: string; cost: string }> = {
  fast: { label: 'Preview', desc: '540p, 8 steps', cost: '0.2x' },
  normal: { label: 'Production', desc: '1080p, 20 steps', cost: '1.0x' },
  hero: { label: 'Hero', desc: '1440p, 40 steps', cost: '2.5x' },
}

export function TierSelector() {
  const defaultTier = useStudioStore((s) => s.defaultTier)
  const setDefaultTier = useStudioStore((s) => s.setDefaultTier)

  return (
    <div className="flex items-center gap-1.5">
      <span className="text-xs text-muted-foreground">Tier:</span>
      <select
        value={defaultTier}
        onChange={(e) => setDefaultTier(e.target.value as RenderTier)}
        className="h-7 rounded border border-border bg-background px-2 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
      >
        {(Object.keys(TIER_INFO) as RenderTier[]).map((tier) => (
          <option key={tier} value={tier}>
            {TIER_INFO[tier].label} ({TIER_INFO[tier].cost})
          </option>
        ))}
      </select>
      <span className="text-[10px] text-muted-foreground">
        {TIER_INFO[defaultTier].desc}
      </span>
    </div>
  )
}
