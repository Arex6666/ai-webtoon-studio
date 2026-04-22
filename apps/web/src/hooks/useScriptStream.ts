/**
 * Hook to consume the /agent/episode/{N}/script/stream SSE endpoint.
 *
 * Returns phase, percent, text-so-far, final data, error, and start()/cancel().
 */
'use client'

import { useCallback, useRef, useState } from 'react'

export interface ScriptStreamEvent {
    phase?: 'analyzing' | 'writing' | 'finalizing'
    pct?: number
    text?: string
}

export interface ScriptStreamState {
    status: 'idle' | 'streaming' | 'done' | 'error'
    phase: 'analyzing' | 'writing' | 'finalizing' | null
    pct: number
    data: any | null
    error: string | null
}

export function useScriptStream(apiBaseUrl: string) {
    const [state, setState] = useState<ScriptStreamState>({
        status: 'idle', phase: null, pct: 0, data: null, error: null,
    })
    const abortRef = useRef<AbortController | null>(null)

    const cancel = useCallback(() => {
        abortRef.current?.abort()
        abortRef.current = null
        setState(s => ({ ...s, status: 'idle' }))
    }, [])

    const start = useCallback(async (
        episodeNumber: number,
        payload: Record<string, unknown>,
    ) => {
        cancel()
        const controller = new AbortController()
        abortRef.current = controller

        setState({ status: 'streaming', phase: null, pct: 0, data: null, error: null })

        try {
            const resp = await fetch(
                `${apiBaseUrl}/api/v1/agent/episode/${episodeNumber}/script/stream`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                    signal: controller.signal,
                },
            )
            if (!resp.ok || !resp.body) {
                throw new Error(`SSE connection failed (${resp.status})`)
            }

            const reader = resp.body.getReader()
            const decoder = new TextDecoder()
            let buffer = ''

            while (true) {
                const { value, done } = await reader.read()
                if (done) break
                buffer += decoder.decode(value, { stream: true })

                let idx
                while ((idx = buffer.indexOf('\n\n')) !== -1) {
                    const frame = buffer.slice(0, idx)
                    buffer = buffer.slice(idx + 2)
                    const parsed = parseFrame(frame)
                    if (!parsed) continue

                    if (parsed.event === 'progress') {
                        setState(s => ({
                            ...s,
                            phase: parsed.data.phase ?? s.phase,
                            pct: parsed.data.pct ?? s.pct,
                        }))
                    } else if (parsed.event === 'chunk') {
                        setState(s => ({
                            ...s,
                            data: { ...(s.data ?? {}), script: (s.data?.script ?? '') + (parsed.data.text ?? '') },
                        }))
                    } else if (parsed.event === 'done') {
                        setState(s => ({ ...s, status: 'done', pct: 100, data: parsed.data }))
                        abortRef.current = null
                        return
                    } else if (parsed.event === 'error') {
                        setState(s => ({ ...s, status: 'error', error: parsed.data.message ?? 'unknown' }))
                        abortRef.current = null
                        return
                    }
                }
            }
        } catch (e) {
            if ((e as any)?.name === 'AbortError') return
            setState(s => ({ ...s, status: 'error', error: e instanceof Error ? e.message : String(e) }))
        } finally {
            abortRef.current = null
        }
    }, [apiBaseUrl, cancel])

    return { ...state, start, cancel }
}

function parseFrame(frame: string): { event: string; data: any } | null {
    const lines = frame.split('\n')
    let event = 'message'
    let dataStr = ''
    for (const line of lines) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) dataStr += line.slice(5).trim()
    }
    if (!dataStr) return null
    try {
        return { event, data: JSON.parse(dataStr) }
    } catch {
        return { event, data: dataStr }
    }
}
