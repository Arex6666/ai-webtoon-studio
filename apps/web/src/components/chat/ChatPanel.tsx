/**
 * ChatPanel — thin wrapper over NewAgentChat (B-1 Phase E Batch 6).
 *
 * Pre-B-1 ChatPanel was a feature-flag dispatcher between LegacyChatPanel
 * (chatStore + WebSocket chatClient) and NewAgentChat (useChat + SSE).
 * The legacy path and NEXT_PUBLIC_USE_NEW_AGENT flag were removed in
 * Batch 6; this file remains only to preserve the existing
 * `import { ChatPanel } from '@/components/chat'` call-sites and to map
 * the old positional prop interface onto NewAgentChat's ChatContext.
 */

'use client';

import React from 'react';
import { NewAgentChat } from './NewAgentChat';

interface ChatPanelProps {
  conversationId: string;
  projectId: string;
  chapterId?: string;
  className?: string;
}

export function ChatPanel(props: ChatPanelProps) {
  return (
    <div className={props.className}>
      <NewAgentChat
        conversationId={props.conversationId}
        context={{
          projectId: props.projectId,
          chapterId: props.chapterId,
        }}
      />
    </div>
  );
}

export default ChatPanel;
