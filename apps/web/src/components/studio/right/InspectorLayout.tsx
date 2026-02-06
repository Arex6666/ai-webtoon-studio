'use client'

import { useFormContext } from 'react-hook-form'
import { PanelSpec } from '@/lib/schema'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

export function InspectorLayout() {
  const { register, watch, setValue } = useFormContext<PanelSpec>()

  const timeOfDay = watch('scene.timeOfDay')
  const weather = watch('scene.weather')

  return (
    <div className="p-4 space-y-6">
      <div className="space-y-2">
        <Label>Location</Label>
        <Input {...register('scene.location')} placeholder="" />
      </div>

      <div className="space-y-2">
        <Label>Time of Day</Label>
        <Select value={timeOfDay} onValueChange={(value) => setValue('scene.timeOfDay', value as any)}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="day">Day</SelectItem>
            <SelectItem value="night">Night</SelectItem>
            <SelectItem value="dusk">Dusk</SelectItem>
            <SelectItem value="dawn">Dawn</SelectItem>
            <SelectItem value="indoor">Indoor</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>Weather</Label>
        <Select value={weather} onValueChange={(value) => setValue('scene.weather', value as any)}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="clear">Clear</SelectItem>
            <SelectItem value="rain">Rain</SelectItem>
            <SelectItem value="snow">Snow</SelectItem>
            <SelectItem value="fog">Fog</SelectItem>
            <SelectItem value="overcast">Overcast</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}
