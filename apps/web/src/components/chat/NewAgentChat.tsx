'use client';

import { useChat } from '@/hooks/useChat';
import type { ChatContext } from '@/lib/api/chatTypes';

import { AgentStateIndicator } from './AgentStateIndicator';
import { ChatInput } from './ChatInput';
import { MessageList } from './MessageList';

interface Props {
  context: ChatContext;
  conversationId?: string;
  toolsAllowlist?: string[];
}

export function NewAgentChat({ context, conversationId, toolsAllowlist }: Props) {
  const chat = useChat({ conversationId, context, toolsAllowlist });

  return (
    <div className="flex flex-col h-full bg-white">
      <MessageList messages={chat.messages} />
      <AgentStateIndicator state={chat.agentState} error={chat.error} />
      <ChatInput
        onSend={chat.sendMessage}
        onCancel={chat.cancel}
        disabled={chat.isStreaming}
      />
    </div>
  );
}
