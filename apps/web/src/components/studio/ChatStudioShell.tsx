'use client'

/**
 * ChatStudioShell — stub.
 *
 * The pre-B-1 implementation depended on `useOrchestrator` +
 * `orchestratorApi` (which posted to `/api/v1/orchestrator/chat/stream`
 * and other `/orchestrator/*` routes). Those routes were deleted in
 * commit 539e7b8 (B-1 Phase E backend cleanup), and the matching
 * frontend modules were deleted in B-1 Phase E Batch 5. The page
 * route at `/studio/[projectId]` is itself slated for removal once
 * the chat-driven studio entry point is reconciled with the new agent
 * runner; until then this stub keeps the build green and points users
 * at the supported entry point.
 */

import Link from 'next/link'

export function ChatStudioShell() {
    return (
        <div className="h-screen w-screen bg-[#020617] flex items-center justify-center text-slate-50 font-sans">
            <div className="max-w-md p-6 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-200">
                <h1 className="text-lg font-semibold mb-2">Studio chat shell removed</h1>
                <p className="text-sm leading-relaxed">
                    The legacy orchestrator-backed studio chat was removed in B-1 Phase E.
                    Use the new chat surface under{' '}
                    <Link href="/chat" className="underline hover:text-amber-100">
                        /chat
                    </Link>{' '}
                    or the agent workspace under{' '}
                    <code className="px-1 py-0.5 rounded bg-amber-500/20">/agent/[projectId]/episodes</code>.
                </p>
            </div>
        </div>
    )
}
