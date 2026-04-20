'use client';

import { useState, useCallback, useEffect } from 'react';
import { api } from '@/lib/api';
import { connect as wsConnect } from '@/lib/ws/client';

interface ParsedPanel {
  panel_index: number;
  action_description: string;
  dialogue?: string;
  shot_type: string;
  camera_angle: string;
  emotion: string;
  characters: string[];
  scene_description?: string;
  time_of_day: string;
  weather: string;
  suggested_duration: number;
}

interface ScriptParseResult {
  panels: ParsedPanel[];
  detected_characters: string[];
  detected_scenes: string[];
  total_duration: number;
  continuity_issues: any[];
}

interface ScriptInputProps {
  onParsed?: (result: ScriptParseResult) => void;
  onError?: (error: string) => void;
  chapterId?: string;
}

const STYLE_OPTIONS = [
  { value: 'korean_webtoon', label: '韩漫风格', desc: '清爽、细腻、色彩柔和' },
  { value: 'manga', label: '日漫风格', desc: '线条感强、网点效果' },
  { value: 'manhwa', label: '漫画风格', desc: '浪漫、唯美氛围' },
  { value: 'comic', label: '美漫风格', desc: '浓烈、饱和、力量感' },
];

export function ScriptInput({ onParsed, onError, chapterId }: ScriptInputProps) {
  const [script, setScript] = useState('');
  const [style, setStyle] = useState('korean_webtoon');
  const [result, setResult] = useState<ScriptParseResult | null>(null);
  const [status, setStatus] = useState<
    'empty' | 'edited' | 'parsing' | 'preview' | 'generating' | 'done' | 'error'
  >('empty');
  const [error, setError] = useState<string | null>(null);
  const [storyboardJobId, setStoryboardJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);

  useEffect(() => {
    if (!storyboardJobId || !chapterId) return;

    const connection = wsConnect();
    const unsubscribe = connection.subscribeChapter('', chapterId, (event) => {
      if (event.type === 'job_progress') {
        const { jobId, progress: prog } = event.payload;
        if (jobId !== storyboardJobId) return;
        if (typeof prog === 'number') {
          const approxTotal = result?.panels?.length ?? 1;
          setProgress({
            done: Math.round(prog * approxTotal),
            total: approxTotal,
          });
        }
      } else if (event.type === 'job_status') {
        const { jobId, status, error: jobError } = event.payload;
        if (jobId !== storyboardJobId) return;
        if (status === 'Succeeded') {
          setStatus('done');
        } else if (status === 'Failed') {
          setStatus('error');
          setError(jobError || '生成失败');
        }
      }
    });

    return () => {
      unsubscribe();
    };
  }, [storyboardJobId, chapterId, result]);

  const handleParse = useCallback(async () => {
    if (!script.trim()) {
      setError('请输入剧本内容');
      setStatus('error');
      return;
    }
    setStatus('parsing');
    setError(null);
    try {
      const response = await fetch(`${api.baseUrl}/api/v1/brain/parse-script`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ script_text: script, style_hint: style }),
      });
      if (!response.ok) throw new Error('解析失败');
      const data: ScriptParseResult = await response.json();
      setResult(data);
      setStatus('preview');
      onParsed?.(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : '解析失败');
      setStatus('error');
      onError?.(err instanceof Error ? err.message : '解析失败');
    }
  }, [script, style, onParsed, onError]);

    const handleConfirm = useCallback(async () => {
        if (!chapterId) {
            setError('缺少章节 ID');
            setStatus('error');
            return;
        }
        setStatus('generating');
        setError(null);
        setProgress(null);
        try {
            const response = await fetch(
                `${api.baseUrl}/api/v1/chapters/${chapterId}/storyboard`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        provider: 'doubao',
                        style_hint: style,
                        target_panels: result?.panels?.length ?? null,
                        auto_apply: true,
                    }),
                },
            );
            if (!response.ok) throw new Error(`生成失败 (${response.status})`);
            const data: { job_id: string; status: string } = await response.json();
            setStoryboardJobId(data.job_id);
            if (data.status === 'succeeded') {
                setStatus('done');
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : '生成失败');
            setStatus('error');
        }
    }, [chapterId, style, result]);

  return (
    <div className="flex flex-col h-full bg-zinc-900 rounded-xl border border-zinc-800">
      {/* 头部 */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
        <h3 className="text-lg font-semibold text-white">剧本输入</h3>
        <div className="flex items-center gap-2">
          <select
            value={style}
            onChange={(e) => setStyle(e.target.value)}
            className="px-3 py-1.5 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-300 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          >
            {STYLE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* 输入区 */}
      <div className="flex-1 p-4">
        <textarea
          value={script}
          onChange={(e) => {
            setScript(e.target.value);
            if (status !== 'generating' && status !== 'parsing') {
              setStatus(e.target.value.trim() ? 'edited' : 'empty');
            }
          }}
          placeholder=""
          className="w-full h-full p-4 bg-zinc-800/50 border border-zinc-700 rounded-lg text-zinc-100 resize-none focus:outline-none focus:ring-2 focus:ring-emerald-500 font-mono text-sm leading-relaxed"
        />
      </div>

      {/* 提示区 */}
      <div className="px-4 py-2 text-xs text-zinc-500 border-t border-zinc-800">
        <span className="text-emerald-400">提示：</span>
        {script.length < 100 && !script.includes('\n')
          ? '检测到一句话输入，将自动扩展为多个分镜'
          : '检测到完整剧本，将按段落解析'}
        <span className="float-right">{script.length} 字符</span>
      </div>

      {/* 操作栏 - 统计信息 */}
      {result && (
        <div className="flex items-center gap-4 px-4 py-2 border-t border-zinc-800 bg-zinc-800/30 text-sm text-zinc-400">
          <span>🎬 {result.panels.length} 个分镜</span>
          <span>👤 {result.detected_characters.length} 个角色</span>
          <span>📍 {result.detected_scenes.length} 个场景</span>
          <span>⏱️ {result.total_duration.toFixed(1)}s</span>
        </div>
      )}

      {/* 状态驱动操作栏 */}
            <div className="px-4 py-3 border-t border-zinc-800 flex items-center gap-2">
                {status === 'empty' || status === 'edited' || status === 'error' ? (
                    <button
                        onClick={handleParse}
                        disabled={!script.trim()}
                        className="px-4 py-2 bg-emerald-600 text-white rounded disabled:opacity-50"
                    >
                        预览分镜
                    </button>
                ) : null}

                {status === 'parsing' ? (
                    <span className="text-sm text-zinc-400">解析中…</span>
                ) : null}

                {status === 'preview' ? (
                    <>
                        <button
                            onClick={handleConfirm}
                            className="px-4 py-2 bg-emerald-600 text-white rounded"
                        >
                            生成正式分镜
                        </button>
                        <button
                            onClick={handleParse}
                            className="px-4 py-2 bg-zinc-700 text-zinc-200 rounded"
                        >
                            重新预览
                        </button>
                    </>
                ) : null}

                {status === 'generating' ? (
                    <span className="text-sm text-zinc-400">
                        正在生成{progress ? `… ${progress.done}/${progress.total}` : '…'}
                    </span>
                ) : null}

                {status === 'done' ? (
                    <button
                        onClick={() => onParsed?.(result!)}
                        className="px-4 py-2 bg-emerald-600 text-white rounded"
                    >
                        查看分镜
                    </button>
                ) : null}

                {status === 'error' && error ? (
                    <span className="text-sm text-red-400">错误：{error}</span>
                ) : null}
            </div>

      {/* 预览面板 */}
      {status === 'preview' && result && (
        <div className="border-t border-zinc-800 max-h-80 overflow-y-auto">
          <div className="p-4 space-y-3">
            {result.continuity_issues.length > 0 && (
              <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg">
                <h4 className="text-sm font-medium text-amber-400 mb-2">⚠️ 连续性提示</h4>
                {result.continuity_issues.map((issue, i) => (
                  <p key={i} className="text-xs text-amber-300/80">{issue.message}</p>
                ))}
              </div>
            )}

            <div className="grid gap-2">
              {result.panels.map((panel) => (
                <div
                  key={panel.panel_index}
                  className="p-3 bg-zinc-800/50 rounded-lg border border-zinc-700/50 hover:border-emerald-500/50 transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 bg-emerald-500/20 text-emerald-400 text-xs rounded">
                        #{panel.panel_index + 1}
                      </span>
                      <span className="px-2 py-0.5 bg-zinc-700 text-zinc-300 text-xs rounded">
                        {panel.shot_type}
                      </span>
                      <span className="px-2 py-0.5 bg-zinc-700 text-zinc-300 text-xs rounded">
                        {panel.emotion}
                      </span>
                    </div>
                    <span className="text-xs text-zinc-500">{panel.suggested_duration}s</span>
                  </div>
                  <p className="mt-2 text-sm text-zinc-300">{panel.action_description}</p>
                  {panel.dialogue && (
                    <p className="mt-1 text-sm text-violet-300 italic">"{panel.dialogue}"</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
