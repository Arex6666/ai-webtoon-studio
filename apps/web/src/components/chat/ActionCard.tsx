/**
 * ActionCard Component
 * Displays an action in progress (rendering, asset creation, etc.)
 */

import React from 'react';
import type { ActionState } from '@/lib/schema/conversation';
import { cn } from '@/lib/utils';

interface ActionCardProps {
  action: ActionState;
}

export function ActionCard({ action }: ActionCardProps) {
  const statusColors = {
    pending: 'bg-gray-100 text-gray-600',
    running: 'bg-blue-100 text-blue-600',
    completed: 'bg-green-100 text-green-600',
    failed: 'bg-red-100 text-red-600',
  };

  const progressPercent = Math.round((action.progress || 0) * 100);

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm mb-3">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-900">
            {action.type}
          </span>
          <span
            className={cn(
              'px-2 py-0.5 rounded text-xs font-medium',
              statusColors[action.status]
            )}
          >
            {action.status}
          </span>
        </div>
      </div>

      {/* Description */}
      <p className="text-sm text-gray-600 mb-3">{action.description}</p>

      {/* Progress Bar */}
      {action.status === 'running' && (
        <div className="mb-3">
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>Progress</span>
            <span>{progressPercent}%</span>
          </div>
          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 transition-all duration-300"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      )}

      {/* Preview Image */}
      {action.previewUrl && (
        <div className="mt-3">
          <img
            src={action.previewUrl}
            alt="Preview"
            className="w-full h-32 object-cover rounded border border-gray-200"
          />
        </div>
      )}

      {/* Error Message */}
      {action.error && (
        <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-600">
          {action.error}
        </div>
      )}
    </div>
  );
}
