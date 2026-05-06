/**
 * ChatPanel Component
 *
 * Feature-flag dispatcher (B-1 Phase B Group 4 / Task 4.1):
 *   - flag OFF (default): renders LegacyChatPanel — stubbed in B-1 Phase E
 *     Batch 5 after the chatStore + WebSocket chat client were deleted.
 *     The flag itself is removed in Batch 6.
 *   - flag ON  (NEXT_PUBLIC_USE_NEW_AGENT=true): renders the new
 *     NewAgentChat (useChat hook + SSE) from Task 3.5.
 *
 * The exported prop interface (ChatPanelProps) is unchanged so existing
 * call-sites keep compiling. When the new path is selected, legacy props
 * are mapped onto NewAgentChat's ChatContext (projectId is required by
 * both; chapterId is forwarded; episodeNumber/panelId are not part of
 * the legacy interface and are intentionally omitted).
 */

'use client';

import React from 'react';
import { NewAgentChat } from './NewAgentChat';
import { featureFlags } from '@/lib/featureFlags';

interface ChatPanelProps {
  conversationId: string;
  projectId: string;
  chapterId?: string;
  className?: string;
}

/**
 * LegacyChatPanel — stub. The pre-B-1 implementation depended on
 * `useChatStore` + `chatClient` (WebSocket), both deleted in B-1 Phase E
 * Batch 5. The component (and the feature flag that selects it) is
 * removed in Batch 6; this stub exists only so the flag-OFF path keeps
 * the build green during Batch 5.
 */
export function LegacyChatPanel(_props: ChatPanelProps) {
  return (
    <div className="p-4 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded">
      Legacy chat path was removed in B-1 Phase E. Set <code>NEXT_PUBLIC_USE_NEW_AGENT=true</code>.
    </div>
  );
}

/**
 * ChatPanel — feature-flag dispatcher. Exported as both a named export
 * (preserving existing `import { ChatPanel } from '@/components/chat'`
 * call-sites) and as the default export.
 *
 * Prop interface is unchanged from the pre-B-1 LegacyChatPanel. When the
 * new path is selected, props are mapped to NewAgentChat's ChatContext.
 * The legacy interface has no episodeNumber/panelId, so those context
 * fields are left undefined — NewAgentChat treats them as optional.
 */
export function ChatPanel(props: ChatPanelProps) {
  if (featureFlags.useNewAgent) {
    return (
      <NewAgentChat
        conversationId={props.conversationId}
        context={{
          projectId: props.projectId,
          chapterId: props.chapterId,
        }}
      />
    );
  }
  return <LegacyChatPanel {...props} />;
}

export default ChatPanel;
