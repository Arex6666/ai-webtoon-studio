/**
 * useEpisodeTreeData
 *
 * Derives the EpisodeTree data from the DB (committed chapters) and the
 * conversation history (agent cards). For each episode it produces a Phase[]
 * with a status derived from what has been persisted so far.
 *
 * Derivation rules (per plan Task 17):
 *   - script:     'locked'  if the chapter exists (episode committed)
 *                 'draft'   if a panels card exists for this episode
 *                 'pending' otherwise
 *   - storyboard: 'locked'  if chapter exists
 *                 'draft'   if panels card exists
 *                 'pending' otherwise
 *   - assets:     'locked'  if characters + scenes + art_style cards all present
 *                 'draft'   if at least one of those cards is present
 *                 'pending' otherwise
 *   - render / qa / export: 'pending' (wired in later tasks)
 */
'use client'

import { useEffect, useState } from 'react'

import { chaptersApi, conversationsApi } from '@/lib/api/services'
import type { Conversation, ConversationMessage } from '@/lib/api/services'
import type { Episode, Phase, PhaseStatus } from '@/components/agent/EpisodeTree'

interface EpisodeCardSummary {
    hasPanels: boolean
    hasCharacters: boolean
    hasScenes: boolean
    hasArtStyle: boolean
    title?: string
}

interface UseEpisodeTreeDataResult {
    episodes: Episode[]
    loading: boolean
    error: string | null
    refresh: () => void
}

function buildPhases(
    chapterCommitted: boolean,
    summary: EpisodeCardSummary | undefined,
): Phase[] {
    const hasAnyAsset = !!summary && (summary.hasCharacters || summary.hasScenes || summary.hasArtStyle)
    const hasAllAssets = !!summary && summary.hasCharacters && summary.hasScenes && summary.hasArtStyle
    const hasPanels = !!summary && summary.hasPanels

    const scriptStatus: PhaseStatus = chapterCommitted ? 'locked' : hasPanels ? 'draft' : 'pending'
    const storyboardStatus: PhaseStatus = chapterCommitted ? 'locked' : hasPanels ? 'draft' : 'pending'
    const assetsStatus: PhaseStatus = hasAllAssets ? 'locked' : hasAnyAsset ? 'draft' : 'pending'

    return [
        { id: 'script', name: '剧本', status: scriptStatus },
        { id: 'storyboard', name: '分镜', status: storyboardStatus },
        { id: 'assets', name: '资产', status: assetsStatus },
        { id: 'render', name: '生成', status: 'pending' },
        { id: 'qa', name: '质检', status: 'pending' },
        { id: 'export', name: '成片', status: 'pending' },
    ]
}

function extractCard(msg: ConversationMessage): { type: string; episode_number?: number } | null {
    const entities = msg.entities_json
    if (!entities || typeof entities !== 'object') return null
    const card = (entities as Record<string, unknown>).card
    if (!card || typeof card !== 'object') return null
    const typed = card as { type?: string; episode_number?: number }
    if (!typed.type) return null
    return { type: typed.type, episode_number: typed.episode_number }
}

export function useEpisodeTreeData(projectId: string | null | undefined): UseEpisodeTreeDataResult {
    const [episodes, setEpisodes] = useState<Episode[]>([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [tick, setTick] = useState(0)

    useEffect(() => {
        if (!projectId) {
            setEpisodes([])
            return
        }

        let cancelled = false
        const run = async () => {
            setLoading(true)
            setError(null)
            try {
                // 1. Committed chapters -> episode_number map
                const chaptersResp = await chaptersApi.list(projectId)
                const chapters = chaptersResp.items || []

                const committedByEpisode = new Map<number, { title: string; chapterId: string }>()
                for (const ch of chapters) {
                    const source = (ch.layout_json as unknown as { source?: { type?: string; episode_number?: number } } | undefined)?.source
                    if (source?.type === 'agent' && typeof source.episode_number === 'number') {
                        committedByEpisode.set(source.episode_number, {
                            title: ch.title,
                            chapterId: ch.id,
                        })
                    }
                }

                // 2. Conversations -> per-episode card summaries
                const conversations: Conversation[] = await conversationsApi.listByProject(projectId, 100, 0)

                const summaryByEpisode = new Map<number, EpisodeCardSummary>()
                const conversationAssetsByEpisode = new Map<number, { hasCharacters: boolean; hasScenes: boolean; hasArtStyle: boolean }>()

                for (const conv of conversations) {
                    let messages: ConversationMessage[] = []
                    try {
                        messages = await conversationsApi.getMessages(conv.id, 200, 0)
                    } catch {
                        continue
                    }

                    // Track conversation-wide asset cards (no episode_number).
                    let convHasCharacters = false
                    let convHasScenes = false
                    let convHasArtStyle = false

                    for (const msg of messages) {
                        const card = extractCard(msg)
                        if (!card) continue

                        if (card.type === 'panels' && typeof card.episode_number === 'number') {
                            const ep = card.episode_number
                            const prev = summaryByEpisode.get(ep) || {
                                hasPanels: false,
                                hasCharacters: false,
                                hasScenes: false,
                                hasArtStyle: false,
                            }
                            summaryByEpisode.set(ep, { ...prev, hasPanels: true })
                        } else if (card.type === 'characters') {
                            if (typeof card.episode_number === 'number') {
                                const ep = card.episode_number
                                const prev = summaryByEpisode.get(ep) || {
                                    hasPanels: false,
                                    hasCharacters: false,
                                    hasScenes: false,
                                    hasArtStyle: false,
                                }
                                summaryByEpisode.set(ep, { ...prev, hasCharacters: true })
                            } else {
                                convHasCharacters = true
                            }
                        } else if (card.type === 'scenes') {
                            if (typeof card.episode_number === 'number') {
                                const ep = card.episode_number
                                const prev = summaryByEpisode.get(ep) || {
                                    hasPanels: false,
                                    hasCharacters: false,
                                    hasScenes: false,
                                    hasArtStyle: false,
                                }
                                summaryByEpisode.set(ep, { ...prev, hasScenes: true })
                            } else {
                                convHasScenes = true
                            }
                        } else if (card.type === 'art_style') {
                            if (typeof card.episode_number === 'number') {
                                const ep = card.episode_number
                                const prev = summaryByEpisode.get(ep) || {
                                    hasPanels: false,
                                    hasCharacters: false,
                                    hasScenes: false,
                                    hasArtStyle: false,
                                }
                                summaryByEpisode.set(ep, { ...prev, hasArtStyle: true })
                            } else {
                                convHasArtStyle = true
                            }
                        }
                    }

                    // Apply conversation-wide asset flags to the conversation's canonical episode.
                    if (typeof conv.episode_number === 'number') {
                        conversationAssetsByEpisode.set(conv.episode_number, {
                            hasCharacters: convHasCharacters,
                            hasScenes: convHasScenes,
                            hasArtStyle: convHasArtStyle,
                        })
                    }
                }

                // Merge conversation-wide asset flags into per-episode summaries.
                for (const [ep, convAssets] of Array.from(conversationAssetsByEpisode.entries())) {
                    const prev = summaryByEpisode.get(ep) || {
                        hasPanels: false,
                        hasCharacters: false,
                        hasScenes: false,
                        hasArtStyle: false,
                    }
                    summaryByEpisode.set(ep, {
                        hasPanels: prev.hasPanels,
                        hasCharacters: prev.hasCharacters || convAssets.hasCharacters,
                        hasScenes: prev.hasScenes || convAssets.hasScenes,
                        hasArtStyle: prev.hasArtStyle || convAssets.hasArtStyle,
                    })
                }

                // 3. Assemble the set of episode numbers we know about.
                const episodeNumbers = new Set<number>()
                for (const ep of Array.from(committedByEpisode.keys())) episodeNumbers.add(ep)
                for (const ep of Array.from(summaryByEpisode.keys())) episodeNumbers.add(ep)

                const sorted = Array.from(episodeNumbers).sort((a, b) => a - b)

                const result: Episode[] = sorted.map((n) => {
                    const committed = committedByEpisode.get(n)
                    const summary = summaryByEpisode.get(n)
                    const title = committed?.title || `第${n}集`
                    return {
                        id: committed?.chapterId || `ep-${n}`,
                        number: n,
                        title,
                        phases: buildPhases(!!committed, summary),
                    }
                })

                if (!cancelled) setEpisodes(result)
            } catch (err: any) {
                if (!cancelled) {
                    setError(err?.message || 'failed to load episode tree data')
                    setEpisodes([])
                }
            } finally {
                if (!cancelled) setLoading(false)
            }
        }

        run()
        return () => {
            cancelled = true
        }
    }, [projectId, tick])

    const refresh = () => setTick((t) => t + 1)

    return { episodes, loading, error, refresh }
}
