'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { jobApi, type JobStatus, type JobStatusResponse } from '@/lib/api/jobApi'
import { useStudioStore } from '@/lib/store/studioStore'

interface JobTrackerState {
  status: JobStatus
  progress: number
  message?: string
  agent?: string
  result?: Record<string, unknown>
  error?: string
  isComplete: boolean
}

const TERMINAL_STATUSES: JobStatus[] = ['succeeded', 'failed', 'canceled']
const POLL_INTERVAL = 2000

export function useJobTracker(jobId: string | null): JobTrackerState {
  const [state, setState] = useState<JobTrackerState>({
    status: 'queued',
    progress: 0,
    isComplete: false,
  })

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Listen to store's unified job state (populated by WS events)
  const storeJob = useStudioStore(s => jobId ? s.unifiedJobs[jobId] : null)

  // Only poll when WS is disconnected
  const wsConnected = useStudioStore(s => s.wsConnected ?? false)

  // Sync from store (WS-driven)
  useEffect(() => {
    if (!storeJob) return
    setState({
      status: storeJob.status as JobStatus,
      progress: storeJob.progress ?? 0,
      message: storeJob.message,
      agent: storeJob.agent,
      result: storeJob.result,
      error: storeJob.error,
      isComplete: TERMINAL_STATUSES.includes(storeJob.status as JobStatus),
    })
  }, [storeJob])

  const poll = useCallback(async () => {
    if (!jobId) return
    try {
      const res = await jobApi.get(jobId)
      setState({
        status: res.status,
        progress: res.progress,
        message: res.message,
        agent: res.agent,
        result: res.result,
        error: res.error,
        isComplete: TERMINAL_STATUSES.includes(res.status),
      })
      useStudioStore.getState().updateJob(jobId, {
        status: res.status,
        progress: res.progress,
        message: res.message,
        agent: res.agent,
        result: res.result,
        error: res.error,
      })
    } catch {
      // Silently retry on next interval
    }
  }, [jobId])

  useEffect(() => {
    if (!jobId || state.isComplete || wsConnected) {
      if (intervalRef.current) clearInterval(intervalRef.current)
      return
    }

    // Only poll when WS is disconnected
    intervalRef.current = setInterval(poll, POLL_INTERVAL)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [jobId, state.isComplete, wsConnected, poll])

  return state
}
