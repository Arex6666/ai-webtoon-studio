'use client'

import { useState } from 'react'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { useStudioStore } from '@/lib/store/studioStore'
import { useToast } from '@/hooks/use-toast'

interface ImportModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function ImportModal({ open, onOpenChange }: ImportModalProps) {
  const [jsonInput, setJsonInput] = useState('')
  const [error, setError] = useState('')
  const { importChapterSpec } = useStudioStore()
  const { toast } = useToast()

  const handleImport = () => {
    setError('')

    if (!jsonInput.trim()) {
      setError('Please paste JSON content')
      return
    }

    try {
      importChapterSpec(jsonInput)
      toast({
        title: 'Import successful',
        description: 'Chapter spec has been imported',
      })
      setJsonInput('')
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invalid JSON format')
    }
  }

  const handleClose = () => {
    setJsonInput('')
    setError('')
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Import Chapter Spec</DialogTitle>
          <DialogDescription>
            Paste the JSON content of a chapter spec file to import it.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <Textarea
            value={jsonInput}
            onChange={(e) => setJsonInput(e.target.value)}
            placeholder=""
            rows={15}
            className="font-mono text-sm"
          />

          {error && (
            <div className="text-sm text-red-500">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={handleClose}>
              Cancel
            </Button>
            <Button onClick={handleImport}>
              Import
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
