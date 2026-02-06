'use client'

import { useState } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Clock, ListTodo } from "lucide-react"
import { JobsConsole } from './JobsConsole'
import { TimelinePanel } from './TimelinePanel'

export function TimelineDock() {
  const [activeTab, setActiveTab] = useState<'timeline' | 'jobs'>('timeline')

  return (
    <div className="h-full flex flex-col border-t border-panel-border bg-panel/30">
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'timeline' | 'jobs')} className="flex-1 flex flex-col">
        <div className="px-4 pt-2 border-b border-panel-border">
          <TabsList className="bg-transparent h-9">
            <TabsTrigger value="timeline" className="data-[state=active]:bg-accent/20 text-xs gap-1.5">
              <Clock className="w-3.5 h-3.5" />
              时间轴
            </TabsTrigger>
            <TabsTrigger value="jobs" className="data-[state=active]:bg-accent/20 text-xs gap-1.5">
              <ListTodo className="w-3.5 h-3.5" />
              渲染队列
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="timeline" className="flex-1 m-0 overflow-hidden">
          <TimelinePanel />
        </TabsContent>

        <TabsContent value="jobs" className="flex-1 m-0 overflow-hidden">
          <JobsConsole />
        </TabsContent>
      </Tabs>
    </div>
  )
}
