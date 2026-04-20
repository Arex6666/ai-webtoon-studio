'use client'

import { useState, useEffect, useCallback } from 'react'
import { apiGet } from '@/lib/api/client'

interface ProviderCost {
  provider: string
  cost: number
}

interface ChapterCost {
  chapter_id: string
  cost: number
}

interface CostTrendPoint {
  date: string | null
  cost: number
  cumulative: number
  provider: string
  type: string
}

interface ChapterSummary {
  chapter_id: string
  total_cost: number
  total_estimated: number
  total_jobs: number
  succeeded: number
  failed: number
  needs_fix: number
  by_provider: Record<string, number>
  by_type: Record<string, number>
}

interface ProjectSummary {
  project_id: string
  total_cost: number
  total_jobs: number
  by_chapter: Record<string, number>
}

interface CostDashboardProps {
  projectId: string
  chapterId?: string
}

export function CostDashboard({ projectId, chapterId }: CostDashboardProps) {
  const [projectSummary, setProjectSummary] = useState<ProjectSummary | null>(null)
  const [chapterSummary, setChapterSummary] = useState<ChapterSummary | null>(null)
  const [trend, setTrend] = useState<CostTrendPoint[]>([])
  const [loading, setLoading] = useState(false)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const [projData, trendData] = await Promise.all([
        apiGet(`/api/v1/chapters/project/${projectId}/cost-summary`),
        apiGet(`/api/v1/chapters/project/${projectId}/cost-trend`),
      ])
      setProjectSummary(projData as ProjectSummary)
      setTrend(((trendData as Record<string, unknown>).trend as CostTrendPoint[]) || [])

      if (chapterId) {
        const chapData = await apiGet(`/api/v1/chapters/${chapterId}/cost-summary`)
        setChapterSummary(chapData as ChapterSummary)
      }
    } catch (e) {
      console.error('Failed to fetch cost data:', e)
    } finally {
      setLoading(false)
    }
  }, [projectId, chapterId])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  if (loading && !projectSummary) {
    return <div className="p-4 text-sm text-muted-foreground">Loading cost data...</div>
  }

  // Aggregate provider costs from trend data
  const providerCosts: Record<string, number> = {}
  for (const p of trend) {
    const prov = p.provider || 'unknown'
    providerCosts[prov] = (providerCosts[prov] || 0) + p.cost
  }
  const providerEntries = Object.entries(providerCosts).sort((a, b) => b[1] - a[1])
  const maxProviderCost = Math.max(...providerEntries.map(([, v]) => v), 0.01)

  // Chapter breakdown
  const chapterEntries = projectSummary
    ? Object.entries(projectSummary.by_chapter).sort((a, b) => b[1] - a[1])
    : []
  const maxChapterCost = Math.max(...chapterEntries.map(([, v]) => v), 0.01)

  return (
    <div className="flex flex-col gap-4 p-4">
      <h2 className="text-sm font-semibold text-foreground">Cost Dashboard</h2>

      {/* Project Summary */}
      {projectSummary && (
        <div className="rounded border p-3">
          <div className="mb-2 text-xs font-medium text-muted-foreground">Project Total</div>
          <div className="flex gap-4">
            <div>
              <div className="text-2xl font-bold">${projectSummary.total_cost.toFixed(4)}</div>
              <div className="text-[10px] text-muted-foreground">{projectSummary.total_jobs} jobs</div>
            </div>
          </div>
        </div>
      )}

      {/* Chapter Summary */}
      {chapterSummary && (
        <div className="rounded border p-3">
          <div className="mb-2 text-xs font-medium text-muted-foreground">Chapter Cost</div>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div>
              <div className="font-bold">${chapterSummary.total_cost.toFixed(4)}</div>
              <div className="text-[10px] text-muted-foreground">Actual</div>
            </div>
            <div>
              <div className="font-bold">${chapterSummary.total_estimated.toFixed(4)}</div>
              <div className="text-[10px] text-muted-foreground">Estimated</div>
            </div>
            <div>
              <div className="font-bold">{chapterSummary.total_jobs}</div>
              <div className="text-[10px] text-muted-foreground">Jobs</div>
            </div>
          </div>
          <div className="mt-2 flex gap-2 text-[10px]">
            <span className="text-green-600">{chapterSummary.succeeded} passed</span>
            <span className="text-red-600">{chapterSummary.failed} failed</span>
            <span className="text-yellow-600">{chapterSummary.needs_fix} needs fix</span>
          </div>
        </div>
      )}

      {/* Cost by Provider (bar chart) */}
      <div className="rounded border p-3">
        <div className="mb-2 text-xs font-medium text-muted-foreground">Cost by Provider</div>
        <div className="flex flex-col gap-1">
          {providerEntries.map(([provider, cost]) => (
            <div key={provider} className="flex items-center gap-2 text-xs">
              <span className="w-16 truncate text-muted-foreground">{provider}</span>
              <div className="flex-1 h-4 bg-muted rounded overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded"
                  style={{ width: `${(cost / maxProviderCost) * 100}%` }}
                />
              </div>
              <span className="w-16 text-right font-mono">${cost.toFixed(4)}</span>
            </div>
          ))}
          {providerEntries.length === 0 && (
            <div className="text-[10px] text-muted-foreground">No data</div>
          )}
        </div>
      </div>

      {/* Cost by Chapter (bar chart) */}
      {chapterEntries.length > 0 && (
        <div className="rounded border p-3">
          <div className="mb-2 text-xs font-medium text-muted-foreground">Cost by Chapter</div>
          <div className="flex flex-col gap-1">
            {chapterEntries.map(([chId, cost]) => (
              <div key={chId} className="flex items-center gap-2 text-xs">
                <span className="w-20 truncate text-muted-foreground">{chId.slice(0, 8)}</span>
                <div className="flex-1 h-4 bg-muted rounded overflow-hidden">
                  <div
                    className="h-full bg-green-500 rounded"
                    style={{ width: `${(cost / maxChapterCost) * 100}%` }}
                  />
                </div>
                <span className="w-16 text-right font-mono">${cost.toFixed(4)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Cost Trend */}
      {trend.length > 0 && (
        <div className="rounded border p-3">
          <div className="mb-2 text-xs font-medium text-muted-foreground">Cost Trend</div>
          <div className="flex items-end gap-px h-24">
            {trend.slice(-50).map((point, idx) => {
              const maxCum = trend[trend.length - 1]?.cumulative || 1
              const height = (point.cumulative / maxCum) * 100
              return (
                <div
                  key={idx}
                  className="flex-1 bg-blue-400 rounded-t min-w-[2px]"
                  style={{ height: `${height}%` }}
                  title={`$${point.cumulative.toFixed(4)} (${point.date || '?'})`}
                />
              )
            })}
          </div>
          <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
            <span>{trend[0]?.date?.slice(0, 10) || ''}</span>
            <span>Cumulative: ${trend[trend.length - 1]?.cumulative.toFixed(4)}</span>
          </div>
        </div>
      )}
    </div>
  )
}
