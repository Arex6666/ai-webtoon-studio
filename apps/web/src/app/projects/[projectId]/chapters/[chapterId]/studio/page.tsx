'use client'

import { StudioShell } from "@/components/studio/StudioShell"

export default function StudioPage({
  params,
}: {
  params: { projectId: string; chapterId: string }
}) {
  return <StudioShell projectId={params.projectId} chapterId={params.chapterId} />
}
