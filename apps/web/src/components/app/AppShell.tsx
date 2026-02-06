'use client'

import { ReactNode } from 'react'
import { usePathname } from 'next/navigation'
import { TopBar } from './TopBar'
import { GlobalNav } from '@/components/layout/GlobalNav'

interface AppShellProps {
  children: ReactNode
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname()
  const isStudio = pathname?.includes('/studio')

  if (isStudio) {
    return <>{children}</>
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <GlobalNav />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-auto p-6 bg-muted/30">
          {children}
        </main>
      </div>
    </div>
  )
}
