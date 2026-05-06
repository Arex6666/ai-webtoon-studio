/**
 * ChatPanel Component
 *
 * Feature-flag dispatcher (B-1 Phase B Group 4 / Task 4.1):
 *   - flag OFF (default): renders LegacyChatPanel (the original implementation,
 *     unchanged behavior — connects via chatStore + WebSocket).
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

import React, { useEffect, useRef } from 'react';
import { useChatStore } from '@/lib/store/chatStore';
import { useShallow } from 'zustand/react/shallow';
import { ChatMessage } from './ChatMessage';
import { ActionCard } from './ActionCard';
import { MessageInput } from './MessageInput';
import { NewAgentChat } from './NewAgentChat';
import { featureFlags } from '@/lib/featureFlags';
import { cn } from '@/lib/utils';

interface ChatPanelProps {
  conversationId: string;
  projectId: string;
  chapterId?: string;
  className?: string;
}

/**
 * LegacyChatPanel — the pre-B-1 implementation. Kept exported so debug
 * tools and tests can reference it directly, bypassing the flag.
 */
export function LegacyChatPanel({
  conversationId,
  projectId,
  chapterId,
  className,
}: ChatPanelProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    messages,
    pendingActions,
    isConnected,
    isStreaming,
    error,
    connect,
    disconnect,
    sendMessage,
  } = useChatStore(
    useShallow(s => ({
      messages: s.messages,
      pendingActions: s.pendingActions,
      isConnected: s.isConnected,
      isStreaming: s.isStreaming,
      error: s.error,
      connect: s.connect,
      disconnect: s.disconnect,
      sendMessage: s.sendMessage,
    }))
  );

  // Connect on mount
  useEffect(() => {
    connect(conversationId, projectId, chapterId);
    return () => disconnect();
  }, [conversationId, projectId, chapterId, connect, disconnect]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, pendingActions]);

  return (
    <div className={cn('flex flex-col h-full bg-gray-50', className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-white border-b">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-gray-900">AI Assistant</h2>
          <span
            className={cn(
              'px-2 py-0.5 rounded-full text-xs font-medium',
              isConnected
                ? 'bg-green-100 text-green-700'
                : 'bg-red-100 text-red-700'
            )}
          >
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* Welcome Message */}
        {messages.length === 0 && (
          <div className="text-center py-12">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gradient-to-br from-emerald-500 to-blue-500 flex items-center justify-center">
              <span className="text-white text-2xl font-bold">AI</span>
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              Welcome to AI Webtoon Studio
            </h3>
            <p className="text-gray-500 max-w-md mx-auto">
              I can help you create comics through conversation. Try saying:
            </p>
            <div className="mt-4 space-y-2">
              {[
                'Create a 4-panel comic about two friends at a cafe',
                'Create a character named Alice with blonde hair',
                'Render all panels',
              ].map((suggestion, i) => (
                <button
                  key={i}
                  onClick={() => sendMessage(suggestion)}
                  disabled={!isConnected}
                  className="block mx-auto px-4 py-2 bg-white border rounded-lg text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                  &quot;{suggestion}&quot;
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Message List */}
        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}

        {/* Pending Actions */}
        {pendingActions.length > 0 && (
          <div className="mt-4">
            <div className="text-xs font-medium text-gray-500 mb-2">
              Actions in Progress
            </div>
            {pendingActions.map((action) => (
              <ActionCard key={action.id} action={action} />
            ))}
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
            {error}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <MessageInput
        onSend={sendMessage}
        disabled={!isConnected || isStreaming}
        placeholder={
          isStreaming
            ? 'AI is responding...'
            : isConnected
              ? 'Type your message...'
              : 'Connecting...'
        }
      />
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
