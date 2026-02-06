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

export function InspectorStory() {
  const { register, watch, setValue } = useFormContext<PanelSpec>()

  const shotType = watch('shot.shotType')
  const cameraMove = watch('shot.cameraMove')
  const durationSec = watch('shot.durationSec')

  return (
    <div className="p-4 space-y-6">
      <div className="space-y-2">
        <Label className="text-muted-foreground text-xs font-semibold uppercase tracking-wider">景别 (Shot Type)</Label>
        <Select value={shotType} onValueChange={(value) => setValue('shot.shotType', value as any)}>
          <SelectTrigger>
            <SelectValue placeholder="选择景别" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ECU">极大特写 (ECU)</SelectItem>
            <SelectItem value="CU">特写 (CU)</SelectItem>
            <SelectItem value="MCU">中特写 (MCU)</SelectItem>
            <SelectItem value="MS">中景 (MS)</SelectItem>
            <SelectItem value="MLS">中远景 (MLS)</SelectItem>
            <SelectItem value="LS">远景 (LS)</SelectItem>
            <SelectItem value="ELS">大远景 (ELS)</SelectItem>
            <SelectItem value="OTS">越肩视点 (OTS)</SelectItem>
            <SelectItem value="POV">主观视角 (POV)</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label className="text-muted-foreground text-xs font-semibold uppercase tracking-wider">运镜 (Camera Move)</Label>
        <Select value={cameraMove} onValueChange={(value) => setValue('shot.cameraMove', value as any)}>
          <SelectTrigger>
            <SelectValue placeholder="选择运镜" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="static">静止 (Static)</SelectItem>
            <SelectItem value="pan">摇摄 (Pan)</SelectItem>
            <SelectItem value="tilt">俯仰 (Tilt)</SelectItem>
            <SelectItem value="zoom_in">推近 (Zoom In)</SelectItem>
            <SelectItem value="zoom_out">拉远 (Zoom Out)</SelectItem>
            <SelectItem value="dolly">推轨 (Dolly)</SelectItem>
            <SelectItem value="track">跟踪 (Track)</SelectItem>
            <SelectItem value="crane">升降 (Crane)</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label className="text-muted-foreground text-xs font-semibold uppercase tracking-wider">时长 (秒)</Label>
        <Input
          type="number"
          step="0.1"
          min="0.5"
          max="15"
          value={durationSec}
          onChange={(e) => setValue('shot.durationSec', parseFloat(e.target.value))}
        />
      </div>

      <div className="space-y-2">
        <Label className="text-muted-foreground text-xs font-semibold uppercase tracking-wider">镜头参数</Label>
        <Input {...register('shot.lensHint')} placeholder="" />
      </div>

      <div className="space-y-2">
        <Label className="text-muted-foreground text-xs font-semibold uppercase tracking-wider">氛围</Label>
        <Input {...register('scene.mood')} placeholder="" />
      </div>
    </div>
  )
}
