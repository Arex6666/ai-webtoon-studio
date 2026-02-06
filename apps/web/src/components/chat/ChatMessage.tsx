/**
 * ChatMessage Component
 * Displays a single message in the chat interface
 * Supports Markdown rendering including images
 */

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ChatMessage as ChatMessageType } from '@/lib/schema/conversation';
import { cn } from '@/lib/utils';

interface ChatMessageProps {
  message: ChatMessageType;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  // Debug: log message content to check format
  React.useEffect(() => {
    if (message.content && message.content.includes('![')) {
      console.log('[ChatMessage] Markdown image detected:', message.content.substring(0, 200));
    }
  }, [message.content]);

  return (
    <div
      className={cn(
        'flex w-full mb-4',
        isUser ? 'justify-end' : 'justify-start'
      )}
    >
      <div
        className={cn(
          'max-w-[80%] rounded-lg px-4 py-3 shadow-sm',
          isUser
            ? 'bg-blue-600 text-white'
            : isSystem
              ? 'bg-gray-100 text-gray-700 border border-gray-200'
              : 'bg-white text-gray-900 border border-gray-200'
        )}
      >
        {/* Message Header */}
        {!isUser && (
          <div className="flex items-center gap-2 mb-2">
            <div className="w-6 h-6 rounded-full bg-gradient-to-br from-emerald-500 to-blue-500 flex items-center justify-center">
              <span className="text-white text-xs font-bold">AI</span>
            </div>
            <span className="text-xs font-medium text-gray-500">
              {message.intent && (
                <span className="px-2 py-0.5 bg-gray-100 rounded text-gray-600">
                  {message.intent}
                </span>
              )}
            </span>
          </div>
        )}

        {/* Message Content */}
        <div
          className={cn(
            'prose prose-sm max-w-none',
            isUser ? 'prose-invert' : '',
            // Custom styles for images in chat
            '[&_img]:max-w-full [&_img]:rounded-lg [&_img]:shadow-md [&_img]:my-2'
          )}
        >
          {message.isStreaming ? (
            <div className="flex items-center gap-2">
              <span>{message.content}</span>
              <span className="inline-block w-1 h-4 bg-current animate-pulse" />
            </div>
          ) : (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                // Custom image renderer with loading state
                img: ({ src, alt }) => (
                  <img
                    src={src}
                    alt={alt || 'Generated image'}
                    loading="lazy"
                    className="max-w-full h-auto rounded-lg shadow-md my-2 cursor-pointer hover:opacity-90 transition-opacity"
                    onClick={() => src && window.open(src, '_blank')}
                    onError={(e) => {
                      e.currentTarget.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="150"><rect fill="%23f0f0f0" width="200" height="150"/><text x="100" y="75" fill="%23999" text-anchor="middle" font-size="14">Image failed to load</text></svg>';
                    }}
                  />
                ),
                // Keep links clickable
                a: ({ href, children }) => (
                  <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline">
                    {children}
                  </a>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          )}
        </div>

        {/* Tool Calls */}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-200">
            <div className="text-xs font-medium text-gray-500 mb-2">
              Tool Calls:
            </div>
            {message.toolCalls.map((toolCall, index) => (
              <div
                key={index}
                className="text-xs bg-gray-50 rounded px-2 py-1 mb-1 font-mono"
              >
                <span className="font-semibold">{toolCall.tool_name}</span>
                <span className="text-gray-400 ml-1">
                  ({Object.keys(toolCall.parameters).length} params)
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Timestamp */}
        <div
          className={cn(
            'text-xs mt-2',
            isUser ? 'text-blue-100' : 'text-gray-400'
          )}
        >
          {message.timestamp.toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}
