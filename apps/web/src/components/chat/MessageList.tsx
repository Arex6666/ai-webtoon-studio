'use client';

import { useEffect, useRef } from 'react';

import type { ChatMessage } from '@/lib/api/chatTypes';
import { Message } from './Message';

interface Props {
  messages: ChatMessage[];
}

export function MessageList({ messages }: Props) {
  const scrollerRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollerRef.current) {
      scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
    }
  }, [messages.length, messages[messages.length - 1]?.content?.length]);

  return (
    <div ref={scrollerRef} className="flex-1 overflow-y-auto p-3 space-y-3">
      {messages.length === 0 ? (
        <div className="text-center text-sm text-gray-400 mt-8">
          No messages yet. Send something to start.
        </div>
      ) : (
        messages.map((m) => <Message key={m.id} message={m} />)
      )}
    </div>
  );
}
