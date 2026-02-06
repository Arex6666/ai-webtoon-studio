'use client'

import { Button } from '@/components/ui/button'
import { Settings, User } from 'lucide-react'

export function TopBar() {
  return (
    <div className="h-14 border-b bg-background flex items-center justify-between px-4">
      <h1 className="text-xl font-semibold">Webtoon Studio</h1>
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon">
          <Settings className="h-5 w-5" />
        </Button>
        <Button variant="ghost" size="icon">
          <User className="h-5 w-5" />
        </Button>
      </div>
    </div>
  )
}
