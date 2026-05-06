'use client';

import { useCallback, useRef, useState } from 'react';

interface Props {
  onSend: (text: string) => Promise<void> | void;
  onCancel?: () => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInput({ onSend, onCancel, disabled, placeholder }: Props) {
  const [text, setText] = useState('');
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  const submit = useCallback(async () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    setText('');
    await onSend(trimmed);
  }, [text, disabled, onSend]);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        void submit();
      }
    },
    [submit],
  );

  return (
    <div className="border-t border-gray-200 bg-white p-3">
      <textarea
        ref={taRef}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        rows={2}
        placeholder={placeholder ?? 'Ask the agent...'}
        className="w-full resize-y border border-gray-200 rounded p-2 text-sm focus:outline-none focus:ring focus:border-blue-300"
      />
      <div className="mt-2 flex justify-end gap-2">
        {disabled && onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="px-3 py-1 text-sm text-gray-700 border border-gray-300 rounded hover:bg-gray-50"
          >
            Cancel
          </button>
        )}
        <button
          type="button"
          onClick={() => void submit()}
          disabled={disabled || !text.trim()}
          className="px-4 py-1 text-sm bg-blue-600 text-white rounded disabled:bg-gray-300 hover:bg-blue-700"
        >
          {disabled ? 'Sending...' : 'Send'}
        </button>
      </div>
    </div>
  );
}
