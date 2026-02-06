'use client';

import { useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface ContinuityIssue {
  panel_index: number;
  issue_type: 'time_change' | 'weather_change' | 'location_jump' | 'costume_change';
  severity: 'info' | 'warning' | 'error';
  message: string;
  prev_value?: string;
  current_value?: string;
  suggestion?: string;
}

interface ContinuityCheckerProps {
  panels: Array<{
    id: string;
    order: number;
    time_of_day?: string;
    weather?: string;
    scene_id?: string;
  }>;
  onFixApplied?: (panelIndex: number, fix: any) => void;
}

const SEVERITY_STYLES = {
  info: {
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/30',
    text: 'text-blue-400',
    icon: 'ℹ️',
  },
  warning: {
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    text: 'text-amber-400',
    icon: '⚠️',
  },
  error: {
    bg: 'bg-red-500/10',
    border: 'border-red-500/30',
    text: 'text-red-400',
    icon: '❌',
  },
};

const ISSUE_TYPE_LABELS: Record<string, string> = {
  time_change: '时间变化',
  weather_change: '天气变化',
  location_jump: '场景跳跃',
  costume_change: '服装变化',
};

export function ContinuityChecker({ panels, onFixApplied }: ContinuityCheckerProps) {
  const [issues, setIssues] = useState<ContinuityIssue[]>([]);
  const [isChecking, setIsChecking] = useState(false);
  const [isExpanded, setIsExpanded] = useState(true);
  const [fixingIndex, setFixingIndex] = useState<number | null>(null);

  const runCheck = useCallback(async () => {
    if (panels.length < 2) {
      setIssues([]);
      return;
    }

    setIsChecking(true);
    try {
      const response = await fetch(`${api.baseUrl}/api/v1/brain/check-continuity`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          panels: panels.map((p) => ({
            id: p.id,
            order: p.order,
            time_of_day: p.time_of_day,
            weather: p.weather,
            scene_id: p.scene_id,
          })),
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setIssues(data.issues || []);
      }
    } catch (err) {
      console.error('Continuity check failed:', err);
    } finally {
      setIsChecking(false);
    }
  }, [panels]);

  const handleFix = useCallback(
    async (issue: ContinuityIssue, index: number) => {
      setFixingIndex(index);
      try {
        const response = await fetch(`${api.baseUrl}/api/v1/brain/suggest-fix`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            issue: {
              panel_index: issue.panel_index,
              issue_type: issue.issue_type,
              severity: issue.severity,
              message: issue.message,
              prev_value: issue.prev_value,
              current_value: issue.current_value,
              suggestion: issue.suggestion,
            },
            context: { panels },
          }),
        });

        if (response.ok) {
          const fix = await response.json();
          onFixApplied?.(issue.panel_index, fix);

          // 移除已修复的问题
          setIssues((prev) => prev.filter((_, i) => i !== index));
        }
      } catch (err) {
        console.error('Apply fix failed:', err);
      } finally {
        setFixingIndex(null);
      }
    },
    [panels, onFixApplied]
  );

  const warningCount = issues.filter((i) => i.severity === 'warning').length;
  const errorCount = issues.filter((i) => i.severity === 'error').length;

  return (
    <div className="bg-zinc-900 rounded-xl border border-zinc-800 overflow-hidden">
      {/* 头部 */}
      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-zinc-800/50 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-medium text-zinc-200">连续性检测</h3>
          {issues.length > 0 && (
            <div className="flex items-center gap-2">
              {warningCount > 0 && (
                <span className="px-2 py-0.5 bg-amber-500/20 text-amber-400 text-xs rounded">
                  {warningCount} 警告
                </span>
              )}
              {errorCount > 0 && (
                <span className="px-2 py-0.5 bg-red-500/20 text-red-400 text-xs rounded">
                  {errorCount} 错误
                </span>
              )}
            </div>
          )}
          {issues.length === 0 && !isChecking && (
            <span className="px-2 py-0.5 bg-emerald-500/20 text-emerald-400 text-xs rounded">
              ✓ 通过
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              runCheck();
            }}
            disabled={isChecking}
            className="px-3 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs rounded-lg transition-colors disabled:opacity-50"
          >
            {isChecking ? '检测中...' : '重新检测'}
          </button>
          <span className="text-zinc-500">{isExpanded ? '▼' : '▶'}</span>
        </div>
      </div>

      {/* 问题列表 */}
      {isExpanded && (
        <div className="border-t border-zinc-800">
          {issues.length === 0 ? (
            <div className="p-4 text-center text-zinc-500 text-sm">
              {isChecking ? '正在检测...' : '暂无连续性问题'}
            </div>
          ) : (
            <div className="p-3 space-y-2 max-h-64 overflow-y-auto">
              {issues.map((issue, index) => {
                const style = SEVERITY_STYLES[issue.severity];
                const isFixing = fixingIndex === index;

                return (
                  <div
                    key={index}
                    className={`p-3 rounded-lg border ${style.bg} ${style.border}`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-2">
                        <span className="text-lg">{style.icon}</span>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-zinc-400">
                              分镜 #{issue.panel_index + 1}
                            </span>
                            <span className={`text-xs ${style.text}`}>
                              {ISSUE_TYPE_LABELS[issue.issue_type]}
                            </span>
                          </div>
                          <p className="text-sm text-zinc-300 mt-1">{issue.message}</p>
                          {issue.suggestion && (
                            <p className="text-xs text-zinc-500 mt-1">
                              💡 {issue.suggestion}
                            </p>
                          )}
                        </div>
                      </div>
                      <button
                        onClick={() => handleFix(issue, index)}
                        disabled={isFixing}
                        className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white text-xs rounded transition-colors disabled:opacity-50"
                      >
                        {isFixing ? '修复中...' : '一键修复'}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* 批量操作 */}
          {issues.length > 1 && (
            <div className="px-4 py-3 border-t border-zinc-800 flex justify-end">
              <button className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm rounded-lg transition-colors">
                修复全部 ({issues.length})
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
