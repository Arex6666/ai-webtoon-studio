/** Chat landing — /chat with no project selected. */
'use client'

import { ChatEmptyState } from '@/components/chat/ChatEmptyState'

export default function ChatLandingPage() {
    return (
        <div className="h-screen flex flex-col bg-background">
            <nav className="border-b px-6 py-3 flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <h1 className="text-xl font-bold">AI Webtoon Studio</h1>
                    <span className="text-sm text-muted-foreground">Chat Mode</span>
                </div>
            </nav>
            <div className="flex-1 overflow-y-auto">
                <ChatEmptyState />
            </div>
        </div>
    )
}
