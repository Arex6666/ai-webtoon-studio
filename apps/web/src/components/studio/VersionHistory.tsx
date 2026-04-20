'use client'

import { useState, useEffect, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { apiGet, apiPost } from '@/lib/api/client'

interface SnapshotItem {
  id: string
  snapshot_type: string
  reason: string | null
  content_hash: string | null
  parent_id: string | null
  created_at: string | null
}

interface VersionHistoryProps {
  entityType: string
  entityId: string
}

const TYPE_ICONS: Record<string, string> = {
  auto: 'A',
  manual: 'M',
  before_patch: 'P',
  milestone: 'S',
}

export function VersionHistory({ entityType, entityId }: VersionHistoryProps) {
  const [snapshots, setSnapshots] = useState<SnapshotItem[]>([])
  const [loading, setLoading] = useState(false)
  const [rolling, setRolling] = useState<string | null>(null)

  const fetchSnapshots = useCallback(async () => {
    if (!entityType || !entityId) return
    setLoading(true)
    try {
      const data = await apiGet(`/api/v1/versions/${entityType}/${entityId}/snapshots?limit=30`) as { snapshots?: SnapshotItem[] }
      setSnapshots(data.snapshots || [])
    } catch (e) {
      console.error('Failed to fetch snapshots:', e)
    } finally {
      setLoading(false)
    }
  }, [entityType, entityId])

  useEffect(() => {
    fetchSnapshots()
  }, [fetchSnapshots])

  const handleRollback = async (snapshotId: string) => {
    setRolling(snapshotId)
    try {
      await apiPost(`/api/v1/versions/${entityType}/${entityId}/rollback/${snapshotId}`, {})
      await fetchSnapshots()
    } catch (e) {
      console.error('Rollback failed:', e)
    } finally {
      setRolling(null)
    }
  }

  if (loading && snapshots.length === 0) {
    return <div className="p-3 text-xs text-muted-foreground">Loading versions...</div>
  }

  if (snapshots.length === 0) {
    return <div className="p-3 text-xs text-muted-foreground">No version history yet.</div>
  }

  return (
    <div className="flex flex-col gap-1 p-2">
      <div className="mb-1 text-xs font-medium text-foreground">Version History</div>
      <div className="flex flex-col gap-0.5">
        {snapshots.map((snap, idx) => (
          <div
            key={snap.id}
            className="flex items-center gap-2 rounded px-2 py-1.5 text-xs hover:bg-accent"
          >
            <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded bg-muted text-[10px] font-bold">
              {TYPE_ICONS[snap.snapshot_type] || '?'}
            </span>
            <div className="flex-1 min-w-0">
              <div className="truncate text-foreground">
                {snap.reason || snap.snapshot_type}
              </div>
              <div className="text-[10px] text-muted-foreground">
                {snap.created_at
                  ? new Date(snap.created_at).toLocaleString()
                  : 'Unknown time'}
              </div>
            </div>
            {idx > 0 && (
              <Button
                size="sm"
                variant="ghost"
                className="h-6 px-2 text-[10px]"
                disabled={rolling === snap.id}
                onClick={() => handleRollback(snap.id)}
              >
                {rolling === snap.id ? '...' : 'Rollback'}
              </Button>
            )}
            {idx === 0 && (
              <span className="text-[10px] text-green-600 font-medium">Current</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
