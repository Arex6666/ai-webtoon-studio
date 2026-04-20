'use client'

import { useEffect, useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useJobTracker } from '@/hooks/useJobTracker'
import { Loader2, CheckCircle2, AlertCircle, Sparkles, Terminal } from 'lucide-react'
import { cn } from '@/lib/utils'

/** Safely coerce unknown values to display strings */
function safeStr(val: unknown): string {
  if (val === null || val === undefined) return ''
  if (typeof val === 'string') return val
  if (typeof val === 'object' && val !== null && 'message' in val && typeof (val as any).message === 'string') return (val as any).message
  try { return JSON.stringify(val) } catch { return String(val) }
}

interface AgentStep {
  id: string
  agent: string
  message: string
  status: 'running' | 'done' | 'error'
  timestamp: number
}

export function AgentTaskRunner({ jobId }: { jobId: string }) {
  const state = useJobTracker(jobId)
  const [steps, setSteps] = useState<AgentStep[]>([])
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!state.message) return
    const safeMessage = safeStr(state.message)
    
    setSteps(prev => {
      const last = prev[prev.length - 1]
      // If same message, don't duplicate
      if (last && last.message === safeMessage && last.agent === (state.agent ?? 'System')) {
        // If state changed to complete, update last step to done
        if (state.isComplete && last.status === 'running') {
            return [...prev.slice(0, -1), { ...last, status: state.status === 'succeeded' ? 'done' : 'error' }]
        }
        return prev
      }

      const newPrev = prev.map(step => step.status === 'running' ? { ...step, status: 'done' as const } : step)
      
      const newStep: AgentStep = {
        id: Math.random().toString(36).slice(2),
        agent: state.agent ?? 'System',
        message: safeMessage,
        status: state.isComplete ? (state.status === 'succeeded' ? 'done' : 'error') : 'running',
        timestamp: Date.now()
      }
      return [...newPrev, newStep]
    })
  }, [state.message, state.agent, state.isComplete, state.status])

  useEffect(() => {
    // scroll to bottom
    if (containerRef.current) {
        containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [steps])

  return (
    <div className="flex flex-col flex-1 h-full w-full bg-[#0C0C0C] border border-[#27272A] rounded-xl overflow-hidden font-mono text-sm max-h-[350px]">
      <div className="flex items-center gap-2 px-4 py-3 bg-[#18181B] border-b border-[#27272A]">
        <Terminal className="w-4 h-4 text-[#71717A]" />
        <span className="text-[#FAFAFA] font-medium">Agent Cluster Execution</span>
        {state.status === 'running' && (
          <span className="ml-auto flex items-center gap-2 text-xs text-[#10B981]">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#10B981] opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#10B981]"></span>
            </span>
            Active
          </span>
        )}
      </div>
      
      <div ref={containerRef} className="flex-1 overflow-y-auto p-4 space-y-3 scroll-smooth">
        <AnimatePresence initial={false}>
          {steps.map((step) => (
            <motion.div
              key={step.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-start gap-3 group"
            >
              <div className="mt-0.5 whitespace-nowrap">
                {step.status === 'running' ? (
                  <Loader2 className="w-4 h-4 text-[#3B82F6] animate-spin" />
                ) : step.status === 'done' ? (
                  <CheckCircle2 className="w-4 h-4 text-[#10B981]" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-[#EF4444]" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-2 flex-wrap">
                  <span className={cn(
                    "px-1.5 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider",
                    step.agent === 'Script Assistant' && "bg-[#8B5CF6]/20 text-[#8B5CF6]",
                    step.agent === 'Director Agent' && "bg-[#F59E0B]/20 text-[#F59E0B]",
                    step.agent === 'Layout Assistant' && "bg-[#10B981]/20 text-[#10B981]",
                    (!step.agent || step.agent === 'System') && "bg-[#27272A] text-[#71717A]"
                  )}>
                    {step.agent}
                  </span>
                  <span className={cn(
                    "text-[#FAFAFA]",
                    step.status === 'done' && "text-[#A1A1AA]"
                  )}>
                    {step.message}
                  </span>
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        
        {state.isComplete && state.status === 'succeeded' && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
            className="pt-4 mt-2 border-t border-[#27272A] flex items-center gap-2 text-[#10B981]"
          >
            <Sparkles className="w-4 h-4" />
            <span>Workflow completed successfully. Opening draft preview...</span>
          </motion.div>
        )}
      </div>
      
      {state.status === 'running' && (
        <div className="h-1 bg-[#27272A] w-full">
           <div 
             className="h-full bg-gradient-to-r from-[#3B82F6] to-[#10B981] transition-all duration-300"
             style={{ width: `${Math.max(5, state.progress * 100)}%` }}
           />
        </div>
      )}
    </div>
  )
}
