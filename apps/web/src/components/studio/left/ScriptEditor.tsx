'use client'

import { useEffect, useState, useRef } from 'react'
import { Textarea } from "@/components/ui/textarea"
import { useStudioStore } from "@/lib/store/studioStore"
import { useShallow } from "zustand/react/shallow"
import { chaptersApi } from "@/lib/api/services"
import { FileText, Check, Loader2, AlertCircle, Cloud } from "lucide-react"

export function ScriptEditor() {
  const { script, setScript, chapterId } = useStudioStore(
    useShallow(s => ({ script: s.script, setScript: s.setScript, chapterId: s.chapterId }))
  )
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [scriptVersion, setScriptVersion] = useState<string | null>(null)
  const saveTimerRef = useRef<NodeJS.Timeout | null>(null)

  // 自动保存到 API (debounced 800ms)
  useEffect(() => {
    if (!chapterId || !script) {
      setSaveStatus('idle')
      return
    }

    // 清除之前的定时器
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current)
    }

    setSaveStatus('saving')

    saveTimerRef.current = setTimeout(async () => {
      try {
        const result = await chaptersApi.saveScript(chapterId, script)
        setScriptVersion(result.script_version)
        setSaveStatus('saved')

        // 同时备份到 localStorage（离线模式）
        const key = `ai-webtoon:script:${chapterId}`
        localStorage.setItem(key, script)

        // 3秒后恢复 idle 状态
        setTimeout(() => setSaveStatus('idle'), 3000)
      } catch (error) {
        console.error('Failed to save script:', error)
        setSaveStatus('error')

        // 失败时保存到 localStorage
        const key = `ai-webtoon:script:${chapterId}`
        localStorage.setItem(key, script)

        // 5秒后恢复 idle 状态
        setTimeout(() => setSaveStatus('idle'), 5000)
      }
    }, 800)

    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current)
      }
    }
  }, [script, chapterId])

  const wordCount = script.length
  const lineCount = script.split('\n').filter(line => line.trim()).length

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-white/5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-muted-foreground/50" />
          <h3 className="font-semibold text-foreground/80">剧本</h3>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {saveStatus === 'saving' && (
            <span className="flex items-center gap-1">
              <Loader2 className="w-3 h-3 animate-spin" />
              保存中...
            </span>
          )}
          {saveStatus === 'saved' && (
            <span className="flex items-center gap-1 text-emerald-500">
              <Cloud className="w-3 h-3" />
              已同步
            </span>
          )}
          {saveStatus === 'error' && (
            <span className="flex items-center gap-1 text-amber-500" title="已保存到本地，稍后会重试">
              <AlertCircle className="w-3 h-3" />
              离线保存
            </span>
          )}
          <span>{wordCount} 字</span>
          {lineCount > 0 && <span>• {lineCount} 行</span>}
        </div>
      </div>

      {/* Editor */}
      <div className="flex-1 p-4 overflow-hidden">
        <Textarea
          value={script}
          onChange={(e) => setScript(e.target.value)}
          placeholder=""
          className="h-full resize-none bg-zinc-900/80 border-white/10 text-sm leading-relaxed font-mono focus-visible:ring-primary/30"
        />
      </div>
    </div>
  )
}

