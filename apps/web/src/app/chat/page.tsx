/**
 * Chat Page
 * Main page for the conversational agent interface
 */

'use client';

import React, { useState, useEffect } from 'react';
import { ChatPanel } from '@/components/chat';

// Generate UUID using crypto API
function generateId(): string {
  return crypto.randomUUID();
}

export default function ChatPage() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [projectId] = useState('demo-project'); // TODO: Get from context

  // Create a new conversation on mount
  useEffect(() => {
    const id = generateId();
    setConversationId(id);
  }, []);

  if (!conversationId) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col">
      {/* Navigation Bar */}
      <nav className="bg-white border-b px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-bold text-gray-900">
            AI Webtoon Studio
          </h1>
          <span className="text-sm text-gray-500">Chat Mode</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setConversationId(generateId())}
            className="px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg"
          >
            New Chat
          </button>
        </div>
      </nav>

      {/* Chat Panel */}
      <ChatPanel
        conversationId={conversationId}
        projectId={projectId}
        className="flex-1"
      />
    </div>
  );
}
