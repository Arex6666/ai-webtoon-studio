'use client'

import { ReactNode, useEffect, useRef } from 'react'
import { useForm, FormProvider } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useStudioStore } from '@/lib/store/studioStore'
import { useShallow } from 'zustand/react/shallow'
import { panelSpecSchema, PanelSpec } from '@/lib/schema'

interface InspectorFormProviderProps {
  children: ReactNode
}

export function InspectorFormProvider({ children }: InspectorFormProviderProps) {
  const { selectedPanelId, getSelectedSpec, setPanelSpec } = useStudioStore(
    useShallow(s => ({ selectedPanelId: s.selectedPanelId, getSelectedSpec: s.getSelectedSpec, setPanelSpec: s.setPanelSpec }))
  )
  const selectedSpec = getSelectedSpec()
  const prevPanelIdRef = useRef<string | null>(null)

  const form = useForm<PanelSpec>({
    resolver: zodResolver(panelSpecSchema),
    defaultValues: selectedSpec || undefined,
  })

  // Reset form when selected panel changes
  useEffect(() => {
    if (selectedPanelId !== prevPanelIdRef.current) {
      prevPanelIdRef.current = selectedPanelId

      if (selectedSpec) {
        form.reset(selectedSpec)
      }
    }
  }, [selectedPanelId, selectedSpec, form])

  // Debounced sync form changes to store (300ms)
  useEffect(() => {
    const subscription = form.watch((value) => {
      if (!selectedPanelId || !value) return

      const timer = setTimeout(() => {
        // Only update changed fields
        setPanelSpec(selectedPanelId, value as Partial<PanelSpec>)
      }, 300)

      return () => clearTimeout(timer)
    })

    return () => subscription.unsubscribe()
  }, [selectedPanelId, form, setPanelSpec])

  return (
    <FormProvider {...form}>
      {children}
    </FormProvider>
  )
}
